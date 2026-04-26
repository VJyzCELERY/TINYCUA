"""PostgreSQL full-text search implementation with tsvector."""

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine


class PostgreSQLSearch:
    """PostgreSQL tsvector full-text search implementation."""

    def initialize(self, engine: Engine) -> None:
        """Create search index if it doesn't exist.

        Args:
            engine: SQLAlchemy engine
        """
        with engine.connect() as conn:
            conn.execute(
                text("""
                    CREATE EXTENSION IF NOT EXISTS unaccent
                """)
            )
            conn.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_messages_content_fts
                    ON messages USING GIN(to_tsvector('english', content))
                """)
            )
            conn.commit()

    def index_message(
        self,
        engine: Engine,
        message_id: uuid.UUID,
        content: str,
    ) -> None:
        """Index a message for search.

        Note: PostgreSQL automatically indexes via the GIN index,
        this method is a no-op but kept for API compatibility.

        Args:
            engine: SQLAlchemy engine
            message_id: UUID of the message
            content: Message content to index
        """
        pass

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
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id FROM messages
                    WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                    ORDER BY ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) DESC
                    LIMIT :limit
                """),
                {"query": query, "limit": limit},
            )
            return [uuid.UUID(row[0]) for row in result.fetchall()]

    def remove_message(
        self,
        engine: Engine,
        message_id: uuid.UUID,
    ) -> None:
        """Remove a message from the search index.

        Note: PostgreSQL automatically handles removal via GIN index,
        this method is a no-op but kept for API compatibility.

        Args:
            engine: SQLAlchemy engine
            message_id: UUID of the message to remove
        """
        pass

    def reindex(self, engine: Engine) -> None:
        """Rebuild the search index.

        Args:
            engine: SQLAlchemy engine
        """
        with engine.connect() as conn:
            conn.execute(
                text("""
                    REINDEX INDEX idx_messages_content_fts
                """)
            )
            conn.commit()
