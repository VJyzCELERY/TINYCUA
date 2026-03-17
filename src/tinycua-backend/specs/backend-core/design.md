# Design Document: tinycua-backend Core

**Spec**: `specs/backend-core/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-17

---

## Overview

The tinycua-backend provides a REST API for agent management, session storage, and execution triggering. It uses FastAPI and SQLAlchemy with PostgreSQL.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           tinycua-backend                              │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        FastAPI App                               │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │  │
│  │  │   Auth   │  │  Agents   │  │ Sessions │  │     Run        │  │  │
│  │  │  Middle  │  │  Router   │  │  Router  │  │    Router      │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    SQLAlchemy + SessionStore                     │  │
│  │                  (tinycua-sdk storage layer)                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ POST /internal/v1/run
                                    │ Authorization: Bearer runner-token
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           tinycua-runner                                │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Configuration

### `.config.yaml`

```yaml
runner:
  url: "http://localhost:8001"
  token: "runner-secret-token"

database:
  url: "postgresql://user:pass@localhost:5432/tinycua"

auth:
  jwt_secret: "your-secret-key"
  jwt_algorithm: "HS256"

server:
  host: "0.0.0.0"
  port: 8000
```

### Config Loader

```python
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import yaml
from pathlib import Path

class RunnerConfig(BaseModel):
    url: str
    token: str

class DatabaseConfig(BaseModel):
    url: str

class AuthConfig(BaseModel):
    jwt_secret: str
    jwt_algorithm: str = "HS256"

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000

class Config(BaseSettings):
    runner: RunnerConfig
    database: DatabaseConfig
    auth: AuthConfig
    server: ServerConfig

    @classmethod
    def load(cls, path: str = ".config.yaml"):
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
```

### Hot Reload

```python
import threading
import time

class ConfigWatcher:
    def __init__(self, path: str, callback):
        self.path = path
        self.callback = callback
        self._running = False
    
    def start(self):
        self._running = True
        thread = threading.Thread(target=self._watch)
        thread.daemon = True
        thread.start()
    
    def _watch(self):
        mtime = Path(self.path).stat().st_mtime
        while self._running:
            time.sleep(1)
            new_mtime = Path(self.path).stat().st_mtime
            if new_mtime != mtime:
                mtime = new_mtime
                self.callback(Config.load(self.path))
```

---

## Database Models

### Tenant

```python
class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship("User", back_populates="tenant")
    api_keys = relationship("APIKey", back_populates="tenant")
    agents = relationship("Agent", back_populates="tenant")
    sessions = relationship("Session", back_populates="tenant")
```

### User

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # Optional, or use API keys only
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="users")
```

### APIKey

```python
class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), nullable=False)  # Hash of the API key
    name = Column(String(255), nullable=False)
    scopes = Column(JSON, default=list)  # ["agent:read", "agent:write"]
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="api_keys")
```

### Agent

```python
class Agent(Base):
    __tablename__ = "agents"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    config = Column(JSON, nullable=False)  # Agent config from SDK
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="agents")
    sessions = relationship("Session", back_populates="agent")
```

---

## Authentication

### Middleware

```python
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer
import jwt

async def get_current_tenant(request: Request) -> Tenant:
    """Extract tenant from API key or JWT token."""
    
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization")
    
    scheme, token = auth_header.split(" ", 1)
    
    if scheme.lower() == "bearer":
        # Try JWT first
        try:
            payload = jwt.decode(
                token, 
                config.jwt_secret, 
                algorithms=[config.jwt_algorithm]
            )
            tenant_id = payload.get("tenant_id")
            tenant = db.query(Tenant).get(tenant_id)
            if not tenant:
                raise HTTPException(status_code=401, detail="Invalid token")
            return tenant
        except jwt.InvalidTokenError:
            pass
        
        # Try API key
        key_hash = hash_token(token)
        api_key = db.query(APIKey).filter_by(key_hash=key_hash).first()
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API key expired")
        
        return api_key.tenant
    
    raise HTTPException(status_code=401, detail="Invalid authentication scheme")
```

### Scope Checking

