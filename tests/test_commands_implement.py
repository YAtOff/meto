"""Tests for /implement command.

This command is like /done but also prompts to start implementation.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from meto.agent.commands import handle_slash_command
from meto.agent.session import NullSessionLogger, Session
from meto.conf import settings


def test_implement_requires_plan_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that /implement only works when in plan mode."""
    session = Session(session_logger_cls=NullSessionLogger)

    # Try /implement when not in plan mode
    was_handled, result = handle_slash_command("/implement", session)
    assert was_handled is True
    assert result is None
    assert session.mode is None

    # Verify the flag was not set
    assert session.start_implementation is False


def test_implement_clears_history_and_injects_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that /implement clears history and injects follow-up message."""
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session(session_logger_cls=NullSessionLogger)

    # Enter plan mode
    handle_slash_command("/plan", session)
    assert session.mode is not None

    plan_file = getattr(session.mode, "plan_file", None)
    assert isinstance(plan_file, Path)

    # Create plan file
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# Plan\n\n1. Step\n", encoding="utf-8")

    # Mock Confirm.ask to return False (user declines to start implementation)
    with patch("rich.prompt.Confirm.ask", return_value=False):
        was_handled, result = handle_slash_command("/implement", session)
        assert was_handled is True
        assert result is None

    # Verify mode was exited
    assert session.mode is None

    # Verify history was cleared and follow-up message injected
    assert len(session.history) == 1
    msg = session.history[0]
    assert msg["role"] == "system"
    assert str(plan_file) in msg["content"]
    assert "FOLLOW THE PLAN" in msg["content"]

    # Verify flag was NOT set (user declined)
    assert session.start_implementation is False


def test_implement_sets_flag_on_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that /implement sets start_implementation flag when user confirms."""
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session(session_logger_cls=NullSessionLogger)

    # Enter plan mode
    handle_slash_command("/plan", session)
    assert session.mode is not None

    plan_file = getattr(session.mode, "plan_file", None)
    assert isinstance(plan_file, Path)

    # Create plan file
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text("# Plan\n\n1. Step\n", encoding="utf-8")

    # Mock Confirm.ask to return True (user confirms to start implementation)
    with patch("rich.prompt.Confirm.ask", return_value=True):
        was_handled, result = handle_slash_command("/implement", session)
        assert was_handled is True
        assert result is None

    # Verify mode was exited
    assert session.mode is None

    # Verify history was cleared and follow-up message injected
    assert len(session.history) == 1
    msg = session.history[0]
    assert msg["role"] == "system"
    assert str(plan_file) in msg["content"]
    assert "FOLLOW THE PLAN" in msg["content"]

    # Verify flag WAS set (user confirmed)
    assert session.start_implementation is True


def test_implement_without_plan_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that /implement handles missing plan file gracefully."""
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")

    session = Session(session_logger_cls=NullSessionLogger)

    # Enter plan mode
    handle_slash_command("/plan", session)
    assert session.mode is not None

    # Don't create the plan file
    # Mock Confirm.ask (should not be called)
    mock_confirm = MagicMock(return_value=True)

    with patch("rich.prompt.Confirm.ask", mock_confirm):
        was_handled, result = handle_slash_command("/implement", session)
        assert was_handled is True
        assert result is None

    # Verify mode was exited
    assert session.mode is None

    # Verify history was cleared (no message injected since no plan file)
    assert len(session.history) == 0

    # Verify flag was NOT set (no plan file)
    assert session.start_implementation is False

    # Confirm.ask should not have been called
    mock_confirm.assert_not_called()
