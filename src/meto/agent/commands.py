"""Slash commands for interactive mode."""

from __future__ import annotations

import json
from typing import Any

import typer


def handle_slash_command(user_input: str, history: list[dict[str, Any]]) -> bool:
    """Handle slash commands. Returns True if command was handled."""
    if not user_input.startswith("/"):
        return False

    parts = user_input.split(maxsplit=1)
    command = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if command == "/clear":
        history.clear()
        print("History cleared.")
        return True
    elif command == "/help":
        _print_help()
        return True
    elif command == "/quit":
        print("Goodbye!")
        raise typer.Exit(code=0)
    elif command == "/export":
        _export_history(history, args)
        return True
    else:
        print(f"Unknown command: {command}")
        return True


def _print_help() -> None:
    """Print available commands."""
    print("Available commands:")
    print("  /clear          - Clear conversation history")
    print("  /export [file]  - Export conversation to JSON")
    print("  /help           - Show this help")
    print("  /quit           - Exit meto")


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