```python
def require_scope(required_scope: str):
    """Dependency to check if API key has required scope."""
    async def scope_checker(tenant: Tenant = Depends(get_current_tenant)):
        # Get API key from header
        # Check if required_scope in key.scopes
        # If not, raise 403 Forbidden
        pass
    return scope_checker
```

---

## API Routes

### Agents Router

```python
@router.post("/agents", response_model=AgentResponse)
async def create_agent(
    agent: AgentCreate,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Create a new agent."""
    db_agent = Agent(
        tenant_id=tenant.id,
        name=agent.name,
        config=agent.config
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

@router.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    tenant: Tenant = Depends(get_current_tenant),
    limit: int = 100,
    offset: int = 0
):
    """List all agents for the tenant."""
    return db.query(Agent).filter(
        Agent.tenant_id == tenant.id
    ).offset(offset).limit(limit).all()

@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get an agent by ID."""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.delete("/agents/{agent_id}")
async def delete_agent(
    agent_id: UUID,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Delete an agent."""
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"deleted": True}
```

### Sessions Router

```python
@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    tenant: Tenant = Depends(get_current_tenant),
    agent_id: UUID = None,
    limit: int = 100,
    offset: int = 0
):
    """List sessions for the tenant."""
    query = db.query(Session).filter(Session.tenant_id == tenant.id)
    if agent_id:
        query = query.filter(Session.agent_id == agent_id)
    return query.offset(offset).limit(limit).all()

@router.get("/sessions/{session_id}", response_model=SessionWithMessages)
async def get_session(
    session_id: UUID,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Get session with messages."""
    session = db.query(Session).filter(
        Session.id == session_id,
        Session.tenant_id == tenant.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = store.get_messages(session_id)
    return {"session": session, "messages": messages}
```

### Run Router

```python
@router.post("/agents/{agent_id}/run")
async def run_agent(
    agent_id: UUID,
    request: RunRequest,
    tenant: Tenant = Depends(get_current_tenant)
):
    """Execute an agent and stream results."""
    
    # 1. Load agent
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant.id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # 2. Load or create session
    session_id = request.session_id
    if session_id:
        session = db.query(Session).filter(
            Session.id == session_id,
            Session.tenant_id == tenant.id
        ).first()
    else:
        session = Session(
            tenant_id=tenant.id,
            agent_id=agent_id,
            name=request.name or f"Session {datetime.utcnow()}"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    
    # 3. Load messages from store
    messages = store.get_messages(session_id)
    
    # 4. Call runner
    runner_url = f"{config.runner.url}/internal/v1/run"
    headers = {"Authorization": f"Bearer {config.runner.token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            runner_url,
            headers=headers,
            json={
                "agent_config": agent.config,
                "session_id": str(session_id),
                "db_url": config.database.url,
                "user_input": request.user_input,
            },
            timeout=None
        )
    
    # 5. Stream response back to client
    async def event_generator():
        async for line in response.aiter_lines():
            yield line
    
    return StreamingResponse(event_generator())
```

---

## Sequence Diagrams

### 1. Agent Deployment Flow

```
Client (SDK)                    Backend                      Database
    │                            │                              │
    │ POST /v1/agents            │                              │
    │ Authorization: Bearer key  │                              │
    │───────────────────────────▶│                              │
    │                            │ Validate API Key             │
    │                            │───▶ Check tenant            │
    │                            │◀─── Get tenant              │
    │                            │                              │
    │                            │ Insert Agent                │
    │                            │───────────────────────────▶│
    │                            │◀───────────────────────────│
    │                            │                              │
    │ 201 Created                │                              │
    │ { agent_id: "..." }        │                              │
    │◀───────────────────────────│                              │
    │                            │                              │
```

### 2. Agent Execution Flow

