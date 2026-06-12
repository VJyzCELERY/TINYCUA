"""Propagation logic for TinyCUA node context."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from tinycua.models.chat_record import ChatRecord
from tinycua.models.session import Session
from tinycua.models.session_context_entry import SessionContextEntry

logger = logging.getLogger(__name__)


@dataclass
class PropagationRule:
    """Configuration controlling what crosses node/session boundaries.

    Attributes:
        chat_history: Where to append ChatRecord audit trail.
        session_context_target: Where to propagate session context.
        session_context_mode: How much context to propagate.
        token_usage: Where to propagate token usage.
        failure: Where to propagate failure information.
        dedupe: Whether to deduplicate records during propagation.
    """

    chat_history: Literal["none", "parent", "root", "parent_and_root"] = "none"
    session_context_target: Literal["none", "parent", "root", "parent_and_root"] = "none"
    session_context_mode: Literal["none", "final", "full", "selected"] = "none"
    token_usage: Literal["none", "parent", "root", "parent_and_root"] = "none"
    failure: Literal["none", "parent", "root", "parent_and_root"] = "none"
    dedupe: bool = False


# Predefined propagation profiles
PROPAGATION_PROFILES: dict[str, PropagationRule] = {
    "transient_legacy": PropagationRule(
        chat_history="none",
        session_context_target="none",
        session_context_mode="none",
        token_usage="none",
        failure="none",
        dedupe=False,
    ),
    "natural_termination_legacy": PropagationRule(
        chat_history="parent_and_root",
        session_context_target="parent_and_root",
        session_context_mode="final",
        token_usage="parent_and_root",
        failure="parent_and_root",
        dedupe=True,
    ),
    "mid_progress_legacy": PropagationRule(
        chat_history="parent",
        session_context_target="parent",
        session_context_mode="full",
        token_usage="parent",
        failure="parent",
        dedupe=False,
    ),
    "selected_internal_output": PropagationRule(
        chat_history="root",
        session_context_target="root",
        session_context_mode="selected",
        token_usage="root",
        failure="root",
        dedupe=True,
    ),
}


def dedupe_records(
    source: list[SessionContextEntry],
    destination: list[SessionContextEntry],
) -> list[SessionContextEntry]:
    """Filter source records against destination by origin_record_id.

    When origin_record_id is present, compares by origin_record_id.
    Falls back to record_id when origin_record_id is None.

    Args:
        source: Records to filter.
        destination: Existing records to check against.

    Returns:
        Filtered list of records not already in destination.
    """
    # Build lookup of existing records by origin_record_id and record_id
    existing_origin_ids: set[str] = set()
    existing_record_ids: set[str] = set()

    for entry in destination:
        if entry.origin_record_id:
            existing_origin_ids.add(entry.origin_record_id)
        existing_record_ids.add(entry.record_id)

    filtered: list[SessionContextEntry] = []
    for entry in source:
        # Check by origin_record_id if present
        if entry.origin_record_id:
            if entry.origin_record_id not in existing_origin_ids:
                filtered.append(entry)
        # Fall back to record_id
        elif entry.record_id not in existing_record_ids:
            filtered.append(entry)

    return filtered


def _append_chat_record(
    session: Session,
    record: ChatRecord,
) -> None:
    """Append a ChatRecord to a session's chat_history.

    Args:
        session: Target session.
        record: ChatRecord to append.
    """
    session.chat_history.append(record)
    logger.debug(
        "appended_chat_record session=%s record_type=%s",
        session.session_id,
        record.record_type,
    )


def _propagate_context_to_session(
    source_entries: list[SessionContextEntry],
    target_session: Session,
    dedupe: bool,
) -> None:
    """Propagate context entries to a target session.

    Args:
        source_entries: Entries to propagate.
        target_session: Target session to propagate to.
        dedupe: Whether to deduplicate records.
    """
    if dedupe:
        entries_to_add = dedupe_records(source_entries, target_session.session_context)
    else:
        entries_to_add = source_entries

    target_session.session_context.extend(entries_to_add)
    logger.debug(
        "propagated_context target_session=%s entries_added=%d",
        target_session.session_id,
        len(entries_to_add),
    )


def propagate_on_termination(
    node_session: Session,
    parent_session: Session | None,
    root_session: Session,
    rule: PropagationRule,
) -> None:
    """Propagate context on node termination.

    Prior + input segments propagate upward to parent/root.
    Output segment is excluded from upward propagation (forwarded separately).

    Args:
        node_session: The terminating node's session.
        parent_session: The parent session (may be None for root nodes).
        root_session: The root session.
        rule: Propagation rule to apply.
    """
    # Separate entries by segment
    prior_entries: list[SessionContextEntry] = []
    input_entries: list[SessionContextEntry] = []
    output_entries: list[SessionContextEntry] = []

    for entry in node_session.session_context:
        if entry.segment == "prior":
            prior_entries.append(entry)
        elif entry.segment == "input":
            input_entries.append(entry)
        elif entry.segment == "output":
            output_entries.append(entry)

    # Propagate prior + input segments upward
    entries_to_propagate = prior_entries + input_entries

    # Propagate to parent if rule says so
    if parent_session is not None and rule.session_context_target in ("parent", "parent_and_root"):
        _propagate_context_to_session(entries_to_propagate, parent_session, rule.dedupe)

    # Propagate to root if rule says so
    if rule.session_context_target in ("root", "parent_and_root"):
        _propagate_context_to_session(entries_to_propagate, root_session, rule.dedupe)

    # Append ChatRecord to chat_history if rule says so
    if rule.chat_history != "none" and output_entries:
        record = ChatRecord(
            role="assistant",
            record_type="propagation",
            content=[entry.content for entry in output_entries],
            visibility="internal",
            source_node_id=node_session.session_id,
            source_session_id=node_session.session_id,
            created_seq=max(entry.created_seq for entry in output_entries) if output_entries else 0,
        )

        if rule.chat_history in ("parent", "parent_and_root") and parent_session is not None:
            _append_chat_record(parent_session, record)

        if rule.chat_history in ("root", "parent_and_root"):
            _append_chat_record(root_session, record)

    logger.debug(
        "propagate_on_termination node_session=%s prior=%d input=%d output=%d",
        node_session.session_id,
        len(prior_entries),
        len(input_entries),
        len(output_entries),
    )


def forward_output_to_next(
    node_session: Session,
    next_node_input: Any,
) -> list[SessionContextEntry]:
    """Forward output segment to next node as NodeInput.

    Args:
        node_session: The terminating node's session.
        next_node_input: Input for the next node.

    Returns:
        List of output entries to forward.
    """
    output_entries = [
        entry for entry in node_session.session_context
        if entry.segment == "output"
    ]

    logger.debug(
        "forward_output_to_next node_session=%s output_count=%d",
        node_session.session_id,
        len(output_entries),
    )

    return output_entries


def finalize_terminal_output(
    terminal_session: Session,
    root_session: Session,
) -> str | None:
    """Finalize terminal output exception.

    Terminal ResponseNode output is committed to root session_context
    and returned to SDK caller, not forwarded to a next node.

    Args:
        terminal_session: The terminal node's session.
        root_session: The root session.

    Returns:
        The terminal output content string, or None if no output.
    """
    output_entries = [
        entry for entry in terminal_session.session_context
        if entry.segment == "output"
    ]

    if not output_entries:
        return None

    # Commit output to root session_context
    root_session.session_context.extend(output_entries)

    # Return the content string of the first output entry
    first_output = output_entries[0]
    content = first_output.content if isinstance(first_output.content, str) else str(first_output.content)

    logger.debug(
        "finalize_terminal_output terminal_session=%s root_session=%s content_len=%d",
        terminal_session.session_id,
        root_session.session_id,
        len(content),
    )

    return content