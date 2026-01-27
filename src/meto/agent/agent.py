from __future__ import annotations

from typing import Any

from meto.agent.agent_registry import get_all_agents, get_tools_for_agent
from meto.agent.exceptions import SubagentError
from meto.agent.session import NullSessionLogger, Session
from meto.agent.tool_schema import populate_skill_descriptions
from meto.conf import settings


class Agent:
    name: str
    prompt: str
    session: Session
    tools: list[dict[str, Any]]
    max_turns: int

    @classmethod
    def main(cls, session: Session) -> Agent:
        # The main agent uses the default system prompt and has access to all tools.
        # `prompt` is reserved for future per-agent system prompt customization.
        return cls(
            name="main",
            prompt="",
            session=session,
            allowed_tools="*",
            max_turns=settings.MAIN_AGENT_MAX_TURNS,
        )

    @classmethod
    def subagent(cls, name: str) -> Agent:
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
            )
        else:
            # Build helpful error message with available agents
            available = ", ".join(sorted(all_agents.keys()))
            raise SubagentError(f"Unknown agent type '{name}'. Available agents: {available}")

    @classmethod
    def fork(cls, allowed_tools: list[str] | str) -> Agent:
        return cls(
            name="fork",
            prompt="",
            session=Session(session_logger_cls=NullSessionLogger),
            allowed_tools=allowed_tools,
            max_turns=settings.SUBAGENT_MAX_TURNS,
        )

    def __init__(
        self,
        name: str,
        prompt: str,
        session: Session,
        allowed_tools: list[str] | str,
        max_turns: int,
    ) -> None:
        self.name = name
        self.prompt = prompt
        self.session = session
        self.max_turns = max_turns

        # Get base tools for agent
        base_tools = get_tools_for_agent(allowed_tools)

        # Populate skill descriptions if skill_loader is available
        if session.skill_loader:
            skills = session.skill_loader.get_skill_descriptions()
            self.tools = populate_skill_descriptions(base_tools, skills)
        else:
            self.tools = base_tools

    @property
    def tool_names(self) -> list[str]:
        return [tool["function"]["name"] for tool in self.tools]

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.tool_names
