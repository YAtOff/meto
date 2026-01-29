from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.permission_policy import ExternalPathPermissionCheck
from meto.conf import settings


def test_external_path_permission_check_inside_allowed_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ensure CWD is in allowed dirs.
    monkeypatch.chdir(tmp_path)

    # Point meto dirs into the temp directory to keep the test hermetic.
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")
    monkeypatch.setattr(settings, "AGENTS_DIR", tmp_path / "agents")
    monkeypatch.setattr(settings, "COMMANDS_DIR", tmp_path / "commands")
    monkeypatch.setattr(settings, "SKILLS_DIR", tmp_path / "skills")

    check = ExternalPathPermissionCheck()

    inside = tmp_path / "file.txt"
    assert check.is_required({"path": str(inside)}) is False


def test_external_path_permission_check_outside_allowed_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")
    monkeypatch.setattr(settings, "AGENTS_DIR", tmp_path / "agents")
    monkeypatch.setattr(settings, "COMMANDS_DIR", tmp_path / "commands")
    monkeypatch.setattr(settings, "SKILLS_DIR", tmp_path / "skills")

    check = ExternalPathPermissionCheck()

    outside = tmp_path.parent / "outside.txt"
    assert check.is_required({"path": str(outside)}) is True


def test_external_path_permission_check_fail_closed_on_invalid_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "PLAN_DIR", tmp_path / "plans")
    monkeypatch.setattr(settings, "AGENTS_DIR", tmp_path / "agents")
    monkeypatch.setattr(settings, "COMMANDS_DIR", tmp_path / "commands")
    monkeypatch.setattr(settings, "SKILLS_DIR", tmp_path / "skills")

    check = ExternalPathPermissionCheck()

    # Embedded NUL should raise in pathlib; policy should require permission.
    assert check.is_required({"path": "\x00"}) is True
