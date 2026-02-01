"""Unit tests for ReasoningLogger hook result logging."""

import json
from pathlib import Path

import pytest

from meto.agent.hooks import HookResult
from meto.agent.reasoning_log import ReasoningLogger
from meto.conf import Settings


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    """Create a Settings instance with temp log dir."""
    return Settings(
        LOG_DIR=tmp_path / "logs",
        SESSION_DIR=tmp_path / "sessions",
        AGENTS_DIR=tmp_path / ".meto" / "agents",
        COMMANDS_DIR=tmp_path / ".meto" / "commands",
        SKILLS_DIR=tmp_path / ".meto" / "skills",
        HOOKS_FILE=tmp_path / ".meto" / "hooks.yaml",
    )


@pytest.fixture
def reasoning_logger(tmp_settings: Settings, tmp_path: Path) -> ReasoningLogger:
    """Create a ReasoningLogger instance with temporary settings."""
    from unittest.mock import patch

    # Patch the global settings with our tmp_settings
    with patch("meto.agent.reasoning_log.settings", tmp_settings):
        logger = ReasoningLogger(session_id="test-session", agent_name="test-agent")
        yield logger
        logger.close()


@pytest.fixture
def sample_hook_result() -> HookResult:
    """Create a sample HookResult for testing."""
    return HookResult(
        hook_name="test-hook",
        success=True,
        exit_code=0,
        blocked=False,
        error=None,
        stdout="Hook executed successfully",
        stderr="",
    )


def get_log_entries(tmp_settings: Settings) -> list[dict]:
    """Helper to read all log entries from temp settings."""
    log_files = list(tmp_settings.LOG_DIR.glob("*.jsonl"))
    if not log_files:
        return []

    entries = []
    for log_file in log_files:
        lines = log_file.read_text().strip().split("\n")
        for line in lines:
            if line:
                entries.append(json.loads(line))
    return entries


def test_log_hook_result_session_start(
    reasoning_logger: ReasoningLogger, sample_hook_result: HookResult, tmp_settings: Settings
) -> None:
    """Test logging session_start hook results without tool context."""
    reasoning_logger.log_hook_result(
        event_type="session_start",
        result=sample_hook_result,
    )

    # Read the log file and verify the entry
    entries = get_log_entries(tmp_settings)
    assert len(entries) >= 1

    log_entry = entries[-1]
    assert log_entry["type"] == "hook"
    assert log_entry["event"] == "session_start"
    assert log_entry["hook_name"] == "test-hook"
    assert log_entry["success"] is True
    assert log_entry["exit_code"] == 0
    assert log_entry["blocked"] is False
    assert log_entry["error"] is None
    assert log_entry["stdout"] == "Hook executed successfully"
    assert log_entry["stderr"] == ""
    # Tool name and args should not be present for session_start
    assert "tool_name" not in log_entry
    assert "tool_args" not in log_entry


def test_log_hook_result_pre_tool_use(
    reasoning_logger: ReasoningLogger, sample_hook_result: HookResult, tmp_settings: Settings
) -> None:
    """Test logging pre_tool_use hook results with tool name and arguments."""
    tool_name = "shell"
    tool_args = {"command": "echo 'hello world'", "timeout": 30}

    reasoning_logger.log_hook_result(
        event_type="pre_tool_use",
        result=sample_hook_result,
        tool_name=tool_name,
        tool_args=tool_args,
    )

    # Read the log file and verify the entry
    entries = get_log_entries(tmp_settings)
    assert len(entries) >= 1

    log_entry = entries[-1]
    assert log_entry["type"] == "hook"
    assert log_entry["event"] == "pre_tool_use"
    assert log_entry["hook_name"] == "test-hook"
    assert log_entry["tool_name"] == tool_name
    assert "tool_args" in log_entry
    # Args should be summarized
    assert "command" in log_entry["tool_args"]
    assert isinstance(log_entry["tool_args"]["command"], str)


