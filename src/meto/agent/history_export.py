"""
Agent context dumping and serialization utilities for the agent loop.
Provides methods to extract, format, and save conversation history.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from rich.console import Console

from meto.conf import settings


def dump_agent_context(
    history: list[dict[str, Any]],
    output_format: str = "json",
    *,
    include_system: bool = True,
    format: str | None = None,
) -> str:
    """
    Dump agent context (conversation history) in a specified format.

    Args:
        history: The agent conversation history list
        output_format: Output format - "json", "pretty_json", "markdown", or "text"
        include_system: Whether to include system messages in the output
        format: Deprecated alias for output_format (kept for compatibility)

    Returns:
        Formatted string representation of the agent context
    """
    history_to_dump = history
    if not include_system:
        history_to_dump = [msg for msg in history if msg.get("role") != "system"]

    if format is not None:
        # Backwards-compatible alias.
        if output_format != "json" and format != output_format:
            raise ValueError("Provide only one of 'output_format' or deprecated 'format'.")
        output_format = format

    if output_format == "json":
        return json.dumps(history_to_dump, indent=2)

    elif output_format == "pretty_json":
        return json.dumps(history_to_dump, indent=2, ensure_ascii=False)

    elif output_format == "markdown":
        return _format_as_markdown(history_to_dump)

    elif output_format == "text":
        return _format_as_text(history_to_dump)

    else:
        raise ValueError(f"Unknown format: {output_format}")


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
    output_format: str = "json",
    *,
    include_system: bool = True,
    format: str | None = None,
) -> None:
    """
    Save agent context to a file.

    Args:
        history: The agent conversation history
        filepath: Path where to save the context
        output_format: Output format ("json", "pretty_json", "markdown", "text")
        include_system: Whether to include system messages in the output
        format: Deprecated alias for output_format (kept for compatibility)
    """
    content = dump_agent_context(
        history,
        output_format,
        include_system=include_system,
        format=format,
    )

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
    system_messages = [m for m in history if m.get("role") == "system"]

    total_tool_calls = sum(len(m.get("tool_calls", [])) for m in assistant_messages)

    tools_used: set[str] = set()
    for m in assistant_messages:
        for tc in m.get("tool_calls", []):
            fn_name = tc.get("function", {}).get("name")
            if isinstance(fn_name, str) and fn_name:
                tools_used.add(fn_name)

    # Sum actual prompt_tokens from assistant messages
    total_prompt_tokens = sum(m.get("prompt_tokens", 0) for m in assistant_messages)
    total_completion_tokens = sum(m.get("completion_tokens", 0) for m in assistant_messages)
    total_tokens = total_prompt_tokens + total_completion_tokens

    # Fall back to estimate if no actual tokens tracked
    tokens_estimate = _estimate_tokens(history)
    using_actual = total_prompt_tokens > 0

    # Calculate context window %
    model = settings.DEFAULT_MODEL
    window = settings.MODEL_CONTEXT_WINDOWS.get(model, 128000)
    base_tokens = total_prompt_tokens if using_actual else tokens_estimate
    context_percent = (base_tokens / window) * 100

    return {
        "timestamp": datetime.now().isoformat(),
        "total_messages": len(history),
        "user_messages": len(user_messages),
        "assistant_messages": len(assistant_messages),
        "tool_messages": len(tool_messages),
        "system_messages": len(system_messages),
        "total_tool_calls": total_tool_calls,
        "unique_tools_used": sorted(tools_used),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens if using_actual else tokens_estimate,
        "total_tokens_estimate": tokens_estimate,
        "using_actual_tokens": using_actual,
        "context_window_percent": context_percent,
        "context_window_size": window,
        "model": model,
        "project_instructions": _get_agents_md_metadata(),
    }


def _get_agents_md_metadata() -> dict[str, Any]:
    """Return metadata about AGENTS.md in the current working directory.

    This is intended for summaries/debugging only and MUST NOT include the file
    contents.
    """

    agents_path = Path.cwd() / "AGENTS.md"

    try:
        stat = agents_path.stat()
    except FileNotFoundError:
        return {
            "status": "missing",
            "path": str(agents_path),
        }
    except OSError as e:
        return {
            "status": "unreadable",
            "path": str(agents_path),
            "error": str(e),
        }

    # Compute lines + sha256 prefix without returning the file body.
    try:
        raw = agents_path.read_bytes()
        lines = raw.count(b"\n") + (1 if raw else 0)
        sha256 = hashlib.sha256(raw).hexdigest()[:12]
    except OSError as e:
        return {
            "status": "unreadable",
            "path": str(agents_path),
            "bytes": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "error": str(e),
        }

    return {
        "status": "present",
        "path": str(agents_path),
        "bytes": stat.st_size,
        "lines": lines,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "sha256": sha256,
    }


def _estimate_tokens(history: list[dict[str, Any]]) -> int:
    """Rough estimate of token count (4 chars ≈ 1 token)."""
    total_chars = sum(len(str(m.get("content", ""))) for m in history)
    return max(1, total_chars // 4)


def _format_size(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    size = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_context_summary(history: list[dict[str, Any]]) -> None:
    """Format and print a human-readable, multi-line context summary.

    Intended for interactive surfaces (e.g., the REPL `/context` command).
    The summary always reflects the full history as provided (including system
    messages, if present). Uses rich.Console for colorful output.
    """
    console = Console()
    summary = get_context_summary(history)

    # Header
    console.print()
    console.print("[bold cyan]Context summary[/]", justify="center")
    console.print(f"[dim]{'-' * 80}[/]", justify="center")

    # Timestamp & basic info
    console.print()
    console.print(f"[dim]Timestamp:[/] {summary.get('timestamp', '')}")
    console.print(f"[dim]Total messages:[/] [cyan]{summary.get('total_messages', 0)}[/cyan]")

    # Message breakdown by role
    console.print()
    console.print("[blue]By role:[/]")
    console.print(f"  [dim]system:[/]      [blue]{summary.get('system_messages', 0)}[/blue]")
    console.print(f"  [dim]user:[/]        [blue]{summary.get('user_messages', 0)}[/blue]")
    console.print(f"  [dim]assistant:[/]   [blue]{summary.get('assistant_messages', 0)}[/blue]")
    console.print(f"  [dim]tool:[/]        [blue]{summary.get('tool_messages', 0)}[/blue]")

    # Tools section
    console.print()
    console.print("[green]Tools:[/]")
    console.print(
        f"  [dim]Tool calls:[/]       [green]{summary.get('total_tool_calls', 0)}[/green]"
    )

    tools_raw = summary.get("unique_tools_used")
    tools_list: list[str] = []
    if isinstance(tools_raw, list):
        for item in cast(list[object], tools_raw):
            if isinstance(item, str):
                tools_list.append(item)
    tools_str = ", ".join(tools_list) if tools_list else "(none)"
    console.print(f"  [dim]Unique tools used:[/] [green]{tools_str}[/green]")

    # Token usage
    console.print()
    console.print("[yellow]Token usage:[/]")
    if summary.get("using_actual_tokens"):
        console.print(
            f"  [dim]Prompt:[/]     [yellow]{summary.get('total_prompt_tokens', 0)}[/yellow]"
        )
        console.print(
            f"  [dim]Completion:[/] [yellow]{summary.get('total_completion_tokens', 0)}[/yellow]"
        )
        console.print(f"  [dim]Total:[/]      [yellow]{summary.get('total_tokens', 0)}[/yellow]")
    else:
        console.print(
            f"  [dim]Estimate:[/] [yellow]{summary.get('total_tokens_estimate', 0)}[/yellow]"
        )

    # Context window
    console.print()
    console.print("[magenta]Context window:[/]")
    console.print(
        f"  [dim]Usage:[/] [magenta]{summary.get('context_window_percent', 0):.1f}%[/magenta] "
        f"[dim]of[/] [magenta]{summary.get('context_window_size', 0):,}[/magenta] "
        f"[dim]({summary.get('model', '')})[/]"
    )

    # Project instructions (simplified - no mtime, no sha256)
    project_instructions_raw = summary.get("project_instructions")
    if isinstance(project_instructions_raw, dict):
        console.print()
        console.print("[bold cyan]Project instructions (AGENTS.md):[/]")
        project_instructions = cast(dict[str, Any], project_instructions_raw)

        status = project_instructions.get("status", "unknown")
        path = project_instructions.get("path", "")
        status_str = status if isinstance(status, str) else str(status)
        path_str = path if isinstance(path, str) else str(path)
        console.print(f"  [dim]Status:[/] [cyan]{status_str}[/cyan]")
        console.print(f"  [dim]Path:[/]   {path_str}")

        # Size in human-readable format
        bytes_val = project_instructions.get("bytes")
        if bytes_val is not None:
            size_str = _format_size(int(bytes_val))
            console.print(f"  [dim]Size:[/]   {size_str}")

        # Line count
        if "lines" in project_instructions:
            console.print(f"  [dim]Lines:[/]  {project_instructions.get('lines')}")

        # Error message if unreadable
        if "error" in project_instructions:
            console.print(f"  [dim]Error:[/]  {project_instructions.get('error')}")

    # Footer
    console.print(f"[dim]{'-' * 80}[/]", justify="center")
    console.print()
