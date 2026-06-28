"""Node-input message helpers.

Centralises the "extract the original user query from a NodeInput" pattern
that was duplicated between ``InformationDigester._extract_original_query``
and ``QueryAnalyst._extract_user_query``. Both pull the last ``role=="user"``
message from the input's messages; the digester additionally checks the
input's ``metadata["original_query"]`` first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tinycua.models.node_input import convert_node_input_to_messages

if TYPE_CHECKING:
    from tinycua.models.node_input import NodeInputLike


def extract_user_query(
    input_data: NodeInputLike | None,
    *,
    prefer_metadata_original: bool = False,
) -> str:
    """Extract the original user query from a NodeInput.

    Args:
        input_data: The node input (NodeInput dataclass, dict, or None).
        prefer_metadata_original: When True, check
            ``input_data.metadata["original_query"]`` first and return it if
            present (the digester's behaviour). When False, only scan the
            messages (the query-analyst's behaviour).

    Returns:
        The user query string, or an empty string when no user message is
        found.
    """
    if input_data is None:
        return ""
    if prefer_metadata_original:
        metadata = getattr(input_data, "metadata", None)
        if isinstance(metadata, dict):
            original = metadata.get("original_query")
            if isinstance(original, str) and original.strip():
                return original
    try:
        messages = convert_node_input_to_messages(input_data)
    except (TypeError, ValueError):
        return ""
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    if messages:
        return str(messages[0].get("content", ""))
    return ""
