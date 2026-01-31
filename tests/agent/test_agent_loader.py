from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.exceptions import ToolNotFoundError
from meto.agent.loaders.agent_loader import AgentLoader, get_tools_for_agent, parse_agent_file
from meto.agent.tool_schema import TOOLS


def test_get_tools_for_agent_star_returns_all_tools() -> None:
    tools = get_tools_for_agent("*")
    assert tools == TOOLS


def test_get_tools_for_agent_unknown_raises() -> None:
    with pytest.raises(ToolNotFoundError):
        get_tools_for_agent(["definitely_not_a_tool"])


def test_parse_agent_file_valid_returns_config(tmp_path: Path) -> None:
    p = tmp_path / "ok.md"
    p.write_text(
        "---\ndescription: Example agent\ntools:\n  - shell\n---\nThis is the prompt body.\n",
        encoding="utf-8",
    )

    cfg = parse_agent_file(p)
    assert cfg is not None
    assert cfg["description"] == "Example agent"
    assert cfg["tools"] == ["shell"]
    assert "prompt" in cfg and "This is the prompt body." in cfg["prompt"]


def test_parse_agent_file_invalid_returns_none(tmp_path: Path) -> None:
    # Missing description + missing tools => invalid
    p = tmp_path / "bad.md"
    p.write_text("---\nname: bad\n---\nBody\n", encoding="utf-8")

    cfg = parse_agent_file(p)
    assert cfg is None


def test_agent_loader_merges_and_user_overrides_builtin(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    # Override built-in "code" by providing "code.md" (keyed by filename stem).
    (agents_dir / "code.md").write_text(
        "---\ndescription: My custom code agent\ntools: '*'\n---\nMy custom prompt\n",
        encoding="utf-8",
    )

    loader = AgentLoader(agents_dir)
    all_agents = loader.get_all_agents()

    assert "code" in all_agents
    assert all_agents["code"]["description"] == "My custom code agent"


def test_has_agent_and_get_agent_config(tmp_path: Path) -> None:
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()

    (agents_dir / "foo.md").write_text(
        "---\ndescription: Foo agent\ntools:\n  - list_dir\n---\nFoo prompt\n",
        encoding="utf-8",
    )

    loader = AgentLoader(agents_dir)

    assert loader.has_agent("foo") is True
    cfg = loader.get_agent_config("foo")
    assert cfg["description"] == "Foo agent"

    with pytest.raises(ValueError):
        loader.get_agent_config("missing-agent")
