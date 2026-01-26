"""Backwards-compatible tool API.

Tool schemas live in `meto.agent.tool_schema`.
Tool runtime/execution lives in `meto.agent.tool_runner`.

This module exists to preserve the historic import paths:
  - `from meto.agent.tools import TOOLS`
  - `from meto.agent.tools import run_tool`

New code should prefer importing from the schema/runtime modules directly.
"""

from __future__ import annotations

from typing import Any

from meto.agent.session import Session
from meto.agent.subagent import execute_task
from meto.agent.tool_runner import DefaultToolRunner

_DEFAULT_RUNNER = DefaultToolRunner(subagent_executor=execute_task)


def run_tool(
    tool_name: str,
    parameters: dict[str, Any],
    logger: Any | None = None,
    session: Session | None = None,
) -> str:
    return _DEFAULT_RUNNER.run_tool(tool_name, parameters, logger, session)