```
Client (SDK)                    Backend                      Runner                      Database
    │                            │                              │                           │
    │ POST /v1/agents/{id}/run   │                              │                           │
    │ Authorization: Bearer key   │                              │                           │
    │ X-Session-ID: session-123  │                              │                           │
    │───────────────────────────▶│                              │                           │
    │                            │ Validate Auth               │                           │
    │                            │───▶ Get tenant              │                           │
    │                            │◀─── OK                     │                           │
    │                            │                              │                           │
    │                            │ Load Agent                  │                           │
    │                            │───────────────────────────▶│                           │
    │                            │◀───────────────────────────│                           │
    │                            │                              │                           │
    │                            │ Load Session + Messages    │                           │
    │                            │───────────────────────────▶│                           │
    │                            │◀───────────────────────────│                           │
    │                            │                              │                           │
    │                            │ POST /internal/v1/run     │                           │
    │                            │ Authorization: Bearer token │                           │
    │                            │ {                           │                           │
    │                            │   agent_config: {...},      │                           │
    │                            │   session_id: "...",        │                           │
    │                            │   db_url: "...",           │                           │
    │                            │   user_input: "..."        │                           │
    │                            │───────────────────────────▶│                           │
    │                            │                              │                           │
    │                            │                              │ Connect to db_url        │
    │                            │                              │─────────────────────────▶│
    │                            │                              │◀─────────────────────────│
    │                            │                              │                           │
    │                            │     [SSE Events]            │                           │
    │                            │◀───────────────────────────│                           │
    │                            │                              │                           │
    │    [SSE Events]           │                              │                           │
    │◀───────────────────────────│                              │                           │
    │                            │                              │                           │
    │                            │ Store new messages          │                           │
    │                            │───────────────────────────▶│                           │
    │                            │◀───────────────────────────│                           │
    │                            │                              │                           │
```

### 3. Session Context Retrieval Flow

```
Client                         Backend                      Runner                      Database
    │                            │                              │                           │
    │ GET /v1/sessions/{id}     │                              │                           │
    │ Authorization: Bearer key  │                              │                           │
    │───────────────────────────▶│                              │                           │
    │                            │ Validate Auth               │                           │
    │                            │───▶ OK                     │                           │
    │                            │                              │                           │
    │                            │ Load Session                │                           │
    │                            │───────────────────────────▶│                           │
    │                            │◀───────────────────────────│                           │
    │                            │                              │                           │
    │                            │ Get Messages                │                           │
    │                            │───────────────────────────▶│                           │
    │                            │◀───────────────────────────│                           │
    │                            │                              │                           │
    │ 200 OK                    │                              │                           │
    │ { session: {...},         │                              │                           │
    │   messages: [...] }       │                              │                           │
    │◀───────────────────────────│                              │                           │
    │                            │                              │                           │
```

### 4. Runner Context Tools Flow (Inside Runner)

```
Runner                         SessionStore                 Database
    │                            │                              │
    │ User input:               │                              │
    │ "What is my name?"        │                              │
    │                            │                              │
    │ Agent decides to use      │                              │
    │ get_recent_turns()        │                              │
    │                            │                              │
    │                            │ get_recent_turns(          │
    │                            │   session_id=...)          │
    │                            │───────────────────────────▶│
    │                            │◀───────────────────────────│
    │                            │                              │
    │ returns: {"turns": [...]} │                              │
    │                            │                              │
    │ Agent uses context in      │                              │
    │ response generation        │                              │
    │                            │                              │
```

---

## Implementation Phases

### Phase 1: Setup + Config + Auth

- [ ] Project setup (FastAPI, SQLAlchemy)
- [ ] Config loader with hot-reload
- [ ] Database models (Tenant, User, APIKey)
- [ ] Auth middleware (JWT + API key)
- [ ] Tenant isolation

### Phase 2: Agent CRUD

- [ ] Agent model
- [ ] Agent routes (CRUD)
- [ ] Unit tests

### Phase 3: Session + Messages

- [ ] Session model (uses SDK SessionStore)
- [ ] Session routes
- [ ] Message endpoints

### Phase 4: Runner Integration

- [ ] Run endpoint
- [ ] Runner communication
- [ ] SSE streaming
- [ ] Message storage after execution

---

## Testing Plan

### Unit Tests
- Config loading
- Auth middleware (JWT validation, API key validation)
- Agent CRUD
- Session CRUD

### Integration Tests
- Full flow: create agent → run → verify messages stored
- Multi-tenancy isolation
- Runner communication
