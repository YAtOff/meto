import json
import logging
from datetime import UTC, datetime
from typing import Any, override

from rich.console import Console

from meto.conf import settings

logger = logging.getLogger("agent")


class JSONFormatter(logging.Formatter):
    @override
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "session_id": getattr(record, "session_id", None),
            "turn": getattr(record, "turn", None),
        }
        return json.dumps(log_obj)


class ReasoningLogger:
    """Structured logging for agent reasoning with JSON file + colored stderr."""

    session_id: str
    turn_count: int
    console: Console

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.turn_count = 0
        self.console = Console(stderr=True)

        # JSON file handler
        json_handler = logging.FileHandler(settings.log_file)
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)

    def _log(self, level: int, msg: str, **kwargs: Any) -> None:
        """Internal log method that adds session context."""
        extra = {"session_id": self.session_id, **kwargs}
        logger.log(level, msg, extra=extra)

    def log_user_input(self, prompt: str):
        """Log the incoming user prompt."""
        self._log(logging.INFO, f"User input: {prompt}")
        self.console.print(f"[bold cyan]→[/] {prompt}")

    def log_api_request(self, messages: list[dict[str, Any]]) -> None:
        """Log the messages being sent to the model."""
        logger.debug(f"[{self.session_id}] API request with {len(messages)} messages")

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

    def log_tool_selection(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Log when the model selects a tool."""
        self._log(
            logging.INFO,
            f"Tool selected: {tool_name} with args: {json.dumps(arguments, indent=2)}",
        )
        args_preview = json.dumps(arguments, ensure_ascii=False)[:100]
        self.console.print(f"[dim]🔧 {tool_name} {args_preview}...[/]")

    def log_tool_execution(self, tool_name: str, result: str, error: bool = False):
        """Log tool execution results."""
        level = logging.ERROR if error else logging.INFO
        truncated = result[:200] + "..." if len(result) > 200 else result
        self._log(level, f"Tool '{tool_name}' result: {truncated}")

        if error:
            self.console.print(f"[red]✗ {tool_name}:[/] {truncated}")
        else:
            self.console.print(f"[green]✓ {tool_name}[/]")

    def log_loop_completion(self, reason: str):
        """Log why the agent loop ended."""
        self._log(
            logging.INFO,
            f"Loop completed after {self.turn_count} turns. Reason: {reason}",
        )
        self.console.print(f"[dim]Done: {reason}[/]")
