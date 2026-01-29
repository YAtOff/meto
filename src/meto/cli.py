"""Command-line interface for meto"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Annotated

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.enums import EditingMode

from meto.agent.agent import Agent
from meto.agent.agent_loop import run_agent_loop
from meto.agent.commands import handle_slash_command
from meto.agent.exceptions import AgentInterrupted
from meto.agent.session import Session, get_session_info, list_session_files
from meto.conf import settings

app = typer.Typer(add_completion=False)


def _strip_single_trailing_newline(text: str) -> str:
    """Strip exactly one trailing newline sequence from stdin-style input.

    Useful for one-shot mode where stdin often ends with a newline
    (e.g. `echo "..." | meto --one-shot`). Preserves all other whitespace.
    """
    if text.endswith("\r\n"):
        return text[:-2]
    if text.endswith("\n"):
        return text[:-1]
    return text


def interactive_loop(
    prompt_text: str = ">>> ",
    session: Session | None = None,
    yolo_mode: bool = False,
) -> None:
    """Run interactive prompt loop with slash command and agent execution."""
    session = session or Session()
    main_agent = Agent.main(session, yolo_mode=yolo_mode)
    prompt_session = PromptSession(editing_mode=EditingMode.EMACS)

    while True:
        # Dynamic prompt based on active session mode
        current_prompt = (
            session.mode.prompt_prefix(prompt_text or ">>> ")
            if session.mode
            else prompt_text or ">>> "
        )

        try:
            user_input = prompt_session.prompt(current_prompt)
        except (EOFError, KeyboardInterrupt):
            return

        # Handle slash commands
        was_handled, cmd_result = handle_slash_command(user_input, session)

        if was_handled:
            if cmd_result:
                try:
                    # Choose agent based on context
                    if cmd_result.context == "fork":
                        agent = (
                            Agent.subagent(cmd_result.agent, yolo_mode=yolo_mode)
                            if cmd_result.agent
                            else Agent.fork(cmd_result.allowed_tools or "*", yolo_mode=yolo_mode)
                        )
                    else:
                        agent = main_agent

                    for output in run_agent_loop(cmd_result.prompt, agent):
                        print(output)
                except AgentInterrupted:
                    print("\n[Agent interrupted]")
            continue

        # No slash command, run agent loop with user input
        try:
            for output in run_agent_loop(user_input, main_agent):
                print(output)
        except AgentInterrupted:
            print("\n[Agent interrupted]")


@app.callback(invoke_without_command=True)
def run(
    ctx: typer.Context,
    one_shot: Annotated[
        bool,
        typer.Option(
            "--one-shot",
            help="Read the prompt from stdin, run the agent loop with it, and exit.",
        ),
    ] = False,
    session_id: Annotated[
        str | None,
        typer.Option(
            "--session",
            help="Resume session by ID (format: timestamp-randomsuffix)",
        ),
    ] = None,
    yolo: Annotated[
        bool | None,
        typer.Option(
            "--yolo",
            help="Skip permission prompts for tools (default: from YOLO_MODE setting).",
        ),
    ] = None,
) -> None:
    """Run meto."""

    if ctx.invoked_subcommand is not None:
        return

    session = Session(sid=session_id) if session_id else Session()
    yolo_mode = yolo if yolo is not None else settings.YOLO_MODE

    if one_shot:
        text = _strip_single_trailing_newline(sys.stdin.read())
        agent = Agent.main(session, yolo_mode=yolo_mode)
        try:
            for output in run_agent_loop(text, agent):
                print(output)
        except AgentInterrupted:
            print("\n[Agent interrupted]", file=sys.stderr)
            raise typer.Exit(code=130) from None
        raise typer.Exit(code=0)

    interactive_loop(session=session, yolo_mode=yolo_mode)


@app.command()
def sessions(
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Max sessions to show"),
    ] = 10,
) -> None:
    """List available sessions."""
    session_files = list_session_files()[:limit]

    if not session_files:
        print("No sessions found.")
        return

    print(f"{'Session ID':<30} {'Created':<20} {'Messages':<10} {'Size':<10}")
    print("-" * 75)
    for path in session_files:
        info = get_session_info(path)
        created = datetime.fromisoformat(info["created"]).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{info['id']:<30} {created:<20} {info['message_count']:<10} {info['size']:<10}")


def main() -> None:
    app()
