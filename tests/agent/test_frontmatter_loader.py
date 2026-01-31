from __future__ import annotations

from meto.agent.frontmatter_loader import parse_yaml_frontmatter


def test_parse_yaml_frontmatter_with_frontmatter() -> None:
    content = "---\nname: test\ndescription: hi\n---\nBody text\n"
    parsed = parse_yaml_frontmatter(content)

    assert parsed["metadata"]["name"] == "test"
    assert parsed["metadata"]["description"] == "hi"
    assert parsed["body"] == "Body text"


def test_parse_yaml_frontmatter_without_frontmatter() -> None:
    content = "Just body\nSecond line\n"
    parsed = parse_yaml_frontmatter(content)

    assert parsed["metadata"] == {}
    assert parsed["body"] == "Just body\nSecond line"
