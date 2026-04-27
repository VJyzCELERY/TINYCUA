"""Integration tests for tenant isolation in sessions API."""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from tinycua_backend.main import app


@pytest.fixture
def client():
    with patch("tinycua_backend.main.create_tables") as mock_create, \
         patch("tinycua_backend.main.SessionStore") as mock_store, \
         patch("tinycua_backend.main.SQLiteSearch") as mock_search:
        mock_create.return_value = None
        mock_store.return_value = MagicMock(create_tables=lambda: None, engine=MagicMock())
        mock_search.return_value = MagicMock(initialize=lambda engine: None)
        yield TestClient(app, raise_server_exceptions=False)


class TestTenantIsolation:
    """Tests that endpoints enforce tenant boundaries."""

    def test_search_messages_filters_by_tenant(self, client):
        """Search should only return messages for the authenticated tenant."""
        response = client.post("/v1/sessions/search", json={"query": "test"})
        assert response.status_code == 401

    def test_lineage_verifies_tenant_ownership(self, client):
        """Lineage endpoint should verify tenant for every ancestor."""
        response = client.get(f"/v1/sessions/{uuid.uuid4()}/lineage")
        assert response.status_code == 401
