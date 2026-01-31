from __future__ import annotations

from datetime import UTC, datetime

import pytest

import meto.agent.modes.plan as plan_mod
from meto.agent.modes.plan import PlanMode, _generate_plan_filename
from meto.agent.session import NullSessionLogger, Session


def test_plan_mode_implements_session_mode_contract() -> None:
    mode = PlanMode()
    assert mode.name == "plan"
    assert mode.agent_name == "planner"
    assert mode.prompt_prefix(">>> ") == "[PLAN] >>> "
    frag = mode.system_prompt_fragment()
    assert "PLAN MODE ACTIVE" in frag


def test_generate_plan_filename_is_stable_with_injected_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(plan_mod.random, "choices", lambda *_a, **_k: list("abcdef"))
    now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=UTC)

    name = _generate_plan_filename(now=now)
    assert name == "plan-20260131_120000-abcdef.md"


def test_plan_mode_enter_sets_plan_file_and_exit_returns_artifact(tmp_path) -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    mode = PlanMode()
    session.enter_mode(mode)

    assert mode.plan_file is not None
    assert str(mode.plan_file).endswith(".md")

    # Write content to trigger followup message creation.
    mode.plan_file.write_text("Plan content\n", encoding="utf-8")

    result = session.exit_mode()
    assert result is not None
    assert result.artifact_path == mode.plan_file
    assert result.followup_system_message is not None
    assert "FOLLOW THE PLAN" in result.followup_system_message
