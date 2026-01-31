from __future__ import annotations

from meto.agent.agent import Agent
from meto.agent.session import NullSessionLogger, Session
from meto.agent.tool_schema import TOOLS
from meto.conf import settings


def test_agent_main_has_all_tools_reuses_session_and_sets_hooks_flag() -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    agent = Agent.main(session)

    assert agent.session is session
    assert agent.run_hooks is True
    assert agent.max_turns == settings.MAIN_AGENT_MAX_TURNS
    assert agent.tool_names == [t["function"]["name"] for t in TOOLS]


def test_agent_subagent_creates_fresh_session_inherits_yolo_never_runs_hooks() -> None:
    parent = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    agent = Agent.subagent("plan", parent)

    assert agent.session is not parent
    assert agent.session.yolo_mode is True
    assert agent.run_hooks is False
    assert agent.max_turns == settings.SUBAGENT_MAX_TURNS
    assert agent.name == "plan"


def test_agent_fork_uses_explicit_allowlist_and_inherits_yolo() -> None:
    parent = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    agent = Agent.fork(["list_dir", "read_file"], parent)

    assert agent.session is not parent
    assert agent.session.yolo_mode is True
    assert agent.run_hooks is False
    assert agent.has_tool("list_dir") is True
    assert agent.has_tool("read_file") is True
    assert agent.has_tool("shell") is False


def test_tool_names_and_has_tool() -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    agent = Agent.fork(["list_dir"], session)

    assert agent.tool_names == ["list_dir"]
    assert agent.has_tool("list_dir") is True
    assert agent.has_tool("read_file") is False
