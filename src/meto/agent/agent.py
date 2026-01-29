"""Agent object used by the CLI and agent loop.

An Agent bundles:
- a session (conversation history + todos)
- an allowed tool set (OpenAI tool schemas)
- optional lifecycle hooks
- a max turn budget for the tool-calling loop

Main agents are stateful (shared session); subagents are isolated (fresh session).
"""

from __future__ import annotations

from typing import Any

from meto.agent.agent_registry import get_all_agents, get_tools_for_agent
from meto.agent.exceptions import SubagentError
from meto.agent.session import NullSessionLogger, Session
from meto.agent.skill_loader import get_skill_loader
from meto.agent.tool_schema import populate_skill_descriptions
from meto.conf import settings


class Agent:
    """Runtime configuration for one agent execution context.

    This is intentionally a lightweight container. Most behavior lives in:
    - :func:`meto.agent.agent_loop.run_agent_loop` (LLM/tool loop)
    - :func:`meto.agent.tool_runner.run_tool` (tool execution)
    - :mod:`meto.agent.agent_registry` (agent definitions + tool selection)
    """

    name: str
    prompt: str
    session: Session
    tools: list[dict[str, Any]]
    max_turns: int
    run_hooks: bool
    yolo_mode: bool

    @classmethod
    def main(cls, session: Session, yolo_mode: bool = False) -> Agent:
        """Create the main (interactive) agent.

        The main agent:
        - reuses the provided Session across prompts
        - has access to all tools
        - runs hooks (configured globally via the hooks file)
        """
        return cls(
            name="main",
            prompt="",
            session=session,
            allowed_tools="*",
            max_turns=settings.MAIN_AGENT_MAX_TURNS,
            run_hooks=True,
            yolo_mode=yolo_mode,
        )

    @classmethod
    def subagent(cls, name: str, yolo_mode: bool = False) -> Agent:
        """Create an isolated subagent.

        Subagents run with a fresh session (no shared history) and a stricter
        tool allowlist defined by the agent registry. They never run hooks.
        """
        all_agents = get_all_agents()
        agent_config = all_agents.get(name)

        if agent_config:
            prompt = agent_config["prompt"]
            allowed_tools = agent_config.get("tools", [])
            return cls(
                name=name,
                prompt=prompt,
                session=Session(session_logger_cls=NullSessionLogger),
                allowed_tools=allowed_tools,
                max_turns=settings.SUBAGENT_MAX_TURNS,
                run_hooks=False,
                yolo_mode=yolo_mode,
            )

        available = ", ".join(sorted(all_agents.keys()))
        raise SubagentError(f"Unknown agent type '{name}'. Available agents: {available}")

    @classmethod
    def fork(cls, allowed_tools: list[str] | str, yolo_mode: bool = False) -> Agent:
        """Create a generic subagent with an explicit tool allowlist.

        Used for custom commands that want to restrict tool access
        without creating a full agent configuration.
        """
        return cls(
            name="fork",
            prompt="",
            session=Session(session_logger_cls=NullSessionLogger),
            allowed_tools=allowed_tools,
            max_turns=settings.SUBAGENT_MAX_TURNS,
            run_hooks=False,
            yolo_mode=yolo_mode,
        )

    def __init__(
        self,
        name: str,
        prompt: str,
        session: Session,
        allowed_tools: list[str] | str,
        max_turns: int,
        run_hooks: bool = False,
        yolo_mode: bool = False,
    ) -> None:
        """Create an Agent.

        Args:
            name: Agent name (e.g. "main", "explore", "plan").
            prompt: Optional extra per-agent system prompt content.
            session: Conversation session (history + todos).
            allowed_tools: "*" or a list of tool names.
            max_turns: Max model/tool iterations per user prompt.
            run_hooks: If True, run lifecycle hooks for this agent.
            yolo_mode: If True, skip tool permission prompts.
        """
        self.name = name
        self.prompt = prompt
        self.session = session
        self.max_turns = max_turns
        self.run_hooks = run_hooks
        self.yolo_mode = yolo_mode

        base_tools = get_tools_for_agent(allowed_tools)

        # Populate skill descriptions for the load_skill tool (if present)
        if any(tool["function"]["name"] == "load_skill" for tool in base_tools):
            skills = get_skill_loader().get_skill_descriptions()
            self.tools = populate_skill_descriptions(base_tools, skills)
        else:
            self.tools = base_tools

    @property
    def tool_names(self) -> list[str]:
        """Return the list of tool names exposed to the model."""
        return [tool["function"]["name"] for tool in self.tools]

    def has_tool(self, tool_name: str) -> bool:
        """Return True if this agent exposes the given tool name."""
        return tool_name in self.tool_names
