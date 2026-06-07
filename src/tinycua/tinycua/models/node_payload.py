"""NodePayload dataclass for internal transport of node output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from tinycua.models.state_object import StateObject


@dataclass
class NodePayload(StateObject):
    """Internal transport envelope for a single node's structured output.

    Wraps a node's typed output (e.g., task analysis, reviewer decision)
    for safe internal transport between nodes. Converts to assistant-role
    LLM message dicts via to_message().

    Attributes:
        payload_type: Identifier for the payload kind (e.g., "task_analysis").
        source_node: ID of the node that produced this payload.
        content: Polymorphic content — str, dict, StateObject, or list[dict].
        metadata: Arbitrary metadata dictionary.
    """

    payload_type: str
    source_node: str | None = None
    content: str | dict | StateObject | list[dict] = ""
    metadata: dict = field(default_factory=dict)

    def to_message(self) -> dict:
        """Convert to a single assistant-role message dict.

        Content serialization:
        - str: used directly as content
        - dict: serialized via json.dumps()
        - StateObject: serialized via .to_json()
        - list[dict]: serialized via json.dumps()

        Returns:
            Dictionary with "role" and "content" keys.
        """
        serialized_content = _serialize_content(self.content)
        return {"role": "assistant", "content": serialized_content}

    def to_messages(self) -> list[dict]:
        """Return single-element list from to_message().

        Returns:
            List containing the single assistant-role message.
        """
        return [self.to_message()]


def _serialize_content(content: str | dict | StateObject | list[dict] | None) -> str:
    """Serialize NodePayload content to a string for the message.

    Args:
        content: The content to serialize.

    Returns:
        Serialized string representation.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, StateObject):
        return content.to_json()
    if isinstance(content, (dict, list)):
        return json.dumps(content)
    msg = f"Unsupported content type: {type(content)}"
    raise TypeError(msg)
