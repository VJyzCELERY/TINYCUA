"""Session utilities for agents.

These are utility functions, NOT tools. They manage session lifecycle.
"""

from typing import Any

from tinycua_sdk.session.session import Session


def create_session(name: str = "Untitled Session") -> dict:
    """Create a new session.

    Args:
        name: The name for the session

    Returns:
        Result dict with session_id and name

    """
    session = Session(system_prompt=name)
    session.save()
    return {
        "success": True,
        "session_id": session.session_id,
        "name": name,
    }


def save_session(
    session_id: str,
    messages: list[dict[str, Any]],
    name: str | None = None,
) -> dict:
    """Save messages to a session.

    Args:
        session_id: The session ID to save to
        messages: List of message dicts with role and content
        name: Optional new name for the session

    Returns:
        Result dict with success status

    """
    session = Session(session_id=session_id)
    if name:
        session.system_prompt = name
    session.messages = messages
    session.save()
    return {"success": True, "session_id": session.session_id}


def load_session(session_id: str) -> dict:
    """Load a session by ID.

    Args:
        session_id: The session ID to load

    Returns:
        Result dict with session data or error

    """
    session = Session(session_id=session_id)
    if session.load():
        return {
            "success": True,
            "session_id": session.session_id,
            "name": session.system_prompt,
            "messages": session.messages,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }
    return {"success": False, "error": f"Session {session_id} not found"}


def list_sessions() -> dict:
    """List all saved sessions.

    Returns:
        Result dict with list of sessions

    """
    session = Session()
    session_ids = session.list_sessions()

    sessions = []
    for sid in session_ids:
        s = Session(session_id=sid)
        if s.load():
            sessions.append(
                {
                    "session_id": s.session_id,
                    "name": s.system_prompt,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
            )

    return {"sessions": sessions}


def delete_session(session_id: str) -> dict:
    """Delete a session by ID.

    Args:
        session_id: The session ID to delete

    Returns:
        Result dict with success status

    """
    session = Session(session_id=session_id)
    if session.delete():
        return {"success": True, "session_id": session_id}
    return {"success": False, "error": f"Session {session_id} not found"}


__all__ = [
    "create_session",
    "save_session",
    "load_session",
    "list_sessions",
    "delete_session",
]
