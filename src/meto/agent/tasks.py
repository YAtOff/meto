"""Task management for structured planning and progress tracking."""

from __future__ import annotations


class TaskManager:
    """Manages a structured task list with enforced constraints.

    Constraints:
    - Max 20 items: Prevents endless task lists
    - One in_progress: Forces focus on one thing at a time
    - Required fields: Each item needs content, status, and activeForm

    The activeForm field is the present tense form of what's happening,
    shown when status is "in_progress" (e.g., content="Add tests",
    activeForm="Adding unit tests...").
    """

    def __init__(self) -> None:
        self.items: list[dict[str, str]] = []

    def update(self, items: list[dict[str, str]]) -> str:
        """Validate and update the task list.

        The model sends a complete new list each time. We validate it,
        store it, and return a rendered view that the model will see.

        Validation Rules:
        - Each item must have: content, status, activeForm
        - Status must be: pending | in_progress | completed
        - Only ONE item can be in_progress at a time
        - Maximum 20 items allowed

        Args:
            items: Complete new task list (replaces existing)

        Returns:
            Rendered text view of the task list
        """
        validated: list[dict[str, str]] = []
        in_progress_count = 0

        for i, item in enumerate(items):
            # Extract and validate fields
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            active_form = str(item.get("activeForm", "")).strip()

            # Validation checks
            if not content:
                raise ValueError(f"Item {i}: content required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {i}: invalid status '{status}'")
            if not active_form:
                raise ValueError(f"Item {i}: activeForm required")

            if status == "in_progress":
                in_progress_count += 1

            validated.append(
                {
                    "content": content,
                    "status": status,
                    "activeForm": active_form,
                }
            )

        # Enforce constraints
        if len(validated) > 20:
            raise ValueError("Max 20 tasks allowed")
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")

        self.items = validated
        return self.render()

    def render(self) -> str:
        """Render the task list as human-readable text.

        Format:
            [x] Completed task
            [>] In progress task <- Doing something...
            [ ] Pending task

            (2/3 completed)

        This rendered text is what the model sees as the tool result.
        """
        if not self.items:
            return "No tasks."

        lines: list[str] = []
        for item in self.items:
            if item["status"] == "completed":
                lines.append(f"[x] {item['content']}")
            elif item["status"] == "in_progress":
                lines.append(f"[>] {item['content']} <- {item['activeForm']}")
            else:
                lines.append(f"[ ] {item['content']}")

        completed = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({completed}/{len(self.items)} completed)")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all tasks."""
        self.items.clear()
