from __future__ import annotations

import pytest

from meto.agent.todo import TodoManager


def test_todo_max_20_items_enforced() -> None:
    todos = TodoManager()
    items = [
        {"content": f"t{i}", "status": "pending", "activeForm": f"doing {i}"} for i in range(21)
    ]
    with pytest.raises(ValueError, match="Max 20"):
        todos.update(items)


def test_todo_only_one_in_progress() -> None:
    todos = TodoManager()
    items = [
        {"content": "a", "status": "in_progress", "activeForm": "a"},
        {"content": "b", "status": "in_progress", "activeForm": "b"},
    ]
    with pytest.raises(ValueError, match="Only one todo"):
        todos.update(items)


def test_todo_update_validates_required_fields_and_status() -> None:
    todos = TodoManager()

    with pytest.raises(ValueError, match="content required"):
        todos.update([{"content": "", "status": "pending", "activeForm": "x"}])

    with pytest.raises(ValueError, match="invalid status"):
        todos.update([{"content": "x", "status": "nope", "activeForm": "x"}])

    with pytest.raises(ValueError, match="activeForm required"):
        todos.update([{"content": "x", "status": "pending", "activeForm": ""}])


def test_todo_render_checkbox_format_and_completion_count() -> None:
    todos = TodoManager()
    todos.update(
        [
            {"content": "A", "status": "completed", "activeForm": "done A"},
            {"content": "B", "status": "in_progress", "activeForm": "doing B"},
            {"content": "C", "status": "pending", "activeForm": "doing C"},
        ]
    )

    rendered = todos.render()
    assert "[x] A" in rendered
    assert "[>] B <- doing B" in rendered
    assert "[ ] C" in rendered
    assert "(1/3 completed)" in rendered


def test_todo_clear() -> None:
    todos = TodoManager()
    todos.update([{"content": "A", "status": "pending", "activeForm": "A"}])
    todos.clear()
    assert todos.render() == "No todos."
