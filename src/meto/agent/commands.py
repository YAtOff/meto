"""Slash commands for interactive mode.

Built-in commands are registered in the COMMANDS dict.

Custom commands can be defined as Markdown files in {settings.COMMANDS_DIR}/{command}.md.
When an unknown slash command is entered, the corresponding .md file is searched
for and, if found, its contents are used as a prompt for the agent loop.

Custom command files:
- Must be named {command}.md (e.g., code-review.md)
- Must be located in {settings.COMMANDS_DIR}
- Should contain the prompt text to be sent to the agent
- Can receive arguments, which are appended to the prompt as:
  [Command arguments: arg1 arg2 ...]

Command precedence:
1. Built-in commands (always take precedence)
2. Custom commands (if file exists)
3. Unknown command error
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import re
import shlex
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from openai import OpenAI

from meto.agent.agent_registry import get_all_agents
from meto.agent.context import format_context_summary, save_agent_context
from meto.agent.frontmatter_loader import parse_yaml_frontmatter
from meto.agent.modes.plan import PlanMode
from meto.agent.session import Session, generate_session_id
from meto.conf import settings

SlashCommandHandler = Callable[[list[str], Session], None]


@dataclasses.dataclass(frozen=True, slots=True)
class SlashCommandSpec:
    handler: SlashCommandHandler
    description: str
    usage: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class CustomCommandSpec:
    """Parsed custom command from {settings.COMMANDS_DIR}/*.md."""

    name: str
    description: str
    body: str
    allowed_tools: list[str] | None  # None = all tools
    context: str | None  # "fork" or None
    agent: str | None  # subagent name if context=fork


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
    """Search for custom command file in {settings.COMMANDS_DIR}/{command}.md.

    Args:
        command: Command string (may or may not start with /)

    Returns:
        Path to command file if it exists, None otherwise
    """
    try:
        command_name = _validate_command_name(command)
    except ValueError:
        return None

    # Construct path: {settings.COMMANDS_DIR}/{command}.md
    command_path = settings.COMMANDS_DIR / f"{command_name}.md"

    return command_path if command_path.is_file() else None


def _load_custom_command(command_path: Path) -> CustomCommandSpec:
    """Load and parse custom command file with YAML frontmatter.

    Args:
        command_path: Path to the custom command .md file

    Returns:
        CustomCommandSpec with parsed metadata and body

    Raises:
        ValueError: If file cannot be read or parsed
    """
    try:
        content = command_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read custom command file: {e}") from e
    except UnicodeDecodeError as e:
        raise ValueError(f"Failed to decode custom command file: {e}") from e

    parsed = parse_yaml_frontmatter(content)
    metadata = parsed["metadata"]
    body = parsed["body"]

    return CustomCommandSpec(
        name=metadata.get("name", command_path.stem),
        description=metadata.get("description", ""),
        body=body,
        allowed_tools=metadata.get("allowed-tools"),
        context=metadata.get("context"),
        agent=metadata.get("agent"),
    )


# Regex to match $ARGUMENTS[N] where N is a non-negative integer
_ARG_INDEX_PATTERN = re.compile(r"\$ARGUMENTS\[(\d+)\]")


class ArgumentSubstitutionError(Exception):
    """Raised when argument substitution fails."""


def _substitute_arguments(body: str, args: list[str]) -> str:
    """Substitute $ARGUMENTS and $ARGUMENTS[N] placeholders in command body.

    Args:
        body: Command body text with potential placeholders
        args: List of arguments to substitute

    Returns:
        Body with placeholders replaced

    Raises:
        ArgumentSubstitutionError: If $ARGUMENTS[N] references out-of-bounds index
    """
    substituted = False

    # First, replace $ARGUMENTS[N] patterns
    def replace_indexed(match: re.Match[str]) -> str:
        nonlocal substituted
        index = int(match.group(1))
        if index >= len(args):
            raise ArgumentSubstitutionError(
                f"$ARGUMENTS[{index}] out of bounds (only {len(args)} args provided)"
            )
        substituted = True
        return args[index]

    result = _ARG_INDEX_PATTERN.sub(replace_indexed, body)

    # Then, replace $ARGUMENTS with all args joined
    if "$ARGUMENTS" in result:
        result = result.replace("$ARGUMENTS", " ".join(args))
        substituted = True

    # If no substitution and args present, append ARGUMENTS: <value>
    if not substituted and args:
        args_text = " ".join(shlex.quote(arg) for arg in args)
        result = f"{result}\n\nARGUMENTS: {args_text}"

    return result


@dataclasses.dataclass(frozen=True, slots=True)
class CustomCommandResult:
    """Result of executing a custom command."""

    prompt: str
    context: str | None  # "fork" or None
    agent: str | None  # subagent name if context=fork
    allowed_tools: list[str] | None  # tool restrictions (None = all)


def _execute_custom_command(
    args: list[str],
    command_path: Path,
    session: Session,
) -> CustomCommandResult:
    """Execute custom command by loading file, parsing frontmatter, substituting args.

    Args:
        args: Command arguments (if any)
        command_path: Path to the custom command .md file
        session: Session instance (for potential future use)

    Returns:
        CustomCommandResult with prompt and execution context

    Raises:
        ValueError: If file cannot be loaded
        ArgumentSubstitutionError: If argument substitution fails
    """
    del session  # Unused for now, reserved for future use
    spec = _load_custom_command(command_path)

    # Warn if agent set without context: fork
    if spec.agent and spec.context != "fork":
        print(f"Warning: 'agent: {spec.agent}' has no effect without 'context: fork'")

    # Substitute arguments into body
    prompt = _substitute_arguments(spec.body, args)

    return CustomCommandResult(
        prompt=prompt,
        context=spec.context,
        agent=spec.agent,
        allowed_tools=spec.allowed_tools,
    )


def _cmd_clear(args: list[str], session: Session) -> None:
    """Clear conversation history and start new session if persisting."""
    del args
    session.clear()
    print("History cleared.")


def _get_custom_commands() -> dict[str, CustomCommandSpec]:
    """Discover all custom commands in commands directory.

    Returns:
        Dict mapping command name (with /) to CustomCommandSpec
    """
    commands_dir = settings.COMMANDS_DIR
    if not commands_dir.is_dir():
        return {}

    result: dict[str, CustomCommandSpec] = {}
    for path in commands_dir.glob("*.md"):
        try:
            spec = _load_custom_command(path)
            cmd_name = f"/{spec.name}"
            result[cmd_name] = spec
        except (ValueError, OSError):
            # Skip invalid command files
            continue

    return result


def _cmd_help(args: list[str], session: Session) -> None:
    """Show help for available commands."""
    del args, session  # Unused

    # Built-in commands
    print("Built-in commands:")
    for name in sorted(COMMANDS):
        spec = COMMANDS[name]
        usage = spec.usage or name
        print(f"  {usage:<15} - {spec.description}")

    # Custom commands
    custom_commands = _get_custom_commands()
    if custom_commands:
        print("\nCustom commands:")
        for name in sorted(custom_commands):
            spec = custom_commands[name]
            desc = spec.description or "(no description)"
            print(f"  {name:<15} - {desc}")


def _cmd_quit(args: list[str], session: Session) -> None:
    """Exit meto."""
    del args, session  # Unused
    print("Goodbye!")
    raise typer.Exit(code=0)


def _cmd_export(args: list[str], session: Session) -> None:
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


def _cmd_compact(args: list[str], session: Session) -> None:
    """Summarize conversation history to reduce token count."""
    del args
    _compact_history(session.history)
    session.renew()


def _cmd_context(args: list[str], session: Session) -> None:
    """Show a multi-line context summary."""
    if args:
        print("Usage: /context")
        return
    print(format_context_summary(session.history))


def _cmd_todos(args: list[str], session: Session) -> None:
    """Show current task list."""
    del args
    session.todos.print_rich()


def _cmd_agents(args: list[str], session: Session) -> None:
    """List all available agents."""
    del args, session
    agents = get_all_agents()
    print("Available agents:")
    for name, config in sorted(agents.items()):
        tools = config["tools"]
        tools_str = "*" if tools == "*" else ", ".join(tools)
        print(f"  {name:<12} - {config['description']}")
        print(f"               tools: {tools_str}")


def _cmd_plan(args: list[str], session: Session) -> None:
    """Enter plan mode for systematic exploration and planning."""
    del args
    if session.mode is not None:
        # Keep message backwards-compatible for the common case.
        if isinstance(session.mode, PlanMode):
            print("Already in plan mode. Exit with /done")
        else:
            print(f"Already in {session.mode.name} mode. Exit with /done")
        return

    mode = PlanMode()
    session.enter_mode(mode)
    plan_file = mode.plan_file
    print(f"Plan mode entered. Save your plan to: {plan_file}")
    print("Exit with /done")


def _cmd_done(args: list[str], session: Session) -> None:
    """Exit plan mode, clear context, and insert plan instruction."""
    del args
    if session.mode is None:
        print("Not in plan mode.")
        return

    exit_result = session.exit_mode()

    # Clear history completely
    session.history.clear()
    session.session_id = generate_session_id()
    session.session_logger = session.session_logger_cls(session.session_id)

    # Insert follow-up instruction if provided by the mode.
    if exit_result and exit_result.followup_system_message:
        session.history.append(
            {
                "role": "system",
                "content": exit_result.followup_system_message,
            }
        )
        print(f"History cleared. Follow the plan in: {exit_result.artifact_path}")
    else:
        print(
            "History cleared. No plan file found"
            + (f" at: {exit_result.artifact_path}" if exit_result else ".")
        )


def _cmd_implement(args: list[str], session: Session) -> None:
    """Exit plan mode, clear context, insert plan instruction, and prompt to start implementation."""
    del args
    if session.mode is None:
        print("Not in plan mode.")
        return

    exit_result = session.exit_mode()

    # Clear history completely
    session.history.clear()
    session.session_id = generate_session_id()
    session.session_logger = session.session_logger_cls(session.session_id)

    # Insert follow-up instruction if provided by the mode.
    if exit_result and exit_result.followup_system_message:
        session.history.append(
            {
                "role": "system",
                "content": exit_result.followup_system_message,
            }
        )
        print(f"History cleared. Follow the plan in: {exit_result.artifact_path}")

        # Prompt user to start implementation
        from rich.console import Console
        from rich.prompt import Confirm

        console = Console()
        if Confirm.ask(
            "\nStart implementing the plan now?",
            console=console,
            default=True,
        ):
            # Set flag to trigger implementation
            session.start_implementation = True
    else:
        print(
            "History cleared. No plan file found"
            + (f" at: {exit_result.artifact_path}" if exit_result else ".")
        )


COMMANDS: dict[str, SlashCommandSpec] = {
    "/agents": SlashCommandSpec(
        handler=_cmd_agents,
        description="List all available agents",
    ),
    "/clear": SlashCommandSpec(
        handler=_cmd_clear,
        description="Clear conversation history",
    ),
    "/compact": SlashCommandSpec(
        handler=_cmd_compact,
        description="Summarize conversation to reduce token count",
    ),
    "/context": SlashCommandSpec(
        handler=_cmd_context,
        description="Show a summary of the current context",
    ),
    "/done": SlashCommandSpec(
        handler=_cmd_done,
        description="Exit plan mode + clear context",
    ),
    "/export": SlashCommandSpec(
        handler=_cmd_export,
        description="Export conversation to a file (multiple formats)",
        usage="/export [path] [--format json|pretty_json|markdown|text] [--full]",
    ),
    "/help": SlashCommandSpec(
        handler=_cmd_help,
        description="Show this help",
    ),
    "/implement": SlashCommandSpec(
        handler=_cmd_implement,
        description="Exit plan mode + prompt to start implementation",
    ),
    "/plan": SlashCommandSpec(
        handler=_cmd_plan,
        description="Enter plan mode",
    ),
    "/quit": SlashCommandSpec(
        handler=_cmd_quit,
        description="Exit meto",
    ),
    "/todos": SlashCommandSpec(
        handler=_cmd_todos,
        description="Show current task list",
    ),
}


def handle_slash_command(
    user_input: str,
    session: Session,
) -> tuple[bool, CustomCommandResult | None]:
    """Handle slash commands.

    Args:
        user_input: Raw user input
        session: Session instance

    Returns:
        Tuple of (was_handled, result):
        - was_handled: True if command was processed (built-in or custom)
        - result: If custom command executed, contains CustomCommandResult;
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
            result = _execute_custom_command(args, custom_command_path, session)
            return True, result
        except (ValueError, ArgumentSubstitutionError) as e:
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
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("path", nargs="?", default="")
    parser.add_argument(
        "format", nargs="?", default="json", choices={"json", "pretty_json", "markdown", "text"}
    )
    parser.add_argument(
        "-f", "--format", dest="format_flag", choices={"json", "pretty_json", "markdown", "text"}
    )
    parser.add_argument("--full", "--include-system", action="store_true")

    try:
        ns = parser.parse_args(args)
        export_format = ns.format_flag or ns.format
        return ns.path, export_format, ns.full
    except argparse.ArgumentError as e:
        raise ValueError(str(e)) from e


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
            output_format=export_format,
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

    if not settings.LLM_API_KEY:
        print("METO_LLM_API_KEY is not set. Configure it in .env or environment variables.")
        return

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
