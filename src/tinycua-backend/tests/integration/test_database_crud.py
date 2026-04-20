"""Integration tests for database CRUD operations."""

import uuid

import pytest
from sqlalchemy import select

from tinycua_backend.models import Tenant, User, Agent, Tool
from tinycua_backend.models.tenant import TenantType


class TestTenantCRUD:
    """Test CRUD operations for Tenant."""

    def test_create_tenant(self, db_session):
        """Test creating a new tenant."""
        tenant = Tenant(
            name="Test Tenant",
            tenant_type=TenantType.STANDARD,
        )
        db_session.add(tenant)
        db_session.commit()

        result = db_session.get(Tenant, tenant.id)
        assert result is not None
        assert result.name == "Test Tenant"
        assert result.tenant_type == TenantType.STANDARD

    def test_read_tenant(self, db_session, tenant_a):
        """Test reading a tenant."""
        result = db_session.get(Tenant, tenant_a.id)
        assert result is not None
        assert result.name == "Tenant A"

    def test_update_tenant(self, db_session, tenant_a):
        """Test updating a tenant."""
        tenant_a.name = "Updated Tenant A"
        db_session.commit()

        result = db_session.get(Tenant, tenant_a.id)
        assert result.name == "Updated Tenant A"

    def test_delete_tenant(self, db_session, tenant_a):
        """Test deleting a tenant."""
        tenant_id = tenant_a.id
        db_session.delete(tenant_a)
        db_session.commit()

        result = db_session.get(Tenant, tenant_id)
        assert result is None


class TestUserCRUD:
    """Test CRUD operations for User."""

    def test_create_user(self, db_session, tenant_a):
        """Test creating a new user."""
        user = User(
            email="newuser@example.com",
            password_hash="hashed_password",
            tenant_id=tenant_a.id,
        )
        db_session.add(user)
        db_session.commit()

        result = db_session.get(User, user.id)
        assert result is not None
        assert result.email == "newuser@example.com"
        assert result.tenant_id == tenant_a.id

    def test_read_user(self, db_session, user_a):
        """Test reading a user."""
        result = db_session.get(User, user_a.id)
        assert result is not None
        assert result.email == "user-a@example.com"

    def test_update_user(self, db_session, user_a):
        """Test updating a user."""
        user_a.email = "updated-user@example.com"
        db_session.commit()

        result = db_session.get(User, user_a.id)
        assert result.email == "updated-user@example.com"

    def test_delete_user(self, db_session, user_a):
        """Test deleting a user."""
        user_id = user_a.id
        db_session.delete(user_a)
        db_session.commit()

        result = db_session.get(User, user_id)
        assert result is None


class TestAgentCRUD:
    """Test CRUD operations for Agent."""

    def test_create_agent(self, db_session, tenant_a):
        """Test creating a new agent."""
        agent = Agent(
            name="Test Agent",
            config={"model": "gpt-4"},
            tenant_id=tenant_a.id,
        )
        db_session.add(agent)
        db_session.commit()

        result = db_session.get(Agent, agent.id)
        assert result is not None
        assert result.name == "Test Agent"
        assert result.tenant_id == tenant_a.id

    def test_read_agent(self, db_session, agent_a):
        """Test reading an agent."""
        result = db_session.get(Agent, agent_a.id)
        assert result is not None
        assert result.name == "Agent A"

    def test_update_agent(self, db_session, agent_a):
        """Test updating an agent."""
        agent_a.name = "Updated Agent A"
        agent_a.config = {"model": "gpt-4", "temperature": 0.9}
        db_session.commit()

        result = db_session.get(Agent, agent_a.id)
        assert result.name == "Updated Agent A"
        assert result.config["temperature"] == 0.9

    def test_delete_agent(self, db_session, agent_a):
        """Test deleting an agent."""
        agent_id = agent_a.id
        db_session.delete(agent_a)
        db_session.commit()

        result = db_session.get(Agent, agent_id)
        assert result is None


