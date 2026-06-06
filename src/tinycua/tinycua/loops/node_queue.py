"""NodeQueue placeholder for Milestone 1.1.

In later milestones this will manage the graph of execution nodes.
For M1.1 it is a stub that always reports empty, allowing TinyCUALoop
to bypass node execution and call the LLM directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeQueue:
    """Placeholder node queue for Milestone 1.1.

    Attributes:
        items: List of queued nodes (empty in M1.1).
        current: The currently executing node (None in M1.1).
    """

    items: list[Any] = field(default_factory=list)
    current: Any | None = None

    def is_empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True — always empty in M1.1.
        """
        return True

    def input_for_current(self) -> dict[str, Any]:
        """Get input data for the current node.

        Returns:
            Empty dict — no node execution in M1.1.
        """
        return {}

    def advance(self) -> None:
        """Advance to the next node.

        No-op in M1.1.
        """
