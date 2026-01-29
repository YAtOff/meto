"""Agent type registry for subagent support.

Different agent types have different tool permissions and system prompts.
This enables context-isolated subtasks with appropriate capabilities.

Also handles user-defined agent loading from .meto/agents/.
Supports YAML frontmatter metadata with markdown body for prompts.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict

from meto.agent.exceptions import ToolNotFoundError
from meto.agent.frontmatter_loader import parse_yaml_frontmatter
from meto.agent.tool_schema import TOOLS, TOOLS_BY_NAME
from meto.conf import settings

logger = logging.getLogger(__name__)


class AgentConfig(TypedDict):
    description: str
    tools: list[str] | str
    prompt: str


# Built-in agent configurations
BUILTIN_AGENTS: dict[str, AgentConfig] = {
    "explore": {
        "description": "Read-only exploration - search, find files, analyze code",
        "tools": ["shell", "list_dir", "read_file", "grep_search", "fetch"],
        "prompt": """PLAN MODE exploration agent. Analyze codebase systematically for implementation planning:
1. Identify all files requiring changes
2. Map dependencies between components
3. Note any technical constraints or risks
4. Summarize findings for implementation planning

- Do NOT make changes
- Return structured analysis""",
    },
    "code": {
        "description": "Full agent for implementing features and fixing bugs",
        "tools": "*",  # All tools including run_task
        "prompt": "You are a coding agent. Implement requested changes efficiently.",
    },
    "plan": {
        "description": "Planning agent - design without modifying",
        "tools": ["shell", "list_dir", "read_file", "grep_search", "fetch"],
        "prompt": """PLAN MODE planning agent. Create comprehensive implementation plan:
1. Break down feature into numbered implementation steps
2. Identify required resources and dependencies
3. Note potential implementation challenges
4. Estimate effort for major components

- Output numbered implementation plan only
- No file modifications allowed""",
    },
}


def get_tools_for_agent(requested_tools: list[str] | str) -> list[dict[str, Any]]:
    """Resolve an agent tool allowlist into concrete tool schemas.

    Args:
        requested_tools: Either "*" (all tools) or a list of tool names.

    Raises:
        ToolNotFoundError: If a named tool is not defined in the tool schema.
    """
    if requested_tools == "*":
        return TOOLS

    tools_by_name = TOOLS_BY_NAME
    unknown = [name for name in requested_tools if name not in tools_by_name]
    if unknown:
        known = ", ".join(sorted(tools_by_name))
        missing = ", ".join(unknown)
        raise ToolNotFoundError(f"Unknown tool(s): {missing}. Known tools: {known}")

    return [tools_by_name[name] for name in requested_tools]


def validate_agent_config(config: dict[str, Any]) -> list[str]:
    """Validate agent configuration.

    Args:
        config: Parsed configuration dict

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check required fields
    if "description" not in config or not config["description"]:
        errors.append("Missing or empty 'description' field")
    if not isinstance(config.get("description"), str):
        errors.append("'description' must be a string")

    # Check tools field
    if "tools" not in config:
        errors.append("Missing 'tools' field")
    else:
        tools = config["tools"]
        if tools == "*":
            pass  # All tools allowed
        elif isinstance(tools, list):
            if not tools:
                errors.append("'tools' list cannot be empty")
            for tool in tools:
                if tool not in TOOLS_BY_NAME:
                    errors.append(f"Unknown tool '{tool}' in tools list")
        else:
            errors.append("'tools' must be a list or '*'")

    # Check prompt (from frontmatter or body)
    if "prompt" not in config or not config["prompt"]:
        errors.append("Missing or empty 'prompt' (must be in frontmatter or markdown body)")

    return errors


def parse_agent_file(path: Path) -> AgentConfig | None:
    """Parse a single agent file.

    Args:
        path: Path to agent markdown file

    Returns:
        AgentConfig if valid, None if parsing failed (error logged)
    """
    try:
        content = path.read_text(encoding="utf-8")
        parsed = parse_yaml_frontmatter(content)

        metadata = parsed["metadata"]
        body = parsed["body"]

        # Get name from frontmatter or filename
        name = metadata.get("name", path.stem)

        # Build config dict
        config = {
            "name": name,
            "description": metadata.get("description", ""),
            "tools": metadata.get("tools", []),
        }

        # Prompt can be in frontmatter or body
        config["prompt"] = metadata.get("prompt", body)

        # Validate
        errors = validate_agent_config(config)
        if errors:
            logger.warning(f"Invalid agent file {path}: {', '.join(errors)}")
            return None

        # Return AgentConfig
        return {
            "description": config["description"],
            "tools": config["tools"],
            "prompt": config["prompt"],
        }

    except Exception as e:
        logger.warning(f"Failed to parse agent file {path}: {e}")
        return None


