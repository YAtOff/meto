"""
Agent context dumping and serialization utilities for the agent loop.
Provides methods to extract, format, and save conversation history.
Includes support for user instructions/memory files (similar to CLAUDE.md).
"""

import json
from datetime import datetime
from typing import Any
from pathlib import Path


# ============================================================================
# USER INSTRUCTIONS/MEMORY MANAGEMENT
# ============================================================================

def load_user_instructions(filepath: str | Path = "AGENT_INSTRUCTIONS.md") -> str:
    """
    Load user instructions/memory from a file (similar to CLAUDE.md).
    
    Args:
        filepath: Path to instructions file (default: AGENT_INSTRUCTIONS.md)
    
    Returns:
        Instructions content as string, or empty string if file not found
    
    Example file structure:
        # Agent Instructions
        
        ## Personality
        - Be concise and technical
        - Avoid unnecessary explanations
        
        ## Tools
        - Always validate input before calling tools
        - Prefer get_weather over weather_api
        
        ## Memory
        - User prefers metric units
        - Sofia timezone: UTC+2
    """
    filepath = Path(filepath)
    
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    
    return ""


def create_instructions_template(filepath: str | Path = "AGENT_INSTRUCTIONS.md") -> None:
    """
    Create a template AGENT_INSTRUCTIONS.md file for the user to customize.
    
    Args:
        filepath: Where to create the template
    """
    template = """# Agent Instructions & Memory

## System Behavior
<!-- Define how the agent should behave -->
- Be concise and technical
- Ask clarifying questions when ambiguous
- Prioritize accuracy over speed

## Personality & Tone
<!-- Define the agent's personality -->
- Helpful and professional
- Avoid unnecessary explanations unless asked
- Use appropriate level of detail for the context

## Tools & Methods
<!-- Preferences for tool usage -->
- Always validate input before calling tools
- Prefer tool X over tool Y (explain why)
- Never call tool Z without user confirmation

## User Preferences & Context
<!-- User-specific information -->
- Timezone: UTC+2 (Sofia)
- Units: Metric (km, kg, °C)
- Language: English with technical terminology
- Availability: Business hours

## Knowledge Base
<!-- Important domain-specific info -->
- Domain expertise or context
- Special terminology definitions
- Internal processes or standards

## Guardrails & Limitations
<!-- Safety and ethical boundaries -->
- Do not access sensitive databases
- Always confirm before destructive operations
- Escalate security concerns to user

## Memory & Past Context
<!-- Retain information across sessions -->
- Previous project context
- User's preferred communication style
- Common patterns or preferences
"""
    
    filepath = Path(filepath)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(template)
    
    print(f"✓ Created instructions template: {filepath}")
    print("  Edit this file to customize agent behavior")


def get_system_prompt_with_instructions(
    base_system_prompt: str,
    instructions_filepath: str | Path = "AGENT_INSTRUCTIONS.md"
) -> str:
    """
    Combine base system prompt with user instructions/memory.
    
    Args:
        base_system_prompt: Your original system prompt
        instructions_filepath: Path to user instructions file
    
    Returns:
        Combined system prompt with instructions
    
    Usage in agent loop:
        SYSTEM_PROMPT = get_system_prompt_with_instructions(
            "You are a helpful assistant...",
            "AGENT_INSTRUCTIONS.md"
        )
    """
    instructions = load_user_instructions(instructions_filepath)
    
    if not instructions:
        return base_system_prompt
    
    combined = f"""{base_system_prompt}

## Custom Instructions & Memory

Below are custom instructions and context for this session:

{instructions}"""
    
    return combined


# ============================================================================
# CONTEXT DUMPING & SERIALIZATION
# ============================================================================

def dump_agent_context(history: list[dict[str, Any]], format: str = "json") -> str:
    """
    Dump agent context (conversation history) in a specified format.
    
    Args:
        history: The agent conversation history list
        format: Output format - "json", "pretty_json", "markdown", or "text"
    
    Returns:
        Formatted string representation of the agent context
    """
    if format == "json":
        return json.dumps(history, indent=2)
    
    elif format == "pretty_json":
        return json.dumps(history, indent=2, ensure_ascii=False)
    
    elif format == "markdown":
        return _format_as_markdown(history)
    
    elif format == "text":
        return _format_as_text(history)
    
    else:
        raise ValueError(f"Unknown format: {format}")


