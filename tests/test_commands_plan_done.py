"""Tests for /plan and /done commands.

These tests validate that exiting plan mode clears history and injects a
follow-up system message pointing to the plan artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.commands import handle_slash_command
from meto.agent.session import NullSessionLogger, Session
from meto.conf import settings


def test_plan_then_done_injects_followup_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Keep the test hermetic: plan artifacts go into tmp.
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session(session_logger_cls=NullSessionLogger)

    was_handled, result = handle_slash_command("/plan", session)
    assert was_handled is True
    assert result is None

    assert session.mode is not None
    # PlanMode exposes the artifact path as `plan_file`.
    plan_file = getattr(session.mode, "plan_file", None)
    assert isinstance(plan_file, Path)

    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# Plan\n\n1. Step\n", encoding="utf-8")

    was_handled, result = handle_slash_command("/done", session)
    assert was_handled is True
    assert result is None

    assert session.mode is None

    assert len(session.history) == 1
    msg = session.history[0]
    assert msg["role"] == "system"
    assert str(plan_file) in msg["content"]
    assert "FOLLOW THE PLAN" in msg["content"]
