# Design: Auth, User Accounts, and Session Management

## Overview

This document describes the internal architecture of the auth and session subsystem in
`tinycua-backend`. It translates spec requirements into a concrete module structure,
ORM models, class designs, sequence diagrams, and migration strategy.

---

## Package Layout

```
src/tinycua-backend/
└── tinycua_backend/
    ├── auth/
    │   ├── __init__.py
    │   ├── middleware.py        # BearerAuthMiddleware
    │   ├── jwt.py               # encode_access_token(), decode_token()
    │   ├── apikey.py            # generate_key(), hash_key(), verify_key()
    │   └── password.py          # hash_password(), verify_password()
    ├── database/
    │   ├── __init__.py
    │   ├── engine.py            # SQLAlchemy engine + SessionLocal factory
    │   ├── models.py            # ORM models: User, ApiKey, RefreshToken,
    │   │                        #              Session, SessionMessage
    │   └── migrations/
    │       ├── env.py           # Alembic env
    │       ├── script.py.mako
    │       └── versions/
    │           └── 0001_initial.py   # Initial migration (all 5 tables)
    ├── sessions/
    │   ├── __init__.py
    │   └── service.py           # SessionService
    └── routes/
        ├── auth.py              # POST /v1/auth/register, /token, /refresh
        │                        # POST/GET/DELETE /v1/auth/apikeys
        └── sessions.py          # POST/GET/DELETE /v1/sessions[/{id}]
```

---

## Database Models (`database/models.py`)

```python
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text
)
from sqlalchemy.orm import DeclarativeBase, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    username    = Column(String(64), unique=True, nullable=False)
    email       = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)   # bcrypt hash
    is_master   = Column(Boolean, nullable=False, default=False)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    api_keys        = relationship("ApiKey", back_populates="user", cascade="all, delete")
    refresh_tokens  = relationship("RefreshToken", back_populates="user", cascade="all, delete")
    sessions        = relationship("Session", back_populates="user", cascade="all, delete")

class ApiKey(Base):
    __tablename__ = "api_keys"
    id          = Column(String(32), primary_key=True)   # "key_<random>"
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String(128), nullable=False)
    key_hash    = Column(String(64), nullable=False)     # SHA-256 hex
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    revoked     = Column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="api_keys")

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash  = Column(String(64), nullable=False)     # SHA-256 hex
    expires_at  = Column(DateTime, nullable=False)
    used        = Column(Boolean, nullable=False, default=False)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="refresh_tokens")

class Session(Base):
    __tablename__ = "sessions"
    id          = Column(String(32), primary_key=True)   # "sess_<random>"
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    name        = Column(String(128), nullable=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at  = Column(DateTime, nullable=False, default=datetime.utcnow,
                         onupdate=datetime.utcnow)

    user     = relationship("User", back_populates="sessions")
    messages = relationship("SessionMessage", back_populates="session",
                            cascade="all, delete", order_by="SessionMessage.id")

class SessionMessage(Base):
    __tablename__ = "session_messages"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(String(32), ForeignKey("sessions.id"), nullable=False)
    role        = Column(String(16), nullable=False)    # "user" | "assistant"
    content     = Column(Text, nullable=False)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("Session", back_populates="messages")
```

---

## `database/engine.py`

```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from tinycua_backend.config import get_settings

def _get_engine():
    settings = get_settings()
    url = settings.database_url
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    # Enable foreign key enforcement for SQLite
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
    return engine

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = _get_engine()
    return _engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## `auth/password.py` — Password Hashing

```python
from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(plain: str) -> str:
    return _ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)
```

## `auth/jwt.py` — JWT Helpers

```python
import uuid
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from tinycua_backend.config import get_settings

_ALGORITHM = "HS256"
_ACCESS_EXPIRY_MINUTES = 15

def encode_access_token(user_id: int, username: str, is_master: bool) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub":       str(user_id),
        "username":  username,
        "is_master": is_master,
        "iat":       now,
        "exp":       now + timedelta(minutes=_ACCESS_EXPIRY_MINUTES),
        "jti":       str(uuid.uuid4()),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALGORITHM)