class TestToolCRUD:
    """Test CRUD operations for Tool."""

    def test_create_tool(self, db_session, tenant_a):
        """Test creating a new tool."""
        tool = Tool(
            name="Test Tool",
            description="A test tool",
            source="def test():\n    return True",
            parameters={},
            version="1.0.0",
            tenant_id=tenant_a.id,
        )
        db_session.add(tool)
        db_session.commit()

        result = db_session.get(Tool, tool.id)
        assert result is not None
        assert result.name == "Test Tool"
        assert result.tenant_id == tenant_a.id

    def test_read_tool(self, db_session, tool_a):
        """Test reading a tool."""
        result = db_session.get(Tool, tool_a.id)
        assert result is not None
        assert result.name == "Tool A"

    def test_update_tool(self, db_session, tool_a):
        """Test updating a tool."""
        tool_a.name = "Updated Tool A"
        tool_a.description = "Updated description"
        db_session.commit()

        result = db_session.get(Tool, tool_a.id)
        assert result.name == "Updated Tool A"
        assert result.description == "Updated description"

    def test_delete_tool(self, db_session, tool_a):
        """Test deleting a tool."""
        tool_id = tool_a.id
        db_session.delete(tool_a)
        db_session.commit()

        result = db_session.get(Tool, tool_id)
        assert result is None


class TestSessionCRUD:
    """Test CRUD operations for Session (backend metadata only)."""

    def test_create_session(self, db_session, tenant_a, agent_a):
        """Test creating a new session."""
        from tinycua_backend.models import Session

        session = Session(
            name="Test Session",
            tenant_id=tenant_a.id,
            agent_id=agent_a.id,
        )
        db_session.add(session)
        db_session.commit()

        result = db_session.get(Session, session.id)
        assert result is not None
        assert result.name == "Test Session"
        assert result.tenant_id == tenant_a.id

    def test_read_session(self, db_session, tenant_a, agent_a):
        """Test reading a session."""
        from tinycua_backend.models import Session

        session = Session(
            name="Test Session",
            tenant_id=tenant_a.id,
            agent_id=agent_a.id,
        )
        db_session.add(session)
        db_session.commit()

        result = db_session.get(Session, session.id)
        assert result is not None
        assert result.name == "Test Session"

    def test_delete_session(self, db_session, tenant_a, agent_a):
        """Test deleting a session."""
        from tinycua_backend.models import Session

        session = Session(
            name="Test Session",
            tenant_id=tenant_a.id,
            agent_id=agent_a.id,
        )
        db_session.add(session)
        db_session.commit()

        session_id = session.id
        db_session.delete(session)
        db_session.commit()

        result = db_session.get(Session, session_id)
        assert result is None

    def test_update_session(self, db_session, tenant_a, agent_a):
        """Test updating a session."""
        from tinycua_backend.models import Session
        session = Session(
            name="Original Name",
            tenant_id=tenant_a.id,
            agent_id=agent_a.id,
        )
        db_session.add(session)
        db_session.commit()

        session.name = "Updated Name"
        db_session.commit()

        result = db_session.get(Session, session.id)
        assert result.name == "Updated Name"

    def test_list_sessions(self, db_session, tenant_a, agent_a):
        """Test listing sessions for a tenant."""
        from tinycua_backend.models import Session
        for i in range(3):
            session = Session(
                name=f"Session {i}",
                tenant_id=tenant_a.id,
                agent_id=agent_a.id,
            )
            db_session.add(session)
        db_session.commit()

        sessions = db_session.execute(
            select(Session).where(Session.tenant_id == tenant_a.id)
        ).scalars().all()

        assert len(sessions) >= 3


class TestMultiTenantCRUD:
    """Test CRUD operations across multiple tenants."""

    def test_tenants_are_isolated(self, db_session, tenant_a, tenant_b):
        """Test that tenants have separate data."""
        result = db_session.execute(select(Tenant).where(Tenant.id == tenant_a.id)).scalars().first()
        assert result is not None
        assert result.name == "Tenant A"

        result = db_session.execute(select(Tenant).where(Tenant.id == tenant_b.id)).scalars().first()
        assert result is not None
        assert result.name == "Tenant B"

    def test_users_belong_to_tenants(self, db_session, tenant_a, tenant_b, user_a, user_b):
        """Test that users belong to their respective tenants."""
        result = db_session.get(User, user_a.id)
        assert result.tenant_id == tenant_a.id

        result = db_session.get(User, user_b.id)
        assert result.tenant_id == tenant_b.id
