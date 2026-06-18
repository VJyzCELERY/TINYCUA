"""TaskCreateNode for deterministic root task creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode
from tinycua.models.digested_information import DigestedInformation

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.models.node_input import NodeInputLike
    from tinycua.models.session import Session

_TASK_CREATE_INSTRUCTION = (
    "You are a task creation node. Your role is to create structured "
    "tasks from user requests and digested context. "
    "Use the available context to break down the request into "
    "well-defined, actionable tasks."
)

_TASK_CREATE_CONTINUATION = (
    "Based on the request context above, initialize the root roadmap "
    "using task tools. Create actionable tasks and avoid repeating upstream "
    "context verbatim. Initialize one root task; decomposition into subtasks "
    "is owned by TaskAnalyzer."
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
        for entry in reversed(session.session_context):
            # Handle both dict and SessionContextEntry
            if isinstance(entry, dict):
                content = entry.get("content")
            else:
                content = entry.content
            if isinstance(content, DigestedInformation):
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

        return None