def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Raises jose.JWTError on failure (expired, bad signature).
    Returns the payload dict on success.
    """
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
```

## `auth/apikey.py` — API Key Helpers

```python
import hashlib
import secrets
import string

_PREFIX = "tinycua-sk-"

def generate_key() -> tuple[str, str]:
    """
    Returns (raw_key, key_hash).
    raw_key is shown to the user once. key_hash is stored in DB.
    """
    raw = _PREFIX + secrets.token_urlsafe(32)
    return raw, _hash_key(raw)

def hash_key(raw: str) -> str:
    return _hash_key(raw)

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def verify_key(raw: str, stored_hash: str) -> bool:
    return hashlib.compare_digest(_hash_key(raw), stored_hash)
```

---

## `auth/middleware.py` — BearerAuthMiddleware

```python
import hmac
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import JWTError
from tinycua_backend.auth.jwt import decode_token
from tinycua_backend.auth.apikey import hash_key
from tinycua_backend.database.engine import SessionLocal
from tinycua_backend.database.models import ApiKey, User

_EXEMPT_PATHS = {"/health"}

class AuthenticatedUser:
    def __init__(self, id: int, username: str, is_master: bool):
        self.id = id
        self.username = username
        self.is_master = is_master

class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthorized()

        token = auth_header[len("Bearer "):]

        # Try JWT first
        try:
            claims = decode_token(token)
            request.state.user = AuthenticatedUser(
                id=int(claims["sub"]),
                username=claims["username"],
                is_master=claims["is_master"],
            )
            return await call_next(request)
        except JWTError:
            pass

        # Fall back to API key lookup
        key_hash = hash_key(token)
        with SessionLocal() as db:
            api_key = (
                db.query(ApiKey)
                .filter_by(key_hash=key_hash, revoked=False)
                .first()
            )
            if api_key is None:
                return _unauthorized()
            user = db.query(User).filter_by(id=api_key.user_id).first()
            if user is None:
                return _unauthorized()
            # Update last_used_at
            from datetime import datetime
            api_key.last_used_at = datetime.utcnow()
            db.commit()

        request.state.user = AuthenticatedUser(
            id=user.id, username=user.username, is_master=user.is_master
        )
        return await call_next(request)

def _unauthorized():
    from starlette.responses import JSONResponse
    return JSONResponse(
        status_code=401,
        content={"error": {"code": "unauthorized", "message": "Invalid or missing credentials."}},
    )
```

---

## `routes/auth.py` — Auth Routes

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession
from tinycua_backend.database.engine import get_db
from tinycua_backend.database.models import User, ApiKey, RefreshToken
from tinycua_backend.auth.password import hash_password, verify_password
from tinycua_backend.auth.jwt import encode_access_token
from tinycua_backend.auth.apikey import generate_key

router = APIRouter(prefix="/v1/auth")

@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: DBSession = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(422, detail="Password must be at least 8 characters.")
    if db.query(User).filter(
        (User.username == body.username) | (User.email == body.email)
    ).first():
        raise HTTPException(409, detail={"code": "conflict", "message": "Username or email taken."})
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}

@router.post("/token")
def login(body: LoginRequest, db: DBSession = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == body.username) | (User.email == body.username)
    ).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, detail="Invalid credentials.")
    access_token = encode_access_token(user.id, user.username, user.is_master)
    raw_refresh, refresh_hash = _generate_refresh_token()
    _store_refresh_token(db, user.id, refresh_hash)
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 900,
        "refresh_token": raw_refresh,
    }

@router.post("/refresh")
def refresh_token(body: RefreshRequest, db: DBSession = Depends(get_db)):
    token_row = _find_valid_refresh_token(db, body.refresh_token)
    if not token_row:
        raise HTTPException(401, detail="Invalid or expired refresh token.")
    token_row.used = True
    user = db.query(User).filter_by(id=token_row.user_id).first()
    access_token = encode_access_token(user.id, user.username, user.is_master)
    raw_refresh, refresh_hash = _generate_refresh_token()
    _store_refresh_token(db, user.id, refresh_hash)
    db.commit()
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 900,
        "refresh_token": raw_refresh,
    }

@router.post("/apikeys", status_code=201)
def create_apikey(body: CreateApiKeyRequest, request: Request,
                  db: DBSession = Depends(get_db)):
    raw_key, key_hash = generate_key()
    api_key = ApiKey(
        id=f"key_{secrets.token_hex(8)}",
        user_id=request.state.user.id,
        name=body.name,
        key_hash=key_hash,
    )
    db.add(api_key)
    db.commit()
    return {"id": api_key.id, "name": api_key.name, "key": raw_key,
            "created_at": api_key.created_at}

@router.get("/apikeys")
def list_apikeys(request: Request, db: DBSession = Depends(get_db)):
    keys = db.query(ApiKey).filter_by(user_id=request.state.user.id, revoked=False).all()
    return {"api_keys": [
        {"id": k.id, "name": k.name, "created_at": k.created_at,
         "last_used_at": k.last_used_at}
        for k in keys
    ]}

@router.delete("/apikeys/{key_id}", status_code=204)
def revoke_apikey(key_id: str, request: Request, db: DBSession = Depends(get_db)):
    key = db.query(ApiKey).filter_by(id=key_id, user_id=request.state.user.id).first()
    if not key:
        raise HTTPException(404)
    key.revoked = True
    db.commit()
```

---

## `routes/sessions.py` — Session Routes

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession
from tinycua_backend.database.engine import get_db
from tinycua_backend.database.models import Session as SessionModel, SessionMessage
import secrets

router = APIRouter(prefix="/v1/sessions")

@router.post("", status_code=201)
def create_session(body: CreateSessionRequest, request: Request,
                   db: DBSession = Depends(get_db)):
    session = SessionModel(
        id=f"sess_{secrets.token_hex(12)}",
        user_id=request.state.user.id,
        name=body.name if body else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "name": session.name, "created_at": session.created_at}

@router.get("")
def list_sessions(request: Request, limit: int = 20, after: str | None = None,
                  db: DBSession = Depends(get_db)):
    q = db.query(SessionModel).filter_by(user_id=request.state.user.id)
    if after:
        q = q.filter(SessionModel.id > after)
    sessions = q.order_by(SessionModel.created_at.desc()).limit(limit).all()
    return {"sessions": [
        {"id": s.id, "name": s.name, "created_at": s.created_at,
         "message_count": len(s.messages)}
        for s in sessions
    ]}

@router.get("/{session_id}")
def get_session(session_id: str, request: Request, limit: int = 50,
                db: DBSession = Depends(get_db)):
    session = db.query(SessionModel).filter_by(
        id=session_id, user_id=request.state.user.id
    ).first()
    if not session:
        raise HTTPException(404)
    messages = session.messages[-limit:]
    return {
        "id": session.id, "name": session.name,
        "created_at": session.created_at, "updated_at": session.updated_at,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }

@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, request: Request, db: DBSession = Depends(get_db)):
    session = db.query(SessionModel).filter_by(
        id=session_id, user_id=request.state.user.id
    ).first()
    if not session:
        raise HTTPException(404)
    db.delete(session)
    db.commit()
```

---

## `sessions/service.py` — SessionService

```python
from sqlalchemy.orm import Session as DBSession
from tinycua_backend.database.models import Session as SessionModel, SessionMessage
from fastapi import HTTPException

class SessionService:
    def __init__(self, db: DBSession) -> None:
        self._db = db

    def load_history(self, session_id: str, user_id: int) -> list[dict]:
        """
        Return session message history as a list of input items
        (dicts with 'role' and 'content' keys).
        Raises HTTP 404 if session not found or not owned by user.
        """
        session = self._db.query(SessionModel).filter_by(
            id=session_id, user_id=user_id
        ).first()
        if not session:
            raise HTTPException(404, detail="Session not found.")
        return [{"role": m.role, "content": m.content} for m in session.messages]

    def save_turn(
        self,
        session_id: str,
        user_id: int,
        user_input: str,
        assistant_output: str,
    ) -> None:
        """Append a user + assistant turn to the session."""
        session = self._db.query(SessionModel).filter_by(
            id=session_id, user_id=user_id
        ).first()
        if not session:
            return  # session deleted during the request — silently skip
        self._db.add(SessionMessage(
            session_id=session_id, role="user", content=user_input))
        self._db.add(SessionMessage(
            session_id=session_id, role="assistant", content=assistant_output))
        self._db.commit()

    def get_context(self, session_id: str) -> str:
        """
        Return a plain-text summary of the session for the get_context native tool.
        MVP: concatenates the last 3 assistant messages.
        Phase 2: replace with LLM-generated rolling summary.
        """
        session = self._db.query(SessionModel).filter_by(id=session_id).first()
        if not session:
            return "No session context available."
        assistant_msgs = [
            m.content for m in session.messages if m.role == "assistant"
        ][-3:]
        if not assistant_msgs:
            return "No prior assistant responses in this session."
        return "\n\n---\n\n".join(assistant_msgs)
```

---

## Sequence Diagram: Login Flow

```
Client
  │
  │  POST /v1/auth/token { username, password }
  ▼
routes/auth.py login()
  │  db.query(User).filter(username=…).first()
  │  verify_password(plain, hash)  → 401 if mismatch
  │
  │  encode_access_token(user.id, username, is_master)  → JWT (15 min)
  │  _generate_refresh_token()  → (raw_token, token_hash)
  │  RefreshToken(user_id, token_hash, expires_at=now+30d)  → DB
  ▼
HTTP 200 { access_token, token_type, expires_in, refresh_token }
```

## Sequence Diagram: Request Auth (JWT path)

```
Client
  │  Authorization: Bearer <JWT>
  ▼
BearerAuthMiddleware
  │  jwt.decode_token(token)
  │    → payload { sub, username, is_master, exp }
  │  request.state.user = AuthenticatedUser(id, username, is_master)
  ▼
Route handler (request.state.user available)
```

## Sequence Diagram: Request Auth (API key path)

```
Client
  │  Authorization: Bearer tinycua-sk-…
  ▼
BearerAuthMiddleware
  │  jwt.decode_token(token)  → JWTError (not a JWT)
  │  hash_key(token)
  │  db.query(ApiKey).filter(key_hash=…, revoked=False).first()
  │    → None → 401
  │    → found → load User
  │  api_key.last_used_at = now  → db.commit()
  │  request.state.user = AuthenticatedUser(…)
  ▼
Route handler
```

## Sequence Diagram: Session Turn

```
Client
  │  POST /v1/responses { session_id: "sess_xyz", input: [user_msg] }
  ▼
BearerAuthMiddleware  (sets request.state.user)
  ▼
routes/responses.py handle_responses()
  │  SessionService.load_history("sess_xyz", user.id)
  │      → history = [ {role:user,…}, {role:assistant,…}, … ]
  │  body = _prepend_history(body, history)
  │
  │  OrchestrationLoop.run(body, …)
  │      → provider calls, tool calls, final Response
  │
  │  SessionService.save_turn("sess_xyz", user.id, user_input, assistant_output)
  ▼
HTTP 200  Response
```

---

## Alembic Setup

`database/migrations/env.py` is the standard Alembic env, configured to:

- Import `Base` from `tinycua_backend.database.models`.
- Read `TINYCUA_DATABASE_URL` from `config.Settings` for the migration connection URL.
- Use `Base.metadata` for `target_metadata`.

Initial migration `0001_initial.py` creates all five tables in dependency order:
`users` → `api_keys`, `refresh_tokens`, `sessions` → `session_messages`.

Migration execution:

```bash
alembic upgrade head         # apply all migrations
alembic downgrade -1         # roll back one step
alembic revision --autogenerate -m "description"   # generate new migration
```

---

## Error Handling

| Condition                          | HTTP | `error.code`    |
|------------------------------------|------|-----------------|
| Missing/invalid credential         | 401  | `unauthorized`  |
| Expired JWT                        | 401  | `unauthorized`  |
| Used refresh token                 | 401  | `unauthorized`  |
| Duplicate username/email           | 409  | `conflict`      |
| Password too short                 | 422  | `invalid_request`|
| Session not found / wrong user     | 404  | `not_found`     |
| API key not found / wrong user     | 404  | `not_found`     |

---

## Phases

### Phase 1 (MVP)

- User registration + bcrypt password hashing.
- JWT login + 15-min access token + 30-day refresh token (single-use rotation).
- API key create / list / revoke.
- `BearerAuthMiddleware` (JWT → API key fallback).
- Session create / list / get / delete.
- `SessionService`: `load_history()`, `save_turn()`, `get_context()` (last-3 summary).
- SQLite default via SQLAlchemy + Alembic migration.
- `TINYCUA_DATABASE_URL` override to PostgreSQL.

### Phase 2

- Admin endpoint for setting `is_master` (protected by admin token).
- Session summarisation hook (LLM-generated rolling summary).
- OAuth / third-party SSO.
- Role-based access control beyond `is_master`.
- Soft-delete sessions.

---

## Open Questions Resolved

- **OQ-001** (`is_master` admin endpoint): Deferred to Phase 2. Direct DB / CLI in MVP.
- **OQ-002** (Session history summarisation): Deferred to Phase 2. MVP uses last-3
  assistant messages as plain-text context.
- **OQ-003** (Soft-delete sessions): Hard-delete in MVP.
