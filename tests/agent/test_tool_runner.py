from __future__ import annotations

from pathlib import Path

import pytest

import meto.agent.tool_runner as tool_runner
from meto.agent.session import NullSessionLogger, Session


def test_run_tool_unknown_tool_returns_error_string() -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    out = tool_runner.run_tool("nope", {}, session=session)
    assert out.startswith("Error: Unknown tool:")


def test_run_tool_manage_todos_requires_session() -> None:
    out = tool_runner.run_tool("manage_todos", {"items": []}, session=None)
    assert out == "Error: session required for manage_todos"


def test_run_tool_write_and_read_file_roundtrip(tmp_path: Path) -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    p = tmp_path / "a.txt"

    w = tool_runner.run_tool("write_file", {"path": str(p), "content": "hello"}, session=session)
    assert "Successfully wrote" in w

    r = tool_runner.run_tool("read_file", {"path": str(p)}, session=session)
    assert "hello" in r


def test_permission_prompt_can_cancel_before_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # yolo_mode=False should cause prompt; we simulate user cancel.
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=False)

    monkeypatch.setattr(tool_runner, "_prompt_permission", lambda *_a, **_k: False)

    out = tool_runner.run_tool("fetch", {"url": "https://example.com"}, session=session)
    assert out == "(fetch cancelled by user)"
