"""Database session and utilities."""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, configure_mappers

from tinycua_backend.config import get_config
from tinycua_backend.models.base import Base

# Import all models to ensure relationships are set up and configure mappers
# Note: Session is managed by SessionStore, not by backend models
from tinycua_backend.models import Tenant, User, APIKey, Agent, Tool

# Mark as used for side effects
del Tenant, User, APIKey, Agent, Tool

configure_mappers()

_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        config = get_config()
        _engine = create_engine(config.database.url, echo=False)
    return _engine


def get_session_local():
    """Get or create the session local factory."""
    global _SessionLocal
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


def create_tables():
    """Create all database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
