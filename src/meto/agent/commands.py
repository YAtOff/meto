"""Slash commands for interactive mode."""

from __future__ import annotations

import dataclasses
import json
import shlex
from collections.abc import Callable
from typing import Any

import typer

SlashCommandHandler = Callable[[list[str], list[dict[str, Any]]], None]


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


def cmd_clear(args: list[str], history: list[dict[str, Any]]) -> None:
    """Clear conversation history."""
    del args
    history.clear()
    print("History cleared.")


def cmd_help(args: list[str], history: list[dict[str, Any]]) -> None:
    """Show help for available commands."""
    del args
    del history
    print("Available commands:")
    for name in sorted(COMMANDS):
        spec = COMMANDS[name]
        usage = spec.usage or name
        print(f"  {usage:<15} - {spec.description}")


def cmd_quit(args: list[str], history: list[dict[str, Any]]) -> None:
    """Exit meto."""
    del args
    del history
    print("Goodbye!")
    raise typer.Exit(code=0)


def cmd_export(args: list[str], history: list[dict[str, Any]]) -> None:
    """Export conversation history to JSON."""
    if len(args) > 1:
        print("Usage: /export [file]")
        return

    filename = args[0] if args else ""
    _export_history(history, filename)


def cmd_compact(args: list[str], history: list[dict[str, Any]]) -> None:
    """Summarize conversation history to reduce token count."""
    del args
    _compact_history(history)


COMMANDS: dict[str, SlashCommandSpec] = {
    "/clear": SlashCommandSpec(
        handler=cmd_clear,
        description="Clear conversation history",
    ),
    "/compact": SlashCommandSpec(
        handler=cmd_compact,
        description="Summarize conversation to reduce token count",
    ),
    "/export": SlashCommandSpec(
        handler=cmd_export,
        description="Export conversation to JSON",
        usage="/export [file]",
    ),
    "/help": SlashCommandSpec(
        handler=cmd_help,
        description="Show this help",
    ),
    "/quit": SlashCommandSpec(
        handler=cmd_quit,
        description="Exit meto",
    ),
}


def handle_slash_command(user_input: str, history: list[dict[str, Any]]) -> bool:
    """Handle slash commands. Returns True if command was handled."""
    candidate = user_input.lstrip()
    if not candidate.startswith("/"):
        return False

    try:
        argv = _parse_slash_command_argv(candidate)
    except ValueError as e:
        print(f"Command parse error: {e}")
        return True

    if not argv:
        return False

    command = argv[0]
    args = argv[1:]

    # Decision: explicit empty args (e.g. /export "") behave like no args.
    if args == [""]:
        args = []

    spec = COMMANDS.get(command)
    if spec is None:
        print(f"Unknown command: {command}")
        return True

    spec.handler(args, history)
    return True


def _export_history(history: list[dict[str, Any]], filename: str) -> None:
    """Export conversation history to file (user/assistant/tool only)."""
    import datetime

    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"meto_conversation_{timestamp}.json"

    # Filter out system messages
    export_data = [msg for msg in history if msg["role"] != "system"]

    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"Exported to {filename}")
    except Exception as e:
        print(f"Export failed: {e}")


def _compact_history(history: list[dict[str, Any]]) -> None:
    """Summarize conversation history to reduce token count.

    Uses LLM to create a concise summary of the conversation,
    then replaces the history with just the summary.
    """
    from openai import OpenAI

    from meto.conf import settings

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
