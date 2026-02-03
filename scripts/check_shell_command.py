#!/usr/bin/env python3
"""Check shell commands for dangerous patterns before execution."""

import json
import os
import re
import sys

# Exit codes
EXIT_SAFE = 0
EXIT_BLOCK = 2

# Dangerous patterns list (pattern, category, description)
# NOTE: Patterns are designed to avoid false positives by being more specific
DANGEROUS_PATTERNS = [
    # File System Destruction
    (r"rm\s+-rf?\s+/\s*$", "File System", "Recursive root deletion"),
    (r"rm\s+-rf?\s+/\*", "File System", "Recursive root deletion with wildcard"),
    (r"rm\s+-rf?\s+/dev/\w*\s*$", "File System", "Recursive device file deletion"),
    (r"mkfs\.[a-z0-9]+\s+/", "File System", "Filesystem formatting on root"),
    (r"dd\s+.+\s+of=/dev/", "File System", "Disk wiping via dd"),
    (r":\s*\*>\s*/dev/\w+", "File System", "Device file clobbering"),
    # System Destruction
    (r"chmod\s+777\s+/\s*$", "System", "Insecure root permissions"),
    (r"chmod\s+-R\s+777\s+/\s*$", "System", "Recursive insecure root permissions"),
    (r"chown\s+-R\s+.+\s+/", "System", "Recursive ownership changes on root"),
    (r"chmod\s+000\s+/", "System", "Locking root filesystem"),
    # Fork Bombs
    (r":\(\)\{:\|:\&\};:", "Fork Bomb", "Classic bash fork bomb"),
    (
        r"\w+\(\)\s*\{\s*\w+\s*\|\s*\w+\s*&\s*\}\s*;\s*\w+",
        "Fork Bomb",
        "Generalized fork bomb pattern",
    ),
    # Disk Wiping
    (r"dd\s+if=/dev/zero\s+of=/dev/\w+", "Disk Wiping", "Zeroing devices"),
    (r"dd\s+if=/dev/random\s+of=/dev/\w+", "Disk Wiping", "Random overwrite"),
    (r"shred\s+-f\s+-z", "Disk Wiping", "Secure file deletion"),
    (r"wipe\s+-f", "Disk Wiping", "Disk wiping tool"),
    # Network Attacks
    (r"iptables\s+-F\s*$", "Network", "Flush firewall rules"),
    (r"iptables\s+-X\s*$", "Network", "Delete firewall chains"),
    (r"ip6tables\s+-[FX]\s*$", "Network", "Flush IPv6 firewall rules"),
    (r"nft\s+flush\s+ruleset", "Network", "Flush nftables ruleset"),
    (r"arpspoof", "Network", "ARP spoofing/ MITM tool"),
    (r"ettercap", "Network", "MITM tool"),
    # User Account Deletion
    (r"userdel\s+-r\s+root", "User", "Delete root account"),
    (r"deluser\s+--remove-home\s+root", "User", "Delete root account (Debian/Ubuntu)"),
    (r"groupdel\s+root", "User", "Delete root group"),
    # Process Killing
    (r"kill\s+-9\s+-1", "Process", "Kill all processes"),
    (r"killall\s+-9\s+\w+", "Process", "Kill all instances of process"),
    (r"pkill\s+-9\s+\w+", "Process", "Kill processes by name"),
    (r"systemctl\s+stop\s+", "Process", "Service disruption"),
    # Critical File Overwriting
    (r">\s*/etc/passwd\s*$", "Security", "Overwrite passwd file"),
    (r">>\s*/etc/passwd\s*$", "Security", "Append to passwd file"),
    (r">\s*/etc/shadow\s*$", "Security", "Overwrite shadow file"),
    (r">>\s*/etc/shadow\s*$", "Security", "Append to shadow file"),
    (r">\s*/etc/sudoers\s*$", "Security", "Overwrite sudoers file"),
    (r">>\s*/etc/sudoers\s*$", "Security", "Append to sudoers file"),
    (r"echo\s+.+>\s*/boot/", "Security", "Bootloader overwrite"),
    # Other Dangerous Patterns
    (r":.+:\s*\*>\s*/dev/sd[a-z]", "Disk", "Zeroing disk partitions"),
    (r"mkswap\s+/dev/\w+", "Disk", "Swap creation on device"),
    (r"swapoff\s+-a", "System", "Disable all swap"),
]

# Pre-compile patterns for performance
COMPILED_PATTERNS = [
    (re.compile(pattern), category, description)
    for pattern, category, description in DANGEROUS_PATTERNS
]


def is_dangerous_command(command: str) -> tuple[bool, str | None]:
    """Check if command contains dangerous patterns.

    Args:
        command: The shell command to check

    Returns:
        Tuple of (is_dangerous, error_message)
    """
    for pattern, category, description in COMPILED_PATTERNS:
        if pattern.search(command):
            return True, f"{category}: {description}"
    return False, None


def main() -> None:
    """Main entry point for the hook script."""
    # Read input from environment
    hook_input_json = os.environ.get("HOOK_INPUT_JSON")
    if not hook_input_json:
        print("Warning: HOOK_INPUT_JSON not set", file=sys.stderr)
        sys.exit(EXIT_SAFE)

    try:
        hook_input = json.loads(hook_input_json)
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(EXIT_SAFE)

    # Only process shell tool calls
    if hook_input.get("tool") != "shell":
        sys.exit(EXIT_SAFE)

    # Extract command from params
    params = hook_input.get("params") or {}
    command = params.get("command", "")

    # Check command for dangerous patterns
    dangerous, message = is_dangerous_command(command)
    if dangerous:
        print(f"BLOCKED: Dangerous command detected: {message}", file=sys.stderr)
        print(f"Command: {command}", file=sys.stderr)
        sys.exit(EXIT_BLOCK)

    sys.exit(EXIT_SAFE)


if __name__ == "__main__":
    main()
