"""TaskCreateNode for deterministic root task creation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode
from tinycua.loops.session_context_query import find_latest_entry
from tinycua.models.digested_information import DigestedInformation

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session

logger = logging.getLogger(__name__)

_TASK_CREATE_INSTRUCTION = (
    "You are TaskCreate. Initialize exactly one root roadmap from the user "
    "request and digested context. Do not research, write files, execute work, "
    "or decompose tasks."
)

_TASK_CREATE_CONTINUATION = (
    "Define one root task from the available context and summarize its title and "
    "description. TaskAnalyzer owns all subtask decomposition."
)


class TinyCUATaskCreateNode(ProcessNode):
    """First-time deterministic root task creation node.

    Input includes request context from WorkerNode, providing
    context for root task creation alongside the original query.
    """

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
        *,
        instruction: str = _TASK_CREATE_INSTRUCTION,
        is_terminal: bool = False,
    ) -> None:
        """Initialize TaskCreateNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            instruction: Instruction string for this node type.
            is_terminal: Whether this node is terminal.
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=instruction,
            continuation=_TASK_CREATE_CONTINUATION,
            is_terminal=is_terminal,
        )

    def build_messages(
        self,
        session: Session,
        input_data: NodeInputLike,
        resolved_tools: list[object] | None = None,
    ) -> list[dict[str, str]]:
        """Build messages including request context from Worker.

        Extends the base message building to include request context
        from any structured digest present in the session_context.

        Args:
            session: The session containing context and history.
            input_data: The node input to convert to continuation messages.
            resolved_tools: Tools available to this node for prompt exposure.

        Returns:
            List of message dictionaries for the LLM call.
        """
        messages = super().build_messages(session, input_data, resolved_tools)

        # Scan session_context for request context and add it naturally.
        digest_context = self._extract_digest_context(session)
        if digest_context:
            messages.append(
                {
                    "role": "assistant",
                    "content": digest_context,
                }
            )

        return messages

    def _extract_digest_context(self, session: Session) -> str | None:
        """Extract DigestedInformation context from session.

        Args:
            session: The session to scan.

        Returns:
            A formatted string of digest context, or None if no digest.
        """
        content = find_latest_entry(session, DigestedInformation)
        if content is None:
            return None
        parts = [f"Request summary: {content.context_summary}"]
        if content.original_query:
            parts.append(f"User request: {content.original_query}")

        if content.key_points:
            parts.append("Key Points:")
            parts.extend(f"  - {point}" for point in content.key_points)

        if content.advisory_instructions:
            parts.append("Advisory Instructions:")
            parts.extend(
                f"  - {advice}" for advice in content.advisory_instructions
            )

        if content.constraints:
            parts.append("Constraints:")
            parts.extend(
                f"  - {constraint}" for constraint in content.constraints
            )

        if content.known_gaps:
            parts.append("Known Gaps:")
            parts.extend(f"  - {gap}" for gap in content.known_gaps)

        return "\n".join(parts)
