"""Session-context query helpers.

Centralises the repeated "scan ``session.session_context`` for the latest
entry of a given content type" pattern that was duplicated across six
call sites (orchestration_mixin, worker, task_create, query_analyst,
task_nodes). Callers post-process the returned object; the scan itself
is identical everywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tinycua.models.session_context_entry import entry_content

if TYPE_CHECKING:
    from tinycua.models.session import Session


def find_latest_entry(
    session: Session,
    content_type: type,
    *,
    reverse: bool = True,
) -> Any | None:
    """Return the latest session_context entry whose content is ``content_type``.

    Args:
        session: The session whose ``session_context`` is scanned.
        content_type: The type to match on the entry's content.
        reverse: When True (default), scan newest-first and return the most
            recent match. When False, scan oldest-first and return the first
            match.

    Returns:
        The matching content object, or ``None`` when no entry matches.
    """
    entries = list(session.session_context)
    if reverse:
        entries.reverse()
    for entry in entries:
        content = entry_content(entry)
        if isinstance(content, content_type):
            return content
    return None


def has_entry(session: Session, content_type: type) -> bool:
    """Return whether ``session.session_context`` has any entry of ``content_type``."""
    return find_latest_entry(session, content_type) is not None
