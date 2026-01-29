"""Tool execution implementations.

This module contains the runtime implementations for tools exposed to the model
in :mod:`meto.agent.tool_schema`.

Architectural constraint:
    This module must not import the agent loop or CLI to avoid import cycles.
"""

# pyright: reportImportCycles=false

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from prompt_toolkit import PromptSession
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.shortcuts import confirm

from meto.agent.agent import Agent
from meto.agent.permission_policy import PERMISSION_REQUIRED
from meto.agent.session import Session
from meto.agent.skill_loader import SkillLoader
from meto.agent.todo import TodoManager
from meto.conf import settings

# Tool runtime / execution.
#
# Important architectural rule:
# - This module must not import `meto.agent.loop` or `meto.cli`.


class ToolRunner(Protocol):
    """Protocol for objects that can execute a named tool call."""

    def run_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        logger: Any | None = None,
        session: Session | None = None,
    ) -> str: ...


SubagentExecutor = Callable[[str, str, str | None], str]


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


def _run_shell(command: str) -> str:
    """Execute a shell command and return combined stdout/stderr."""

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
    except Exception as ex:  # noqa: BLE001
        return f"(shell execution error: {ex})"

    output = (completed.stdout or "") + (completed.stderr or "")
    output = output.strip()
    if not output:
        output = "(empty)"
    return _truncate(output, settings.MAX_TOOL_OUTPUT_CHARS)


def _list_directory(path: str = ".", recursive: bool = False, include_hidden: bool = False) -> str:
    """List directory contents with structured output."""

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
            entries = sorted(dir_path.rglob("*"), key=lambda p: (p.parent, p.name))
        else:
            entries = sorted(dir_path.iterdir(), key=lambda p: p.name)

        for entry in entries:
            if not include_hidden and entry.name.startswith("."):
                continue

            entry_type = "dir" if entry.is_dir() else "file"
            size = 0
            if entry.is_file():
                try:
                    size = entry.stat().st_size
                except OSError:
                    pass

            size_str = _format_size(size) if entry.is_file() else ""
            try:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                mtime_str = mtime.strftime("%Y-%m-%d %H:%M")
            except OSError:
                mtime_str = "?"

            name = entry.name
            if recursive:
                rel_path = entry.relative_to(dir_path)
                name = str(rel_path)
                if entry.is_dir():
                    name = str(rel_path) + "/"

            size_col = f"    {size_str:>8}" if size_str else "           "
            lines.append(f"  {name:<30} ({entry_type:<4}){size_col}    {mtime_str}")

    except PermissionError:
        return f"Error: Permission denied accessing: {path}"
    except Exception as ex:  # noqa: BLE001
        return f"Error listing directory: {ex}"

    if len(lines) == 1:
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
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} chars to {path}"
    except PermissionError:
        return f"Error: Permission denied writing to {path}"
    except IsADirectoryError:
        return f"Error: Path is a directory, not a file: {path}"
    except Exception as ex:  # noqa: BLE001
        return f"Error writing file {path}: {ex}"


def _manage_todos(todos: TodoManager, items: list[dict[str, Any]]) -> str:
    """Update the todo list for a session."""

    try:
        result = todos.update(items)
        todos.print_rich()
        return result
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

    rg = shutil.which("rg")
    if rg:
        args: list[str] = [
            rg,
            "--line-number",
            "--no-heading",
        ]
        if case_insensitive:
            args.append("-i")

        # `--` ensures patterns beginning with '-' are not interpreted as options.
        args += ["--", pattern, str(search_path)]

        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=settings.TOOL_TIMEOUT_SECONDS,
                cwd=os.getcwd(),
            )
        except subprocess.TimeoutExpired:
            return f"(timeout after {settings.TOOL_TIMEOUT_SECONDS}s)"
        except Exception as ex:  # noqa: BLE001
            return f"(search execution error: {ex})"

        output = (completed.stdout or "") + (completed.stderr or "")
        output = output.strip() or "(empty)"
        return _truncate(output, settings.MAX_TOOL_OUTPUT_CHARS)
    else:
        runner = _pick_shell_runner()
        if runner and ("bash" in runner[0] or "sh" in runner[0]):
            flag = "-i" if case_insensitive else ""
            cmd = f'grep -R {flag} -n "{pattern}" "{path}" 2>/dev/null || true'
        elif runner and ("powershell" in runner[0] or "pwsh" in runner[0]):
            flag = "" if case_insensitive else "-CaseSensitive"
            cmd = (
                f'Select-String -Path "{path}\\*" -Pattern "{pattern}" {flag} '
                "| Select-Object -First 100"
            )
        else:
            return "Error: No suitable search tool found (need rg, grep, or PowerShell)"

    return _run_shell(cmd)


