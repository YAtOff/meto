# pyright: reportImportCycles=false

from __future__ import annotations

import json
import logging
import signal
from collections.abc import Generator
from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

from openai import OpenAI

from meto.agent.exceptions import AgentInterrupted, MaxStepsExceededError
from meto.agent.log import ReasoningLogger
from meto.agent.prompt import build_system_prompt
from meto.agent.tool_runner import run_tool  # pyright: ignore[reportImportCycles]
from meto.conf import settings

if TYPE_CHECKING:
    from meto.agent.agent import Agent

logger = logging.getLogger("agent")


@lru_cache(maxsize=1)
def _get_client() -> OpenAI:
    # Keep client creation in this module (per design), but do it lazily so
    # importing `meto.agent.loop` stays import-light.
    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "METO_LLM_API_KEY is not set. Configure it in .env or environment variables."
        )
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def run_agent_loop(prompt: str, agent: Agent) -> Generator[str, None, None]:
    """Run the agent loop for a single user prompt.

    In interactive mode, this function is called repeatedly and shares module
    state (`agent.session.history`) so the conversation continues.

    Raises:
        AgentInterrupted: If the user interrupts with Ctrl-C during execution.
    """

    if not prompt.strip():
        return

    # Set up signal handler for graceful Ctrl-C interruption
    interrupted = False

    def signal_handler(_signum: int, _frame: Any) -> None:
        nonlocal interrupted
        interrupted = True

    original_handler = signal.signal(signal.SIGINT, signal_handler)

    reasoning_logger = ReasoningLogger(agent.session.session_id, agent.name)
    try:
        reasoning_logger.log_user_input(prompt)
        agent.session.history.append({"role": "user", "content": prompt})
        agent.session.session_logger.log_user(prompt)

        for _turn in range(agent.max_turns):
            # Check for interruption at the start of each turn
            if interrupted:
                reasoning_logger.log_loop_completion("Interrupted by user (Ctrl-C)")
                raise AgentInterrupted("Agent loop interrupted by user")
            # The OpenAI SDK uses large TypedDict unions for `messages` and `tools`.
            # Our history is intentionally JSON-shaped, so treat these as dynamic.
            messages: Any = [
                {"role": "system", "content": build_system_prompt()},
                *agent.session.history,
            ]

            resp = _get_client().chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=messages,
                tools=cast(Any, agent.tools),
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
            agent.session.history.append(assistant_message)
            agent.session.session_logger.log_assistant(
                assistant_message["content"], assistant_message.get("tool_calls")
            )

            if assistant_content:
                yield assistant_content

            if not tool_calls:
                reasoning_logger.log_loop_completion("No more tool calls requested")
                return

            for tc in tool_calls:
                tc_any = tc
                if getattr(tc_any, "type", None) != "function":
                    continue

                fn = tc_any.function
                fn_name = getattr(fn, "name", None)
                if not isinstance(fn_name, str) or not agent.has_tool(fn_name):
                    agent.session.history.append(
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

                # Execute tool (logging happens inside the tool runner)
                tool_output = run_tool(
                    fn_name,
                    arguments,
                    reasoning_logger,
                    agent.session,
                    agent.session.skill_loader,
                )

                agent.session.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc_any.id,
                        "content": tool_output,
                    }
                )
                agent.session.session_logger.log_tool(tc_any.id, tool_output)

        reasoning_logger.log_loop_completion(f"Reached max turns ({agent.max_turns})")
        raise MaxStepsExceededError(f"Exceeded maximum of {agent.max_turns} turns")
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_handler)
        reasoning_logger.close()
