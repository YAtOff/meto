"""Plan mode implementation.

Plan mode guides the model to explore and produce a step-by-step plan which is
saved to a file in `settings.PLAN_DIR`.

Note: tool restrictions are not enforced at runtime; plan mode is a prompting
and UX feature. Permissions are handled separately by `permission_policy`.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path
from typing import override

from meto.agent.modes.base import ModeExitResult, SessionMode
from meto.conf import settings


def _generate_plan_filename(now: datetime | None = None) -> str:
    """Generate a unique plan filename."""

    ts = (now or datetime.now(tz=UTC)).strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=6))
    return f"plan-{ts}-{suffix}.md"


class PlanMode(SessionMode):
    """Mode for systematic exploration and planning."""

    plan_file: Path | None

    def __init__(self) -> None:
        self.plan_file = None

    @property
    @override
    def name(self) -> str:
        return "plan"

    @property
    @override
    def agent_name(self) -> str | None:
        return "planner"

    @override
    def prompt_prefix(self, default_prompt: str) -> str:
        del default_prompt
        return "[PLAN] >>> "

    @override
    def system_prompt_fragment(self) -> str | None:
        plan_file = self.plan_file or "PLAN_FILE_NOT_SET"
        return f"""

----- PLAN MODE ACTIVE -----
You are in PLAN MODE. Your goal is to create a plan and save it to a file.

PLAN FILE: {plan_file}

CRITICAL: You MUST save your final plan to this file using the Write tool.

Workflow:
1. Use explore/plan agents to understand the codebase
2. Design implementation with numbered steps
3. Write the plan to: {plan_file}
4. Use /implement to start implementation, or /done to exit plan mode

- Use run_task tool with explore/plan agents for systematic planning
- Do NOT make file modifications during planning (except the plan file)
- At the end of each plan, give me a list of unresolved questions to answer, if any.
- Your final action MUST be writing the plan to {plan_file}
----- END PLAN MODE -----"""

    @override
    def enter(self, session: object) -> None:
        del session
        self.plan_file = settings.PLAN_DIR / _generate_plan_filename()

    @override
    def exit(self, session: object) -> ModeExitResult:
        del session
        plan_file = self.plan_file
        plan_content: str | None = None

        if plan_file and plan_file.exists():
            try:
                plan_content = plan_file.read_text(encoding="utf-8")
            except OSError:
                plan_content = None

        followup = None
        if plan_file and plan_content:
            followup = f"""FOLLOW THE PLAN stored in: {plan_file}

Read the plan file and follow the implementation steps defined in it.

Use the Read tool to read the full plan file and implement the steps."""

        return ModeExitResult(
            artifact_path=plan_file,
            artifact_content=plan_content,
            followup_system_message=followup,
        )
