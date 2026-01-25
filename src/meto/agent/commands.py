"""Slash commands for interactive mode.

Built-in commands are registered in the COMMANDS dict.

Custom commands can be defined as Markdown files in $PWD/.meto/commands/{command}.md.
When an unknown slash command is entered, the corresponding .md file is searched
for and, if found, its contents are used as a prompt for the agent loop.

Custom command files:
- Must be named {command}.md (e.g., code-review.md)
- Must be located in $PWD/.meto/commands/
- Should contain the prompt text to be sent to the agent
- Can receive arguments, which are appended to the prompt as:
  [Command arguments: arg1 arg2 ...]

Command precedence:
1. Built-in commands (always take precedence)
2. Custom commands (if file exists)
3. Unknown command error
"""

from __future__ import annotations

import dataclasses
import datetime
import re
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from openai import OpenAI

from meto.agent.context import format_context_summary, save_agent_context
from meto.agent.session import Session
from meto.conf import settings

SlashCommandHandler = Callable[[list[str], Session], None]


@dataclasses.dataclass(frozen=True, slots=True)
class SlashCommandSpec:
    handler: SlashCommandHandler
    description: str
    usage: str | None = None


def _parse_slash_command_argv(text: str) -> list[str]:
    """Parse a slash command into argv tokens.

    We aim for a `sys.argv`-like experience:
    - Quotes group tokens (e.g. /export "my file.json")
    - `#` is NOT treated as a comment
    - Backslashes are preserved (important for Windows paths)
    """

    # We intentionally avoid `shlex.split(..., posix=False)` because it tends to
    # preserve quotes as literal characters. We also disable escaping because
    # backslashes are common in Windows paths and should not be treated as
    # escape sequences.
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.escape = ""
    return list(lexer)


def _validate_command_name(command: str) -> str:
    """Validate and sanitize command name.

    Prevents path traversal and ensures valid filename.

    Args:
        command: Command string (may or may not start with /)

    Returns:
        Sanitized command name without leading slash

    Raises:
        ValueError: If command name contains invalid characters
    """
    # Remove leading slash
    name = command.lstrip("/")

    # Prevent path traversal
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid command name: {command}")

    # Allow only alphanumeric, hyphen, underscore
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(f"Invalid command name: {command}")

    return name


def _find_custom_command_file(command: str) -> Path | None:
    """Search for custom command file in $PWD/.meto/commands/{command}.md.

    Args:
        command: Command string (may or may not start with /)

    Returns:
        Path to command file if it exists, None otherwise
    """
    try:
        command_name = _validate_command_name(command)
    except ValueError:
        return None

    # Construct path: $PWD/.meto/commands/{command}.md
    command_path = Path.cwd() / ".meto" / "commands" / f"{command_name}.md"

    return command_path if command_path.is_file() else None


def _load_custom_command_prompt(command_path: Path) -> str:
    """Load and return contents of custom command file.

    Args:
        command_path: Path to the custom command .md file

    Returns:
        File contents as string

    Raises:
        ValueError: If file cannot be read
    """
    try:
        return command_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read custom command file: {e}") from e
    except UnicodeDecodeError as e:
        raise ValueError(f"Failed to decode custom command file: {e}") from e


def _execute_custom_command(
    args: list[str],
    command_path: Path,
    session: Session,
) -> str:
    """Execute custom command by loading file content and appending arguments.

    Args:
        args: Command arguments (if any)
        command_path: Path to the custom command .md file
        session: Session instance (for potential future use)

    Returns:
        Prompt string to pass to agent loop

    Raises:
        ValueError: If file cannot be loaded
    """
    del session  # Unused for now, reserved for future use
    base_prompt = _load_custom_command_prompt(command_path)

    # If args provided, append them to the prompt
    if args:
        args_text = " ".join(shlex.quote(arg) for arg in args)
        return f"{base_prompt}\n\n[Command arguments: {args_text}]"

    return base_prompt


