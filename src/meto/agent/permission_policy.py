"""Tool permission policy.

This module defines when the interactive CLI should ask for user confirmation
before executing a tool.

The default posture is conservative for filesystem tools: if a target path is
outside known meto directories, we require permission (fail closed).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

from meto.conf import settings


class PermissionCheck(ABC):
    """Interface for deciding whether a tool call should prompt for permission."""

    @abstractmethod
    def is_required(self, args: dict[str, Any]) -> bool:
        """Return True if executing the tool with given args should require user permission."""

    @abstractmethod
    def prompt_detail(self, args: dict[str, Any]) -> str:
        """Return a short detail string shown to the user when asking for permission."""


class AlwaysRequirePermissionCheck(PermissionCheck):
    """Policy that always prompts, using one argument as the displayed detail."""

    def __init__(self, detail_arg: str) -> None:
        self.detail_arg: str = detail_arg

    @override
    def is_required(self, args: dict[str, Any]) -> bool:
        return True

    @override
    def prompt_detail(self, args: dict[str, Any]) -> str:
        return args.get(self.detail_arg, "")


class NeverRequirePermissionCheck(PermissionCheck):
    """Policy that never prompts."""

    @override
    def is_required(self, args: dict[str, Any]) -> bool:
        return False

    @override
    def prompt_detail(self, args: dict[str, Any]) -> str:
        return ""


class ExternalPathPermissionCheck(PermissionCheck):
    """Prompt when a path argument points outside known meto directories."""

    @property
    def allowed_dirs(self) -> list[Path]:
        """Directories that are considered safe to operate in without prompting."""
        # Keep this list tight: file system tools should not silently operate on
        # paths outside known meto areas.
        return [
            Path.cwd().resolve(),
            settings.PLAN_DIR.resolve(),
            settings.AGENTS_DIR.resolve(),
            settings.COMMANDS_DIR.resolve(),
            settings.SKILLS_DIR.resolve(),
        ]

    @override
    def is_required(self, args: dict[str, Any]) -> bool:
        """Return True if a given path is outside all allowed directories.

        This check is intentionally conservative: if we cannot validate the path,
        we require permission (fail closed).
        """

        path = args.get("path")
        if not path:
            return False

        try:
            target_path = Path(path).expanduser().resolve()
            for allowed_dir in self.allowed_dirs:
                try:
                    target_path.relative_to(allowed_dir)
                    return False  # Path is inside an allowed directory
                except ValueError:
                    continue
            return True  # Path is outside all allowed directories
        except Exception:
            return True  # Fail closed: require permission if we cannot validate

    @override
    def prompt_detail(self, args: dict[str, Any]) -> str:
        return args.get("path", "")


# Maps tool name -> policy for whether user permission is required before execution.
PERMISSION_REQUIRED: dict[str, PermissionCheck] = {
    "shell": AlwaysRequirePermissionCheck("command"),
    "list_dir": NeverRequirePermissionCheck(),
    "read_file": ExternalPathPermissionCheck(),
    "write_file": ExternalPathPermissionCheck(),
    "grep_search": ExternalPathPermissionCheck(),
    "fetch": AlwaysRequirePermissionCheck("url"),
    "manage_todos": NeverRequirePermissionCheck(),
    "run_task": NeverRequirePermissionCheck(),
    "ask_user_question": NeverRequirePermissionCheck(),
    "load_skill": NeverRequirePermissionCheck(),
}
