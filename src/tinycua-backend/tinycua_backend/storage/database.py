"""Database session and utilities."""

import threading
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, configure_mappers

from tinycua_backend.config import get_config
from tinycua_backend.storage.base import Base

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


def get_engine() -> Engine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                config = get_config()
                _engine = create_engine(
                    config.database.url,
                    echo=False,
                    pool_size=config.database.pool_size,
                    max_overflow=config.database.max_overflow,
                    pool_recycle=config.database.pool_recycle,
                    pool_pre_ping=config.database.pool_pre_ping,
                )
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
