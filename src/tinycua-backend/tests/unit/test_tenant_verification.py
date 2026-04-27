"""Unit tests for tenant verification in sessions API."""

import pytest
import uuid
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from tinycua_backend.api.sessions import _verify_session_tenant


class TestVerifySessionTenant:
    """Tests for _verify_session_tenant."""

    def test_same_user_passes(self):
        """Verification succeeds when session belongs to current user."""
        session = MagicMock(user_id=uuid.uuid4())
        current = MagicMock(is_system=False, user_id=session.user_id, tenant=MagicMock(id=uuid.uuid4()))
        _verify_session_tenant(session, current)  # should not raise

    def test_system_tenant_passes(self):
        """System tenant bypasses verification."""
        session = MagicMock(user_id=uuid.uuid4())
        current = MagicMock(is_system=True, user_id=None, tenant=MagicMock(id=uuid.uuid4()))
        _verify_session_tenant(session, current)  # should not raise

    def test_different_user_raises(self):
        """Verification fails when session belongs to another user."""
        session = MagicMock(user_id=uuid.uuid4())
        current = MagicMock(is_system=False, user_id=uuid.uuid4(), tenant=MagicMock(id=uuid.uuid4()))
        with pytest.raises(HTTPException, match="Session does not belong to this tenant"):
            _verify_session_tenant(session, current)


class TestSearchMessagesTenantFilter:
    """Tests that search_messages constructs a tenant-filtered query."""

    def test_query_joins_session_and_filters_user_id(self):
        """The search endpoint should join Message with Session and filter by user_id."""
        import inspect
        from tinycua_backend.api.sessions import search_messages
        source = inspect.getsource(search_messages)
        assert "join(SessionModel" in source or "join(Session" in source
        assert "SessionModel.user_id == user_id" in source or "user_id ==" in source
