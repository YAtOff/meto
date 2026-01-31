"""Shell execution utilities.

Shared utilities for picking shell runners and executing shell commands.
Used by both tool execution and hooks system.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from meto.conf import settings


def pick_shell_runner() -> list[str] | None:
    """Pick an available shell runner.

    We prefer bash if present (Git Bash / WSL), otherwise PowerShell.
    Returns a base argv list to which the actual command string should be appended.
    """

    bash = shutil.which("bash")
    if bash:
        return [bash, "-lc"]

    pwsh = shutil.which("pwsh")
    if pwsh:
        return [pwsh, "-NoProfile", "-Command"]

    powershell = shutil.which("powershell")
    if powershell:
        return [powershell, "-NoProfile", "-Command"]

    return None


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated to {limit} chars)"


def format_size(size: float) -> str:
    """Format file size in human-readable format."""

    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def run_shell(command: str) -> str:
    """Execute a shell command and return combined stdout/stderr."""

    if not command.strip():
        return "(empty command)"

    runner = pick_shell_runner()
    try:
        if runner is None:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.TOOL_TIMEOUT_SECONDS,
                cwd=os.getcwd(),
            )
        else:
            completed = subprocess.run(
                [*runner, command],
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.TOOL_TIMEOUT_SECONDS,
                cwd=os.getcwd(),
            )
    except subprocess.TimeoutExpired:
        return f"(timeout after {settings.TOOL_TIMEOUT_SECONDS}s)"
    except OSError as ex:
        return f"(shell execution error: {ex})"

    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip()
    if not output:
        output = "(empty)"
    return truncate(output, settings.MAX_TOOL_OUTPUT_CHARS)
