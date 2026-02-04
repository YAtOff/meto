# meto

A minimal coding agent CLI tool. AI agent runs tool-calling loop with multiple tools for command execution.

## Philosophy

**Multiple tools + ONE loop (tool-calling) = capable coding agent**

meto provides a streamlined interface for AI-assisted coding through a simple but powerful architecture: an LLM with access to various tools (shell execution, file operations, grep, web fetch, task management) running in a continuous tool-calling loop until the task is complete.

## Features

- **Interactive & One-Shot Modes**: Run interactively with a REPL or execute single commands
- **Tool-Calling Loop**: Autonomous agent that can execute commands, read/write files, search code, and more
- **Session Persistence**: All conversations saved as JSONL for easy resumption
- **Subagent Pattern**: Spawn isolated agents for subtasks with fresh context
- **Custom Agents**: Define specialized agents with specific tool permissions
- **Skills System**: Lazy-loaded domain expertise modules for on-demand knowledge injection
- **Plan Mode**: Systematic exploration and planning workflow before implementation
- **Hooks System**: Extend agent behavior with shell commands at lifecycle events
- **Slash Commands**: Interactive commands for session management and workflow shortcuts

## Installation

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Install from source

```bash
# Clone the repository
git clone <repository-url>
cd meto

# Install dependencies and run tests
just

# Or install as local tool
uv tool install --editable .
```

## Quick Start

### 1. Configure LLM Access

meto uses LiteLLM proxy for model-agnostic LLM access. Set up your environment:

```bash
# Create .env file
cat > .env << EOF
METO_LLM_API_KEY=your-api-key
METO_LLM_BASE_URL=model-api-endpoint
METO_DEFAULT_MODEL=model-name
EOF
```

### 2. Run Interactive Mode

```bash
# Start interactive session
uv run meto
```

### 3. One-Shot Mode

```bash
# Execute single command
uv run meto --one-shot --prompt "fix the bug in src/main.py"

# or
echo "fix the bug in src/main.py" | uv run meto --one-shot

# Skip permission prompts with --yolo flag
uv run meto --one-shot --yolo --prompt "fix the bug in src/main.py"
```

## Configuration

Environment variables (`.env` supported):

| Variable | Description | Default |
|----------|-------------|---------|
| `METO_LLM_API_KEY` | API key for LLM provider | - |
| `METO_LLM_BASE_URL` | LLM provider API endpoint URL | - |
| `METO_DEFAULT_MODEL` | Model identifier | - |
| `METO_MAIN_AGENT_MAX_TURNS` | Max iterations for main agent | `100` |
| `METO_SUBAGENT_MAX_TURNS` | Max iterations for subagents | `25` |
| `METO_TOOL_TIMEOUT_SECONDS` | Shell command timeout | `300` |
| `METO_MAX_TOOL_OUTPUT_CHARS` | Max tool output length | `50000` |
| `METO_AGENTS_DIR` | Custom agents directory | `.meto/agents` |
| `METO_SKILLS_DIR` | Skills directory | `.meto/skills` |
| `METO_PLAN_DIR` | Plan mode artifacts | `~/.meto/plans` |
| `METO_YOLO_MODE` | Skip permission prompts for tools | `false` |

### YOLO Mode

By default, meto prompts for permission before executing potentially dangerous operations (like shell commands). YOLO mode ("You Only Live Once") disables these safety prompts for faster, uninterrupted operation.

**Enable YOLO mode:**

```bash
# Via command-line flag
uv run meto --yolo

# Via environment variable
export METO_YOLO_MODE=true
uv run meto

# In .env file
echo "METO_YOLO_MODE=true" >> .env
```

**⚠️ Warning**: YOLO mode skips all permission checks. Only use this when you fully trust the agent's operations or are working in a safe/sandboxed environment.

## Core Concepts

### Agent Loop

1. User prompt → conversation history
2. LLM call with system prompt + history + available tools
3. If tool calls: execute tools, append results to history, loop back to step 2
4. If no tool calls: return final response

### Built-in Agents

- **code** (default): Full access to all tools for implementation
- **explore**: Read-only access for codebase exploration
- **plan**: Design-only agent for planning without execution
- **planner**: Specialized agent for plan mode workflow

### Session Modes

Modes customize prompt and UI behavior:

- **Plan Mode**: Systematic exploration and planning before implementation
  - Enter with `/plan` command
  - Creates structured plan file in `~/.meto/plans/`
  - Exit with `/done` or start implementation with `/implement`

### Tools Available

- **shell**: Execute bash/PowerShell commands
- **read_files**: Read file contents
- **write_file**: Create or overwrite files
- **edit_file**: Apply targeted edits to files
- **grep**: Search code with regex patterns
- **web_fetch**: Fetch and parse web content
- **run_task**: Spawn subagent for isolated subtasks
- **load_skill**: Load domain expertise modules on-demand
- **manage_todos***: Task tracking (create, update, list, get)

## Customization

### Custom Agents

Define specialized agents in `.meto/agents/{name}.md`:

```markdown
---
name: reviewer
description: Code review specialist
tools:
  - read_files
  - grep
  - web_fetch
---

You are an expert code reviewer. Focus on:
- Security vulnerabilities
- Performance issues
- Best practices
- Code maintainability
```

### Skills System

Create domain expertise modules in `.meto/skills/{skill-name}/SKILL.md`:

```markdown
---
name: commit-message
description: Generate conventional commit messages
---

# Commit Message Skill

You are an expert at writing clear, informative git commit messages...
```

Skills are lazy-loaded only when needed via the `load_skill` tool.

### Custom Commands

Add workflow shortcuts in `.meto/commands/{name}.md`:

```markdown
---
description: Review pull request changes
allowed-tools:
  - shell
  - read_files
  - grep
context: fork
---

Review the current pull request:
1. Analyze the diff
2. Check for common issues
3. Provide constructive feedback
```

Use with `/name [arguments]` in interactive mode.

### Hooks System

Extend agent behavior with shell commands at lifecycle events in `.meto/hooks.yaml`:

```yaml
hooks:
  - name: security-check
    event: pre_tool_use
    tools: [shell]
    command: scripts/check_shell_command.py
    timeout: 10
```

**Supported Events**:
- `session_start`: When agent session begins
- `pre_tool_use`: Before tool execution (can block with exit code 2)
- `post_tool_use`: After tool execution

## Interactive Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/export` | Export conversation history |
| `/compact` | Compact session history |
| `/todos` | Show task list |
| `/plan` | Enter plan mode |
| `/implement` | Exit plan mode and start implementation |
| `/done` | Exit current mode |
| `/exit`, `/quit` | Exit meto |

## Development

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

- `src/meto/cli.py` - CLI interface and interactive mode
- `src/meto/agent/agent_loop.py` - Main agent loop
- `src/meto/agent/agent.py` - Agent class factory
- `src/meto/agent/tool_runner.py` - Tool execution implementations
- `src/meto/agent/tool_schema.py` - Tool schemas (OpenAI format)
- `src/meto/agent/session.py` - Session persistence (JSONL)
- `src/meto/agent/loaders/` - Agent, skill, and frontmatter loaders
- `src/meto/agent/modes/` - Session mode system
- `src/meto/agent/hooks.py` - Hook system

Sessions persist as JSONL in `~/.meto/sessions/`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions welcome! Please check existing issues or open a new one to discuss changes.
