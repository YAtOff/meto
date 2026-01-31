from __future__ import annotations

import os
import re
from pathlib import Path

from meto.agent.modes.plan import PlanMode
from meto.agent.session import (
    FileSessionLogger,
    NullSessionLogger,
    Session,
    generate_session_id,
    list_session_files,
    load_session,
)


def test_generate_session_id_format() -> None:
    sid = generate_session_id()
    assert re.match(r"^\d{8}_\d{6}-[a-z0-9]{6}$", sid)


def test_file_session_logger_writes_jsonl(tmp_path: Path) -> None:
    logger = FileSessionLogger(session_id="test123", session_dir=tmp_path)

    logger.log_user("hi")
    logger.log_assistant("ok", tool_calls=None)
    logger.log_tool("tc1", "out")

    session_file = tmp_path / "session-test123.jsonl"
    lines = session_file.read_text("utf-8").splitlines()
    assert len(lines) == 3
    assert '"role": "user"' in lines[0]
    assert '"role": "assistant"' in lines[1]
    assert '"role": "tool"' in lines[2]


def test_load_session_returns_openai_style_history(tmp_path: Path) -> None:
    logger = FileSessionLogger(session_id="abc", session_dir=tmp_path)
    logger.log_user("u")
    logger.log_assistant("a", tool_calls=[{"id": "x"}])
    logger.log_tool("tc", "t")

    hist = load_session("abc", session_dir=tmp_path)
    assert [m["role"] for m in hist] == ["user", "assistant", "tool"]
    assert "timestamp" not in hist[0]
    assert "session_id" not in hist[0]
    assert "tool_calls" in hist[1]
    assert hist[2]["tool_call_id"] == "tc"


def test_list_session_files_sorted_by_mtime_desc(tmp_path: Path) -> None:
    p1 = tmp_path / "session-a.jsonl"
    p2 = tmp_path / "session-b.jsonl"
    p1.write_text("{}", "utf-8")
    p2.write_text("{}", "utf-8")

    os.utime(p1, (1, 1))
    os.utime(p2, (2, 2))

    files = list_session_files(session_dir=tmp_path)
    assert files[0].name == "session-b.jsonl"
    assert files[1].name == "session-a.jsonl"


def test_session_enter_exit_mode_and_guardrails() -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    session.enter_mode(PlanMode())

    # Entering again should raise
    try:
        session.enter_mode(PlanMode())
        raise AssertionError("Expected RuntimeError")
    except RuntimeError:
        pass

    exit_result = session.exit_mode()
    assert exit_result is not None
    assert session.mode is None


def test_session_clear_resets_history_todos_and_id() -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    old_id = session.session_id
    session.history.append({"role": "user", "content": "x"})
    session.todos.update([{"content": "a", "status": "pending", "activeForm": "a"}])

    session.clear()

    assert session.session_id != old_id
    assert session.history == []
    assert session.todos.items == []


def test_session_renew_keeps_history_and_changes_id(tmp_path: Path) -> None:
    session_dir = tmp_path / "sessions"
    session_dir.mkdir(exist_ok=True)

    class TmpFileLogger(FileSessionLogger):
        def __init__(self, session_id: str | None = None) -> None:
            super().__init__(session_id=session_id, session_dir=session_dir)

    session = Session(session_logger_cls=TmpFileLogger, yolo_mode=True)
    old_id = session.session_id
    session.history.extend(
        [
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]
    )

    session.renew()

    assert session.session_id != old_id
    assert [m["role"] for m in session.history] == ["user", "assistant"]

    new_file = session_dir / f"session-{session.session_id}.jsonl"
    assert new_file.exists()
    lines = new_file.read_text("utf-8").splitlines()
    assert len(lines) == 2
