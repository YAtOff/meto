from __future__ import annotations

import sys
from pathlib import Path

import pytest

import meto.agent.hooks as hooks_mod
from meto.agent.hooks import EXIT_BLOCK, HookConfig, HooksConfig, HooksManager, get_hooks_manager


def test_hooks_config_load_from_yaml(tmp_path: Path) -> None:
    p = tmp_path / "hooks.yaml"
    p.write_text(
        "hooks:\n  - name: ok\n    event: session_start\n    command: echo hi\n",
        encoding="utf-8",
    )

    cfg = HooksConfig.load_from_yaml(p)
    assert len(cfg.hooks) == 1
    assert cfg.hooks[0].name == "ok"


def test_hooks_manager_get_hooks_for_event_filters_by_tool() -> None:
    cfg = HooksConfig(
        hooks=[
            HookConfig(name="a", event="pre_tool_use", tools=["read_file"], command="noop"),
            HookConfig(name="b", event="pre_tool_use", tools=[], command="noop2"),
        ]
    )
    mgr = HooksManager(config=cfg)

    hooks_for_read = mgr.get_hooks_for_event("pre_tool_use", tool_name="read_file")
    assert [h.name for h in hooks_for_read] == ["a", "b"]

    hooks_for_write = mgr.get_hooks_for_event("pre_tool_use", tool_name="write_file")
    assert [h.name for h in hooks_for_write] == ["b"]


def test_run_hooks_executes_real_subprocess_and_can_block(monkeypatch: pytest.MonkeyPatch) -> None:
    # Use python -c so we don't depend on bash/pwsh quoting behavior.
    monkeypatch.setattr(hooks_mod, "pick_shell_runner", lambda: [sys.executable, "-c"])

    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="block",
                event="pre_tool_use",
                tools=[],
                command=f"import sys; sys.exit({EXIT_BLOCK})",
                timeout=5,
            ),
            HookConfig(
                name="should_not_run",
                event="pre_tool_use",
                tools=[],
                command="print('NO')",
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("pre_tool_use", session_id="s1", tool="read_file")
    assert len(results) == 1
    assert results[0].hook_name == "block"
    assert results[0].blocked is True


def test_get_hooks_manager_is_cached_and_resettable() -> None:
    a = get_hooks_manager()
    b = get_hooks_manager()
    assert a is b