def test_log_hook_result_post_tool_use(
    reasoning_logger: ReasoningLogger, sample_hook_result: HookResult, tmp_settings: Settings
) -> None:
    """Test logging post_tool_use hook results with tool name only."""
    tool_name = "read_file"

    reasoning_logger.log_hook_result(
        event_type="post_tool_use",
        result=sample_hook_result,
        tool_name=tool_name,
    )

    # Read the log file and verify the entry
    entries = get_log_entries(tmp_settings)
    assert len(entries) >= 1

    log_entry = entries[-1]
    assert log_entry["type"] == "hook"
    assert log_entry["event"] == "post_tool_use"
    assert log_entry["hook_name"] == "test-hook"
    assert log_entry["tool_name"] == tool_name
    # Args should not be present for post_tool_use
    assert "tool_args" not in log_entry


def test_log_hook_result_truncation(
    reasoning_logger: ReasoningLogger, tmp_settings: Settings
) -> None:
    """Test that stdout/stderr are truncated to 1000 characters."""
    # Create a result with long output
    long_output = "x" * 1500  # Exceeds 1000 char limit

    hook_result = HookResult(
        hook_name="long-output-hook",
        success=True,
        exit_code=0,
        blocked=False,
        error=None,
        stdout=long_output,
        stderr=long_output,
    )

    reasoning_logger.log_hook_result(
        event_type="session_start",
        result=hook_result,
    )

    # Read the log file and verify truncation
    entries = get_log_entries(tmp_settings)
    log_entry = entries[-1]

    # 1000 chars of content + "... (truncated)" = 1015 total
    assert len(log_entry["stdout"]) == 1015
    assert "..." in log_entry["stdout"]
    assert "(truncated)" in log_entry["stdout"]
    assert len(log_entry["stderr"]) == 1015


def test_log_hook_result_args_summarization(
    reasoning_logger: ReasoningLogger, sample_hook_result: HookResult, tmp_settings: Settings
) -> None:
    """Test that tool arguments are summarized correctly."""
    long_string = "a" * 300  # Exceeds 200 char limit
    list_arg = list(range(100))  # Large list
    dict_arg = {"key" + str(i): "value" for i in range(50)}  # Large dict

    tool_args = {
        "long_string": long_string,
        "list_arg": list_arg,
        "dict_arg": dict_arg,
        "normal_arg": "normal value",
        "number_arg": 42,
    }

    reasoning_logger.log_hook_result(
        event_type="pre_tool_use",
        result=sample_hook_result,
        tool_name="test_tool",
        tool_args=tool_args,
    )

    # Read the log file and verify summarization
    entries = get_log_entries(tmp_settings)
    log_entry = entries[-1]

    summarized = log_entry["tool_args"]

    # Long string should be truncated to 200 chars
    # 200 chars of 'a' + "... (truncated)" = 215 total
    assert len(summarized["long_string"]) == 215
    assert "..." in summarized["long_string"]

    # List should show count
    assert summarized["list_arg"] == "<list with 100 items>"

    # Dict should show count
    assert summarized["dict_arg"] == "<dict with 50 items>"

    # Normal args should be preserved or truncated appropriately
    assert summarized["normal_arg"] == "normal value"
    assert summarized["number_arg"] == "42" or summarized["number_arg"] == 42


def test_log_hook_result_blocked_status(
    reasoning_logger: ReasoningLogger, tmp_settings: Settings
) -> None:
    """Test that blocked status is correctly logged."""
    hook_result = HookResult(
        hook_name="blocking-hook",
        success=True,
        exit_code=2,  # EXIT_BLOCK
        blocked=True,
        error=None,
        stdout="Tool blocked",
        stderr="",
    )

    reasoning_logger.log_hook_result(
        event_type="pre_tool_use",
        result=hook_result,
        tool_name="shell",
    )

    # Read the log file and verify blocked status
    entries = get_log_entries(tmp_settings)
    log_entry = entries[-1]

    assert log_entry["blocked"] is True
    assert log_entry["exit_code"] == 2


