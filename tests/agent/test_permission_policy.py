from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.permission_policy import (
    AlwaysRequirePermissionCheck,
    ExternalPathPermissionCheck,
    NeverRequirePermissionCheck,
)


def test_always_require_permission() -> None:
    check = AlwaysRequirePermissionCheck("x")
    assert check.is_required({"x": "anything"}) is True


def test_never_require_permission() -> None:
    check = NeverRequirePermissionCheck()
    assert check.is_required({"path": "whatever"}) is False


def test_external_path_permission_check(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    check = ExternalPathPermissionCheck()

    inside = tmp_path / "inside.txt"
    assert check.is_required({"path": str(inside)}) is False

    outside_dir = tmp_path_factory.mktemp("outside")
    outside = outside_dir / "outside.txt"
    assert check.is_required({"path": str(outside)}) is True


def test_external_path_permission_check_fail_closed_on_weird_value() -> None:
    check = ExternalPathPermissionCheck()
    assert check.is_required({"path": object()}) is True
