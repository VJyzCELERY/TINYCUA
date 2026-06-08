"""Classification models for QueryAnalyst routing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tinycua.models.node_input import NodeInput
    from tinycua.models.node_payload import NodePayload

# Classification label constants
PASSTHROUGH = "passthrough"
WORKER = "worker"
UNCERTAIN = "uncertain"


@dataclass
class MandatoryPassthrough:
    """Deterministic continuation directive that overrides LLM classification.

    When present in input metadata, QueryAnalyst routes directly to the
    target node/session without invoking the LLM for classification.

    Attributes:
        target_node_id: ID of the node to route to.
        target_session_id: Optional session ID for the target node.
        reason: Human-readable reason for the passthrough.
        payload: Optional payload to forward to the target.
        allow_query_analyst_restart: Whether QueryAnalyst can restart after passthrough.
    """

    target_node_id: str
    target_session_id: str | None = None
    reason: str = ""
    payload: NodeInput | NodePayload | None = None
    allow_query_analyst_restart: bool = True


@dataclass
class QueryAnalystResponse:
    """Structured response from QueryAnalyst classification.

    Reserved for Phase 2 — not yet used. Intended for use in on_complete
    or as a return type for a future method.

    Attributes:
        user_query: The original user query string.
        classification: The classification label (passthrough, worker, uncertain).
        rationale: Optional rationale for the classification decision.
    """

    user_query: str = ""
    classification: str = UNCERTAIN
    rationale: str | None = None
