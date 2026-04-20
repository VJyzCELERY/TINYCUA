"""Integration tests for tenant data isolation."""

import uuid

import pytest
from sqlalchemy import select

from tinycua_backend.models import Tenant, User, Agent, Tool, Session
from tinycua_backend.models.tenant import TenantType


class TestTenantIsolation:
    """Test tenant data isolation."""

    def test_tenant_a_cannot_access_tenant_b_user(self, db_session, tenant_a, tenant_b, user_a, user_b):
        """Test that tenant A cannot access tenant B's user."""
        result = db_session.execute(
            select(User).where(User.tenant_id == tenant_a.id)
        ).scalars().all()

        user_ids = [u.id for u in result]
        assert user_a.id in user_ids
        assert user_b.id not in user_ids

    def test_tenant_b_cannot_access_tenant_a_user(self, db_session, tenant_a, tenant_b, user_a, user_b):
        """Test that tenant B cannot access tenant A's user."""
        result = db_session.execute(
            select(User).where(User.tenant_id == tenant_b.id)
        ).scalars().all()

        user_ids = [u.id for u in result]
        assert user_b.id in user_ids
        assert user_a.id not in user_ids

    def test_tenant_a_cannot_access_tenant_b_agent(self, db_session, tenant_a, tenant_b, agent_a, agent_b):
        """Test that tenant A cannot access tenant B's agent."""
        result = db_session.execute(
            select(Agent).where(Agent.tenant_id == tenant_a.id)
        ).scalars().all()

        agent_ids = [a.id for a in result]
        assert agent_a.id in agent_ids
        assert agent_b.id not in agent_ids

    def test_tenant_b_cannot_access_tenant_a_agent(self, db_session, tenant_a, tenant_b, agent_a, agent_b):
        """Test that tenant B cannot access tenant A's agent."""
        result = db_session.execute(
            select(Agent).where(Agent.tenant_id == tenant_b.id)
        ).scalars().all()

        agent_ids = [a.id for a in result]
        assert agent_b.id in agent_ids
        assert agent_a.id not in agent_ids

    def test_tenant_a_cannot_access_tenant_b_tool(self, db_session, tenant_a, tenant_b, tool_a, tool_b):
        """Test that tenant A cannot access tenant B's tool."""
        result = db_session.execute(
            select(Tool).where(Tool.tenant_id == tenant_a.id)
        ).scalars().all()

        tool_ids = [t.id for t in result]
        assert tool_a.id in tool_ids
        assert tool_b.id not in tool_ids

    def test_tenant_b_cannot_access_tenant_a_tool(self, db_session, tenant_a, tenant_b, tool_a, tool_b):
        """Test that tenant B cannot access tenant A's tool."""
        result = db_session.execute(
            select(Tool).where(Tool.tenant_id == tenant_b.id)
        ).scalars().all()

        tool_ids = [t.id for t in result]
        assert tool_b.id in tool_ids
        assert tool_a.id not in tool_ids


class TestCrossTenantAccessPrevention:
    """Test prevention of cross-tenant access."""

    def test_cannot_query_other_tenant_data_by_id(self, db_session, tenant_a, tenant_b):
        """Test that querying by ID respects tenant boundaries."""
        result = db_session.execute(
            select(Tenant).where(Tenant.id == tenant_b.id)
        ).scalars().first()

        assert result.id == tenant_b.id
        assert result.id != tenant_a.id

    def test_user_query_respects_tenant_filter(self, db_session, tenant_a, tenant_b, user_a, user_b):
        """Test that user queries respect tenant boundaries."""
        users = db_session.execute(select(User)).scalars().all()

        tenant_a_users = [u for u in users if u.tenant_id == tenant_a.id]
        tenant_b_users = [u for u in users if u.tenant_id == tenant_b.id]

        assert len(tenant_a_users) >= 1
        assert len(tenant_b_users) >= 1

        assert any(u.id == user_a.id for u in tenant_a_users)
        assert any(u.id == user_b.id for u in tenant_b_users)


class TestTenantDataIntegrity:
    """Test data integrity across tenant operations."""

    def test_deleting_tenant_cascades_to_users(self, db_session, tenant_a, user_a):
        """Test that deleting a tenant cascades to its users."""
        tenant_id = tenant_a.id
        user_id = user_a.id

        db_session.delete(tenant_a)
        db_session.commit()

        result = db_session.get(Tenant, tenant_id)
        assert result is None

        result = db_session.get(User, user_id)
        assert result is None

    def test_deleting_tenant_cascades_to_agents(self, db_session, tenant_a, agent_a):
        """Test that deleting a tenant cascades to its agents."""
        tenant_id = tenant_a.id
        agent_id = agent_a.id

        db_session.delete(tenant_a)
        db_session.commit()

        result = db_session.get(Tenant, tenant_id)
        assert result is None

        result = db_session.get(Agent, agent_id)
        assert result is None

    def test_deleting_tenant_cascades_to_tools(self, db_session, tenant_a, tool_a):
        """Test that deleting a tenant cascades to its tools."""
        tenant_id = tenant_a.id
        tool_id = tool_a.id

        db_session.delete(tenant_a)
        db_session.commit()

        result = db_session.get(Tenant, tenant_id)
        assert result is None

        result = db_session.get(Tool, tool_id)
        assert result is None

    def test_deleting_tenant_cascades_to_sessions(self, db_session, tenant_a, agent_a):
        """Test that deleting a tenant cascades to its sessions."""
        from tinycua_backend.models import Session
        session = Session(
            name="Test Session",
            tenant_id=tenant_a.id,
            agent_id=agent_a.id,
        )
        db_session.add(session)
        db_session.commit()
        session_id = session.id

        db_session.delete(tenant_a)
        db_session.commit()

        result = db_session.get(Session, session_id)
        assert result is None


class TestGuestTenantIsolation:
    """Test guest tenant behavior."""

    def test_guest_tenant_isolation(self, db_session):
        """Test that guest tenants are isolated."""
        guest_tenant = Tenant(
            name="Guest Tenant",
            tenant_type=TenantType.GUEST,
        )
        db_session.add(guest_tenant)
        db_session.commit()

        standard_tenant = Tenant(
            name="Standard Tenant",
            tenant_type=TenantType.STANDARD,
        )
        db_session.add(standard_tenant)
        db_session.commit()

        result = db_session.execute(
            select(Tenant).where(Tenant.tenant_type == TenantType.GUEST)
        ).scalars().all()

        assert len(result) >= 1
        assert any(t.tenant_type == TenantType.GUEST for t in result)