def _fetch(url: str, max_bytes: int = 100000) -> str:
    """Fetch URL via HTTP GET, return response body as text (truncated)."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return f"Error fetching {url}: unsupported URL scheme '{parsed.scheme}'"

    try:
        req = Request(url, headers={"User-Agent": "meto/0"})
        with urlopen(req, timeout=10) as resp:
            data = resp.read(max_bytes + 1)
            return _truncate(data.decode("utf-8", errors="replace"), max_bytes)
    except URLError as e:
        return f"Error fetching {url}: {e}"
    except Exception as ex:
        return f"Error fetching {url}: {ex}"


def _execute_task(
    prompt: str,
    agent_name: str,
    description: str | None = None,
    plan_mode: bool = False,
    yolo_mode: bool = False,
) -> str:
    """Execute task in isolated subagent via direct `run_agent_loop` call."""
    _ = description  # Reserved for future progress display

    from meto.agent.agent_loop import run_agent_loop  # pyright: ignore[reportImportCycles]

    try:
        agent = Agent.subagent(agent_name, plan_mode=plan_mode, yolo_mode=yolo_mode)
        # Allow subagents that have access to `run_task` to spawn further subagents.
        output = "\n".join(run_agent_loop(prompt, agent))
        return _truncate(output or "(subagent returned no output)", settings.MAX_TOOL_OUTPUT_CHARS)
    except Exception as ex:
        return f"(subagent error: {ex})"


def _ask_user_question(question: str) -> str:
    """Ask user a question using prompt_toolkit and return response."""

    session = PromptSession(editing_mode=EditingMode.EMACS)
    try:
        response = session.prompt(
            f"[bold yellow]?[/bold yellow] [bold cyan]{question}[/bold cyan]\n[dim]Your answer:[/] "
        )
        return response
    except (EOFError, KeyboardInterrupt):
        return "(user cancelled input)"
    except Exception as ex:
        return f"(error getting user input: {ex})"


def _prompt_permission(tool_name: str, detail: str) -> bool:
    """Prompt user for tool permission using prompt_toolkit."""
    try:
        return confirm(f"Run {tool_name}: {detail}? ", suffix=" (y/n) ")
    except (EOFError, KeyboardInterrupt):
        return False


def _load_skill(skill_name: str, skill_loader: SkillLoader) -> str:
    """Load skill content and return wrapped in XML tags."""
    try:
        content = skill_loader.get_skill_content(skill_name)
        # Wrap in XML for clear boundaries
        return f'<skill-loaded name="{skill_name}">\n{content}\n</skill-loaded>'
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: Failed to load skill '{skill_name}': {e}"


def run_tool(
    tool_name: str,
    parameters: dict[str, Any],
    logger: Any | None = None,
    session: Session | None = None,
    skill_loader: SkillLoader | None = None,
    yolo_mode: bool = False,
) -> str:
    """Dispatch and execute a single tool call.

    This function is the single entrypoint used by the agent loop to execute
    tools requested by the model.

    Notes:
        - Permission prompting is enforced here (unless *yolo_mode* is enabled).
        - The return value is always a human-readable string that is appended to
          the conversation history as a tool message.

    Args:
        tool_name: Name of the tool to execute.
        parameters: JSON-like tool arguments.
        logger: Optional reasoning logger for structured trace output.
        session: Session object (required for tools that mutate session state).
        skill_loader: Skill loader instance (required for load_skill).
        yolo_mode: If True, skip interactive permission prompts.
    """
    if logger:
        logger.log_tool_selection(tool_name, parameters)

    # Check permission if required and not in yolo mode
    if not yolo_mode:
        if permission_config := PERMISSION_REQUIRED.get(tool_name, None):
            if permission_config.is_required(parameters):
                detail = permission_config.prompt_detail(parameters)
                if not _prompt_permission(tool_name, detail):
                    return f"({tool_name} cancelled by user)"
        else:
            if not _prompt_permission(tool_name, "(no details available)"):
                return f"({tool_name} cancelled by user)"

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
        elif tool_name == "fetch":
            url = parameters.get("url", "")
            max_bytes = parameters.get("max_bytes", 100000)
            tool_output = _fetch(url, max_bytes)
        elif tool_name == "manage_todos":
            if session is None:
                tool_output = "Error: session required for manage_todos"
            else:
                items = parameters.get("items", [])
                tool_output = _manage_todos(session.todos, cast(list[dict[str, Any]], items))
        elif tool_name == "run_task":
            description = cast(str, parameters.get("description", ""))
            prompt = cast(str, parameters.get("prompt", ""))
            agent_name = cast(str, parameters.get("agent_name", ""))
            plan_mode = session.plan_mode if session else False
            tool_output = _execute_task(prompt, agent_name, description, plan_mode, yolo_mode)
        elif tool_name == "ask_user_question":
            question = parameters.get("question", "")
            tool_output = _ask_user_question(question)
        elif tool_name == "load_skill":
            if skill_loader is None:
                tool_output = "Error: skill_loader not available"
            else:
                skill_name = parameters.get("skill_name", "")
                tool_output = _load_skill(skill_name, skill_loader)
                if logger:
                    logger.log_skill_loaded(skill_name)

        else:
            tool_output = f"Error: Unknown tool: {tool_name}"

        if logger:
            logger.log_tool_execution(tool_name, tool_output, error=False)
    except Exception as e:
        tool_output = str(e)
        if logger:
            logger.log_tool_execution(tool_name, tool_output, error=True)

    return tool_output
