"""Hook system for lifecycle extension points.

Hooks run shell commands at specific points: pre_tool_use, post_tool_use, session_start.
Configuration via .meto/hooks.yaml.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from meto.agent.shell import pick_shell_runner
from meto.conf import settings

logger = logging.getLogger("hooks")

# Hook exit codes
EXIT_OK = 0
EXIT_BLOCK = 2

# Default timeout for hook execution (seconds)
DEFAULT_HOOK_TIMEOUT = 60

HookEvent = Literal["pre_tool_use", "post_tool_use", "session_start"]


class HookConfig(BaseModel):
    """Configuration for a single hook."""

    name: str
    event: HookEvent
    tools: list[str] = Field(default_factory=list)  # Empty = all tools
    command: str
    timeout: int = DEFAULT_HOOK_TIMEOUT

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Hook name must be alphanumeric, dash, or underscore")
        return v


class HooksConfig(BaseModel):
    """Root configuration containing all hooks."""

    hooks: list[HookConfig] = Field(default_factory=list)

    @classmethod
    def load_from_yaml(cls, path: Path) -> HooksConfig:
        """Load hooks config from YAML file."""
        if not path.exists():
            return cls()
        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
            return cls(**data)
        except Exception as e:
            logger.warning(f"Failed to load hooks config from {path}: {e}")
            return cls()


@dataclass
class HookResult:
    """Result from hook execution."""

    hook_name: str
    success: bool
    exit_code: int
    blocked: bool = False  # True if PreToolUse returned EXIT_BLOCK
    error: str | None = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class HookInput:
    """Input data passed to hook via HOOK_INPUT_JSON env var."""

    event: str
    session_id: str
    tool: str | None = None
    tool_call_id: str | None = None
    params: dict[str, Any] | None = None
    result: str | None = None

    def to_json(self) -> str:
        data: dict[str, Any] = {"event": self.event, "session_id": self.session_id}
        if self.tool is not None:
            data["tool"] = self.tool
        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        return json.dumps(data)


def is_python_script(command: str) -> bool:
    """Check if a hook command is a Python script.

    Returns True if the first token ends with .py (case-insensitive),
    but not if an interpreter is already specified (e.g., 'python script.py').
    """
    if not command or not command.strip():
        return False

    first_token = command.strip().split()[0].lower()
    # Check if it's a .py file but not an interpreter command
    return first_token.endswith(".py") and first_token not in {
        "python",
        "python3",
        "pypy",
        "python.exe",
        "python3.exe",
    }


def run_python_script(
    command: str,
    env: dict[str, str],
    timeout: int,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Execute a Python script using sys.executable.

    This ensures the script runs with the same Python interpreter as meto.
    """
    if not sys.executable:
        raise RuntimeError("sys.executable not available - cannot run Python script")

    # Parse command into script path and arguments
    # Use a simple parser that handles quoted arguments properly
    # Don't use shlex.split() as it mishandles Windows paths with backslashes
    parts = []
    current = []
    in_quote = False
    quote_char = None

    i = 0
    while i < len(command):
        c = command[i]

        if in_quote:
            if c == quote_char:
                in_quote = False
                quote_char = None
            else:
                current.append(c)
        elif c in ('"', "'"):
            in_quote = True
            quote_char = c
        elif c.isspace():
            if current:
                parts.append("".join(current))
                current = []
        else:
            current.append(c)

        i += 1

    if current:
        parts.append("".join(current))

    if not parts:
        raise ValueError("Empty command")

    script_path = parts[0]
    args = parts[1:]

    argv = [sys.executable, script_path] + args

    return subprocess.run(
        argv,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


@dataclass
class HooksManager:
    """Manages hook loading and execution."""

    config: HooksConfig
    _hooks_by_event: dict[HookEvent, list[HookConfig]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Index hooks by event for fast lookup
        for hook in self.config.hooks:
            if hook.event not in self._hooks_by_event:
                self._hooks_by_event[hook.event] = []
            self._hooks_by_event[hook.event].append(hook)

    @classmethod
    def load(cls, hooks_path: Path) -> HooksManager:
        """Load hooks from YAML file."""
        config = HooksConfig.load_from_yaml(hooks_path)
        return cls(config=config)

    def get_hooks_for_event(
        self, event: HookEvent, tool_name: str | None = None
    ) -> list[HookConfig]:
        """Get hooks matching event and optionally tool name."""
        hooks = self._hooks_by_event.get(event, [])
        if tool_name is None:
            return hooks
        # Filter by tool name if specified
        return [h for h in hooks if not h.tools or tool_name in h.tools]

    def run_hooks(
        self,
        event: HookEvent,
        session_id: str,
        tool: str | None = None,
        tool_call_id: str | None = None,
        params: dict[str, Any] | None = None,
        result: str | None = None,
    ) -> list[HookResult]:
        """Run all matching hooks for an event.

        Returns list of HookResult. For pre_tool_use, check if any result.blocked is True.
        """
        hooks = self.get_hooks_for_event(event, tool)
        if not hooks:
            return []

        hook_input = HookInput(
            event=event,
            session_id=session_id,
            tool=tool,
            tool_call_id=tool_call_id,
            params=params,
            result=result,
        )

        results: list[HookResult] = []
        for hook in hooks:
            result_obj = self._run_hook(hook, hook_input)
            results.append(result_obj)
            # For pre_tool_use, stop on first block
            if event == "pre_tool_use" and result_obj.blocked:
                break
        return results

    def _run_hook(self, hook: HookConfig, hook_input: HookInput) -> HookResult:
        """Execute a single hook command."""
        try:
            env = os.environ.copy()
            env["HOOK_INPUT_JSON"] = hook_input.to_json()

            # Try to run Python scripts directly with sys.executable
            if is_python_script(hook.command):
                try:
                    proc = run_python_script(
                        command=hook.command,
                        env=env,
                        timeout=hook.timeout,
                        cwd=Path.cwd(),
                    )
                    blocked = hook_input.event == "pre_tool_use" and proc.returncode == EXIT_BLOCK
                    success = proc.returncode == EXIT_OK

                    return HookResult(
                        hook_name=hook.name,
                        success=success,
                        exit_code=proc.returncode,
                        blocked=blocked,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                    )
                except Exception as e:
                    # Log warning and fall back to shell execution
                    logger.warning(
                        f"Python execution failed for hook '{hook.name}': {e}. "
                        f"Falling back to shell execution."
                    )

            # Use shell runner from tool_runner
            runner = pick_shell_runner()
            if runner is None:
                return HookResult(
                    hook_name=hook.name,
                    success=False,
                    exit_code=-1,
                    blocked=hook_input.event == "pre_tool_use",
                    error="No shell runner available",
                )

            proc = subprocess.run(
                [*runner, hook.command],
                env=env,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                cwd=Path.cwd(),
            )

            blocked = hook_input.event == "pre_tool_use" and proc.returncode == EXIT_BLOCK
            success = proc.returncode == EXIT_OK

            return HookResult(
                hook_name=hook.name,
                success=success,
                exit_code=proc.returncode,
                blocked=blocked,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )

        except subprocess.TimeoutExpired:
            logger.warning(f"Hook '{hook.name}' timed out after {hook.timeout}s")
            return HookResult(
                hook_name=hook.name,
                success=False,
                exit_code=-1,
                blocked=hook_input.event == "pre_tool_use",  # Block on timeout for pre_tool_use
                error=f"Timeout after {hook.timeout}s",
            )
        except Exception as e:
            logger.warning(f"Hook '{hook.name}' failed: {e}")
            return HookResult(
                hook_name=hook.name,
                success=False,
                exit_code=-1,
                blocked=hook_input.event == "pre_tool_use",  # Block on failure for pre_tool_use
                error=str(e),
            )


@lru_cache(maxsize=1)
def get_hooks_manager() -> HooksManager:
    """Return the process-global hooks manager.

    Hooks are configured via :data:`meto.conf.settings.HOOKS_FILE`.
    The manager is loaded lazily and cached for the lifetime of the process.
    """

    return HooksManager.load(settings.HOOKS_FILE)


def reset_hooks_manager_cache() -> None:
    """Clear the cached hooks manager.

    Primarily used in tests or when the hooks file is modified during runtime.
    """

    get_hooks_manager.cache_clear()
