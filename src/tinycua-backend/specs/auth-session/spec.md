# Specification: Auth, User Accounts, and Session Management

## Problem Statement

The backend needs a user account system so that access to the API is controlled at the
individual user level rather than by a shared static key. Users must be able to authenticate
via password-based login (returning a short-lived JWT) and via long-lived API keys for
programmatic access. The `is_master` flag on a user account controls access to CUA
capabilities, and is set by a server administrator — not by the user themselves.

Sessions allow stateful conversations: instead of sending the full message history on
every request, the client passes a `session_id` and the backend loads, uses, and updates
the history server-side. Sessions are user-scoped and never accessible across accounts.

---

## Scope

Included in this spec:
- User registration and login (`POST /v1/auth/register`, `POST /v1/auth/token`).
- JWT access token (15-min) + refresh token (30-day).
- Token refresh (`POST /v1/auth/refresh`).
- User-scoped API key management (create, list, revoke).
- `is_master` flag: what it gates, how it is set.
- Session CRUD: create, retrieve history, list sessions.
- `get_context` native tool: specification from the session side.
- Database contract: SQLite default, `TINYCUA_DATABASE_URL` swappable to PostgreSQL.
- Alembic migrations: one initial migration covering all four tables.

Excluded:
- OAuth / third-party SSO — Phase 2.
- Role-based access control beyond `is_master` — Phase 2.
- Frontend/UI — out of scope entirely.

---

## Requirements

### User accounts

- **FR-001**: `POST /v1/auth/register` must accept `username`, `email`, and `password`.
  It must hash the password with bcrypt (cost factor ≥ 12) and create a `User` row.
  Returns `201` with `{ "id": …, "username": …, "email": … }`. Duplicate username or
  email returns `409`.
- **FR-002**: `is_master` defaults to `false` on registration. It can only be set to
  `true` by editing the database directly or via a server-admin CLI command — not via
  the HTTP API. This is intentional: `is_master` grants CUA access and must be an
  explicit out-of-band decision.
- **FR-003**: Passwords must be at least 8 characters. The endpoint must return `422`
  with a clear message if the password is too short.

### Authentication

- **FR-004**: `POST /v1/auth/token` must accept `username` (or `email`) + `password`.
  On success, return:
  ```json
  {
    "access_token": "<JWT>",
    "token_type": "Bearer",
    "expires_in": 900,
    "refresh_token": "<opaque token>"
  }
  ```
  On failure (wrong credentials), return `401`.
- **FR-005**: The JWT access token must have a 15-minute expiry. It must include claims:
  `sub` (user id, as string), `username`, `is_master`, `exp`, `iat`, `jti`.
- **FR-006**: The refresh token must be an opaque random token (32 bytes, base64url
  encoded), stored hashed in the database with a 30-day TTL. Refresh tokens are single-use:
  using one invalidates it and issues a new one.
- **FR-007**: `POST /v1/auth/refresh` must accept `{ "refresh_token": "…" }`. On success,
  return a new `access_token` + `refresh_token` pair. On failure (expired, already used,
  not found), return `401`.
- **FR-008**: All protected endpoints accept `Authorization: Bearer <token>` where
  `<token>` is either a JWT access token or a user-scoped API key. JWT is tried first;
  on failure, API key lookup is tried.

### API keys

- **FR-009**: `POST /v1/auth/apikeys` must generate a new user-scoped API key. Returns:
  ```json
  {
    "id": "key_abc123",
    "name": "my-script",
    "key": "tinycua-sk-…",
    "created_at": "2026-03-11T…"
  }
  ```
  The `key` value is returned **only at creation time** — it is not retrievable later.
  Only the SHA-256 hash is stored in the database.
- **FR-010**: `GET /v1/auth/apikeys` must list all API keys for the authenticated user
  (id, name, created_at, last_used_at). The key value itself is never returned.
- **FR-011**: `DELETE /v1/auth/apikeys/{id}` must revoke a key. Returns `404` if the
  key does not exist or does not belong to the authenticated user.
