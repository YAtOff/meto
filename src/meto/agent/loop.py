from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from openai import OpenAI

from meto.agent.tools import AVAILABLE_TOOLS, TOOLS, run_tool
from meto.conf import settings

# Core idea:
#   ONE tool (shell) + ONE loop (tool-calling) => a capable coding agent.
#
# Notes:
# - We keep the public API minimal: `run_agent_loop(prompt: str, history: list[dict[str, Any]]) -> None`.
# - Interactive mode (meto with no args) runs in a single process, so we keep
#   history in-module for a conversational experience.


# Base system prompt template.
# The final system prompt used for each model call is built by appending
# project memory/user instructions from AGENTS.md (see build_system_prompt()).
SYSTEM_PROMPT = """You are a CLI coding agent running at {cwd}.

You can use tools to do real work: a shell command runner and a directory listing tool.

Rules:
- Prefer acting via the tools over long explanations.
- When you need file context, read it using shell commands (don't guess).
- Keep outputs succinct; summarize what you learned.

Subagent pattern (context isolation via process spawning):
- For complex, self-contained subtasks, run a subagent by calling this tool to execute:
        meto --one-shot
    and pass it a prompt via stdin.
    - PowerShell (here-string):
            @'
            <task>
            '@ | meto --one-shot
    - bash (heredoc):
        meto --one-shot <<'EOF'
        <task>
        EOF
    The subagent runs with fresh history and returns a summary.
"""


def build_system_prompt() -> str:
    """Build the system prompt.

    Appends project memory/user instructions from AGENTS.md in the current
    working directory.

    Note: This intentionally does not cache; it re-reads AGENTS.md each call.
    """

    cwd = os.getcwd()
    prompt = SYSTEM_PROMPT.format(cwd=cwd)

    agents_path = Path(cwd) / "AGENTS.md"
    begin = "----- BEGIN AGENTS.md (project instructions) -----"
    end = "----- END AGENTS.md -----"

    try:
        agents_text = agents_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        agents_text = f"[AGENTS.md missing at: {agents_path}]"
    except OSError as e:
        agents_text = f"[AGENTS.md unreadable at: {agents_path} — {e}]"

    # Always include the delimiter block so the model reliably knows where the
    # project memory starts/ends.
    return "\n".join([prompt.rstrip(), "", begin, agents_text.rstrip(), end, ""])


client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def run_agent_loop(prompt: str, history: list[dict[str, Any]]) -> None:
    """Run the agent loop for a single user prompt.

    In interactive mode, this function is called repeatedly and shares module
    state (`history`) so the conversation continues.
    """

    if not prompt.strip():
        return

    history.append({"role": "user", "content": prompt})

    for _ in range(settings.MAX_TURNS):
        # The OpenAI SDK uses large TypedDict unions for `messages` and `tools`.
        # Our history is intentionally JSON-shaped, so treat these as dynamic.
        messages: Any = [
            {"role": "system", "content": build_system_prompt()},
            *history,
        ]

        resp = client.chat.completions.create(
            model=settings.DEFAULT_MODEL,
            messages=messages,
            tools=cast(Any, TOOLS),
        )

        msg = resp.choices[0].message
        assistant_content = msg.content or ""
        # `tool_calls` typing varies by model/SDK version; treat as dynamic.
        tool_calls: list[Any] = list(getattr(msg, "tool_calls", None) or [])

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_content,
        }
        if tool_calls:
            assistant_message["tool_calls"] = [tc.model_dump() for tc in tool_calls]
        history.append(assistant_message)

        if assistant_content:
            print(assistant_content)

        if not tool_calls:
            return

        for tc in tool_calls:
            tc_any = tc
            if getattr(tc_any, "type", None) != "function":
                continue

            fn = tc_any.function
            fn_name = getattr(fn, "name", None)
            if not isinstance(fn_name, str) or fn_name not in AVAILABLE_TOOLS:
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_any.id,
                        "content": f"Unknown tool: {fn_name}",
                    }
                )
                continue

            try:
                arguments_raw = getattr(fn, "arguments", None) or "{}"
                arguments_any = json.loads(arguments_raw)
            except (TypeError, json.JSONDecodeError):
                arguments_any = {}

            if isinstance(arguments_any, dict):
                arguments = cast(dict[str, Any], arguments_any)
            else:
                arguments = {}

            tool_output = run_tool(fn_name, arguments)

            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_any.id,
                    "content": tool_output,
                }
            )

    print(f"(stopped after {settings.MAX_TURNS} turns; consider increasing METO_MAX_TURNS)")
