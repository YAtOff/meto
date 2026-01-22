"""Agent package public API."""

from .loop import run_agent_loop

# Re-export for convenience (used by `meto.cli`).
__all__ = ["run_agent_loop"]
