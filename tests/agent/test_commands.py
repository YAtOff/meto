from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.commands import (
    ArgumentSubstitutionError,
    CustomCommandResult,
    _parse_slash_command_argv,
    _substitute_arguments,
    handle_slash_command,
)
from meto.agent.session import NullSessionLogger, Session
from meto.conf import settings


def test_handle_slash_command_non_command_returns_false() -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    handled, result = handle_slash_command("hello", session)
    assert handled is False
    assert result is None


def test_handle_slash_command_builtin_help_is_handled(capsys: pytest.CaptureFixture[str]) -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)
    handled, result = handle_slash_command("/help", session)

    assert handled is True
    assert result is None

    out = capsys.readouterr().out
    assert "Built-in commands:" in out


def test_handle_slash_command_custom_md_returns_custom_result(tmp_path: Path) -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    cmd_file = settings.COMMANDS_DIR / "foo.md"
    cmd_file.write_text(
        "---\nname: foo\ndescription: My foo command\n---\nDo something with args: $ARGUMENTS\n",
        encoding="utf-8",
    )

    handled, result = handle_slash_command("/foo a b", session)

    assert handled is True
    assert isinstance(result, CustomCommandResult)
    assert "a b" in result.prompt


def test_command_precedence_builtin_over_custom(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    session = Session(session_logger_cls=NullSessionLogger, yolo_mode=True)

    # Even if there's a custom help.md, /help must invoke built-in.
    (settings.COMMANDS_DIR / "help.md").write_text(
        "---\nname: help\ndescription: hijack\n---\nHACKED\n",
        encoding="utf-8",
    )

    handled, result = handle_slash_command("/help", session)
    assert handled is True
    assert result is None

    out = capsys.readouterr().out
    assert "Built-in commands:" in out
    assert "HACKED" not in out


def test_argument_substitution_out_of_bounds_raises() -> None:
    with pytest.raises(ArgumentSubstitutionError):
        _substitute_arguments("Value: $ARGUMENTS[1]", ["only0"])


def test_parse_slash_command_argv_preserves_backslashes() -> None:
    argv = _parse_slash_command_argv(r"/export C:\\Users\\me\\file.json")
    assert argv == ["/export", r"C:\\Users\\me\\file.json"]
