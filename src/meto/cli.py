"""Command-line interface for meto.

Running modes:
- No args: starts interactive mode.
- --one-shot: reads the prompt from stdin, prints it, and exits.
"""

from __future__ import annotations

import sys
from typing import Annotated, Any

import typer
from prompt_toolkit import prompt

from meto.agent import run_agent_loop

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


def interactive_loop(prompt_text: str = ">>> ") -> None:
    history: list[dict[str, Any]] = []
    while True:
        try:
            user_input = prompt(prompt_text)
        except (EOFError, KeyboardInterrupt):
            # Exit cleanly on Ctrl+Z/Ctrl+D (EOF) or Ctrl+C.
            return

        run_agent_loop(user_input, history)


@app.callback(invoke_without_command=True)
def run(
    one_shot: Annotated[
        bool,
        typer.Option(
            "--one-shot",
            help="Read the prompt from stdin, run the agent loop with it, and exit.",
        ),
    ] = False,
) -> None:
    """Run meto."""

    if one_shot:
        text = _strip_single_trailing_newline(sys.stdin.read())
        run_agent_loop(text, [])
        raise typer.Exit(code=0)

    interactive_loop()


def main() -> None:
    app()