def cmd_clear(args: list[str], session: Session) -> None:
    """Clear conversation history and start new session if persisting."""
    del args
    session.clear()
    print("History cleared.")


def cmd_help(args: list[str], session: Session) -> None:
    """Show help for available commands."""
    del args, session  # Unused
    print("Available commands:")
    for name in sorted(COMMANDS):
        spec = COMMANDS[name]
        usage = spec.usage or name
        print(f"  {usage:<15} - {spec.description}")


def cmd_quit(args: list[str], session: Session) -> None:
    """Exit meto."""
    del args, session  # Unused
    print("Goodbye!")
    raise typer.Exit(code=0)


def cmd_export(args: list[str], session: Session) -> None:
    """Export conversation history to a file."""
    try:
        export_target, export_format, include_system = _parse_export_args(args)
    except ValueError as e:
        print(str(e))
        print("Usage: /export [path] [--format json|pretty_json|markdown|text] [--full]")
        return

    _export_history(
        session.history,
        export_target,
        export_format,
        include_system=include_system,
    )


def cmd_compact(args: list[str], session: Session) -> None:
    """Summarize conversation history to reduce token count."""
    del args
    _compact_history(session.history)
    session.renew()


def cmd_context(args: list[str], session: Session) -> None:
    """Show a multi-line context summary."""
    if args:
        print("Usage: /context")
        return
    print(format_context_summary(session.history))


def cmd_todos(args: list[str], session: Session) -> None:
    """Show current task list."""
    del args
    print(session.todos.render())


COMMANDS: dict[str, SlashCommandSpec] = {
    "/clear": SlashCommandSpec(
        handler=cmd_clear,
        description="Clear conversation history",
    ),
    "/compact": SlashCommandSpec(
        handler=cmd_compact,
        description="Summarize conversation to reduce token count",
    ),
    "/context": SlashCommandSpec(
        handler=cmd_context,
        description="Show a summary of the current context",
    ),
    "/export": SlashCommandSpec(
        handler=cmd_export,
        description="Export conversation to a file (multiple formats)",
        usage="/export [path] [--format json|pretty_json|markdown|text] [--full]",
    ),
    "/help": SlashCommandSpec(
        handler=cmd_help,
        description="Show this help",
    ),
    "/quit": SlashCommandSpec(
        handler=cmd_quit,
        description="Exit meto",
    ),
    "/todos": SlashCommandSpec(
        handler=cmd_todos,
        description="Show current task list",
    ),
}


def handle_slash_command(
    user_input: str,
    session: Session,
) -> tuple[bool, str | None]:
    """Handle slash commands.

    Args:
        user_input: Raw user input
        session: Session instance

    Returns:
        Tuple of (was_handled, custom_prompt):
        - was_handled: True if command was processed (built-in or custom)
        - custom_prompt: If custom command executed, contains prompt for agent loop;
          None for built-in commands or errors
    """
    candidate = user_input.lstrip()
    if not candidate.startswith("/"):
        return False, None

    try:
        argv = _parse_slash_command_argv(candidate)
    except ValueError as e:
        print(f"Command parse error: {e}")
        return True, None

    if not argv:
        return False, None

    command = argv[0]
    args = argv[1:]

    # Decision: explicit empty args (e.g. /export "") behave like no args.
    if args == [""]:
        args = []

    # Check built-in commands first
    spec = COMMANDS.get(command)
    if spec is not None:
        spec.handler(args, session)
        return True, None

    # Check for custom command file
    custom_command_path = _find_custom_command_file(command)
    if custom_command_path is not None:
        try:
            custom_prompt = _execute_custom_command(args, custom_command_path, session)
            return True, custom_prompt
        except ValueError as e:
            print(f"Custom command error: {e}")
            return True, None

    # Unknown command
    print(f"Unknown command: {command}")
    return True, None


