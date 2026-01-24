import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from meto.agent.session import Session
from meto.conf import settings

# Utils


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


def _format_size(size: float) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# Tool implementations


def _run_shell(command: str) -> str:
    """Execute a shell command and return combined stdout/stderr.

    The command is executed via an available shell runner (bash preferred, then
    PowerShell) and is subject to the configured timeout/output truncation.
    """
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


def _write_file(path: str, content: str) -> str:
    """Write content to a file with proper error handling."""
    try:
        file_path = Path(path).expanduser().resolve()
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} chars to {path}"
    except PermissionError:
        return f"Error: Permission denied writing to {path}"
    except IsADirectoryError:
        return f"Error: Path is a directory, not a file: {path}"
    except Exception as ex:  # noqa: BLE001
        return f"Error writing file {path}: {ex}"


def _manage_tasks(session: Session, items: list[dict[str, Any]]) -> str:
    """Update the task list for a session.

    Args:
        session: The session containing the TaskManager
        items: Complete new task list (replaces existing)

    Returns:
        Rendered view of the task list
    """
    try:
        return session.tasks.update(items)
    except Exception as e:
        return f"Error: {e}"


def _run_grep_search(pattern: str, path: str = ".", case_insensitive: bool = False) -> str:
    """Search for pattern in files using ripgrep (rg) with fallback to grep/Select-String."""
    if not pattern.strip():
        return "Error: Empty search pattern"

    try:
        search_path = Path(path).expanduser().resolve()
        if not search_path.exists():
            return f"Error: Path does not exist: {path}"
    except Exception as ex:
        return f"Error accessing path '{path}': {ex}"

    # Try ripgrep first, then grep, then Select-String
    rg = shutil.which("rg")
    if rg:
        flag = "-i" if case_insensitive else ""
        cmd = f'{rg} {flag} --line-number --no-heading "{pattern}" "{path}"'
    else:
        runner = _pick_shell_runner()
        if runner and ("bash" in runner[0] or "sh" in runner[0]):
            flag = "-i" if case_insensitive else ""
            cmd = f'grep -R {flag} -n "{pattern}" "{path}" 2>/dev/null || true'
        elif runner and ("powershell" in runner[0] or "pwsh" in runner[0]):
            flag = "" if case_insensitive else "-CaseSensitive"
            cmd = f'Select-String -Path "{path}\\*" -Pattern "{pattern}" {flag} | Select-Object -First 100'
        else:
            return "Error: No suitable search tool found (need rg, grep, or PowerShell)"

    return _run_shell(cmd)


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
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates parent directories if needed. "
                "Use this for creating or modifying files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file.",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": (
                "Search for a text pattern in files within a directory. "
                "Uses ripgrep (rg) if available, otherwise grep or Select-String. "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern to search for (supports regex).",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory path to search in (defaults to current directory).",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Whether to ignore case when matching.",
                        "default": False,
                    },
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_tasks",
            "description": (
                "Update the task list. Use to plan and track progress on multi-step tasks. "
                "Mark tasks in_progress before starting, completed when done. "
                "Only ONE task can be in_progress at a time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "Complete list of tasks (replaces existing)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "Task description",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "Task status",
                                },
                                "activeForm": {
                                    "type": "string",
                                    "description": "Present tense action, e.g. 'Reading files'",
                                },
                            },
                            "required": ["content", "status", "activeForm"],
                        },
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    },
]
AVAILABLE_TOOLS = [tool["function"]["name"] for tool in TOOLS]


def run_tool(
    tool_name: str,
    parameters: dict[str, Any],
    logger: Any | None = None,
    session: Session | None = None,
) -> str:
    """Run a tool by name with given parameters."""
    if logger:
        logger.log_tool_selection(tool_name, parameters)

    tool_output = ""
    try:
        if tool_name == "shell":
            command = parameters.get("command", "")
            tool_output = _run_shell(command)
        elif tool_name == "list_dir":
            path = parameters.get("path", ".")
            recursive = parameters.get("recursive", False)
            include_hidden = parameters.get("include_hidden", False)
            tool_output = _list_directory(path, recursive, include_hidden)
        elif tool_name == "read_file":
            path = parameters.get("path", "")
            tool_output = _read_file(path)
        elif tool_name == "write_file":
            path = parameters.get("path", "")
            content = parameters.get("content", "")
            tool_output = _write_file(path, content)
        elif tool_name == "grep_search":
            pattern = parameters.get("pattern", "")
            path = parameters.get("path", ".")
            case_insensitive = parameters.get("case_insensitive", False)
            tool_output = _run_grep_search(pattern, path, case_insensitive)
        elif tool_name == "manage_tasks":
            if session is None:
                tool_output = "Error: session required for manage_tasks"
            else:
                items = parameters.get("items", [])
                tool_output = _manage_tasks(session, items)

        if logger:
            logger.log_tool_execution(tool_name, tool_output, error=False)
    except Exception as e:
        tool_output = str(e)
        if logger:
            logger.log_tool_execution(tool_name, tool_output, error=True)

    return tool_output
