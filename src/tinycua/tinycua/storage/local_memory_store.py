"""Local memory store for TinyCUA."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, cast

from sqlalchemy import DateTime, String, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for local memory models."""

    pass

logger = logging.getLogger(__name__)


class MemoryModel(Base):
    """Memory table model."""

    __tablename__ = "memory"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LocalMemoryStore:
    """Local key-value memory store.

    Provides simple key-value storage for agent memory
    using SQLite database.

    Note: This component is implemented for future use. Integration
    with the agent system for persistent memory/knowledge storage
    will be completed in a future stage.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize the local memory store.

        Args:
            db_path: Optional database path. Defaults to ~/.tinycua/data.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".tinycua" / "data.db")
        self._db_url = f"sqlite:///{db_path}"
        self._engine = create_engine(self._db_url)
        self._Session = sessionmaker(bind=self._engine)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure the memory table exists."""
        try:
            Base.metadata.create_all(self._engine)
        except (OSError, SQLAlchemyError):
            logger.exception("Failed to create memory table")

    def set(self, key: str, value: Any) -> bool:
        """Set a memory value.

        Args:
            key: Memory key.
            value: Value to store (must be JSON serializable).

        Returns:
            True if successful, False otherwise.
        """
        session = self._Session()
        try:
            existing = session.get(MemoryModel, key)
            if existing:
                existing.value = cast(str, json.dumps(value))
                existing.updated_at = datetime.utcnow()
            else:
                mem = MemoryModel(
                    key=key,
                    value=json.dumps(value),
                    updated_at=datetime.utcnow(),
                )
                session.add(mem)
            session.commit()
            return True
        except (OSError, SQLAlchemyError, ValueError):
            logger.exception("Failed to set memory: %s", key)
            session.rollback()
            return False
        finally:
            session.close()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a memory value.

        Args:
            key: Memory key.
            default: Default value if key not found.

        Returns:
            Value if found, default otherwise.
        """
        session = self._Session()
        try:
            mem = session.get(MemoryModel, key)
            if mem is None:
                return default
            return json.loads(cast(str, mem.value))
        except (OSError, SQLAlchemyError, ValueError):
            logger.exception("Failed to get memory: %s", key)
            return default
        finally:
            session.close()

    def delete(self, key: str) -> bool:
        """Delete a memory value.

        Args:
            key: Memory key.

        Returns:
            True if deleted, False if not found.
        """
        session = self._Session()
        try:
            mem = session.get(MemoryModel, key)
            if mem:
                session.delete(mem)
                session.commit()
                return True
            return False
        except (OSError, SQLAlchemyError):
            logger.exception("Failed to delete memory: %s", key)
            session.rollback()
            return False
        finally:
            session.close()

    def list_keys(self) -> list[str]:
        """List all memory keys.

        Returns:
            List of memory keys.
        """
        session = self._Session()
        try:
            keys = [cast(str, m.key) for m in session.query(MemoryModel).all()]
            return sorted(keys)
        except (OSError, SQLAlchemyError):
            logger.exception("Failed to list memory keys")
            return []
        finally:
            session.close()

    def clear(self) -> bool:
        """Clear all memory.

        Returns:
            True if successful, False otherwise.
        """
        session = self._Session()
        try:
            session.query(MemoryModel).delete()
            session.commit()
            return True
        except (OSError, SQLAlchemyError):
            logger.exception("Failed to clear memory")
            session.rollback()
            return False
        finally:
            session.close()
