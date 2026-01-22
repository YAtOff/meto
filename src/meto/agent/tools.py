import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
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


def _format_size(size: float) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _list_directory(path: str = ".", recursive: bool = False, include_hidden: bool = False) -> str:
    """List directory contents with structured output.

    Args:
        path: Directory path to list (defaults to current working directory)
        recursive: Whether to list subdirectories recursively
        include_hidden: Whether to include hidden files/directories

    Returns:
        Formatted string output with entry metadata
    """
    try:
        dir_path = Path(path).expanduser().resolve()
        if not dir_path.exists():
            return f"Error: Path does not exist: {path}"
        if not dir_path.is_dir():
            return f"Error: Not a directory: {path}"
    except Exception as ex:
        return f"Error accessing path '{path}': {ex}"

    lines: list[str] = []
    lines.append(f"{dir_path}:")

    try:
        if recursive:
            # Use Path.rglob() for recursive listing
            entries = sorted(dir_path.rglob("*"), key=lambda p: (p.parent, p.name))
        else:
            entries = sorted(dir_path.iterdir(), key=lambda p: p.name)

        for entry in entries:
            # Skip hidden files if not requested
            if not include_hidden and entry.name.startswith("."):
                continue

            entry_type = "dir" if entry.is_dir() else "file"
            size = 0
            if entry.is_file():
                try:
                    size = entry.stat().st_size
                except OSError:
                    pass

            # Format size and last modified time
            size_str = _format_size(size) if entry.is_file() else ""
            try:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
            except OSError:
                mtime_str = "?"

            # Format entry line
            name = entry.name
            if recursive:
                # Show relative path from base directory
                rel_path = entry.relative_to(dir_path)
                name = str(rel_path)
                if entry.is_dir():
                    name = str(rel_path) + "/"

            # Format: name padded to 30 chars, type, size (for files), date
            size_col = f"    {size_str:>8}" if size_str else "           "
            lines.append(f"  {name:<30} ({entry_type:<4}){size_col}    {mtime_str}")

    except PermissionError:
        return f"Error: Permission denied accessing: {path}"
    except Exception as ex:  # noqa: BLE001
        return f"Error listing directory: {ex}"

    if len(lines) == 1:  # Only the header line
        lines.append("  (empty directory)")

    return "\n".join(lines)


def _read_file(path: str) -> str:
    """Read file contents with proper error handling."""
    try:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            return f"Error: File does not exist: {path}"
        if not file_path.is_file():
            return f"Error: Not a file: {path}"

        content = file_path.read_text(encoding="utf-8")
        return _truncate(content, settings.MAX_TOOL_OUTPUT_CHARS)
    except UnicodeDecodeError:
        return f"Error: Cannot decode file {path} as UTF-8 text"
    except PermissionError:
        return f"Error: Permission denied reading {path}"
    except Exception as ex:  # noqa: BLE001
        return f"Error reading file {path}: {ex}"


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
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": (
                "List directory contents with structured output showing names, types, sizes, and timestamps. "
                "Use this for browsing the filesystem structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (defaults to current working directory if empty).",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list subdirectories recursively.",
                        "default": False,
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files and directories (those starting with a dot).",
                        "default": False,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file and return them as text. "
                "Use this for reading configuration files, source code, or any text file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
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
    elif tool_name == "list_dir":
        path = parameters.get("path", ".")
        recursive = parameters.get("recursive", False)
        include_hidden = parameters.get("include_hidden", False)
        if settings.ECHO_COMMANDS:
            print(f"list_dir: {path} (recursive={recursive}, include_hidden={include_hidden})")
        tool_output = _list_directory(path, recursive, include_hidden)
    elif tool_name == "read_file":
        path = parameters.get("path", "")
        if settings.ECHO_COMMANDS:
            print(f"read_file: {path}")
        tool_output = _read_file(path)

    if settings.ECHO_COMMANDS and tool_output:
        print(tool_output)

    return tool_output
