"""Tests for agent_registry module with AgentLoader."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from meto.agent.agent_registry import (
    BUILTIN_AGENTS,
    AgentLoader,
    get_all_agents,
    parse_agent_file,
    validate_agent_config,
)


def test_builtin_agents_exist():
    """Test that built-in agents are defined."""
    assert "explore" in BUILTIN_AGENTS
    assert "code" in BUILTIN_AGENTS
    assert "plan" in BUILTIN_AGENTS


def test_validate_agent_config_valid():
    """Test validation with valid config."""
    config = {
        "description": "Test agent",
        "tools": ["shell", "read_file"],
        "prompt": "Test prompt",
    }
    errors = validate_agent_config(config)
    assert errors == []


def test_validate_agent_config_missing_description():
    """Test validation with missing description."""
    config = {
        "tools": ["shell"],
        "prompt": "Test prompt",
    }
    errors = validate_agent_config(config)
    assert any("description" in err.lower() for err in errors)


def test_validate_agent_config_invalid_tools():
    """Test validation with invalid tools."""
    config = {
        "description": "Test agent",
        "tools": ["invalid_tool"],
        "prompt": "Test prompt",
    }
    errors = validate_agent_config(config)
    assert any("unknown tool" in err.lower() for err in errors)


def test_validate_agent_config_missing_prompt():
    """Test validation with missing prompt."""
    config = {
        "description": "Test agent",
        "tools": ["shell"],
    }
    errors = validate_agent_config(config)
    assert any("prompt" in err.lower() for err in errors)


def test_parse_agent_file_valid():
    """Test parsing a valid agent file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""---
description: Test agent for testing
tools:
  - shell
  - read_file
---

This is the agent prompt.
""")
        f.flush()
        path = Path(f.name)

    try:
        config = parse_agent_file(path)
        assert config is not None
        assert config["description"] == "Test agent for testing"
        assert config["tools"] == ["shell", "read_file"]
        assert config["prompt"] == "This is the agent prompt."
    finally:
        path.unlink()


def test_parse_agent_file_with_prompt_in_frontmatter():
    """Test parsing agent file with prompt in frontmatter."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""---
description: Test agent
tools:
  - shell
prompt: Prompt from frontmatter
---

This body should be ignored.
""")
        f.flush()
        path = Path(f.name)

    try:
        config = parse_agent_file(path)
        assert config is not None
        assert config["prompt"] == "Prompt from frontmatter"
    finally:
        path.unlink()


def test_parse_agent_file_invalid():
    """Test parsing an invalid agent file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("""---
description: Missing tools field
---

Agent prompt.
""")
        f.flush()
        path = Path(f.name)

    try:
        config = parse_agent_file(path)
        assert config is None
    finally:
        path.unlink()


def test_agent_loader_initialization():
    """Test AgentLoader initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = AgentLoader(Path(tmpdir))
        assert loader.agents_dir == Path(tmpdir)


def test_agent_loader_get_all_agents_builtin_only():
    """Test getting all agents with no user agents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = AgentLoader(Path(tmpdir))
        agents = loader.get_all_agents()

        assert "explore" in agents
        assert "code" in agents
        assert "plan" in agents


def test_agent_loader_with_user_agent():
    """Test loading user-defined agent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir)

        # Create a user agent file
        agent_file = agents_dir / "custom.md"
        agent_file.write_text("""---
description: Custom user agent
tools:
  - shell
  - read_file
---

Custom agent prompt.
""")

        loader = AgentLoader(agents_dir)
        agents = loader.get_all_agents()

        assert "custom" in agents
        assert agents["custom"]["description"] == "Custom user agent"
        assert agents["custom"]["prompt"] == "Custom agent prompt."


def test_agent_loader_user_overrides_builtin():
    """Test that user agent overrides built-in agent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir)

        # Create a user agent that overrides "explore"
        agent_file = agents_dir / "explore.md"
        agent_file.write_text("""---
description: Custom explore agent
tools:
  - shell
---

Custom explore prompt.
""")

        loader = AgentLoader(agents_dir)
        agents = loader.get_all_agents()

        assert agents["explore"]["description"] == "Custom explore agent"
        assert agents["explore"]["prompt"] == "Custom explore prompt."


def test_agent_loader_list_agents():
    """Test listing all agent names."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir)

        # Create a user agent
        agent_file = agents_dir / "custom.md"
        agent_file.write_text("""---
description: Custom agent
tools:
  - shell
---

Prompt.
""")

        loader = AgentLoader(agents_dir)
        agent_names = loader.list_agents()

        assert "explore" in agent_names
        assert "code" in agent_names
        assert "plan" in agent_names
        assert "custom" in agent_names


def test_agent_loader_has_agent():
    """Test checking if agent exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = AgentLoader(Path(tmpdir))

        assert loader.has_agent("explore") is True
        assert loader.has_agent("nonexistent") is False


def test_agent_loader_get_agent_config():
    """Test getting specific agent config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = AgentLoader(Path(tmpdir))
        config = loader.get_agent_config("explore")

        assert config["description"] == "Read-only exploration - search, find files, analyze code"


def test_agent_loader_get_agent_config_not_found():
    """Test getting config for non-existent agent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = AgentLoader(Path(tmpdir))

        with pytest.raises(ValueError, match="not found"):
            loader.get_agent_config("nonexistent")


def test_agent_loader_clear_cache():
    """Test cache clearing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir)

        loader = AgentLoader(agents_dir)
        # Load once to populate cache
        loader.get_all_agents()

        # Add a new agent file
        agent_file = agents_dir / "new.md"
        agent_file.write_text("""---
description: New agent
tools:
  - shell
---

New agent prompt.
""")

        # Without clearing cache, new agent won't be loaded
        agents2 = loader.get_all_agents()
        assert "new" not in agents2

        # After clearing cache, new agent should be loaded
        loader.clear_cache()
        agents3 = loader.get_all_agents()
        assert "new" in agents3


def test_agent_loader_caching():
    """Test that caching works correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = AgentLoader(Path(tmpdir))

        # First call should load and cache
        agents1 = loader.get_all_agents()
        # Second call should return cached version (same object reference)
        agents2 = loader.get_all_agents()

        assert agents1 is agents2


def test_get_all_agents_function():
    """Test the module-level get_all_agents function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents = get_all_agents(Path(tmpdir))

        assert "explore" in agents
        assert "code" in agents
        assert "plan" in agents
