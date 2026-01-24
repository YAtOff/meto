"""Command-line interface for meto"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Annotated

import typer
from prompt_toolkit import PromptSession
from prompt_toolkit.enums import EditingMode

from meto.agent import run_agent_loop
from meto.agent.commands import handle_slash_command
from meto.agent.session import Session, get_session_info, list_session_files

app = typer.Typer(add_completion=False)


def _strip_single_trailing_newline(text: str) -> str:
    # When piping input (e.g. echo), stdin usually ends with a trailing newline.
    # Strip exactly one trailing newline sequence, but preserve all other
    # whitespace and internal newlines.
    if text.endswith("\r\n"):
        return text[:-2]
    if text.endswith("\n"):
        return text[:-1]
    return text


def interactive_loop(prompt_text: str = ">>> ", session: Session | None = None) -> None:
    """Run interactive prompt loop with slash command and agent execution."""
    if session is None:
        session = Session()

    prompt_session: PromptSession[str] = PromptSession(editing_mode=EditingMode.EMACS)
    while True:
        try:
            user_input: str = prompt_session.prompt(prompt_text)
        except (EOFError, KeyboardInterrupt):
            # Exit cleanly on Ctrl+Z/Ctrl+D (EOF) or Ctrl+C.
            return

        # Handle slash commands
        was_handled, custom_prompt = handle_slash_command(user_input, session)

        if was_handled:
            # If custom command provided a prompt, run agent loop with it
            if custom_prompt:
                run_agent_loop(custom_prompt, session)
            # Otherwise, built-in command was executed, continue to next iteration
            continue

        # No slash command, run agent loop with user input
        run_agent_loop(user_input, session)


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
) -> None:
    """Run meto."""

    # Typer (Click) always invokes the callback, even when a subcommand is
    # provided. `invoke_without_command=True` only controls whether the callback
    # runs when *no* subcommand is given. Guard here to avoid accidentally
    # starting interactive mode when the user is running a subcommand.
    if ctx.invoked_subcommand is not None:
        return

    if one_shot:
        text = _strip_single_trailing_newline(sys.stdin.read())
        agent_session = Session(session_id) if session_id else Session()
        run_agent_loop(text, agent_session)
        raise typer.Exit(code=0)

    interactive_loop(session=Session(session_id) if session_id else None)


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
