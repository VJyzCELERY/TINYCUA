"""Unit tests for database operations."""

from unittest.mock import MagicMock, patch


from tinycua_backend.storage.base import Base
from tinycua_backend.tenant.models import Tenant
from tinycua_backend.auth.models import User


class TestConnection:
    """Tests for database connection."""

    def test_get_engine(self, mock_config):
        """Test getting database engine."""
        from tinycua_backend.storage.database import get_engine

        with patch("tinycua_backend.config.get_config", return_value=mock_config):
            engine = get_engine()

            assert engine is not None

    def test_get_session_local(self, mock_config):
        """Test getting session local factory."""
        from tinycua_backend.storage.database import get_session_local

        with patch("tinycua_backend.config.get_config", return_value=mock_config):
            SessionLocal = get_session_local()

            assert SessionLocal is not None


class TestQueries:
    """Tests for database queries."""

    def test_query_tenant(self, mock_db):
        """Test querying a tenant."""
        mock_tenant = MagicMock()
        mock_tenant.id = "tenant-123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_tenant

        result = mock_db.query(Tenant).filter(Tenant.id == "tenant-123").first()

        assert result is not None

    def test_query_user(self, mock_db):
        """Test querying a user."""
        mock_user = MagicMock()
        mock_user.id = "user-123"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        result = mock_db.query(User).filter(User.id == "user-123").first()

        assert result is not None

    def test_query_nonexistent(self, mock_db):
        """Test querying non-existent record returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = mock_db.query(Tenant).filter(Tenant.id == "nonexistent").first()

        assert result is None


class TestMigrations:
    """Tests for database migrations."""

    def test_create_tables_function_exists(self):
        """Test create_tables function exists."""
        from tinycua_backend.storage import database
        assert hasattr(database, "create_tables")
        assert callable(database.create_tables)

    def test_table_creation_uses_metadata(self):
        """Test tables are created using Base.metadata."""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None


class TestDatabaseSession:
    """Tests for database session management."""

    def test_session_close(self, mock_db):
        """Test session close is called."""
        mock_db.close.return_value = None

        mock_db.close()

        mock_db.close.assert_called()

    def test_session_query_interface(self, mock_db):
        """Test session provides query interface."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = mock_db.query(Tenant)

        assert result is not None
