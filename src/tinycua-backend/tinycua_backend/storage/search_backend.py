"""Search backend protocol for tinycua-backend."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy.engine import Engine


class SearchBackend(Protocol):
    """Protocol for full-text search backends."""

    def initialize(self, engine: Engine) -> None:
        """Create search index if it doesn't exist.

        Args:
            engine: SQLAlchemy engine
        """
        ...

    def index_message(
        self,
        engine: Engine,
        message_id: uuid.UUID,
        content: str,
    ) -> None:
        """Index a message for search.

        Args:
            engine: SQLAlchemy engine
            message_id: UUID of the message
            content: Message content to index
        """
        ...

    def search(
        self,
        engine: Engine,
        query: str,
        limit: int = 10,
    ) -> list[uuid.UUID]:
        """Search for messages matching the query.

        Args:
            engine: SQLAlchemy engine
            query: Search query
            limit: Maximum number of results

        Returns:
            List of message IDs matching the query
        """
        ...

    def remove_message(
        self,
        engine: Engine,
        message_id: uuid.UUID,
    ) -> None:
        """Remove a message from the search index.

        Args:
            engine: SQLAlchemy engine
            message_id: UUID of the message to remove
        """
        ...

    def reindex(self, engine: Engine) -> None:
        """Rebuild the search index.

        Args:
            engine: SQLAlchemy engine
        """
        ...
