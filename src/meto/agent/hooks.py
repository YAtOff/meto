"""Hook system for lifecycle extension points.

Hooks run shell commands at specific points: pre_tool_use, post_tool_use, session_start.
Configuration via .meto/hooks.yaml.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger("hooks")

# Hook exit codes
EXIT_OK = 0
EXIT_BLOCK = 2

# Default timeout for hook execution (seconds)
DEFAULT_HOOK_TIMEOUT = 60

HookEvent = Literal["pre_tool_use", "post_tool_use", "session_start"]


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

            # Use shell runner from tool_runner
            runner = _pick_shell_runner()
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


# Convenience function for loading hooks from default location
def load_hooks_manager() -> HooksManager:
    """Load hooks from .meto/hooks.yaml in current directory."""
    hooks_path = Path.cwd() / ".meto" / "hooks.yaml"
    return HooksManager.load(hooks_path)
