"""Guest session management for temporary, non-persistent sessions."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass
class GuestMessage:
    """A message in a guest session."""

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GuestSession:
    """A temporary guest session.

    Guest sessions are:
    - Non-persistent (in-memory only)
    - Shared among multiple users
    - Auto-expire after inactivity
    """

    id: str
    agent_id: str
    messages: list[GuestMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        self.messages.append(GuestMessage(role=role, content=content))
        self.last_accessed = datetime.utcnow()

    def get_messages(self) -> list[dict[str, str]]:
        """Get messages as dict list."""
        return [{"role": m.role, "content": m.content} for m in self.messages]


class GuestSessionStore:
    """In-memory store for guest sessions.

    Sessions auto-expire after inactivity_timeout.
    """

    def __init__(self, inactivity_timeout: int = 30):
        """Initialize guest session store.

        Args:
            inactivity_timeout: Minutes before session expires
        """
        self._sessions: dict[str, GuestSession] = {}
        self._inactivity_timeout = timedelta(minutes=inactivity_timeout)
        self._cleanup_task: asyncio.Task | None = None

    def create_session(self, agent_id: str, metadata: dict[str, Any] = None) -> str:
        """Create a new guest session.

        Args:
            agent_id: The agent ID to use
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        session_id = f"guest_{uuid.uuid4().hex[:16]}"
        self._sessions[session_id] = GuestSession(
            id=session_id,
            agent_id=agent_id,
            metadata=metadata or {},
        )
        return session_id

    def get_session(self, session_id: str) -> GuestSession | None:
        """Get a session by ID.

        Args:
            session_id: The session ID

        Returns:
            GuestSession or None if not found/expired
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        # Check expiration
        if datetime.utcnow() - session.last_accessed > self._inactivity_timeout:
            del self._sessions[session_id]
            return None

        session.last_accessed = datetime.utcnow()
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[GuestSession]:
        """List all active sessions."""
        self._cleanup_expired()
        return list(self._sessions.values())

    def _cleanup_expired(self) -> int:
        """Remove expired sessions.

        Returns:
            Number of sessions removed
        """
        now = datetime.utcnow()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_accessed > self._inactivity_timeout
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task:
            return

        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # Check every minute
                count = self._cleanup_expired()
                if count > 0:
                    print(f"Guest session store: cleaned up {count} expired sessions")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None


# Global guest session store instance
_guest_sessions = GuestSessionStore(inactivity_timeout=30)


def get_guest_session_store() -> GuestSessionStore:
    """Get the global guest session store."""
    return _guest_sessions