class AgentLoader:
    """Lazy-load agents: built-in + user-defined agents from .meto/agents/."""

    agents_dir: Path
    _user_agents: dict[str, AgentConfig] | None
    _all_agents_cache: dict[str, AgentConfig] | None

    def __init__(self, agents_dir: Path):
        """Initialize agent loader.

        Args:
            agents_dir: Path to directory containing user agent files
        """
        self.agents_dir = agents_dir
        self._user_agents = None
        self._all_agents_cache = None

    def _discover_agents(self) -> dict[str, AgentConfig]:
        """Discover and parse user-defined agent files.

        Returns:
            Dict mapping agent names to AgentConfig
        """
        if not self.agents_dir.exists():
            logger.debug(f"Agents directory {self.agents_dir} does not exist, skipping user agents")
            return {}

        if not self.agents_dir.is_dir():
            logger.warning(f"Agents directory {self.agents_dir} is not a directory, skipping")
            return {}

        agents: dict[str, AgentConfig] = {}

        for path in sorted(self.agents_dir.glob("*.md")):
            if path.is_file():
                agent_config = parse_agent_file(path)
                if agent_config:
                    name = path.stem
                    agents[name] = agent_config
                    logger.debug(f"Loaded user agent '{name}' from {path}")

        return agents

    def _load_user_agents(self) -> dict[str, AgentConfig]:
        """Load user agents with caching.

        Returns:
            Dict mapping agent names to AgentConfig
        """
        if self._user_agents is None:
            self._user_agents = self._discover_agents()
        return self._user_agents

    def get_all_agents(self) -> dict[str, AgentConfig]:
        """Load all agents (built-in + user-defined).

        User agents override built-in agents with the same name.

        Returns:
            Dict mapping agent names to AgentConfig
        """
        if self._all_agents_cache is not None:
            return self._all_agents_cache

        # Start with built-in agents
        all_agents = dict(BUILTIN_AGENTS)

        # Merge user agents (overrides built-ins)
        user_agents = self._load_user_agents()
        for name, config in user_agents.items():
            if name in all_agents:
                logger.info(f"User agent '{name}' overrides built-in agent")
            all_agents[name] = config

        self._all_agents_cache = all_agents
        return all_agents

    def list_agents(self) -> list[str]:
        """Return list of all available agent names.

        Returns:
            Sorted list of agent names
        """
        return sorted(self.get_all_agents().keys())

    def has_agent(self, agent_name: str) -> bool:
        """Check if an agent exists.

        Args:
            agent_name: Name of agent to check

        Returns:
            True if agent exists, False otherwise
        """
        return agent_name in self.get_all_agents()

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Get configuration for a specific agent.

        Args:
            agent_name: Name of agent to get

        Returns:
            AgentConfig for the agent

        Raises:
            ValueError: If agent not found
        """
        all_agents = self.get_all_agents()
        if agent_name not in all_agents:
            available = ", ".join(sorted(all_agents.keys()))
            raise ValueError(
                f"Agent '{agent_name}' not found. Available agents: {available or '(none)'}"
            )
        return all_agents[agent_name]

    def clear_cache(self) -> None:
        """Clear all caches.

        Useful for testing or when agent files change.
        """
        self._user_agents = None
        self._all_agents_cache = None


@lru_cache(maxsize=16)
def _get_agent_loader(agents_dir: Path | None = None) -> AgentLoader:
    """Get or create the global agent loader instance.

    Args:
        agents_dir: Directory to scan for user agent files

    Returns:
        AgentLoader instance
    """
    resolved = agents_dir if agents_dir is not None else Path(settings.AGENTS_DIR)
    return AgentLoader(resolved)


def clear_agent_cache() -> None:
    """Clear the user agents cache.

    Useful for testing or when agent files change.
    """
    # Reset the loader instance cache entirely.
    _get_agent_loader.cache_clear()


def get_all_agents(agents_dir: Path | None = None) -> dict[str, AgentConfig]:
    """Load all agents (built-in + user-defined).

    User agents override built-in agents with the same name.

    Args:
        agents_dir: Directory to scan for user agent files

    Returns:
        Dict mapping agent names to AgentConfig
    """
    loader = _get_agent_loader(agents_dir)
    return loader.get_all_agents()
