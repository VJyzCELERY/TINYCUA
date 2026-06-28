"""
Database connection/session management for Notion-like Web Application.
Handles SQLite/PostgreSQL connections and SQLAlchemy sessions. """
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from typing import Generator
import os

# Import models to ensure they're registered in Base
from app.models import User, Workspace, Page, Block, Attachment, Comment, Reaction  # noqa: F401


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.Base = declarative_base()
        
    @classmethod
    def get_connection(cls, db_url: str) -> "DatabaseManager":
        """
        Create and return a DatabaseManager instance.
        
        Args:
            db_url: SQLAlchemy database URL (sqlite:// or postgresql+asyncpg://)
            
        Returns:
            Configured DatabaseManager instance
        """
        manager = cls()
        
        # Create engine with appropriate settings for SQLite or PostgreSQL
        if "postgresql" in db_url.lower():
            pool_args = {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_pre_ping": True,  # Detect bad connections quickly
                "connect_timeout": 30,
            }
            manager.engine = create_engine(
                db_url,
                poolclass=manager._get_pool_class(),
                **pool_args
            )
        else:  # SQLite
            manager.engine = create_engine(    
                db_url.replace("sqlite://", "sqlite+aiosqlite://"),
                connect_args={"check_same_thread": False},
                pool_size=10,
                max_overflow=20,
            )
        
        # Create session factory
        manager.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=True,
            bind=manager.engine,
            class_=manager._get_session_class()
        )
        
        return manager
    
    @classmethod
    def get_db(cls) -> Generator[Session, None, None]:
        """
        Dependency for FastAPI to inject database session.
        
        Usage:
            from app.database import get_db
            
            def get_items(db: Session = Depends(get_db)):
                ...
        """
        db = cls.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @staticmethod
    def create_tables() -> None:
        """Create all database tables.
        
        Note: In production, use migrations instead of this method.
        """
        Base.metadata.create_all(bind=DatabaseManager().engine)
    
    @classmethod
    def drop_tables(cls) -> None:
        """Drop all database tables (useful for testing)."""
        if DatabaseManager().engine is not None:
            Base.metadata.drop_all(bind=DatabaseManager().engine)
    
    def _get_pool_class(self):
        from sqlalchemy.pool import NullPool
        return NullPool  # Use null pool for SQLite
    
    @staticmethod
    def _get_session_class():
        """
        Get session class that can handle both synchronous and async operations.
        In production, this would use AsyncSession with asyncio support.
        For now, we use regular Session which works well for most cases.
        """
        return sessionmaker()


# Singleton database manager instance
db_manager = DatabaseManager.get_connection(
    os.getenv("DATABASE_URL", "sqlite:///./notion.db")
)


# Export the dependency function for use in FastAPI routers
get_db = db_manager.get_db
