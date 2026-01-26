"""Agent type registry for subagent support.

Different agent types have different tool permissions and system prompts.
This enables context-isolated subtasks with appropriate capabilities.
"""

from __future__ import annotations

from typing import Any, TypedDict

from meto.agent.exceptions import ToolNotFoundError
from meto.agent.tool_schema import TOOLS


class AgentConfig(TypedDict):
    description: str
    tools: list[str] | str
    prompt: str


AGENTS: dict[str, AgentConfig] = {
    "explore": {
        "description": "Read-only exploration - search, find files, analyze code",
        "tools": ["shell", "list_dir", "read_file", "grep_search", "fetch"],
        "prompt": "You are an exploration agent. Search and analyze, but never modify files. Return concise summary.",
    },
    "code": {
        "description": "Full agent for implementing features and fixing bugs",
        "tools": "*",  # All tools including run_task
        "prompt": "You are a coding agent. Implement requested changes efficiently.",
    },
    "plan": {
        "description": "Planning agent - design without modifying",
        "tools": ["shell", "list_dir", "read_file", "grep_search", "fetch"],
        "prompt": "You are a planning agent. Analyze codebase, output numbered implementation plan. Do NOT make changes.",
    },
}


def get_tools_for_agent(requested_tools: list[str] | str) -> list[dict[str, Any]]:
    if requested_tools == "*":
        return TOOLS
    else:
        tools_by_name = {tool["function"]["name"]: tool for tool in TOOLS}
        unknown = [name for name in requested_tools if name not in tools_by_name]
        if unknown:
            known = ", ".join(sorted(tools_by_name))
            missing = ", ".join(unknown)
            raise ToolNotFoundError(f"Unknown tool(s): {missing}. Known tools: {known}")
        return [tools_by_name[name] for name in requested_tools]
