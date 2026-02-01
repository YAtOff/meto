# CLAUDE.md

This file provides guidance to Meto when working with code in this repository.

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
- `src/meto/agent/loaders/` - Consolidated loader modules
  - `agent_loader.py` - Built-in agents + user agent loader (YAML frontmatter + markdown)
  - `skill_loader.py` - Skills discovery, lazy loading, and content management
  - `frontmatter.py` - YAML frontmatter parsing
- `src/meto/agent/modes/` - Session mode system
  - `base.py` - Base mode interface
  - `plan.py` - Plan mode for systematic exploration and planning
- `src/meto/agent/tool_schema.py` - Tool schemas (OpenAI function calling format)
- `src/meto/agent/tool_runner.py` - Tool execution implementations (shell, file ops, grep, fetch, todos, subagents, skills)
- `src/meto/agent/shell.py` - Shell command execution (bash/PowerShell)
- `src/meto/agent/session.py` - Session persistence (JSONL), history loading, session logging
- `src/meto/agent/system_prompt.py` - System prompt building with AGENTS.md support
- `src/meto/agent/history_export.py` - History export functionality
- `src/meto/agent/hooks.py` - Hook system for event interception
- `src/meto/agent/reasoning_log.py` - Reasoning logging
- `src/meto/agent/todo.py` - Structured task tracking with constraints
- `src/meto/agent/commands.py` - Interactive slash commands (e.g. `/help`, `/export`, `/compact`, `/todos`)
- `src/meto/agent/exceptions.py` - Custom exceptions
- `src/meto/agent/permission_policy.py` - Permission handling
- `src/meto/conf.py` - Pydantic settings from `METO_*` env vars

### Agent Loop Pattern
1. User prompt → history
2. LLM call with system prompt + history + tools
3. If tool_calls: execute tools via tool_runner, append results to history, loop
4. If no tool_calls: return

**Subagent pattern**: For isolated subtasks, spawn new agent via `run_task` tool with fresh session history.

### Session Modes
Modes attach to a `Session` to customize prompt/UI behavior:
- **Plan mode**: Guides systematic exploration and planning, saves plan to file
  - Uses `planner` agent (design-only)
  - Creates plan file in `~/.meto/plans/`
  - `/implement` starts implementation, `/done` exits

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
- `METO_SKILLS_DIR` - Directory for skill directories (default: .meto/skills)
- `METO_PLAN_DIR` - Directory for plan mode artifacts (default: ~/.meto/plans)

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

### Skills System
Skills are self-contained domain expertise modules loaded on-demand via the `load_skill` tool:

**Directory Structure**:
```
.meto/skills/
├── commit-message/
│   └── SKILL.md
├── pdf/
│   ├── SKILL.md
│   └── scripts/
└── code-review/
    └── SKILL.md
```

**SKILL.md Format**:
- YAML frontmatter with `name` (optional, defaults to directory name) and `description` (required)
- Markdown body contains detailed domain instructions (~2000 tokens)
- Can reference additional resources in skill directory

**Key Characteristics**:
- **Lazy Loading**: Metadata loaded at startup, full content loaded only when `load_skill` tool is called
- **Progressive Disclosure**: Skill descriptions shown in tool schema, full content injected as tool result
- **XML Wrapping**: Content wrapped in `<skill-loaded name="...">...</skill-loaded>` tags for clarity
- **Per-Session Caching**: Loaded skills cached in memory to avoid re-reading files
- **No Tool Restrictions**: Skills provide knowledge, not execution context (unlike agents)

**Differences from Commands and Agents**:
| Feature | Commands | Agents | Skills |
|---------|----------|--------|--------|
| Purpose | Workflow shortcuts | Execution contexts | Domain expertise |
| Location | `.meto/commands/*.md` | `.meto/agents/*.md` | `.meto/skills/*/SKILL.md` |
| When Applied | Interactive mode | Subagent spawning | On-demand via tool |
| Knowledge Scope | Workflow orchestration | Tool permissions + prompt | Deep domain knowledge |

**Example Skill** (`.meto/skills/commit-message/SKILL.md`):
```markdown
---
name: commit-message
description: Generate conventional commit messages following best practices
---

# Commit Message Skill

You are an expert at writing clear, informative git commit messages...
```

### Key Architecture Notes
- Tool schema (`tool_schema.py`) MUST stay import-light, separate from runtime (`tool_runner.py`)
- Agent loop uses OpenAI SDK via LiteLLM proxy (model-agnostic)
- Shell tool prefers bash (Git Bash/WSL), falls back to PowerShell on Windows
- Sessions persist as JSONL in `~/.meto/sessions/`
- Todo system enforces: max 20 items, only one in_progress at a time
- Built-in agents: explore (read-only), plan (design-only), code (full access), planner (planning mode)
- Skills system: lazy-loaded expertise modules injected via tool results (preserves prompt cache)
- Modes system: extensible session states for different workflows (plan mode currently implemented)
