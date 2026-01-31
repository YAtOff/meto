"""Reasoning/logging utilities.

The agent uses two logging surfaces:
- a JSONL trace file (machine-readable)
- rich-colored stderr output (human-readable)

This module keeps the logging concerns isolated from the agent loop/tool runner.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, override

from rich.console import Console
from rich.panel import Panel

from meto.conf import settings

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.propagate = False


class JSONFormatter(logging.Formatter):
    """Format log records as a single-line JSON object."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
            "agent_name": getattr(record, "agent_name", None),
            "agent_run_id": getattr(record, "agent_run_id", None),
            "turn": getattr(record, "turn", None),
        }
        return json.dumps(log_obj)


class ReasoningLogger:
    """Structured logging for agent reasoning with JSON file + colored stderr."""

    session_id: str
    agent_name: str
    agent_run_id: str | None
    turn_count: int
    console: Console

    _logger: logging.Logger
    _json_handler: logging.FileHandler | None

    def __init__(self, session_id: str, agent_name: str, agent_run_id: str | None = None) -> None:
        self.session_id = session_id
        self.agent_name = agent_name
        self.agent_run_id = agent_run_id or str(datetime.now().timestamp())
        self.turn_count = 0
        self.console = Console(stderr=True)

        # Instance-specific logger to avoid accumulating handlers on a module-global logger.
        self._logger = logging.getLogger(
            f"meto.agent.reasoning.{self.session_id}.{self.agent_run_id}"
        )
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        # Ensure we never duplicate handlers even if the same logger name is reused.
        for h in list(self._logger.handlers):
            try:
                h.close()
            finally:
                self._logger.removeHandler(h)

        self._json_handler = None

        # JSON file handler
        json_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
        json_handler.setFormatter(JSONFormatter())
        self._logger.addHandler(json_handler)
        self._json_handler = json_handler

    def close(self) -> None:
        """Close any file handlers attached to this logger.

        In interactive usage, ReasoningLogger instances are created frequently.
        Explicitly closing handlers prevents file descriptor leaks and duplicate logs.
        """

        for h in list(self._logger.handlers):
            try:
                h.close()
            finally:
                self._logger.removeHandler(h)
        self._json_handler = None

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """Internal log method that adds session context."""
        extra = {
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "agent_run_id": self.agent_run_id,
            **kwargs,
        }
        self._logger.log(level, msg, extra=extra)

    def log_user_input(self, prompt: str) -> None:
        """Log the incoming user prompt."""
        self._log(logging.INFO, f"User input: {prompt}")
        self.console.print(f"[bold cyan]→[/] {prompt}")

    def log_api_request(self, messages: list[dict[str, Any]]) -> None:
        """Log the messages being sent to the model."""
        self._logger.debug(f"[{self.session_id}] API request with {len(messages)} messages")

    def log_model_response(self, response: Any, _model: str) -> None:
        """Log the raw model response."""
        self.turn_count += 1

        msg = response.choices[0].message
        assistant_content = msg.content or ""
        tool_calls = list(getattr(msg, "tool_calls", None) or [])

        self._log(logging.INFO, f"Turn {self.turn_count}: Model response", turn=self.turn_count)

        if assistant_content:
            self._log(logging.INFO, f"Assistant reasoning: {assistant_content}")
            self.console.print(f"[bold]Turn {self.turn_count}:[/] {assistant_content}")

        self._log(logging.INFO, f"Tool calls requested: {len(tool_calls)}")

        # Log token usage if available
        if hasattr(response, "usage"):
            self._log(
                logging.INFO,
                f"Token usage - Input: {response.usage.prompt_tokens}, "
                f"Output: {response.usage.completion_tokens}",
            )
            # Also print to console for user visibility
            self.console.print(
                f"[dim]📊 Tokens: {response.usage.prompt_tokens} sent, "
                f"{response.usage.completion_tokens} received[/]"
            )

    def log_tool_selection(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Log when the model selects a tool."""
        self._log(
            logging.INFO,
            f"Tool selected: {tool_name} with args: {json.dumps(arguments, indent=2)}",
        )
        args_preview = json.dumps(arguments, ensure_ascii=False)[:100]
        self.console.print(f"[dim]🔧 {tool_name} {args_preview}...[/]")

    def log_tool_execution(self, tool_name: str, result: str, error: bool = False) -> None:
        """Log tool execution results."""
        level = logging.ERROR if error else logging.INFO
        truncated = result[:200] + "..." if len(result) > 200 else result
        self._log(level, f"Tool '{tool_name}' result: {truncated}")

        if error:
            self.console.print(f"[red]✗ {tool_name}:[/] {truncated}")
        else:
            self.console.print(f"[green]✓ {tool_name}[/]")

    def log_skill_loaded(self, skill_name: str) -> None:
        """Log when a skill is loaded."""
        self._log(logging.INFO, f"Skill loaded: {skill_name}")
        self.console.print(f"[dim]ℹ️  Skill loaded: {skill_name}[/]")

    def log_loop_completion(self, reason: str) -> None:
        """Log why the agent loop ended."""
        self._log(
            logging.INFO,
            f"Loop completed after {self.turn_count} turns. Reason: {reason}",
        )
        self.console.print(f"[dim]Done: {reason}[/]")

    def log_system_prompt(self, prompt: str) -> None:
        """Log the system prompt being sent to the model."""
        self._log(logging.INFO, f"System prompt: {prompt[:500]}...")
        if settings.LOG_SYSTEM_PROMPT:
            display_prompt = prompt[:1000] + "..." if len(prompt) > 1000 else prompt
            self.console.print(
                Panel(
                    display_prompt,
                    title="[bold]System Prompt[/]",
                    border_style="dim blue",
                    padding=(0, 1),
                )
            )
