"""Shared integration test fixtures for tinycua-backend."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from tinycua_backend.tenant.models import Tenant
from tinycua_backend.auth.models import User, APIKey
from tinycua_backend.storage.models import Agent, Tool
from tinycua_backend.storage.base import Base
from tinycua_backend.tenant.models import TenantType


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine using SQLite in-memory."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Create a database session for testing."""
    SessionLocal = sessionmaker(autocommit=False, expire_on_commit=False, bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def tenant_a(db_session: Session) -> Tenant:
    """Create tenant A for testing."""
    tenant = Tenant(
        name="Tenant A",
        tenant_type=TenantType.STANDARD,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def tenant_b(db_session: Session) -> Tenant:
    """Create tenant B for testing."""
    tenant = Tenant(
        name="Tenant B",
        tenant_type=TenantType.STANDARD,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return tenant


@pytest.fixture
def user_a(db_session: Session, tenant_a: Tenant) -> User:
    """Create a user for tenant A."""
    user = User(
        email="user-a@example.com",
        password_hash="hashed_password_a",
        tenant_id=tenant_a.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session: Session, tenant_b: Tenant) -> User:
    """Create a user for tenant B."""
    user = User(
        email="user-b@example.com",
        password_hash="hashed_password_b",
        tenant_id=tenant_b.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def agent_a(db_session: Session, tenant_a: Tenant) -> Agent:
    """Create an agent for tenant A."""
    agent = Agent(
        name="Agent A",
        config={"model": "gpt-4", "temperature": 0.7},
        tenant_id=tenant_a.id,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def agent_b(db_session: Session, tenant_b: Tenant) -> Agent:
    """Create an agent for tenant B."""
    agent = Agent(
        name="Agent B",
        config={"model": "gpt-3.5-turbo", "temperature": 0.5},
        tenant_id=tenant_b.id,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


@pytest.fixture
def tool_a(db_session: Session, tenant_a: Tenant) -> Tool:
    """Create a tool for tenant A."""
    tool = Tool(
        name="Tool A",
        description="A test tool for tenant A",
        source="def tool_a():\n    return 'Tool A'",
        parameters={},
        version="1.0.0",
        tenant_id=tenant_a.id,
    )
    db_session.add(tool)
    db_session.commit()
    db_session.refresh(tool)
    return tool


@pytest.fixture
def tool_b(db_session: Session, tenant_b: Tenant) -> Tool:
    """Create a tool for tenant B."""
    tool = Tool(
        name="Tool B",
        description="A test tool for tenant B",
        source="def tool_b():\n    return 'Tool B'",
        parameters={},
        version="1.0.0",
        tenant_id=tenant_b.id,
    )
    db_session.add(tool)
    db_session.commit()
    db_session.refresh(tool)
    return tool
