"""PostgreSQL full-text search implementation with tsvector."""

import logging
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


class PostgreSQLSearch:
    """PostgreSQL tsvector full-text search implementation."""

    def initialize(self, engine: Engine) -> None:
        """Create search index and trigger if they don't exist.

        Args:
            engine: SQLAlchemy engine
        """
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        CREATE EXTENSION IF NOT EXISTS unaccent
                    """)
                )

                conn.execute(
                    text("""
                        CREATE INDEX IF NOT EXISTS idx_messages_content_fts
                        ON messages USING GIN(content_vector)
                    """)
                )

                conn.execute(
                    text("""
                        CREATE OR REPLACE FUNCTION messages_content_vector_trigger()
                        RETURNS trigger AS $$
                        BEGIN
                            NEW.content_vector := to_tsvector('english', NEW.content);
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql
                    """)
                )

                conn.execute(
                    text("""
                        CREATE TRIGGER IF NOT EXISTS messages_content_vector_update
                        BEFORE INSERT OR UPDATE ON messages
                        FOR EACH ROW EXECUTE FUNCTION messages_content_vector_trigger()
                    """)
                )

                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize search index: {e}")
            raise

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
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE messages
                        SET content_vector = to_tsvector('english', :content)
                        WHERE id = :id
                    """),
                    {"content": content, "id": str(message_id)},
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to index message {message_id}: {e}")

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
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id FROM messages
                        WHERE content_vector @@ plainto_tsquery('english', :query)
                        ORDER BY ts_rank(content_vector, plainto_tsquery('english', :query)) DESC
                        LIMIT :limit
                    """),
                    {"query": query, "limit": limit},
                )
                return [uuid.UUID(row[0]) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def search_with_content(
        self,
        engine: Engine,
        query: str,
        limit: int = 10,
    ) -> list[dict]:
        """Search for messages matching the query and return content.

        Args:
            engine: SQLAlchemy engine
            query: Search query
            limit: Maximum number of results

        Returns:
            List of dictionaries with id and content
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT id, content FROM messages
                        WHERE content_vector @@ plainto_tsquery('english', :query)
                        ORDER BY ts_rank(content_vector, plainto_tsquery('english', :query)) DESC
                        LIMIT :limit
                    """),
                    {"query": query, "limit": limit},
                )
                return [
                    {"id": uuid.UUID(row[0]), "content": row[1]}
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.error(f"Search with content failed: {e}")
            return []

    def remove_message(
        self,
        engine: Engine,
        message_id: uuid.UUID,
    ) -> None:
        """Remove a message from the search index.

        Note: PostgreSQL handles this via the trigger,
        this method is kept for API compatibility.

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
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE messages
                        SET content_vector = to_tsvector('english', content)
                    """)
                )
                conn.commit()

                conn.execute(
                    text("""
                        REINDEX INDEX idx_messages_content_fts
                    """)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to reindex: {e}")
            raise

    def get_stats(self, engine: Engine) -> Optional[dict]:
        """Get search index statistics.

        Args:
            engine: SQLAlchemy engine

        Returns:
            Dictionary with index statistics or None on error
        """
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT
                            COUNT(*) as total_messages,
                            COUNT(content_vector) as indexed_messages,
                            COUNT(*) - COUNT(content_vector) as pending_index
                        FROM messages
                    """)
                )
                row = result.fetchone()
                if row is None:
                    return {
                        "total_messages": 0,
                        "indexed_messages": 0,
                        "pending_index": 0,
                    }
                return {
                    "total_messages": row[0],
                    "indexed_messages": row[1],
                    "pending_index": row[2],
                }
        except Exception as e:
            logger.error(f"Failed to get search stats: {e}")
            return None
