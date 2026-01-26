# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**meto** is a minimal coding agent CLI tool. AI agent runs tool-calling loop with multiple tools for command execution.

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

**Core philosophy**: Multiple tools + ONE loop (tool-calling) = capable coding agent.

### Components
- `src/meto/cli.py` - CLI interface (Typer), interactive mode (prompt-toolkit), one-shot mode
- `src/meto/agent/agent_loop.py` - Main agent loop: LLM calls, tool execution, history management
- `src/meto/agent/agent.py` - Agent class with main/subagent factory methods
- `src/meto/agent/agent_loader.py` - User-defined agent loader (YAML frontmatter + markdown)
- `src/meto/agent/agent_registry.py` - Built-in agents + user agent merging
- `src/meto/agent/tool_schema.py` - Tool schemas (OpenAI function calling format)
- `src/meto/agent/tool_runner.py` - Tool execution implementations (shell, file ops, grep, fetch, todos, subagents)
- `src/meto/agent/session.py` - Session persistence (JSONL), history loading, session logging
- `src/meto/agent/todo.py` - Structured task tracking with constraints
- `src/meto/agent/commands.py` - Interactive slash commands (e.g. `/help`, `/export`, `/compact`, `/todos`)
- `src/meto/agent/context.py` - Context export formats and summary helpers
- `src/meto/agent/prompt.py` - System prompt building with AGENTS.md support
- `src/meto/conf.py` - Pydantic settings from `METO_*` env vars

### Agent Loop Pattern
1. User prompt → history
2. LLM call with system prompt + history + tools
3. If tool_calls: execute tools via tool_runner, append results to history, loop
4. If no tool_calls: return

**Subagent pattern**: For isolated subtasks, spawn new agent via `run_task` tool with fresh session history.

### Configuration
Environment variables (`.env` supported):
- `METO_LLM_API_KEY` - API key for LiteLLM proxy
- `METO_LLM_BASE_URL` - LiteLLM proxy URL (default: http://localhost:4444)
- `METO_DEFAULT_MODEL` - Model (default: gpt-4.1)
- `METO_MAIN_AGENT_MAX_TURNS` - Max iterations for main agent (default: 100)
- `METO_SUBAGENT_MAX_TURNS` - Max iterations for subagents (default: 25)
- `METO_TOOL_TIMEOUT_SECONDS` - Shell timeout (default: 300)
- `METO_MAX_TOOL_OUTPUT_CHARS` - Max output (default: 50000)
- `METO_AGENTS_DIR` - Directory for user-defined agents (default: .meto/agents)

### Custom Commands
Slash commands can be defined as Markdown files in `.meto/commands/{name}.md`:
- Frontmatter with `allowed-tools` restricts available tools
- `description` field shown in `/help`
- File content becomes the agent prompt
- Arguments appended as `[Command arguments: ...]`

### User-Defined Agents
Custom agents can be defined as Markdown files in `.meto/agents/{name}.md`:
- YAML frontmatter with `description`, `tools`, optional `name` and `prompt`
- Markdown body used as system prompt if `prompt` not in frontmatter
- User agents override built-in agents with same name
- See `AGENTS.md` for full documentation and examples

### Key Architecture Notes
- Tool schema (`tool_schema.py`) MUST stay import-light, separate from runtime (`tool_runner.py`)
- Agent loop uses OpenAI SDK via LiteLLM proxy (model-agnostic)
- Shell tool prefers bash (Git Bash/WSL), falls back to PowerShell on Windows
- Sessions persist as JSONL in `~/.meto/sessions/`
- Todo system enforces: max 20 items, only one in_progress at a time
- Built-in agents: explore (read-only), plan (design-only), code (full access)
