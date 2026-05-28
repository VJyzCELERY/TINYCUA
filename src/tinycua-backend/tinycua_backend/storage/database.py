"""Database session and utilities."""

import threading
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, configure_mappers

from tinycua_backend.config import get_config
from tinycua_backend.storage.base import Base
from tinycua_sdk.storage.store import SessionStore

# Import all models to ensure relationships are set up and configure mappers
# Note: Session is managed by SessionStore, not by backend models
from tinycua_backend.tenant.models import Tenant
from tinycua_backend.auth.models import User, APIKey
from tinycua_backend.storage.models import Agent, Tool

# Mark as used for side effects
del Tenant, User, APIKey, Agent, Tool

configure_mappers()

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_engine_lock = threading.Lock()
_session_local_lock = threading.Lock()


def is_postgresql(url: str) -> bool:
    """Check if the database URL is PostgreSQL.

    Args:
        url: Database URL

    Returns:
        True if PostgreSQL, False otherwise
    """
    return url.startswith("postgresql") or url.startswith("postgres")


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                config = get_config()
                url = config.database.url

                engine_kwargs: dict[str, int | bool | str | type] = {
                    "echo": False,
                    "pool_size": config.database.pool_size,
                    "max_overflow": config.database.max_overflow,
                    "pool_recycle": config.database.pool_recycle,
                    "pool_pre_ping": config.database.pool_pre_ping,
                }

                if is_postgresql(url):
                    from sqlalchemy.pool import QueuePool

                    engine_kwargs["poolclass"] = QueuePool

                _engine = create_engine(url, **engine_kwargs)
    return _engine


def get_session_local() -> sessionmaker[Session]:
    """Get or create the session local factory."""
    global _SessionLocal
    if _SessionLocal is None:
        with _session_local_lock:
            if _SessionLocal is None:
                engine = get_engine()
                _SessionLocal = sessionmaker(
                    bind=engine, autocommit=False, expire_on_commit=False
                )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Get a database session.

    Yields:
        Database session
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


_session_store: SessionStore | None = None
_session_store_lock = threading.Lock()


def get_session_store() -> SessionStore:
    """Get cached SessionStore instance.

    The store is cached globally and recreated if the database URL changes.
    """
    global _session_store
    config = get_config()
    if _session_store is None or _session_store.database_url != config.database.url:
        with _session_store_lock:
            if _session_store is None or _session_store.database_url != config.database.url:
                _session_store = SessionStore(config.database.url)
    return _session_store
