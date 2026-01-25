"""Subagent execution module.

Handles spawning isolated subagents via run_agent_loop.
Separate module to avoid circular import between tools.py and loop.py.

Cycle: loop -> registry -> tools -> subagent -> loop
Broken by using runtime-only import of run_agent_loop.
"""

from meto.conf import settings


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated to {limit} chars)"


def execute_task(prompt: str, agent_name: str, description: str | None = None) -> str:
    """Execute task in isolated subagent via direct `run_agent_loop` call."""
    _ = description  # Reserved for future progress display

    # Import at runtime to avoid static import cycles:
    # loop -> agent_registry -> tools -> subagent -> loop
    from meto.agent.agent import Agent
    from meto.agent.loop import run_agent_loop

    try:
        agent = Agent.subagent(agent_name)
        output = "\n".join(run_agent_loop(prompt, agent))
        return _truncate(output or "(subagent returned no output)", settings.MAX_TOOL_OUTPUT_CHARS)
    except Exception as ex:
        return f"(subagent error: {ex})"
