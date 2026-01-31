from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from meto.agent.modes.plan import PlanMode
from meto.agent.session import NullSessionLogger, Session
from meto.agent.system_prompt import build_system_prompt


def test_build_system_prompt_includes_agents_md_and_agent_instructions(tmp_path: Path) -> None:
    # AGENTS.md is created in conftest and cwd is already tmp_path.
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    agent = SimpleNamespace(prompt="EXTRA AGENT PROMPT")
    prompt = build_system_prompt(session=session, agent=agent)

    assert "BEGIN AGENTS.md" in prompt
    assert "These are test instructions." in prompt
    assert "AGENT INSTRUCTIONS" in prompt
    assert "EXTRA AGENT PROMPT" in prompt


def test_build_system_prompt_includes_mode_fragment_and_rereads_agents_md(tmp_path: Path) -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    session.enter_mode(PlanMode())

    p1 = build_system_prompt(session=session, agent=None)
    assert "PLAN MODE ACTIVE" in p1

    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Updated\n\nNew instructions.\n", encoding="utf-8")

    p2 = build_system_prompt(session=session, agent=None)
    assert "New instructions." in p2
