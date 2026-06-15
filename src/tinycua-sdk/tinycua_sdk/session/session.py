"""Session management for conversation state."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class Session:
    """A conversation session with message history."""

    def __init__(
        self,
        session_id: str | None = None,
        storage_path: str | None = None,
        system_prompt: str = "You are a helpful assistant.",
    ):
        """Initialize a session.

        Args:
            session_id: Unique session ID (generated if not provided)
            storage_path: Path to store session data
            system_prompt: System prompt for the session

        """
        import uuid

        self.session_id = session_id or str(uuid.uuid4())
        self.storage_path = Path(storage_path or self._default_storage_path())
        self.system_prompt = system_prompt
        self.messages: list[dict[str, Any]] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session.

        Args:
            role: Message role (user, assistant, tool)
            content: Message content
            **kwargs: Additional message metadata

        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }
        message.update(kwargs)
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def get_messages(self) -> list[dict[str, Any]]:
        """Get all messages."""
        return self.messages

    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages = []
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Serialize session to dict."""
        return {
            "session_id": self.session_id,
            "system_prompt": self.system_prompt,
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Deserialize session from dict."""
        session = cls(
            session_id=data.get("session_id"),
            system_prompt=data.get("system_prompt", "You are a helpful assistant."),
        )
        session.messages = data.get("messages", [])
        session.created_at = datetime.fromisoformat(
            data.get("created_at", datetime.utcnow().isoformat())
        )
        session.updated_at = datetime.fromisoformat(
            data.get("updated_at", datetime.utcnow().isoformat())
        )
        return session

    def save(self) -> None:
        """Save session to disk."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        file_path = self.storage_path / f"{self.session_id}.json"
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load(self, session_id: str | None = None) -> bool:
        """Load session from disk.

        Args:
            session_id: Session ID to load (uses self.session_id if None)

        Returns:
            True if loaded successfully

        """
        load_id = session_id or self.session_id
        file_path = self.storage_path / f"{load_id}.json"

        if not file_path.exists():
            return False

        with open(file_path, "r") as f:
            data = json.load(f)

        loaded = Session.from_dict(data)
        self.session_id = loaded.session_id
        self.messages = loaded.messages
        self.system_prompt = loaded.system_prompt
        self.created_at = loaded.created_at
        self.updated_at = loaded.updated_at
        return True

    def delete(self) -> bool:
        """Delete session from disk.

        Returns:
            True if deleted successfully

        """
        file_path = self.storage_path / f"{self.session_id}.json"
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all session IDs in storage."""
        if not self.storage_path.exists():
            return []
        return [p.stem for p in self.storage_path.glob("*.json")]

    @staticmethod
    def _default_storage_path() -> str:
        """Get default storage path."""
        home = Path.home()
        tinycua_dir = home / ".tinycua" / "sessions"
        return str(tinycua_dir)


__all__ = ["Session"]