def test_log_hook_result_error_handling(
    reasoning_logger: ReasoningLogger, tmp_settings: Settings
) -> None:
    """Test that errors are correctly logged."""
    hook_result = HookResult(
        hook_name="failing-hook",
        success=False,
        exit_code=1,
        blocked=False,
        error="Hook execution failed",
        stdout="",
        stderr="Error occurred",
    )

    reasoning_logger.log_hook_result(
        event_type="session_start",
        result=hook_result,
    )

    # Read the log file and verify error handling
    entries = get_log_entries(tmp_settings)
    log_entry = entries[-1]

    assert log_entry["success"] is False
    assert log_entry["exit_code"] == 1
    assert log_entry["blocked"] is False
    assert log_entry["error"] == "Hook execution failed"
    assert log_entry["stderr"] == "Error occurred"


def test_truncate_output_no_truncation(reasoning_logger: ReasoningLogger) -> None:
    """Test _truncate_output with string under the limit."""
    short_string = "Hello, world!"
    result = reasoning_logger._truncate_output(short_string)
    assert result == short_string


def test_truncate_output_exact_limit(reasoning_logger: ReasoningLogger) -> None:
    """Test _truncate_output with string exactly at the limit."""
    exact_string = "x" * 1000
    result = reasoning_logger._truncate_output(exact_string)
    assert result == exact_string


def test_truncate_output_over_limit(reasoning_logger: ReasoningLogger) -> None:
    """Test _truncate_output with string over the limit."""
    long_string = "x" * 1100
    result = reasoning_logger._truncate_output(long_string)
    assert len(result) == 1015  # 1000 + "... (truncated)"
    assert result.endswith("... (truncated)")


def test_truncate_output_custom_limit(reasoning_logger: ReasoningLogger) -> None:
    """Test _truncate_output with custom max_length."""
    string = "x" * 150
    result = reasoning_logger._truncate_output(string, max_length=100)
    assert len(result) == 115  # 100 + "... (truncated)" which is 15 chars
    assert result.endswith("... (truncated)")


def test_summarize_args_empty(reasoning_logger: ReasoningLogger) -> None:
    """Test _summarize_args with empty dict."""
    result = reasoning_logger._summarize_args({})
    assert result == {}


def test_summarize_args_none_value(reasoning_logger: ReasoningLogger) -> None:
    """Test _summarize_args with None value."""
    result = reasoning_logger._summarize_args({"key": None})
    # None should be converted to string "None"
    assert result["key"] == "None"


def test_summarize_args_boolean_value(reasoning_logger: ReasoningLogger) -> None:
    """Test _summarize_args with boolean value."""
    result = reasoning_logger._summarize_args({"flag": True})
    assert result["flag"] == "True"


def test_log_hook_result_multiple_hooks(
    reasoning_logger: ReasoningLogger, tmp_settings: Settings
) -> None:
    """Test logging multiple hook results."""
    hook_results = [
        HookResult(
            hook_name="hook-1",
            success=True,
            exit_code=0,
            blocked=False,
            error=None,
            stdout="Output 1",
            stderr="",
        ),
        HookResult(
            hook_name="hook-2",
            success=False,
            exit_code=1,
            blocked=False,
            error="Error 2",
            stdout="",
            stderr="Error output",
        ),
    ]

    for result in hook_results:
        reasoning_logger.log_hook_result(
            event_type="session_start",
            result=result,
        )

    # Verify both entries are in the log
    hook_entries = [e for e in get_log_entries(tmp_settings) if e.get("type") == "hook"]

    assert len(hook_entries) >= 2

    # Check first hook
    assert any(e["hook_name"] == "hook-1" and e["success"] is True for e in hook_entries)

    # Check second hook
    assert any(
        e["hook_name"] == "hook-2" and e["success"] is False and e["error"] == "Error 2"
        for e in hook_entries
    )
