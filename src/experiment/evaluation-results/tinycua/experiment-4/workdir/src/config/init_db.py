"""
SQLite Database Initialization Script using sqlmodel
This script sets up the database schema for the Notion-like app.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from sqlmodel import SQLModel, Session, Field
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine as sqlalchemy_create_engine


# Load environment variables from .env file
load_dotenv()


def get_database_path() -> Path:
    """Get absolute database path from workspace root (where .env is located)."""
    # Workspace root is /workspace/experiment-4 where .env resides
    # Resolve this file's location and go up to workspace root (where .env is located)
    # From src/config/init_db.py: parent=config/, grandparent=src/, great-grandparent=experiment-4/
    workspace_root = Path(__file__).resolve().parent.parent.parent
    
    env_url = os.getenv("DATABASE_URL")
    
    if not env_url or not env_url.startswith("sqlite"):
        # Default to SQLite in workspace root directory
        return workspace_root / "app.db"
    
    # Extract the path portion after 'sqlite:///' 
    # This could be relative like './experiment-4/app.db' or absolute
    path_str = env_url.replace("sqlite:///","")
    
    if path_str.startswith("/"):
        # Absolute path - use as-is and resolve to handle symlinks/etc.
        return Path(path_str).resolve()
    else:
        # Relative path - resolve from workspace root (where .env is)
        db_path = workspace_root / path_str
        return db_path.resolve()


def create_engine(db_path: Path):
    """Create SQLAlchemy engine with proper URL construction."""
    # Construct the SQLite URL from the absolute path
    db_url = f"sqlite:///{db_path}"
    return sqlalchemy_create_engine(
        db_url,
        connect_args={"check_same_thread": False}  # Allow single-threaded SQLite access in container context
    )


# Define the base class for SQLModel tables
Base = declarative_base()


# Global engine instance - created at module load time for dependency injection
db_path = get_database_path()
engine = create_engine(db_path)


# Function to create all tables
def init_database():
    """
    Initialize the database by creating all tables.

    Returns:
        The SQLAlchemy engine instance
    """
    SQLModel.metadata.create_all(engine)
    print(f"Database initialized successfully at {db_path}")
    return engine


# Function to drop all tables (useful for development/testing)
def drop_database():
    """
    Drop all tables in the database.
    """
    SQLModel.metadata.drop_all(engine)
    print(f"All tables dropped from {db_path}")


# Main initialization function - runs when script is executed directly
if __name__ == "__main__":
    # Check if we should initialize or drop database based on environment
    action = os.getenv("DB_ACTION", "init")  # Default to 'init', can be set to 'drop' for testing

    print(f"Database path: {db_path}")
    print(f"Resolved path: {db_path.resolve()}")
    
    if action.lower() == "init":
        init_database()
        print(f"Database initialized with SQLite at: {db_path}")

        # Create a session and insert some sample data for testing (optional)
        with Session(engine) as session:
            from src.models.blocks import Page
            sample_page = Page(
                id="sample-page-1",
                title="Welcome to your Notion-like App!"
            )
            session.add(sample_page)
            session.commit()
            print("Sample data inserted.")

    else:
        drop_database()
