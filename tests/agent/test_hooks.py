from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import meto.agent.hooks as hooks_mod
from meto.agent.hooks import (
    EXIT_BLOCK,
    HookConfig,
    HooksConfig,
    HooksManager,
    get_hooks_manager,
    is_python_script,
    run_python_script,
)

# ============================================================================
# Tests for is_python_script()
# ============================================================================


def test_is_python_script_detection_basic() -> None:
    """Test basic Python script detection."""
    assert is_python_script("script.py") is True
    assert is_python_script("  script.py  ") is True
    assert is_python_script("SCRIPT.PY") is True
    assert is_python_script("my-script.py") is True
    assert is_python_script("path/to/script.py") is True


def test_is_python_script_detection_negative() -> None:
    """Test commands that should NOT be detected as Python scripts."""
    assert is_python_script("python script.py") is False
    assert is_python_script("python3 script.py") is False
    assert is_python_script("pypy script.py") is False
    assert is_python_script("python script.PY") is False
    assert is_python_script("echo hello") is False
    assert is_python_script("bash script.sh") is False
    assert is_python_script("./script") is False


def test_is_python_script_edge_cases() -> None:
    """Test edge cases for Python script detection."""
    assert is_python_script("") is False
    assert is_python_script("   ") is False
    assert is_python_script("script.py") is True
    assert is_python_script('"script.py"') is False  # Quoted path is not detected as .py
    assert is_python_script("python.exe script.py") is False
    assert is_python_script("python3.exe script.py") is False
    assert is_python_script("script.py arg1 arg2") is True


def test_is_python_script_windows_executable() -> None:
    """Test Windows Python executable detection."""
    assert is_python_script("python") is False
    assert is_python_script("python.exe") is False
    assert is_python_script("python3") is False
    assert is_python_script("python3.exe") is False
    assert is_python_script("pypy") is False
    assert is_python_script("script.py") is True
    assert is_python_script("SCRIPT.PY") is True


# ============================================================================
# Tests for run_python_script()
# ============================================================================


