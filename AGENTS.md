# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**meto** is a minimal coding agent CLI tool. AI agent runs tool-calling loop with ONE tool (shell) for command execution.

## Development Commands

```bash
# Primary workflows (via just)
just              # install + lint + test
just install      # sync dependencies
just lint         # ruff format + check
just test         # pytest
just build        # build wheel
just clean        # remove build artifacts

# Direct commands
uv run pytest                    # run tests
uv run python devtools/lint.py   # lint
uv build                         # build
uv tool install --editable .     # install as local tool
```

## Architecture

**Core philosophy**: ONE tool (shell) + ONE loop (tool-calling) = capable coding agent.

### Components
- `src/meto/cli.py` - CLI interface (Typer), interactive mode (prompt-toolkit), one-shot mode
- `src/meto/agent/loop.py` - Main agent loop: LLM calls, tool execution, history management
- `src/meto/agent/context.py` - Conversation history serialization, export formats, and `/context` summary helpers
- `src/meto/agent/commands.py` - Interactive slash commands (e.g. `/help`, `/export`, `/compact`, `/context`)
- `src/meto/agent/tools.py` - Shell tool: auto-selects bash (Git Bash/WSL) or PowerShell
- `src/meto/conf.py` - Pydantic settings from `METO_*` env vars

### Agent Loop Pattern
1. User prompt → history
2. LLM call with system prompt + history + tools
3. If tool_calls: execute shell, append results to history, loop
4. If no tool_calls: return

**Subagent pattern**: For isolated subtasks, spawn new meto instance via `meto --one-shot` with prompt via stdin (PowerShell here-string `@'...' @` or bash heredoc).

### Configuration
Environment variables (`.env` supported):
- `METO_LLM_API_KEY` - API key for LiteLLM proxy
- `METO_LLM_BASE_URL` - LiteLLM proxy URL (default: http://localhost:4444)
- `METO_DEFAULT_MODEL` - Model (default: gpt-4.1)
- `METO_MAX_TURNS` - Max iterations (default: 25)
- `METO_TOOL_TIMEOUT_SECONDS` - Shell timeout (default: 300)
- `METO_MAX_TOOL_OUTPUT_CHARS` - Max output (default: 50000)

### Key Implementation Details
- History kept in-module for interactive mode (conversational)
- OpenAI SDK via LiteLLM proxy (model-agnostic)
- Shell tool prefers bash, falls back to PowerShell on Windows
- Public API: `run_agent_loop(prompt: str, history: list) -> None`
