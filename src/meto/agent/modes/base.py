"""Base types for session modes.

A *session mode* is an optional state machine attached to a `Session`.
Modes can:
- customize the interactive prompt prefix
- augment the system prompt
- manage mode-specific artifacts (e.g., a plan file)

The mode interface is intentionally small so additional modes can be added
without broad refactors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ModeExitResult:
    """Result produced when exiting a mode.

    Attributes:
        artifact_path: Optional path produced/managed by the mode.
        artifact_content: Optional text content (e.g., read from artifact_path).
        followup_system_message: Optional system message to seed the next session
            history after exiting the mode.
    """

    artifact_path: Path | None
    artifact_content: str | None
    followup_system_message: str | None


class SessionMode(ABC):
    """Interface for session modes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short human-friendly name for the mode (e.g., "plan")."""

    @property
    def agent_name(self) -> str | None:
        """Optional agent name to use instead of main agent (e.g., "planner")."""
        return None

    @abstractmethod
    def prompt_prefix(self, default_prompt: str) -> str:
        """Return the prompt string to show in interactive mode."""

    @abstractmethod
    def system_prompt_fragment(self) -> str | None:
        """Return additional system prompt text to append (if any)."""

    @abstractmethod
    def enter(self, session: object) -> None:
        """Enter the mode, initializing any mode-specific state."""

    @abstractmethod
    def exit(self, session: object) -> ModeExitResult:
        """Exit the mode and return any relevant artifacts/results."""
