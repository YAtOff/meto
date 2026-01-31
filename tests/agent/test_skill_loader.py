from __future__ import annotations

from pathlib import Path

import pytest

from meto.agent.loaders.skill_loader import SkillLoader, clear_skill_cache, get_skill_loader


def test_skill_loader_discovers_skills_and_returns_descriptions(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    (skills_dir / "demo").mkdir(parents=True)
    (skills_dir / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\n# Body\n",
        encoding="utf-8",
    )

    loader = SkillLoader(skills_dir)
    desc = loader.get_skill_descriptions()

    assert desc == {"demo": "Demo skill"}
    assert loader.has_skill("demo") is True
    assert loader.has_skill("missing") is False


def test_get_skill_content_includes_resources_and_is_cached(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    (skills_dir / "demo").mkdir(parents=True)
    (skills_dir / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill\n---\nBody text\n",
        encoding="utf-8",
    )
    (skills_dir / "demo" / "extra.txt").write_text("x", encoding="utf-8")

    loader = SkillLoader(skills_dir)

    c1 = loader.get_skill_content("demo")
    c2 = loader.get_skill_content("demo")

    assert c1 == c2
    assert "Body text" in c1
    assert "Available Resources" in c1
    assert "extra.txt" in c1


def test_get_skill_content_unknown_raises(tmp_path: Path) -> None:
    loader = SkillLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.get_skill_content("nope")


def test_get_skill_loader_is_cached_and_clearable(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    clear_skill_cache()
    a = get_skill_loader(skills_dir=skills_dir)
    b = get_skill_loader(skills_dir=skills_dir)
    assert a is b

    clear_skill_cache()
    c = get_skill_loader(skills_dir=skills_dir)
    assert c is not a
