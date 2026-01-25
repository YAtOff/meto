import os
from pathlib import Path

# Base system prompt template.
# The final system prompt used for each model call is built by appending
# project memory/user instructions from AGENTS.md (see build_system_prompt()).
SYSTEM_PROMPT = """You are a CLI coding agent running at {cwd}.

You can use tools to do real work: a shell command runner and a directory listing tool.

Rules:
- Use manage_todos to track multi-step tasks (3+ steps)
- Mark todos in_progress before starting, completed when done
- Only ONE todo can be in_progress at a time
- Prefer acting via the tools over long explanations.
- When you need file context, read it using shell commands (don't guess).
- Keep outputs succinct; summarize what you learned.

Subagent pattern (via run_task tool):
- Use run_task for complex subtasks with isolated context
- Agent (name: description):
  - explore: Read-only (search, read, analyze) - returns summary
  - plan: Design-only (analyze, produce plan) - no modifications
  - code: Full access (implement features, fix bugs)
- Subagents run with fresh history, keep main conversation clean
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
