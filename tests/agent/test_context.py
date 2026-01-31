from __future__ import annotations

import json
from pathlib import Path

import pytest

from meto.agent.context import dump_agent_context, get_context_summary, save_agent_context


def _sample_history() -> list[dict[str, object]]:
    return [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": "hi",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "type": "function",
                    "function": {"name": "list_dir", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "tc_1", "content": "ok"},
    ]


@pytest.mark.parametrize("fmt", ["json", "pretty_json", "markdown", "text"])
def test_dump_agent_context_formats(fmt: str) -> None:
    out = dump_agent_context(_sample_history(), output_format=fmt)
    assert isinstance(out, str)
    assert out


def test_dump_agent_context_excludes_system_when_include_system_false() -> None:
    out = dump_agent_context(_sample_history(), output_format="json", include_system=False)
    parsed = json.loads(out)
    roles = [m["role"] for m in parsed]
    assert "system" not in roles


def test_save_agent_context_writes_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = tmp_path / "ctx.json"
    save_agent_context(_sample_history(), target, output_format="json")
    assert target.exists()
    assert json.loads(target.read_text("utf-8"))


def test_get_context_summary_returns_stats_dict() -> None:
    summary = get_context_summary(_sample_history())

    assert isinstance(summary, dict)
    assert summary["total_messages"] == 4
    assert summary["user_messages"] == 1
    assert summary["assistant_messages"] == 1
    assert summary["tool_messages"] == 1
    assert isinstance(summary["unique_tools_used"], list)
    assert "list_dir" in summary["unique_tools_used"]
    assert "project_instructions" in summary
