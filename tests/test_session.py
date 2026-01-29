"""Tests for Session class focusing on start_implementation flag."""

from __future__ import annotations

from meto.agent.session import NullSessionLogger, Session


def test_session_initializes_with_start_implementation_false() -> None:
    """Test that Session initializes with start_implementation=False."""
    session = Session(session_logger_cls=NullSessionLogger)
    assert session.start_implementation is False


def test_session_clear_resets_start_implementation() -> None:
    """Test that clear() resets start_implementation to False."""
    session = Session(session_logger_cls=NullSessionLogger)
    session.start_implementation = True
    assert session.start_implementation is True

    session.clear()
    assert session.start_implementation is False


def test_session_renew_resets_start_implementation() -> None:
    """Test that renew() resets start_implementation to False."""
    session = Session(session_logger_cls=NullSessionLogger)
    session.start_implementation = True
    old_session_id = session.session_id

    assert session.start_implementation is True

    session.renew()

    # Should have new session ID
    assert session.session_id != old_session_id
    # Should reset flag
    assert session.start_implementation is False
