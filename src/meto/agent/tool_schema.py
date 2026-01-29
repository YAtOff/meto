from __future__ import annotations

import copy
from typing import Any

# Model-facing tool schemas (OpenAI function calling / tools API).
#
# Important architectural rule:
# - This module must stay import-light and must not import tool runtime code.
# - Tool execution lives in `meto.agent.tool_runner`.

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "shell",
            "description": (
                "Execute a shell command and return its output. "
                "Use it to inspect files, edit files, run tests, etc. "
                "For complex subtasks, spawn a subagent by running: meto --one-shot"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute.",
                    }
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": (
                "List directory contents with structured output showing names, types, sizes, and timestamps. "
                "Use this for browsing the filesystem structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (defaults to current working directory if empty).",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list subdirectories recursively.",
                        "default": False,
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files and directories (those starting with a dot).",
                        "default": False,
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file and return them as text. "
                "Use this for reading configuration files, source code, or any text file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write content to a file. Creates parent directories if needed. "
                "Use this for creating or modifying files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file.",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": (
                "Search for a text pattern in files within a directory. "
                "Uses ripgrep (rg) if available, otherwise grep or Select-String. "
                "Returns matching lines with file paths and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern to search for (supports regex).",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory path to search in (defaults to current directory).",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Whether to ignore case when matching.",
                        "default": False,
                    },
                },
                "required": ["pattern"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch",
            "description": (
                "Fetch web resources via HTTP GET. Returns response body as text. "
                "Handles redirects automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Max response bytes (default: 100000)",
                    },
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manage_todos",
            "description": (
                "Update the todo list. Use to plan and track progress on multi-step todos. "
                "Mark todos in_progress before starting, completed when done. "
                "Only ONE todo can be in_progress at a time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "Complete list of todos (replaces existing)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {
                                    "type": "string",
                                    "description": "Todo description",
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["pending", "in_progress", "completed"],
                                    "description": "Todo status",
                                },
                                "activeForm": {
                                    "type": "string",
                                    "description": "Present tense action, e.g. 'Reading files'",
                                },
                            },
                            "required": ["content", "status", "activeForm"],
                        },
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_task",
            "description": (
                "Spawn subagent for isolated subtask. Each agent type has specific tools. "
                "Use for: exploration (read-only), planning (design), coding (implementation)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Short task name (3-5 words)",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Detailed instructions for subagent",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "Name of agent to spawn",
                    },
                },
                "required": ["description", "prompt", "agent_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "description": "Ask the user a question and return their response",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user",
                    }
                },
                "required": ["question"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": (
                "Load domain expertise for specialized tasks. "
                "Use when you need domain-specific knowledge not in your base knowledge.\n"
                "{skill_descriptions}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of skill to load (e.g., 'pdf', 'commit-message')",
                    }
                },
                "required": ["skill_name"],
                "additionalProperties": False,
            },
        },
    },
]

TOOLS_BY_NAME = {tool["function"]["name"]: tool for tool in TOOLS}
AVAILABLE_TOOLS = list(TOOLS_BY_NAME.keys())


def populate_skill_descriptions(
    tools: list[dict[str, Any]], skills: dict[str, str]
) -> list[dict[str, Any]]:
    """Populate {skill_descriptions} placeholder in load_skill tool description.

    Args:
        tools: List of tool schemas (will be deep copied)
        skills: Dict mapping skill names to descriptions

    Returns:
        New list of tools with skill descriptions populated
    """
    tools_copy = copy.deepcopy(tools)

    # Find load_skill tool and replace placeholder
    for tool in tools_copy:
        if tool["function"]["name"] == "load_skill":
            description = tool["function"]["description"]

            # Format skill descriptions
            if skills:
                skill_lines = [f"- {name}: {desc}" for name, desc in sorted(skills.items())]
                skill_text = "Available skills:\n" + "\n".join(skill_lines)
            else:
                skill_text = "No skills currently available."

            # Replace placeholder
            tool["function"]["description"] = description.replace(
                "{skill_descriptions}", skill_text
            )
            break

    return tools_copy
