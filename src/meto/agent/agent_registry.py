"""Agent type registry for subagent support.

Different agent types have different tool permissions and system prompts.
This enables context-isolated subtasks with appropriate capabilities.

Also handles user-defined agent loading from .meto/agents/.
Supports YAML frontmatter metadata with markdown body for prompts.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, TypedDict

import yaml

from meto.agent.exceptions import ToolNotFoundError
from meto.agent.tool_schema import TOOLS, TOOLS_BY_NAME
from meto.conf import settings

logger = logging.getLogger(__name__)

# Regex to match YAML frontmatter between --- delimiters
FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)

# Cache for loaded user agents
_user_agents_cache: dict[str, AgentConfig] | None = None


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
        tools_by_name = TOOLS_BY_NAME
        unknown = [name for name in requested_tools if name not in tools_by_name]
        if unknown:
            known = ", ".join(sorted(tools_by_name))
            missing = ", ".join(unknown)
            raise ToolNotFoundError(f"Unknown tool(s): {missing}. Known tools: {known}")
        return [tools_by_name[name] for name in requested_tools]


def parse_yaml_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: Full file content with potential frontmatter

    Returns:
        Dict with 'metadata' (parsed YAML) and 'body' (remaining content)
    """
    match = FRONTMATTER_PATTERN.match(content)
    if match:
        yaml_block, body = match.groups()
        metadata = yaml.safe_load(yaml_block) or {}
        return {"metadata": metadata, "body": body.strip()}
    else:
        # No frontmatter found, treat entire content as body
        return {"metadata": {}, "body": content.strip()}


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


def discover_agents(agents_dir: Path) -> dict[str, AgentConfig]:
    """Discover and parse user-defined agent files.

    Args:
        agents_dir: Directory to scan for agent files

    Returns:
        Dict mapping agent names to AgentConfig
    """
    if not agents_dir.exists():
        logger.debug(f"Agents directory {agents_dir} does not exist, skipping user agents")
        return {}

    if not agents_dir.is_dir():
        logger.warning(f"Agents directory {agents_dir} is not a directory, skipping")
        return {}

    agents: dict[str, AgentConfig] = {}

    for path in sorted(agents_dir.glob("*.md")):
        if path.is_file():
            agent_config = parse_agent_file(path)
            if agent_config:
                name = path.stem
                agents[name] = agent_config
                logger.debug(f"Loaded user agent '{name}' from {path}")

    return agents


def load_all_agents(agents_dir: Path) -> dict[str, AgentConfig]:
    """Load all agents (built-in + user-defined).

    User agents override built-in agents with the same name.

    Args:
        agents_dir: Directory to scan for user agent files

    Returns:
        Dict mapping agent names to AgentConfig
    """
    global _user_agents_cache

    # Use cache if available
    if _user_agents_cache is None:
        user_agents = discover_agents(agents_dir)
        _user_agents_cache = user_agents
    else:
        user_agents = _user_agents_cache

    # Start with built-in agents
    all_agents = dict(AGENTS)

    # Merge user agents (overrides built-ins)
    for name, config in user_agents.items():
        if name in all_agents:
            logger.info(f"User agent '{name}' overrides built-in agent")
        all_agents[name] = config

    return all_agents


def clear_agent_cache() -> None:
    """Clear the user agents cache.

    Useful for testing or when agent files change.
    """
    global _user_agents_cache
    _user_agents_cache = None


def get_all_agents(agents_dir: Path | None = None) -> dict[str, AgentConfig]:
    """Load all agents (built-in + user-defined).

    User agents override built-in agents with the same name.

    Args:
        agents_dir: Directory to scan for user agent files

    Returns:
        Dict mapping agent names to AgentConfig
    """
    return load_all_agents(agents_dir if agents_dir else Path(settings.AGENTS_DIR))