def _parse_export_args(args: list[str]) -> tuple[str, str, bool]:
    """Parse /export arguments.

    Supported forms:
      /export
      /export <path>
      /export <path> <format>
      /export [<path>] --format <format> [--full]

    Notes:
      - Default format is json
      - Default is to EXCLUDE system messages unless --full is provided
    """

    supported_formats = {"json", "pretty_json", "markdown", "text"}
    export_format = "json"
    include_system = False
    export_target = ""

    # First, capture a positional path (if present) until we hit flags.
    positionals: list[str] = []
    i = 0
    while i < len(args) and not args[i].startswith("-"):
        positionals.append(args[i])
        i += 1

    # Remaining args are flags (and their values).
    while i < len(args):
        tok = args[i]

        if tok in ("--full", "--include-system"):
            include_system = True
            i += 1
            continue

        if tok in ("--format", "-f"):
            if i + 1 >= len(args):
                raise ValueError("/export: missing value for --format")
            candidate = args[i + 1]
            if candidate not in supported_formats:
                raise ValueError(f"/export: unsupported format: {candidate}")
            export_format = candidate
            i += 2
            continue

        raise ValueError(f"/export: unknown option: {tok}")

    # Interpret positionals.
    if len(positionals) == 0:
        export_target = ""
    elif len(positionals) == 1:
        export_target = positionals[0]
    elif len(positionals) == 2:
        export_target = positionals[0]
        candidate_format = positionals[1]
        if candidate_format not in supported_formats:
            raise ValueError(
                "/export: second positional must be a format (json|pretty_json|markdown|text)"
            )
        export_format = candidate_format
    else:
        raise ValueError("/export: too many positional arguments")

    return export_target, export_format, include_system


def _export_history(
    history: list[dict[str, Any]],
    export_target: str,
    export_format: str,
    *,
    include_system: bool,
) -> None:
    """Export conversation history to file.

    By default exports user/assistant/tool messages only. If include_system is True,
    system messages are included as well.
    """
    ext_by_format = {
        "json": ".json",
        "pretty_json": ".json",
        "markdown": ".md",
        "text": ".txt",
    }
    ext = ext_by_format.get(export_format, ".txt")

    # Resolve path target:
    # - empty => default filename in CWD
    # - existing directory OR trailing slash => generate filename inside
    # - file path without suffix => append inferred extension
    if not export_target:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = Path(f"meto_conversation_{timestamp}{ext}")
    else:
        raw = export_target
        is_directory_hint = raw.endswith("/") or raw.endswith("\\")
        target_path = Path(raw)

        if (target_path.exists() and target_path.is_dir()) or is_directory_hint:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"meto_conversation_{timestamp}{ext}"
            filepath = target_path / filename
        else:
            filepath = target_path
            if filepath.suffix == "":
                filepath = filepath.with_suffix(ext)

    try:
        save_agent_context(
            history,
            filepath,
            format=export_format,
            include_system=include_system,
        )
        print(f"Exported to {filepath}")
    except Exception as e:
        print(f"Export failed: {e}")


def _compact_history(history: list[dict[str, Any]]) -> None:
    """Summarize conversation history to reduce token count.

    Uses LLM to create a concise summary of the conversation,
    then replaces the history with just the summary.
    """
    if not history:
        print("No history to compact.")
        return

    # Build conversation text for summarization (exclude system messages)
    conversation_text = "\n".join(
        f"{msg['role']}: {msg.get('content', '')}"
        for msg in history
        if msg["role"] in ("user", "assistant")
    )

    client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)

    try:
        resp = client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize the following conversation concisely. "
                    "Preserve key context, decisions, and technical details. "
                    "Output as a single paragraph.",
                },
                {"role": "user", "content": conversation_text},
            ],
        )
        summary = resp.choices[0].message.content or "Conversation summary unavailable."

        # Replace history with a single user message containing the summary
        history.clear()
        history.append(
            {
                "role": "user",
                "content": f"[Previous conversation summary]: {summary}",
            }
        )
        print(f"History compacted. ({len(conversation_text)} chars -> {len(summary)} chars)")
    except Exception as e:
        print(f"Compact failed: {e}")
