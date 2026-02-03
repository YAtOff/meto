#!/usr/bin/env python3
"""Check if a file operation is attempting to access a secret file.

This script is designed to be used as a pre_tool_use hook in meto.
It reads hook input from HOOK_INPUT_JSON environment variable and
blocks read_file and write_file operations on files matching secret patterns.

Exit codes:
    0: allow operation (no secret detected)
    1: error (invalid input)
    2: block operation (secret detected)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Secret patterns to detect
SECRET_PATTERNS = {
    "exact": [".env", ".key", ".pem"],
    "prefix": ["secrets", "credentials"],
    "contains": ["secret", "credential"],
}


def get_hook_input() -> dict[str, Any]:
    """Parse hook input from environment variable.

    Returns:
        Parsed hook input dictionary.

    Raises:
        SystemExit: If input is missing or invalid (exit code 1).
    """
    hook_input_json = os.environ.get("HOOK_INPUT_JSON")
    if not hook_input_json:
        # No input provided - not our concern, allow
        sys.exit(0)

    try:
        return json.loads(hook_input_json)
    except json.JSONDecodeError as e:
        print(f"Invalid HOOK_INPUT_JSON: {e}", file=sys.stderr)
        sys.exit(1)


def should_check_tool(tool_name: str) -> bool:
    """Check if this tool should be checked for secret files.

    Args:
        tool_name: Name of the tool being called.

    Returns:
        True if tool should be checked, False otherwise.
    """
    return tool_name in ("read_file", "write_file")


def normalize_path(path_str: str) -> Path:
    """Normalize and resolve path to absolute path.

    Args:
        path_str: Path string (can be absolute or relative).

    Returns:
        Resolved absolute Path object.
    """
    # Handle empty path
    if not path_str:
        raise ValueError("Path is empty")

    path = Path(path_str)

    # Resolve to absolute path (following symlinks)
    # Use strict=False to allow non-existent paths (we just need to check the pattern)
    resolved = path.resolve(strict=False)

    # Convert to forward slashes for consistent pattern matching
    # We'll work with the normalized string for pattern matching
    return resolved


def is_secret_file(path: Path) -> bool:
    """Check if a path matches secret file patterns.

    Args:
        path: Path object to check.

    Returns:
        True if path matches any secret pattern, False otherwise.
    """
    # Convert to string with forward slashes for matching
    str(path).replace("\\", "/")

    # Extract filename and parts
    filename = path.name.lower()
    path_parts = [part.lower() for part in path.parts]

    # Check exact filename patterns
    for exact_pattern in SECRET_PATTERNS["exact"]:
        if filename == exact_pattern.lower():
            return True

    # Check prefix patterns (secrets*, credentials*)
    for prefix_pattern in SECRET_PATTERNS["prefix"]:
        if filename.startswith(prefix_pattern.lower()):
            return True

    # Check directory components for "secret" or "credential"
    for part in path_parts:
        for contains_pattern in SECRET_PATTERNS["contains"]:
            if contains_pattern.lower() in part:
                return True

    return False


def get_file_path(hook_input: dict[str, Any]) -> str | None:
    """Extract file path from hook input parameters.

    Args:
        hook_input: Parsed hook input dictionary.

    Returns:
        File path string or None if not found.
    """
    params = hook_input.get("params", {})
    return params.get("path")


def main() -> None:
    """Main entry point for the script."""
    # Parse hook input
    hook_input = get_hook_input()

    # Get tool name
    tool_name = hook_input.get("tool")
    if not tool_name:
        # No tool specified - allow
        sys.exit(0)

    # Only check read_file and write_file tools
    if not should_check_tool(tool_name):
        sys.exit(0)

    # Get file path
    file_path = get_file_path(hook_input)
    if not file_path:
        # No path parameter - not our concern, allow
        sys.exit(0)

    # Normalize and check path
    try:
        path = normalize_path(file_path)
    except ValueError as e:
        print(f"Invalid path: {e}", file=sys.stderr)
        sys.exit(1)

    # Check if path matches secret patterns
    if is_secret_file(path):
        # Block the operation
        sys.exit(2)

    # Allow the operation
    sys.exit(0)


if __name__ == "__main__":
    main()
