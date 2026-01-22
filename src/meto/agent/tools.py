import os
import shutil
import subprocess
from typing import Any

from meto.conf import settings


def _pick_shell_runner() -> list[str] | None:
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


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated to {limit} chars)"


def _run_shell(command: str) -> str:
    if not command.strip():
        return "(empty command)"

    runner = _pick_shell_runner()
    try:
        if runner is None:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=settings.TOOL_TIMEOUT_SECONDS,
                cwd=os.getcwd(),
            )
        else:
            completed = subprocess.run(
                [*runner, command],
                shell=False,
                capture_output=True,
                text=True,
                timeout=settings.TOOL_TIMEOUT_SECONDS,
                cwd=os.getcwd(),
            )
    except subprocess.TimeoutExpired:
        return f"(timeout after {settings.TOOL_TIMEOUT_SECONDS}s)"
    except Exception as ex:  # noqa: BLE001
        return f"(shell execution error: {ex})"

    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip()
    if not output:
        output = "(empty)"
    return _truncate(output, settings.MAX_TOOL_OUTPUT_CHARS)


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": (
                "Execute a shell command and return its output. "
                "Use it to inspect files, edit files, run tests, etc. "
                "For complex subtasks, spawn a subagent by running: meto --one-shot"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    }
]
AVAILABLE_TOOLS = [tool["function"]["name"] for tool in TOOLS]


def run_tool(tool_name: str, parameters: dict[str, Any]) -> str:
    """Run a tool by name with given parameters."""
    tool_output = ""
    if tool_name == "shell":
        command = parameters.get("command", "")
        if settings.ECHO_COMMANDS:
            print(f"$ {command}")
        tool_output = _run_shell(command)

    if settings.ECHO_COMMANDS and tool_output:
        print(tool_output)

    return tool_output
