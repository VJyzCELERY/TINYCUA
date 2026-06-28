"""Stream event models and helper functions for TinyCUA streaming.

Provides structured event dicts yielded during streaming, including
lifecycle events for node boundaries (started, llm_call, completed,
error, retry). These events are plain dicts to maintain SDK BaseLoop
compatibility (AsyncIterator[dict[str, Any]]).
"""

from __future__ import annotations

import time
from typing import Any, Literal


def make_lifecycle_event(
    event_type: Literal[
        "node.started", "node.llm_call", "node.completed", "node.error", "node.retry"
    ],
    node_id: str,
    node_type: str,
    attempt: int = 1,
    content: str | None = None,
    finish_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a lifecycle event dict with standard fields.

    Args:
        event_type: The lifecycle event type.
        node_id: ID of the node producing this event.
        node_type: Type of the node (e.g., "ProcessNode", "DecisionNode").
        attempt: Current attempt number (1-based).
        content: Final content for completed/error events.
        finish_reason: One of "completed", "error", "retry", "empty".
        metadata: Additional context (route_label, etc.).

    Returns:
        A dict representing the lifecycle event.
    """
    event: dict[str, Any] = {
        "type": event_type,
        "node_id": node_id,
        "node_type": node_type,
        "timestamp": time.time(),
        "attempt": attempt,
        "content": content,
        "finish_reason": finish_reason,
        "metadata": metadata or {},
    }
    return event


def enrich_stream_event(
    event: dict[str, Any],
    node_id: str,
    node_type: str,
    attempt: int = 1,
    include_metadata: bool = True,
) -> dict[str, Any]:
    """Add node metadata to an existing stream event dict.

    Args:
        event: The event dict to enrich.
        node_id: ID of the node producing this event.
        node_type: Type of the node.
        attempt: Current attempt number (1-based).
        include_metadata: Whether to include the metadata fields.

    Returns:
        The enriched event dict (mutated in place and returned).
    """
    if include_metadata:
        event["node_id"] = node_id
        event["node_type"] = node_type
        event["attempt"] = attempt
    return event
