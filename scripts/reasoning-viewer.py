#!/usr/bin/env python
"""Reasoning Log Viewer - CLI tool for tailing agent reasoning logs."""

from __future__ import annotations

import colorsys
import hashlib
import json
import time
from pathlib import Path

import typer

# ANSI reset code
RESET_COLOR = "\x1b[0m"


def hash_to_color(agent_run_id: str) -> str:
    """
    Convert agent_run_id to a 24-bit ANSI color code.

    Uses MD5 hash to generate deterministic but random-looking colors.
    Maps hash bytes to HSL color space, then converts to RGB.

    Args:
        agent_run_id: Unique identifier for agent run

    Returns:
        ANSI escape code for 24-bit RGB color
    """
    # Hash the agent_run_id with MD5
    hash_bytes = hashlib.md5(agent_run_id.encode()).digest()

    # Use first 3 bytes for H, L, S (HLS in Python's colorsys)
    h = hash_bytes[0] / 255.0  # Hue: 0.0-1.0
    lightness = hash_bytes[1] / 255.0  # Lightness: 0.0-1.0
    s = hash_bytes[2] / 255.0  # Saturation: 0.0-1.0

    # Convert HLS to RGB
    r, g, b = colorsys.hls_to_rgb(h, lightness, s)

    # Scale to 0-255 and round
    r = int(round(r * 255))
    g = int(round(g * 255))
    b = int(round(b * 255))

    # Format as 24-bit ANSI escape code
    return f"\x1b[38;2;{r};{g};{b}m"


def format_agent_name(agent_name: str, agent_run_id: str) -> str:
    """
    Wrap agent name in color codes based on agent_run_id.

    Args:
        agent_name: Display name of the agent
        agent_run_id: Unique identifier for the agent run (used for color)

    Returns:
        Agent name wrapped in ANSI color codes
    """
    color_code = hash_to_color(agent_run_id)
    return f"{color_code}{agent_name}{RESET_COLOR}"


def format_turn_display(turn: int | None) -> str:
    """
    Format turn number for display.

    Args:
        turn: Turn number (may be None)

    Returns:
        String representation ("-" if None)
    """
    return "-" if turn is None else str(turn)


def parse_log_entry(
    line: str,
) -> dict[str, str | int | None] | None:
    """
    Parse a JSONL log entry and extract display fields.

    Args:
        line: JSONL line from log file

    Returns:
        Dict with keys: level, agent_name, turn, message, agent_run_id
        Returns None if parsing fails or required fields are missing
    """
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None

    # Check for required fields
    required_fields = ["level", "agent_name", "turn", "message", "agent_run_id"]
    for field in required_fields:
        if field not in entry:
            return None

    return {
        "level": entry["level"],
        "agent_name": entry["agent_name"],
        "turn": entry["turn"],
        "message": entry["message"],
        "agent_run_id": entry["agent_run_id"],
    }


def should_display_entry(
    entry: dict[str, str | int | None], level_filters: list[str], agent_filters: list[str]
) -> bool:
    """
    Check if a log entry should be displayed based on filters.

    Args:
        entry: Parsed log entry dict
        level_filters: List of log levels to include (empty = all)
        agent_filters: List of agent names to include (empty = all)

    Returns:
        True if entry matches all filters, False otherwise
    """
    if level_filters and entry["level"] not in level_filters:
        return False

    if agent_filters and entry["agent_name"] not in agent_filters:
        return False

    return True


def format_log_entry(entry: dict[str, str | int | None]) -> str:
    """
    Format a parsed log entry for display.

    Format: {level} {colored_agent_name}:{turn_display} {message}

    Args:
        entry: Parsed log entry dict

    Returns:
        Formatted string ready for display
    """
    colored_agent_name = format_agent_name(str(entry["agent_name"]), str(entry["agent_run_id"]))
    turn_val = entry["turn"]
    # Ensure turn is int or None (JSON may have given us int or null)
    turn = None if turn_val is None else int(turn_val)
    turn_display = format_turn_display(turn)

    return f"{entry['level']} {colored_agent_name}:{turn_display} {entry['message']}"


def read_new_lines(file_path: Path, offset: int) -> tuple[list[str], int]:
    """
    Read new lines from a log file starting from offset.

    Args:
        file_path: Path to log file
        offset: Byte offset to start reading from

    Returns:
        Tuple of (new_lines, new_offset)
    """
    lines = []
    with open(file_path, encoding="utf-8") as f:
        f.seek(offset)
        lines = f.readlines()
        new_offset = f.tell()

    return lines, new_offset


def tail_log_file(file_path: Path, level_filters: list[str], agent_filters: list[str]) -> None:
    """
    Tail a log file and print matching entries.

    Args:
        file_path: Path to log file
        level_filters: List of log levels to include (empty = all)
        agent_filters: List of agent names to include (empty = all)
    """
    offset = 0

    try:
        # Initial read from beginning
        lines, offset = read_new_lines(file_path, offset)
        for line in lines:
            line = line.rstrip("\n\r")
            entry = parse_log_entry(line)
            if entry is not None:
                if should_display_entry(entry, level_filters, agent_filters):
                    print(format_log_entry(entry))
            else:
                # Malformed JSON or missing fields
                print(f"[ERROR] {line}")

        # Polling loop
        while True:
            time.sleep(1)
            lines, offset = read_new_lines(file_path, offset)
            for line in lines:
                line = line.rstrip("\n\r")
                entry = parse_log_entry(line)
                if entry is not None:
                    if should_display_entry(entry, level_filters, agent_filters):
                        print(format_log_entry(entry))
                else:
                    # Malformed JSON or missing fields
                    print(f"[ERROR] {line}")

    except KeyboardInterrupt:
        # Exit immediately on Ctrl+C
        pass


def validate_log_file(file_path: Path) -> None:
    """
    Validate that the log file exists and is readable.

    Args:
        file_path: Path to validate

    Raises:
        typer.BadParameter: If file doesn't exist or isn't a file
    """
    if not file_path.exists():
        raise typer.BadParameter(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise typer.BadParameter(f"Not a file: {file_path}")


# Create Typer app
app = typer.Typer()


@app.command()
def main(
    log_file: str,
    agent: list[str] | None = typer.Option(  # noqa: B008
        None, "--agent", help="Filter by agent name (can be used multiple times)"
    ),
    level: list[str] | None = typer.Option(  # noqa: B008
        None, "--level", help="Filter by log level (can be used multiple times)"
    ),
) -> None:
    """
    Tail and display agent reasoning logs with color-coded agent names.

    Shows log entries in format: {level} {agent_name}:{turn} {message}

    Agent names are color-coded based on agent_run_id to distinguish
    between different agent runs of the same agent type.

    Use --agent and --level to filter output (AND logic between filter types).
    """
    # Convert string path to Path object
    log_path = Path(log_file)

    # Validate log file exists
    validate_log_file(log_path)

    # Convert None to empty list
    agent_filters = agent or []
    level_filters = level or []

    # Start tailing
    tail_log_file(log_path, level_filters, agent_filters)


if __name__ == "__main__":
    app()
