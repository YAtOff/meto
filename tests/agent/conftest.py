from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from meto.agent.hooks import reset_hooks_manager_cache
from meto.agent.loaders import clear_agent_cache, clear_skill_cache
from meto.conf import settings


@pytest.fixture(autouse=True)
def _isolate_meto_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests hermetic: redirect meto paths to tmp_path + reset singletons."""

    session_dir = tmp_path / "sessions"
    plan_dir = tmp_path / "plans"
    agents_dir = tmp_path / ".meto" / "agents"
    commands_dir = tmp_path / ".meto" / "commands"
    skills_dir = tmp_path / ".meto" / "skills"
    hooks_file = tmp_path / ".meto" / "hooks.yaml"

    for d in [session_dir, plan_dir, agents_dir, commands_dir, skills_dir, hooks_file.parent]:
        d.mkdir(parents=True, exist_ok=True)

    # Minimal hooks file (valid YAML)
    hooks_file.write_text("hooks: []\n", encoding="utf-8")

    # Ensure modules that read cwd/AGENTS.md are deterministic
    monkeypatch.chdir(tmp_path)
    (tmp_path / "AGENTS.md").write_text(
        "# Test AGENTS.md\n\nThese are test instructions.\n",
        encoding="utf-8",
    )

    # Patch settings to point at tmp dirs
    monkeypatch.setattr(settings, "SESSION_DIR", session_dir, raising=False)
    monkeypatch.setattr(settings, "PLAN_DIR", plan_dir, raising=False)
    monkeypatch.setattr(settings, "AGENTS_DIR", agents_dir, raising=False)
    monkeypatch.setattr(settings, "COMMANDS_DIR", commands_dir, raising=False)
    monkeypatch.setattr(settings, "SKILLS_DIR", skills_dir, raising=False)
    monkeypatch.setattr(settings, "HOOKS_FILE", hooks_file, raising=False)

    # Clear caches that memoize directories
    clear_agent_cache()
    clear_skill_cache()
    reset_hooks_manager_cache()

    yield

    clear_agent_cache()
    clear_skill_cache()
    reset_hooks_manager_cache()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail fast if anything tries to hit the network."""

    def _blocked(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("Network access is disabled in unit tests")

    monkeypatch.setattr(urllib.request, "urlopen", _blocked, raising=True)

    # Tool runner imports urlopen directly; patch that alias too.
    import meto.agent.tool_runner as tool_runner

    monkeypatch.setattr(tool_runner, "urlopen", _blocked, raising=True)

    yield
