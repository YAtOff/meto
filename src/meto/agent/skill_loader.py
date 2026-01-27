"""Skill loader for on-demand domain expertise.

Skills are self-contained knowledge modules loaded reactively when needed.
Each skill is a directory containing SKILL.md with YAML frontmatter + markdown body.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypedDict

from meto.agent.frontmatter_loader import parse_yaml_frontmatter

logger = logging.getLogger(__name__)


class SkillMetadata(TypedDict):
    """Lightweight metadata for skill discovery."""

    name: str
    description: str
    path: Path


class SkillConfig(TypedDict):
    """Full skill configuration with content."""

    name: str
    description: str
    content: str
    resources: list[str]


def validate_skill_config(config: dict[str, Any]) -> list[str]:
    """Validate skill configuration.

    Args:
        config: Parsed configuration dict

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check required fields
    if "description" not in config or not config["description"]:
        errors.append("Missing or empty 'description' field")
    if "description" in config and not isinstance(config["description"], str):
        errors.append("'description' must be a string")

    # Name is optional (defaults to directory name)
    if "name" in config and not isinstance(config["name"], str):
        errors.append("'name' must be a string")

    return errors


class SkillLoader:
    """Lazy-load skills: metadata at init, content on demand."""

    skills_dir: Path
    _skills: dict[str, SkillMetadata]
    _content_cache: dict[str, str]

    def __init__(self, skills_dir: Path):
        """Initialize skill loader and discover available skills.

        Args:
            skills_dir: Path to directory containing skill subdirectories
        """
        self.skills_dir = skills_dir
        self._skills = {}
        self._content_cache = {}

        # Discover skills at initialization
        self._discover_skills()

    def _discover_skills(self) -> None:
        """Scan skills directory for SKILL.md files."""
        if not self.skills_dir.exists():
            logger.debug(f"Skills directory {self.skills_dir} does not exist, no skills loaded")
            return

        if not self.skills_dir.is_dir():
            logger.warning(f"Skills directory {self.skills_dir} is not a directory")
            return

        # Each skill is a subdirectory containing SKILL.md
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue

            try:
                # Parse metadata only (lazy loading)
                content = skill_file.read_text(encoding="utf-8")
                parsed = parse_yaml_frontmatter(content)
                metadata: dict[str, Any] = parsed["metadata"]  # type: ignore[assignment]

                # Get name from frontmatter or directory name
                name = str(metadata.get("name", skill_dir.name))
                description = str(metadata.get("description", ""))

                # Validate
                config = {"name": name, "description": description}
                errors = validate_skill_config(config)
                if errors:
                    logger.warning(f"Invalid skill {skill_file}: {', '.join(errors)}")
                    continue

                # Store metadata
                self._skills[name] = {
                    "name": name,
                    "description": description,
                    "path": skill_file,
                }
                logger.debug(f"Discovered skill '{name}' at {skill_file}")

            except Exception as e:
                logger.warning(f"Failed to parse skill file {skill_file}: {e}")
                continue

    def get_skill_descriptions(self) -> dict[str, str]:
        """Return name->description mapping for all discovered skills.

        Returns:
            Dict mapping skill names to descriptions
        """
        return {name: meta["description"] for name, meta in self._skills.items()}

    def get_skill_content(self, skill_name: str) -> str:
        """Load full skill content (with caching).

        Args:
            skill_name: Name of skill to load

        Returns:
            Full skill content (markdown body)

        Raises:
            ValueError: If skill not found
        """
        # Check cache first
        if skill_name in self._content_cache:
            return self._content_cache[skill_name]

        # Look up skill metadata
        if skill_name not in self._skills:
            available = ", ".join(sorted(self._skills.keys()))
            raise ValueError(
                f"Skill '{skill_name}' not found. Available skills: {available or '(none)'}"
            )

        skill_meta = self._skills[skill_name]
        skill_path = skill_meta["path"]

        try:
            # Read full file content
            content = skill_path.read_text(encoding="utf-8")
            parsed = parse_yaml_frontmatter(content)
            body = parsed["body"]

            # Check for additional resources in skill directory
            skill_dir = skill_path.parent
            resources = []
            for item in sorted(skill_dir.iterdir()):
                if item.name != "SKILL.md":
                    resources.append(item.name)

            # Build full content with resource hints
            full_content = body
            if resources:
                full_content += "\n\n## Available Resources\n"
                full_content += "Additional files in this skill directory:\n"
                for resource in resources:
                    full_content += f"- {resource}\n"

            # Cache for future calls
            self._content_cache[skill_name] = full_content
            return full_content

        except Exception as e:
            raise ValueError(f"Failed to load skill '{skill_name}': {e}") from e

    def list_skills(self) -> list[str]:
        """Return list of all available skill names.

        Returns:
            Sorted list of skill names
        """
        return sorted(self._skills.keys())

    def has_skill(self, skill_name: str) -> bool:
        """Check if a skill exists.

        Args:
            skill_name: Name of skill to check

        Returns:
            True if skill exists, False otherwise
        """
        return skill_name in self._skills
