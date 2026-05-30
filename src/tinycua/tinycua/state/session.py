"""Session state object."""

from __future__ import annotations

__all__ = ["Session", "OwnerType"]

import dataclasses
from typing import Literal

from tinycua.state.base import StateObject
from tinycua.state.execution_log import ExecutionLog

OwnerType = Literal["primary", "child"]


@dataclasses.dataclass
class Session(StateObject):
    """Canonical session container with chat history, context, and execution log.

    Attributes:
        session_id: Unique session identifier.
        owner_type: Whether this is a primary (user-facing) or child (sub-session).
        owner_name: Name of the owner agent or user.
        chat_history: JSON turn log entries as list of dicts.
        context: Structured markdown context string.
        execution_log: Optional execution log for sub-session actions.
    """

    session_id: str
    owner_type: OwnerType
    owner_name: str
    chat_history: list[dict]
    context: str
    execution_log: ExecutionLog | None = None

    def __post_init__(self) -> None:
        """Validate enum fields."""
        self._validate_enum(
            self.owner_type,
            {"primary", "child"},
            "owner_type",
        )
