"""SQLite FTS5 full-text search implementation."""

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

from tinycua_backend.storage.search_backend import SearchBackend


class SQLiteSearch(SearchBackend):
    """SQLite FTS5 full-text search implementation."""

    FTS_TABLE = "messages_fts"

    def initialize(self, engine: Engine) -> None:
        """Create FTS5 virtual table if it doesn't exist.

        Args:
            engine: SQLAlchemy engine
        """
        with engine.connect() as conn:
            conn.execute(
                text(f"""
                    CREATE VIRTUAL TABLE IF NOT EXISTS {self.FTS_TABLE} USING fts5(
                        message_id UNINDEXED,
                        content,
                        tokenize='porter'
                    )
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

        Args:
            engine: SQLAlchemy engine
            message_id: UUID of the message
            content: Message content to index
        """
        with engine.connect() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {self.FTS_TABLE} (message_id, content)
                    VALUES (:message_id, :content)
                """),
                {"message_id": str(message_id), "content": content},
            )
            conn.commit()

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
                text(f"""
                    SELECT message_id FROM {self.FTS_TABLE}
                    WHERE {self.FTS_TABLE} MATCH :query
                    ORDER BY rank
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

        Args:
            engine: SQLAlchemy engine
            message_id: UUID of the message to remove
        """
        with engine.connect() as conn:
            conn.execute(
                text(f"""
                    DELETE FROM {self.FTS_TABLE}
                    WHERE message_id = :message_id
                """),
                {"message_id": str(message_id)},
            )
            conn.commit()

    def reindex(self, engine: Engine) -> None:
        """Rebuild the FTS index from the messages table.

        Args:
            engine: SQLAlchemy engine
        """
        with engine.connect() as conn:
            conn.execute(
                text(f"""
                    INSERT INTO {self.FTS_TABLE}({self.FTS_TABLE})
                    VALUES('rebuild')
                """)
            )
            conn.commit()
