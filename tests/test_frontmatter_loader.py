"""Tests for frontmatter_loader module."""

from __future__ import annotations

from meto.agent.frontmatter_loader import parse_yaml_frontmatter


def test_parse_yaml_frontmatter_with_frontmatter():
    """Test parsing content with valid YAML frontmatter."""
    content = """---
name: test-agent
description: Test agent description
tools:
  - shell
  - read_file
---

This is the markdown body content.
It can have multiple lines."""

    result = parse_yaml_frontmatter(content)

    assert result["metadata"] == {
        "name": "test-agent",
        "description": "Test agent description",
        "tools": ["shell", "read_file"],
    }
    assert result["body"] == "This is the markdown body content.\nIt can have multiple lines."


def test_parse_yaml_frontmatter_without_frontmatter():
    """Test parsing content without frontmatter."""
    content = "Just plain markdown content\nwith multiple lines."

    result = parse_yaml_frontmatter(content)

    assert result["metadata"] == {}
    assert result["body"] == "Just plain markdown content\nwith multiple lines."


def test_parse_yaml_frontmatter_empty_frontmatter():
    """Test parsing content with empty frontmatter."""
    content = """---

---

Body content here."""

    result = parse_yaml_frontmatter(content)

    assert result["metadata"] == {}
    assert result["body"] == "Body content here."


def test_parse_yaml_frontmatter_empty_body():
    """Test parsing content with frontmatter but empty body."""
    content = """---
name: test
---
"""

    result = parse_yaml_frontmatter(content)

    assert result["metadata"] == {"name": "test"}
    assert result["body"] == ""


def test_parse_yaml_frontmatter_complex_yaml():
    """Test parsing with complex YAML structures."""
    content = """---
name: complex-agent
config:
  nested:
    value: 123
  list:
    - item1
    - item2
tags:
  - tag1
  - tag2
---

Body content."""

    result = parse_yaml_frontmatter(content)

    assert result["metadata"]["name"] == "complex-agent"
    assert result["metadata"]["config"]["nested"]["value"] == 123
    assert result["metadata"]["config"]["list"] == ["item1", "item2"]
    assert result["metadata"]["tags"] == ["tag1", "tag2"]
    assert result["body"] == "Body content."
