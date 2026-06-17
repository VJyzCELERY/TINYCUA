"""NodeInput dataclass for internal transport between nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from tinycua.models.node_handoff import NodeHandoff
from tinycua.models.node_payload import NodePayload
from tinycua.models.state_object import StateObject


@dataclass
class NodeInput(StateObject):
    """Internal transport envelope for node-to-node handoff.

    Wraps payloads and continuation messages for passing between nodes.
    Converts to a list of LLM message dicts via to_messages(), with
    payloads converted to assistant messages followed by continuation
    messages.

    Attributes:
        input_type: Identifier for the input kind (e.g., "continuation").
        source_node: ID of the node that produced this input.
        target_node: ID of the intended recipient node.
        messages: Continuation messages as role/content dicts.
        payloads: Structured payloads from the source node.
        metadata: Arbitrary metadata dictionary.
    """

    input_type: str
    source_node: str | None = None
    target_node: str | None = None
    messages: list[dict] = field(default_factory=list)
    payloads: list[NodePayload] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_messages(self) -> list[dict]:
        """Convert to list of message dicts.

        Order: payloads converted via NodePayload.to_message(),
        then self.messages appended in order.

        Returns:
            List of message dictionaries.
        """
        result = []
        for payload in self.payloads:
            result.extend(payload.to_messages())
        result.extend(self.messages)
        return result


# Type alias for flexible node input
NodeInputLike: TypeAlias = str | NodeInput | NodePayload | NodeHandoff | list[dict] | dict


def convert_node_input_to_messages(
    node_input: NodeInputLike,
    *,
    source: Literal["external", "internal"] = "internal",
) -> list[dict]:
    """Convert any NodeInputLike variant to a list of message dicts.

    Conversion rules:
    - str + source="external" -> [{"role": "user", "content": text}]
    - str + source="internal" -> [{"role": "assistant", "content": text}]
    - NodeInput -> node_input.to_messages()
    - NodePayload -> node_payload.to_messages()
    - list[dict] -> passed through directly

    Args:
        node_input: The input to convert.
        source: Whether the string is from an external user or internal node.
            Only used when node_input is a string. Defaults to "internal".

    Returns:
        List of message dictionaries.
    """
    if isinstance(node_input, str):
        if not node_input.strip():
            msg = "Empty input"
            raise ValueError(msg)
        role = "user" if source == "external" else "assistant"
        return [{"role": role, "content": node_input}]
    if isinstance(node_input, NodeInput):
        return node_input.to_messages()
    if isinstance(node_input, NodePayload):
        return node_input.to_messages()
    if isinstance(node_input, NodeHandoff):
        return [node_input.to_message()]
    if isinstance(node_input, list):
        return node_input
    if isinstance(node_input, dict) and not node_input:
        return []
    msg = f"Unsupported NodeInputLike type: {type(node_input)}"
    raise TypeError(msg)
