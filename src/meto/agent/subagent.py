"""Subagent execution.

This module runs subagents via a direct in-process call to `run_agent_loop`.

Architectural note:
- This module may import the loop.
- The tool runtime must NOT import this module; instead it receives
    `execute_task` via dependency injection.
"""

from __future__ import annotations

from meto.agent.agent import Agent
from meto.agent.loop import run_agent_loop
from meto.agent.tool_runner import DefaultToolRunner
from meto.conf import settings


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (truncated to {limit} chars)"


def execute_task(prompt: str, agent_name: str, description: str | None = None) -> str:
    """Execute task in isolated subagent via direct `run_agent_loop` call."""
    _ = description  # Reserved for future progress display

    try:
        agent = Agent.subagent(agent_name)
        # Allow subagents that have access to `run_task` to spawn further subagents.
        tool_runner = DefaultToolRunner(subagent_executor=execute_task)
        output = "\n".join(run_agent_loop(prompt, agent, tool_runner))
        return _truncate(output or "(subagent returned no output)", settings.MAX_TOOL_OUTPUT_CHARS)
    except Exception as ex:
        return f"(subagent error: {ex})"
