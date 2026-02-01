import json
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

import typer

app = typer.Typer(add_completion=False)

PROMPT_TEMPLATE = """<context>
{input_dir}/plan.md is a plan for the feature that should be implemented.
{input_dir}/progress.json is the progress on the work on the feature.
</context>
<task>
Pick the first pending task from the progress file and implement it.
Then commit the changes and mark the task as complete in the progress file.
</task>
"""
PROGRESS_FILE = "progress.json"


class Task(TypedDict):
    id: int
    description: str
    status: str


class Progress(TypedDict):
    tasks: list[Task]


def run_meto(prompt: str | None = None) -> None:
    """Run meto in one-shot mode with the given prompt."""

    process = subprocess.Popen(
        ["python", "-m", "meto", "--one-shot"],
        executable=sys.executable,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    stdout, _ = process.communicate(input=prompt)
    print(stdout, flush=True)


def get_tasks(input_dir: str) -> list[Task]:
    """Extract pending tasks from the progress file."""
    progress_file = Path(input_dir) / PROGRESS_FILE
    with progress_file.open("r") as file:
        progress_data: Progress = json.load(file)
        return progress_data.get("tasks", [])


@app.command()
def run_ralph_loop(input_dir: str) -> None:
    """Run the Ralph loop."""

    tasks = get_tasks(input_dir=input_dir)
    while tasks and any(task.get("status") == "pending" for task in tasks):
        prompt = PROMPT_TEMPLATE.format(input_dir=input_dir)
        run_meto(prompt=prompt)
        tasks = get_tasks(input_dir=input_dir)


if __name__ == "__main__":
    app()
