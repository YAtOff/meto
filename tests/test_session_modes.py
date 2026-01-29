"""Tests for session modes.

These tests ensure that the session-level mode abstraction works and that
PlanMode still provides the expected UX/prompt behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.modes.plan import PlanMode
from meto.agent.prompt import build_system_prompt
from meto.agent.session import Session
from meto.conf import settings


def test_plan_mode_enter_sets_plan_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session()
    session.enter_mode(PlanMode())

    assert session.mode is not None
    assert session.mode.name == "plan"
    assert isinstance(session.mode, PlanMode)
    assert session.mode.plan_file is not None
    assert str(session.mode.plan_file).endswith(".md")
    assert session.mode.plan_file.parent == settings.PLAN_DIR


def test_plan_mode_augment_system_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session()
    session.enter_mode(PlanMode())
    assert isinstance(session.mode, PlanMode)
    assert session.mode.plan_file is not None

    prompt = build_system_prompt(session)
    assert "PLAN MODE ACTIVE" in prompt
    assert "PLAN FILE:" in prompt
    assert str(session.mode.plan_file) in prompt


def test_plan_mode_exit_reads_plan_and_returns_followup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session()
    session.enter_mode(PlanMode())

    assert isinstance(session.mode, PlanMode)
    plan_file = session.mode.plan_file
    assert plan_file is not None

    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# My Plan\n\n1. Do thing\n", encoding="utf-8")

    result = session.exit_mode()

    assert result is not None
    assert result.artifact_path == plan_file
    assert result.artifact_content is not None
    assert "My Plan" in result.artifact_content
    assert result.followup_system_message is not None
    assert str(plan_file) in result.followup_system_message

    assert session.mode is None
    assert session.last_mode_exit == result
