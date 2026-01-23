"""
Agent context dumping and serialization utilities for the agent loop.
Provides methods to extract, format, and save conversation history.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast


def dump_agent_context(
    history: list[dict[str, Any]],
    format: str = "json",
    *,
    include_system: bool = True,
) -> str:
    """
    Dump agent context (conversation history) in a specified format.

    Args:
        history: The agent conversation history list
        format: Output format - "json", "pretty_json", "markdown", or "text"
        include_system: Whether to include system messages in the output

    Returns:
        Formatted string representation of the agent context
    """
    history_to_dump = history
    if not include_system:
        history_to_dump = [msg for msg in history if msg.get("role") != "system"]

    if format == "json":
        return json.dumps(history_to_dump, indent=2)

    elif format == "pretty_json":
        return json.dumps(history_to_dump, indent=2, ensure_ascii=False)

    elif format == "markdown":
        return _format_as_markdown(history_to_dump)

    elif format == "text":
        return _format_as_text(history_to_dump)

    else:
        raise ValueError(f"Unknown format: {format}")


def _format_as_markdown(history: list[dict[str, Any]]) -> str:
    """Format history as readable Markdown."""
    lines = ["# Agent Conversation History\n"]

    for i, msg in enumerate(history, 1):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        lines.append(f"## Message {i}: {role}\n")

        if role == "USER":
            lines.append(f"{content}\n")

        elif role == "ASSISTANT":
            if content:
                lines.append(f"**Response:**\n\n{content}\n")

            if "tool_calls" in msg:
                lines.append("**Tool Calls:**\n")
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args = fn.get("arguments", "{}")

                    # Parse arguments if it's a string
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except json.JSONDecodeError:
                            pass

                    lines.append(f"- **{fn_name}**")
                    if isinstance(fn_args, dict) and fn_args:
                        lines.append(f"  ```json\n  {json.dumps(fn_args, indent=2)}\n  ```")
                    lines.append("")

        elif role == "TOOL":
            tool_call_id = msg.get("tool_call_id", "unknown")
            lines.append(f"**Tool Call ID:** `{tool_call_id}`\n")
            lines.append(f"**Output:**\n\n{content}\n")

        elif role == "SYSTEM":
            lines.append(f"```\n{content}\n```\n")

        lines.append("")

    return "\n".join(lines)


def _format_as_text(history: list[dict[str, Any]]) -> str:
    """Format history as simple readable text."""
    lines = ["=" * 80]
    lines.append("AGENT CONVERSATION HISTORY")
    lines.append("=" * 80)
    lines.append("")

    for i, msg in enumerate(history, 1):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")

        lines.append(f"\n[Message {i}] {role}")
        lines.append("-" * 40)

        if role == "USER":
            lines.append(content)

        elif role == "ASSISTANT":
            if content:
                lines.append(f"Response:\n{content}")

            if "tool_calls" in msg:
                lines.append("\nTool Calls:")
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args = fn.get("arguments", "{}")

                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except json.JSONDecodeError:
                            pass

                    lines.append(f"  - {fn_name}")
                    if isinstance(fn_args, dict) and fn_args:
                        # JSON tool arguments are expected to be a mapping of string keys to values.
                        args_dict = cast(dict[str, Any], fn_args)
                        for key, value in args_dict.items():
                            lines.append(f"      {key}: {value}")

        elif role == "TOOL":
            tool_call_id = msg.get("tool_call_id", "unknown")
            lines.append(f"Tool Call ID: {tool_call_id}")
            lines.append(f"Output:\n{content}")

        elif role == "SYSTEM":
            lines.append(f"[System Message]\n{content}")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


def save_agent_context(
    history: list[dict[str, Any]],
    filepath: str | Path,
    format: str = "json",
    *,
    include_system: bool = True,
) -> None:
    """
    Save agent context to a file.

    Args:
        history: The agent conversation history
        filepath: Path where to save the context
        format: Output format ("json", "pretty_json", "markdown", "text")
        include_system: Whether to include system messages in the output
    """
    content = dump_agent_context(history, format, include_system=include_system)

    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✓ Agent context saved to {filepath}")


def get_context_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Get a summary of the agent context.

    Returns:
        Dictionary with conversation statistics and metadata
    """
    user_messages = [m for m in history if m.get("role") == "user"]
    assistant_messages = [m for m in history if m.get("role") == "assistant"]
    tool_messages = [m for m in history if m.get("role") == "tool"]

    total_tool_calls = sum(len(m.get("tool_calls", [])) for m in assistant_messages)

    tools_used: set[str] = set()
    for m in assistant_messages:
        for tc in m.get("tool_calls", []):
            fn_name = tc.get("function", {}).get("name")
            if isinstance(fn_name, str) and fn_name:
                tools_used.add(fn_name)

    return {
        "timestamp": datetime.now().isoformat(),
        "total_messages": len(history),
        "user_messages": len(user_messages),
        "assistant_messages": len(assistant_messages),
        "tool_messages": len(tool_messages),
        "total_tool_calls": total_tool_calls,
        "unique_tools_used": sorted(tools_used),
        "total_tokens_estimate": _estimate_tokens(history),
    }


def _estimate_tokens(history: list[dict[str, Any]]) -> int:
    """Rough estimate of token count (4 chars ≈ 1 token)."""
    total_chars = sum(len(str(m.get("content", ""))) for m in history)
    return max(1, total_chars // 4)