- **FR-012**: A revoked API key must be rejected immediately (within the same request
  cycle) — no caching of valid keys beyond the current request.

### Sessions

- **FR-013**: `POST /v1/sessions` must create a new session for the authenticated user.
  Accepts optional `{ "name": "…" }`. Returns `{ "id": "sess_…", "name": …,
  "created_at": … }`.
- **FR-014**: `GET /v1/sessions` must list all sessions for the authenticated user
  (id, name, created_at, message_count). Paginated (cursor-based).
- **FR-015**: `GET /v1/sessions/{id}` must return session metadata + the last N messages
  (configurable, default 50). Returns `404` if the session does not exist or belongs to
  another user.
- **FR-016**: `DELETE /v1/sessions/{id}` must delete the session and all its messages.
  Returns `404` if not found or not owned.
- **FR-017**: Sessions are automatically updated by `POST /v1/responses` when
  `session_id` is present (see `openai-responses` spec). No separate
  "append message" endpoint is exposed — history is only written by the orchestration loop.
- **FR-018**: The `get_context` native tool (auto-injected by the orchestration loop when
  a session is active) must be handled by calling `SessionService.get_context(session_id)`.
  The implementation must return a plain-text summary of earlier turns. The exact
  summarisation strategy is deferred to Phase 2; in MVP it returns the concatenation of
  the last N assistant messages (default 3).

### Database

- **FR-019**: The default database URL is `sqlite:///./tinycua.db`. Setting the
  `TINYCUA_DATABASE_URL` environment variable overrides it to any SQLAlchemy-compatible
  URL (e.g. `postgresql+asyncpg://user:pw@host/db`).
- **FR-020**: All schema changes must be managed via Alembic. The initial migration must
  create tables: `users`, `api_keys`, `refresh_tokens`, `sessions`, `session_messages`.
- **FR-021**: Foreign keys must be enforced. For SQLite, `PRAGMA foreign_keys = ON` must
  be issued on every connection.

---

## Entity Summary

### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | auto-increment |
| `username` | text UNIQUE NOT NULL | |
| `email` | text UNIQUE NOT NULL | |
| `password_hash` | text NOT NULL | bcrypt |
| `is_master` | bool NOT NULL DEFAULT false | CUA access gate |
| `created_at` | datetime NOT NULL | UTC |

### `api_keys`
| Column | Type | Notes |
|---|---|---|
| `id` | text PK | `key_<random>` |
| `user_id` | int FK users.id NOT NULL | |
| `name` | text NOT NULL | |
| `key_hash` | text NOT NULL | SHA-256 of raw key |
| `created_at` | datetime NOT NULL | |
| `last_used_at` | datetime | updated on use |
| `revoked` | bool NOT NULL DEFAULT false | |

### `refresh_tokens`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | auto-increment |
| `user_id` | int FK users.id NOT NULL | |
| `token_hash` | text NOT NULL | SHA-256 of raw token |
| `expires_at` | datetime NOT NULL | now + 30 days |
| `used` | bool NOT NULL DEFAULT false | single-use |
| `created_at` | datetime NOT NULL | |

### `sessions`
| Column | Type | Notes |
|---|---|---|
| `id` | text PK | `sess_<random>` |
| `user_id` | int FK users.id NOT NULL | |
| `name` | text | optional label |
| `created_at` | datetime NOT NULL | |
| `updated_at` | datetime NOT NULL | updated on each turn |

### `session_messages`
| Column | Type | Notes |
|---|---|---|
| `id` | int PK | auto-increment |
| `session_id` | text FK sessions.id NOT NULL | |
| `role` | text NOT NULL | `"user"` or `"assistant"` |
| `content` | text NOT NULL | |
| `created_at` | datetime NOT NULL | |

---

## Acceptance Scenarios

### Scenario 1 — Registration
```
When POST /v1/auth/register { username: "alice", email: "a@b.com", password: "secret123" }
Then HTTP 201
And User row created with bcrypt password_hash
And is_master = false
```

