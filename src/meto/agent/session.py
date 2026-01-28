"""Session persistence for meto agent."""

from __future__ import annotations

import json
import logging
import random
import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:
    from meto.agent.skill_loader import SkillLoader

from meto.agent.todo import TodoManager
from meto.conf import settings

logger = logging.getLogger("agent")


def generate_session_id() -> str:
    """Generate timestamp-based session ID: {timestamp}-{random_suffix}."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
    return f"{timestamp}-{random_suffix}"


class SessionLogger(ABC):
    """Base class for session loggers."""

    session_id: str

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    @abstractmethod
    def log_user(self, content: str) -> None:
        del content
        raise NotImplementedError

    @abstractmethod
    def log_assistant(self, content: str | None, tool_calls: list[Any] | None) -> None:
        del content
        del tool_calls
        raise NotImplementedError

    @abstractmethod
    def log_tool(self, tool_call_id: str, content: str) -> None:
        del tool_call_id
        del content
        raise NotImplementedError


class NullSessionLogger(SessionLogger):
    """No-op session logger."""

    session_id: str

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self.session_id = session_id

    @override
    def log_user(self, content: str) -> None:
        del content
        pass

    @override
    def log_assistant(self, content: str | None, tool_calls: list[Any] | None) -> None:
        del content
        del tool_calls
        pass

    @override
    def log_tool(self, tool_call_id: str, content: str) -> None:
        del tool_call_id
        del content
        pass


class FileSessionLogger(SessionLogger):
    """Append-only JSONL logger for chat history persistence."""

    session_id: str
    session_file: Path
    _lock: threading.Lock

    def __init__(
        self, session_id: str | None = None, session_dir: Path = settings.SESSION_DIR
    ) -> None:
        self.session_id = session_id or generate_session_id()
        super().__init__(self.session_id)
        self.session_file = session_dir / f"session-{self.session_id}.jsonl"
        self._lock = threading.Lock()

        # Ensure parent directory exists
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, message: dict[str, Any]) -> None:
        """Thread-safe append to JSONL file."""
        with self._lock:
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")

    @override
    def log_user(self, content: str) -> None:
        """Log user message with timestamp."""
        msg = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "role": "user",
            "content": content,
            "session_id": self.session_id,
        }
        self._append(msg)

    @override
    def log_assistant(self, content: str | None, tool_calls: list[Any] | None) -> None:
        """Log assistant response with optional tool_calls."""
        msg: dict[str, Any] = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "role": "assistant",
            "content": content,
            "session_id": self.session_id,
        }
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self._append(msg)

    @override
    def log_tool(self, tool_call_id: str, content: str) -> None:
        """Log tool execution result."""
        msg = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
            "session_id": self.session_id,
        }
        self._append(msg)


def load_session(session_id: str, session_dir: Path = settings.SESSION_DIR) -> list[dict[str, Any]]:
    """Load conversation history from session file.

    Returns OpenAI-style history list (no timestamps/session_id wrapper).
    """
    session_file = session_dir / f"session-{session_id}.jsonl"

    if not session_file.exists():
        return []

    messages = []
    try:
        with open(session_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    raw = json.loads(line)
                    # Extract OpenAI message format, strip metadata
                    msg: dict[str, Any] = {"role": raw["role"], "content": raw.get("content")}
                    if "tool_calls" in raw:
                        msg["tool_calls"] = raw["tool_calls"]
                    if "tool_call_id" in raw:
                        msg["tool_call_id"] = raw["tool_call_id"]
                    messages.append(msg)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load session {session_id}: {e}")
        return []

    return messages


def list_session_files(session_dir: Path = settings.SESSION_DIR) -> list[Path]:
    """Return list of session-*.jsonl files, sorted by mtime (newest first)."""
    pattern = "session-*.jsonl"
    if not session_dir.exists():
        return []
    return sorted(
        session_dir.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def get_session_info(path: Path) -> dict[str, Any]:
    """Return session metadata: id, created, modified, size, message_count."""
    stat = path.stat()
    message_count = 0
    try:
        with open(path, encoding="utf-8") as f:
            message_count = sum(1 for _ in f)
    except OSError:
        message_count = 0

    return {
        "id": path.stem.replace("session-", ""),
        "path": str(path),
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "size": stat.st_size,
        "message_count": message_count,
    }


class Session:
    """Wraps session_id, history, session_logger, and todos for unified session management."""

    session_id: str
    history: list[dict[str, Any]]
    session_logger_cls: type[SessionLogger]
    session_logger: SessionLogger
    todos: TodoManager
    skill_loader: SkillLoader | None
    plan_mode: bool

    def __init__(
        self,
        sid: str | None = None,
        session_logger_cls: type[SessionLogger] | None = None,
        skill_loader: SkillLoader | None = None,
    ) -> None:
        self.session_logger_cls = session_logger_cls or FileSessionLogger
        self.skill_loader = skill_loader
        if sid:
            self.session_id = sid
            self.history = load_session(sid)
            self.session_logger = self.session_logger_cls(sid)
        else:
            self.session_id = generate_session_id()
            self.history = []
            self.session_logger = self.session_logger_cls(self.session_id)
        self.todos = TodoManager()
        self.plan_mode = False

    def clear(self) -> None:
        """Clear history and todos, start new session with new ID."""
        self.history.clear()
        self.todos.clear()
        self.session_id = generate_session_id()
        self.session_logger = self.session_logger_cls(self.session_id)
        self.plan_mode = False

    def renew(self) -> None:
        """Generate new session ID with current history preserved."""
        self.session_id = generate_session_id()
        self.session_logger = self.session_logger_cls(self.session_id)
        self.todos = TodoManager()
        self.plan_mode = False
        for msg in self.history:
            if msg["role"] == "user":
                self.session_logger.log_user(msg["content"])
            elif msg["role"] == "assistant":
                self.session_logger.log_assistant(msg["content"], msg.get("tool_calls"))
            elif msg["role"] == "tool":
                self.session_logger.log_tool(msg["tool_call_id"], msg["content"])

    def enter_plan_mode(self) -> None:
        """Enter plan mode for systematic exploration and planning."""
        self.plan_mode = True

    def exit_plan_mode(self) -> str:
        """Exit plan mode and return summary of planning session.

        Returns:
            Summary text of planning session
        """
        self.plan_mode = False
        # Generate summary from recent history
        if not self.history:
            return "No planning history."
        # Count planning-related messages
        planning_msgs = sum(1 for msg in self.history if msg["role"] in ("user", "assistant"))
        return f"Planning session complete: {planning_msgs} messages exchanged."

    def extract_plan_history(self) -> list[dict[str, Any]]:
        """Extract plan mode conversation from history.

        Returns messages from /plan command to current point.
        """
        # Find where plan mode started
        plan_start_idx = -1
        for i, msg in enumerate(self.history):
            if msg["role"] == "user" and "/plan" in msg.get("content", ""):
                plan_start_idx = i
                break

        if plan_start_idx == -1:
            return []

        return self.history[plan_start_idx:].copy()
