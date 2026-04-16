"""Chat session state for LLM chat."""

import time
from dataclasses import dataclass, field
from typing import cast

from village.chat.sequential_thinking import TaskBreakdown
from village.chat.task_spec import TaskSpec
from village.extensibility.thinking_refiners import QueryRefinement


@dataclass
class ChatSession:
    """Chat session state."""

    current_task: TaskSpec | None = None
    refinements: list[dict[str, object]] = field(default_factory=list)
    current_iteration: int = 0
    current_breakdown: TaskBreakdown | None = None
    query_refinement: QueryRefinement | None = None

    def get_current_spec(self) -> TaskSpec | None:
        """Get latest task spec."""
        if self.current_iteration == 0:
            return self.current_task
        elif self.refinements:
            task_spec_dict = cast(dict[str, object], self.refinements[-1]["task_spec"])
            return TaskSpec.from_dict(task_spec_dict)
        return self.current_task

    def add_refinement(self, task_spec: TaskSpec, user_input: str) -> None:
        """Add a refinement to history."""
        self.current_iteration += 1
        self.refinements.append(
            {
                "iteration": self.current_iteration,
                "task_spec": task_spec.__dict__,
                "user_input": user_input,
                "timestamp": time.time(),
            }
        )
        self.current_task = task_spec

    def undo_refinement(self) -> bool:
        """Undo to previous refinement."""
        if self.current_iteration == 0:
            return False

        self.refinements.pop()
        self.current_iteration -= 1
        if self.refinements:
            task_spec_dict = cast(dict[str, object], self.refinements[-1]["task_spec"])
            self.current_task = TaskSpec.from_dict(task_spec_dict)
        return True
