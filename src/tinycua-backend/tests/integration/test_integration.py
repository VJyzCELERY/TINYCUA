"""Integration tests for complete workflows."""

import pytest
from sqlalchemy import select

from tinycua_backend.tenant.models import Tenant
from tinycua_backend.auth.models import User
from tinycua_backend.storage.models import Agent, Tool
from tinycua_backend.tenant.models import TenantType


class TestCompleteWorkflow:
    """Test complete tenant workflow with all entities."""

    def test_create_tenant_with_user_agent_tool(self, db_session):
        """Test creating a complete tenant with user, agent, and tool."""
        tenant = Tenant(
            name="Integration Test Tenant",
            tenant_type=TenantType.STANDARD,
        )
        db_session.add(tenant)
        db_session.commit()

        user = User(
            email="integration@example.com",
            password_hash="hashed_password",
            tenant_id=tenant.id,
        )
        db_session.add(user)
        db_session.commit()

        agent = Agent(
            name="Integration Agent",
            config={"model": "gpt-4"},
            tenant_id=tenant.id,
        )
        db_session.add(agent)
        db_session.commit()

        tool = Tool(
            name="Integration Tool",
            description="A test tool for integration",
            source="def test():\n    return True",
            parameters={},
            version="1.0.0",
            tenant_id=tenant.id,
        )
        db_session.add(tool)
        db_session.commit()

        result = db_session.get(Tenant, tenant.id)
        assert result is not None
        assert result.name == "Integration Test Tenant"

        users = db_session.execute(
            select(User).where(User.tenant_id == tenant.id)
        ).scalars().all()
        assert len(users) == 1
        assert users[0].email == "integration@example.com"

        agents = db_session.execute(
            select(Agent).where(Agent.tenant_id == tenant.id)
        ).scalars().all()
        assert len(agents) == 1
        assert agents[0].name == "Integration Agent"

        tools = db_session.execute(
            select(Tool).where(Tool.tenant_id == tenant.id)
        ).scalars().all()
        assert len(tools) == 1
        assert tools[0].name == "Integration Tool"

