"""Unit tests for PostgreSQL-specific functionality."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError


class TestPostgresSearch:
    """Tests for PostgreSQL search module."""

    def test_search_returns_empty_list_on_error(self):
        """Test that search returns empty list on database error."""
        from tinycua_backend.storage.search_postgres import PostgreSQLSearch

        search = PostgreSQLSearch()
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")

        result = search.search(mock_engine, "test query")
        assert result == []

    def test_search_with_content_returns_empty_list_on_error(self):
        """Test that search_with_content returns empty list on error."""
        from tinycua_backend.storage.search_postgres import PostgreSQLSearch

        search = PostgreSQLSearch()
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")

        result = search.search_with_content(mock_engine, "test query")
        assert result == []

    def test_get_stats_returns_none_on_error(self):
        """Test that get_stats returns None on error."""
        from tinycua_backend.storage.search_postgres import PostgreSQLSearch

        search = PostgreSQLSearch()
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")

        result = search.get_stats(mock_engine)
        assert result is None

    def test_index_message_handles_error(self):
        """Test that index_message handles errors gracefully."""
        from tinycua_backend.storage.search_postgres import PostgreSQLSearch

        search = PostgreSQLSearch()
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")

        search.index_message(mock_engine, uuid.uuid4(), "test content")

    def test_reindex_raises_on_error(self):
        """Test that reindex raises exception on error."""
        from tinycua_backend.storage.search_postgres import PostgreSQLSearch

        search = PostgreSQLSearch()
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")

        with pytest.raises(SQLAlchemyError):
            search.reindex(mock_engine)

    def test_initialize_raises_on_error(self):
        """Test that initialize raises exception on error."""
        from tinycua_backend.storage.search_postgres import PostgreSQLSearch

        search = PostgreSQLSearch()
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = SQLAlchemyError("Connection failed")

        with pytest.raises(SQLAlchemyError):
            search.initialize(mock_engine)


class TestMigrationValidation:
    """Tests for migration table name validation."""

    def test_validate_table_name_accepts_valid_tables(self):
        """Test that validate_table_name accepts valid table names."""
        from tinycua_backend.migrations.migrate_sqlite_to_postgres import validate_table_name

        for table in ["tenants", "users", "api_keys", "agents", "tools", "sessions", "messages"]:
            result = validate_table_name(table)
            assert result == table

    def test_validate_table_name_rejects_invalid_tables(self):
        """Test that validate_table_name rejects invalid table names."""
        from tinycua_backend.migrations.migrate_sqlite_to_postgres import validate_table_name

        with pytest.raises(ValueError):
            validate_table_name("invalid_table")

    def test_allowed_tables_is_frozen_set(self):
        """Test that ALLOWED_TABLES is a frozenset."""
        from tinycua_backend.migrations.migrate_sqlite_to_postgres import ALLOWED_TABLES

        assert isinstance(ALLOWED_TABLES, frozenset)
        assert "tenants" in ALLOWED_TABLES
        assert "users" in ALLOWED_TABLES