def test_run_python_script_executes_successfully(tmp_path: Path) -> None:
    """Test that run_python_script executes a script successfully."""
    script = tmp_path / "test.py"
    script.write_text("print('hello world')", encoding="utf-8")

    result = run_python_script(
        command=str(script),
        env={},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode == 0
    assert "hello world" in result.stdout
    assert result.stderr == ""


def test_run_python_script_with_arguments(tmp_path: Path) -> None:
    """Test that run_python_script passes arguments correctly."""
    script = tmp_path / "args.py"
    script.write_text(
        "import sys; print(' '.join(sys.argv[1:]))",
        encoding="utf-8",
    )

    result = run_python_script(
        command=f'{script} arg1 "arg with spaces" arg3',
        env={},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode == 0
    assert "arg1" in result.stdout
    assert "arg with spaces" in result.stdout
    assert "arg3" in result.stdout


def test_run_python_script_script_not_found(tmp_path: Path) -> None:
    """Test that run_python_script handles missing script."""
    result = run_python_script(
        command=str(tmp_path / "nonexistent.py"),
        env={},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode != 0
    assert "No such file" in result.stderr or "cannot find" in result.stderr.lower()


def test_run_python_script_syntax_error(tmp_path: Path) -> None:
    """Test that run_python_script handles script syntax errors."""
    script = tmp_path / "syntax.py"
    script.write_text("print('unclosed string", encoding="utf-8")

    result = run_python_script(
        command=str(script),
        env={},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode != 0
    assert "SyntaxError" in result.stderr or "syntax error" in result.stderr.lower()


def test_run_python_script_with_exit_code(tmp_path: Path) -> None:
    """Test that run_python_script returns correct exit codes."""
    script = tmp_path / "exit.py"
    script.write_text("import sys; sys.exit(42)", encoding="utf-8")

    result = run_python_script(
        command=str(script),
        env={},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode == 42


def test_run_python_script_uses_sys_executable(tmp_path: Path) -> None:
    """Test that run_python_script uses sys.executable."""
    # Create a script that prints the interpreter path
    script = tmp_path / "interpreter.py"
    script.write_text("import sys; print(sys.executable)", encoding="utf-8")

    result = run_python_script(
        command=str(script),
        env={},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode == 0
    # The script should have used the same Python interpreter
    assert str(sys.executable) in result.stdout


def test_run_python_script_env_vars(tmp_path: Path) -> None:
    """Test that run_python_script receives environment variables."""
    script = tmp_path / "env.py"
    script.write_text(
        "import os; print(os.environ.get('TEST_VAR', 'not set'))",
        encoding="utf-8",
    )

    result = run_python_script(
        command=str(script),
        env={"TEST_VAR": "test_value"},
        timeout=5,
        cwd=Path.cwd(),
    )

    assert result.returncode == 0
    assert "test_value" in result.stdout


def test_run_python_script_timeout(tmp_path: Path) -> None:
    """Test that run_python_script respects timeout."""
    script = tmp_path / "sleep.py"
    script.write_text("import time; time.sleep(10)", encoding="utf-8")

    with pytest.raises(subprocess.TimeoutExpired):
        run_python_script(
            command=str(script),
            env={},
            timeout=1,  # 1 second timeout
            cwd=Path.cwd(),
        )


# ============================================================================
# Integration tests with HooksManager
# ============================================================================


def test_python_hook_execution_integration(tmp_path: Path) -> None:
    """Test that Python scripts are executed via sys.executable."""
    # Create a Python script hook
    script = tmp_path / "hook.py"
    script.write_text("print('hook executed')", encoding="utf-8")

    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="python-hook",
                event="session_start",
                command=str(script),
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("session_start", session_id="test-session")
    assert len(results) == 1
    assert results[0].success is True
    assert "hook executed" in results[0].stdout


def test_python_hook_with_arguments_integration(tmp_path: Path) -> None:
    """Test Python hook with arguments."""
    script = tmp_path / "args.py"
    script.write_text("import sys; print(' '.join(sys.argv[1:]))", encoding="utf-8")

    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="python-hook-args",
                event="session_start",
                command=f'{script} arg1 "arg2"',
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("session_start", session_id="test-session")
    assert len(results) == 1
    assert results[0].success is True
    assert "arg1" in results[0].stdout
    assert "arg2" in results[0].stdout


def test_python_hook_script_not_found_integration() -> None:
    """Test that missing Python script hooks are handled gracefully."""
    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="missing-hook",
                event="session_start",
                command="nonexistent.py",
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("session_start", session_id="test-session")
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error is None  # Should not have error field, should have stderr


def test_python_hook_can_block(tmp_path: Path) -> None:
    """Test that Python hook can block tool execution."""
    script = tmp_path / "block.py"
    script.write_text("import sys; sys.exit(2)", encoding="utf-8")  # EXIT_BLOCK = 2

    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="blocking-hook",
                event="pre_tool_use",
                command=str(script),
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("pre_tool_use", session_id="test-session", tool="read_file")
    assert len(results) == 1
    assert results[0].blocked is True


def test_backward_compatibility_shell_commands() -> None:
    """Test that non-Python commands still work via shell."""
    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="echo-hook",
                event="session_start",
                command="echo hello",
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("session_start", session_id="test-session")
    assert len(results) == 1
    assert results[0].success is True
    assert "hello" in results[0].stdout


def test_python_command_explicit_interpreter_uses_shell(tmp_path: Path) -> None:
    """Test that 'python script.py' commands use shell, not direct Python execution."""
    # This is to ensure backward compatibility
    cfg = HooksConfig(
        hooks=[
            HookConfig(
                name="explicit-python",
                event="session_start",
                command=f"{sys.executable} -c \"print('hello')\"",
                timeout=5,
            ),
        ]
    )
    mgr = HooksManager(config=cfg)

    results = mgr.run_hooks("session_start", session_id="test-session")
    assert len(results) == 1
    assert results[0].success is True
    assert "hello" in results[0].stdout


# ============================================================================
# Existing tests (kept for backward compatibility)
# ============================================================================


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
