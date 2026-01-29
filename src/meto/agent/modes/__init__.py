"""Session modes.

A session mode is an optional state machine attached to a `Session` that can
customize prompt/UI behavior and manage mode-specific artifacts.
"""

from __future__ import annotations

from meto.agent.modes.base import ModeExitResult, SessionMode
from meto.agent.modes.plan import PlanMode

__all__ = [
    "ModeExitResult",
    "SessionMode",
    "PlanMode",
]
