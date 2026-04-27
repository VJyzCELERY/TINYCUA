"""Local storage manager for TinyCUA."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TINYCUA_DIR = Path.home() / ".tinycua"
DEFAULT_DB_PATH = TINYCUA_DIR / "data.db"


class LocalStorageManager:
    """Manager for local SQLite storage.

    Handles database initialization, schema creation,
    and provides access to session and memory stores.
    """

    _instance: Optional[LocalStorageManager] = None
    _initialized: bool = False

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the local storage manager.

        Args:
            db_path: Optional path to SQLite database. Defaults to ~/.tinycua/data.db
        """
        self._db_path = db_path or DEFAULT_DB_PATH
        self._ensure_directory()

    @classmethod
    def get_instance(cls, db_path: Optional[Path] = None) -> LocalStorageManager:
        """Get or create the singleton instance.

        Args:
            db_path: Optional path to SQLite database.

        Returns:
            LocalStorageManager instance.
        """
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    def _ensure_directory(self) -> None:
        """Ensure the ~/.tinycua directory exists."""
        try:
            TINYCUA_DIR.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError):
            logger.exception("Failed to create tinycua directory")

    @property
    def db_path(self) -> Path:
        """Get the database path.

        Returns:
            Path to SQLite database.
        """
        return self._db_path

    @property
    def database_url(self) -> str:
        """Get the SQLAlchemy database URL.

        Returns:
            Database URL string.
        """
        return f"sqlite:///{self._db_path}"

    def is_initialized(self) -> bool:
        """Check if storage is initialized.

        Returns:
            True if database tables exist.
        """
        return self._initialized

    def initialize(self) -> bool:
        """Initialize the database and create tables.

        Returns:
            True if successful, False otherwise.
        """
        try:
            from tinycua_sdk.storage.store import SessionStore

            store = SessionStore(self.database_url)
            store.create_tables()
            self._initialized = True
            logger.info("Database initialized at %s", self._db_path)
            return True
        except (OSError, ValueError, ImportError):
            logger.exception("Failed to initialize database")
            return False

    def get_store(self):
        """Get the session store instance.

        Returns:
            SessionStore instance or None on error.
        """
        try:
            from tinycua_sdk.storage.store import SessionStore

            return SessionStore(self.database_url)
        except (OSError, ValueError, ImportError):
            logger.exception("Failed to get session store")
            return None

    def backup(self, backup_path: Optional[Path] = None) -> bool:
        """Create a backup of the database.

        Args:
            backup_path: Optional backup path. Defaults to data.db.backup.

        Returns:
            True if successful, False otherwise.
        """
        if not self._db_path.exists():
            return False

        try:
            backup = backup_path or Path(str(self._db_path) + ".backup")
            shutil.copy2(self._db_path, backup)
            logger.info("Database backed up to %s", backup)
            return True
        except (OSError, shutil.SameFileError):
            logger.exception("Failed to backup database")
            return False

    def get_storage_info(self) -> dict:
        """Get storage information.

        Returns:
            Dictionary with storage info.
        """
        info = {
            "db_path": str(self._db_path),
            "exists": self._db_path.exists(),
            "size_bytes": 0,
            "initialized": self._initialized,
        }

        if self._db_path.exists():
            try:
                info["size_bytes"] = self._db_path.stat().st_size
            except (OSError, PermissionError):
                pass

        return info
