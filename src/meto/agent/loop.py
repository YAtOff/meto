from __future__ import annotations

import json
import logging
from typing import Any, cast

from openai import OpenAI

from meto.agent.log import ReasoningLogger
from meto.agent.prompt import build_system_prompt
from meto.agent.session import Session
from meto.agent.tools import AVAILABLE_TOOLS, TOOLS, run_tool
from meto.conf import settings

logger = logging.getLogger("agent")
client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def run_agent_loop(prompt: str, session: Session, agent_name: str = "main") -> None:
    """Run the agent loop for a single user prompt.

    In interactive mode, this function is called repeatedly and shares module
    state (`session.history`) so the conversation continues.
    """

    if not prompt.strip():
        return

    reasoning_logger = ReasoningLogger(session.session_id, agent_name)
    reasoning_logger.log_user_input(prompt)
    session.history.append({"role": "user", "content": prompt})
    session.session_logger.log_user(prompt)

    for _turn in range(settings.MAX_TURNS):
        # The OpenAI SDK uses large TypedDict unions for `messages` and `tools`.
        # Our history is intentionally JSON-shaped, so treat these as dynamic.
        messages: Any = [
            {"role": "system", "content": build_system_prompt()},
            *session.history,
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

        # Log model reasoning and response
        reasoning_logger.log_model_response(resp, settings.DEFAULT_MODEL)

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_content,
        }
        if tool_calls:
            assistant_message["tool_calls"] = [tc.model_dump() for tc in tool_calls]
        session.history.append(assistant_message)
        session.session_logger.log_assistant(
            assistant_message["content"], assistant_message.get("tool_calls")
        )

        if assistant_content:
            print(assistant_content)

        if not tool_calls:
            reasoning_logger.log_loop_completion("No more tool calls requested")
            return

        for tc in tool_calls:
            tc_any = tc
            if getattr(tc_any, "type", None) != "function":
                continue

            fn = tc_any.function
            fn_name = getattr(fn, "name", None)
            if not isinstance(fn_name, str) or fn_name not in AVAILABLE_TOOLS:
                session.history.append(
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
            except (TypeError, json.JSONDecodeError) as e:
                arguments_any = {}
                logger.error(
                    f"[{reasoning_logger.session_id}] Failed to parse arguments for {fn_name}: {e}"
                )

            if isinstance(arguments_any, dict):
                arguments = cast(dict[str, Any], arguments_any)
            else:
                arguments = {}

            # Execute tool (logging happens inside run_tool)
            tool_output = run_tool(fn_name, arguments, reasoning_logger)

            session.history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc_any.id,
                    "content": tool_output,
                }
            )
            session.session_logger.log_tool(tc_any.id, tool_output)

    reasoning_logger.log_loop_completion(f"Reached max turns ({settings.MAX_TURNS})")
    print(f"(stopped after {settings.MAX_TURNS} turns; consider increasing METO_MAX_TURNS)")