### Scenario 2 — Login and token issuance
```
When POST /v1/auth/token { username: "alice", password: "secret123" }
Then HTTP 200
And access_token is a valid JWT with claims: sub, username, is_master, exp
And refresh_token is a 32-byte base64url string
And refresh_token stored as hash in refresh_tokens table
```

### Scenario 3 — Access token protects endpoint
```
Given valid JWT access_token
When POST /v1/responses with Authorization: Bearer <access_token>
Then request is processed (auth middleware extracts user)
```

### Scenario 4 — Expired access token falls through to API key check
```
Given expired JWT
And valid API key for the same user
When Authorization: Bearer <api_key>
Then JWT decode fails (expiry)
And API key lookup succeeds
And request is processed
```

### Scenario 5 — Refresh token rotation
```
Given valid refresh_token "rt_abc"
When POST /v1/auth/refresh { refresh_token: "rt_abc" }
Then HTTP 200 with new access_token + new refresh_token "rt_xyz"
And rt_abc marked used = true
When POST /v1/auth/refresh { refresh_token: "rt_abc" } again
Then HTTP 401 (already used)
```

### Scenario 6 — API key lifecycle
```
When POST /v1/auth/apikeys { name: "my-script" }
Then HTTP 201 with { id, name, key: "tinycua-sk-…" }
When GET /v1/auth/apikeys
Then list includes { id, name } but NOT key value
When DELETE /v1/auth/apikeys/{id}
Then HTTP 204
And subsequent requests with that key return 401
```

### Scenario 7 — Session create and history load
```
When POST /v1/sessions { name: "research-session" }
Then HTTP 201 with { id: "sess_xyz", name, created_at }
When POST /v1/responses { session_id: "sess_xyz", input: [user_msg] }
Then history loaded (empty on first use)
And after response, turn appended to session_messages
When POST /v1/responses { session_id: "sess_xyz", input: [next_user_msg] }
Then prior turn is prepended to input[]
```

### Scenario 8 — Session ownership
```
Given session "sess_xyz" owned by user "alice"
When user "bob" calls GET /v1/sessions/sess_xyz
Then HTTP 404 (not exposed to other users)
```

### Scenario 9 — get_context tool returns session summary
```
Given session with 5 prior turns
And provider returns function_call for "get_context"
When orchestration loop handles get_context
Then SessionService.get_context("sess_xyz") called
And result contains plain-text summary of last 3 assistant messages
And no Runner call is made
```

### Scenario 10 — Duplicate registration
```
When POST /v1/auth/register with existing username
Then HTTP 409
And body.error.code = "conflict"
```

---

## Testing Plan

- **Unit**: password hashing/verification, JWT encode/decode, refresh token generation +
  hashing, API key generation + hash comparison, `SessionService.load_history()`,
  `SessionService.save_turn()`, `SessionService.get_context()` summary logic.
- **Integration**: full registration → login → refresh → API call → session create →
  session use → session delete flow against an in-memory SQLite database.
- **Security**: expired JWT → 401; used refresh token → 401; revoked API key → 401;
  cross-user session access → 404; is_master=false + CUA tool → `cua_access_denied`.

---

## Open Questions

- **OQ-001**: Should the `is_master` flag be settable via an admin endpoint protected by
  a separate admin token, or only via direct DB access / CLI?
  Recommendation: direct DB / admin CLI in MVP. An admin HTTP endpoint introduces
  additional attack surface and is deferred to Phase 2.
- **OQ-002**: Should session history be summarised before being prepended to `input[]`
  (to avoid growing context windows)? Recommendation: raw history in MVP; summarisation
  hook deferred to Phase 2 (ties into `Agent._prune_messages()`).
- **OQ-003**: Should `DELETE /v1/sessions/{id}` be a soft-delete (flag) or hard-delete?
  Recommendation: hard-delete in MVP for simplicity.