def _format_as_markdown(history: list[dict[str, Any]]) -> str:
    """Format history as readable Markdown."""
    lines = ["# Agent Conversation History\n"]
    
    for i, msg in enumerate(history, 1):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        
        lines.append(f"## Message {i}: {role}\n")
        
        if role == "USER":
            lines.append(f"{content}\n")
        
        elif role == "ASSISTANT":
            if content:
                lines.append(f"**Response:**\n\n{content}\n")
            
            if "tool_calls" in msg:
                lines.append("**Tool Calls:**\n")
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args = fn.get("arguments", "{}")
                    
                    # Parse arguments if it's a string
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except json.JSONDecodeError:
                            pass
                    
                    lines.append(f"- **{fn_name}**")
                    if isinstance(fn_args, dict) and fn_args:
                        lines.append(f"  ```json\n  {json.dumps(fn_args, indent=2)}\n  ```")
                    lines.append("")
        
        elif role == "TOOL":
            tool_call_id = msg.get("tool_call_id", "unknown")
            lines.append(f"**Tool Call ID:** `{tool_call_id}`\n")
            lines.append(f"**Output:**\n\n{content}\n")
        
        elif role == "SYSTEM":
            lines.append(f"```\n{content}\n```\n")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_as_text(history: list[dict[str, Any]]) -> str:
    """Format history as simple readable text."""
    lines = ["=" * 80]
    lines.append("AGENT CONVERSATION HISTORY")
    lines.append("=" * 80)
    lines.append("")
    
    for i, msg in enumerate(history, 1):
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        
        lines.append(f"\n[Message {i}] {role}")
        lines.append("-" * 40)
        
        if role == "USER":
            lines.append(content)
        
        elif role == "ASSISTANT":
            if content:
                lines.append(f"Response:\n{content}")
            
            if "tool_calls" in msg:
                lines.append("\nTool Calls:")
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "unknown")
                    fn_args = fn.get("arguments", "{}")
                    
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except json.JSONDecodeError:
                            pass
                    
                    lines.append(f"  - {fn_name}")
                    if isinstance(fn_args, dict) and fn_args:
                        for key, value in fn_args.items():
                            lines.append(f"      {key}: {value}")
        
        elif role == "TOOL":
            tool_call_id = msg.get("tool_call_id", "unknown")
            lines.append(f"Tool Call ID: {tool_call_id}")
            lines.append(f"Output:\n{content}")
        
        elif role == "SYSTEM":
            lines.append(f"[System Message]\n{content}")
    
    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


def save_agent_context(
    history: list[dict[str, Any]],
    filepath: str | Path,
    format: str = "json"
) -> None:
    """
    Save agent context to a file.
    
    Args:
        history: The agent conversation history
        filepath: Path where to save the context
        format: Output format ("json", "pretty_json", "markdown", "text")
    """
    content = dump_agent_context(history, format)
    
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✓ Agent context saved to {filepath}")


def print_agent_context(
    history: list[dict[str, Any]],
    format: str = "markdown"
) -> None:
    """
    Print agent context to stdout in a readable format.
    
    Args:
        history: The agent conversation history
        format: Output format ("markdown", "text", "json", "pretty_json")
    """
    content = dump_agent_context(history, format)
    print(content)


def get_context_summary(history: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Get a summary of the agent context.
    
    Returns:
        Dictionary with conversation statistics and metadata
    """
    user_messages = [m for m in history if m.get("role") == "user"]
    assistant_messages = [m for m in history if m.get("role") == "assistant"]
    tool_messages = [m for m in history if m.get("role") == "tool"]
    
    total_tool_calls = sum(
        len(m.get("tool_calls", []))
        for m in assistant_messages
    )
    
    tools_used = set()
    for m in assistant_messages:
        for tc in m.get("tool_calls", []):
            fn_name = tc.get("function", {}).get("name")
            if fn_name:
                tools_used.add(fn_name)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_messages": len(history),
        "user_messages": len(user_messages),
        "assistant_messages": len(assistant_messages),
        "tool_messages": len(tool_messages),
        "total_tool_calls": total_tool_calls,
        "unique_tools_used": sorted(tools_used),
        "total_tokens_estimate": _estimate_tokens(history),
    }


def _estimate_tokens(history: list[dict[str, Any]]) -> int:
    """Rough estimate of token count (4 chars ≈ 1 token)."""
    total_chars = sum(
        len(str(m.get("content", "")))
        for m in history
    )
    return max(1, total_chars // 4)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """Example of how to use these functions in your agent loop."""
    
    # Step 1: Initialize instructions (create template if doesn't exist)
    create_instructions_template("AGENT_INSTRUCTIONS.md")
    
    # Step 2: Load instructions and create system prompt
    base_prompt = "You are a helpful assistant with access to tools."
    system_prompt = get_system_prompt_with_instructions(
        base_prompt,
        "AGENT_INSTRUCTIONS.md"
    )
    
    # Step 3: Use in your agent loop
    history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What's the weather?"},
        {
            "role": "assistant",
            "content": "I'll check the weather for you.",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "Sofia"}'
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": "Weather in Sofia: 15°C, Cloudy"
        },
    ]
    
    # Step 4: Dump context in various ways
    print("=== SYSTEM PROMPT WITH INSTRUCTIONS ===")
    print(system_prompt)
    
    print("\n=== CONVERSATION SUMMARY ===")
    summary = get_context_summary(history)
    print(json.dumps(summary, indent=2))
    
    print("\n=== MARKDOWN FORMAT ===")
    print_agent_context(history, format="markdown")
    
    print("\n=== TEXT FORMAT ===")
    print_agent_context(history, format="text")
    
    # Step 5: Save to files
    save_agent_context(history, "agent_context.json", format="pretty_json")
    save_agent_context(history, "agent_context.md", format="markdown")
    save_agent_context(history, "agent_context.txt", format="text")


if __name__ == "__main__":
    example_usage()
