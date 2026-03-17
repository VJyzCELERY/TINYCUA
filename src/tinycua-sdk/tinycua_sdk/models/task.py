"""Task planning models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TodoItem:
    """A single todo item in a task plan."""

    id: str
    description: str
    status: str = "pending"
    tool_name: str | None = None
    tool_args: dict = field(default_factory=dict)
    result: Any = None


@dataclass
class TaskPlan:
    """A plan with todo list."""

    main_task: str
    todo: list[TodoItem] = field(default_factory=list)


@dataclass
class PlanningResult:
    """Result from planning execution."""

    plan: TaskPlan
    final_response: str
