# Design Document: API Version Header

**Spec**: `specs/api-version-header/spec.md`
**Status**: Draft
**Last Updated**: 2026-05-12

---

## Overview

Add an `X-API-Version` response header to all HTTP responses from tinycua-backend. The version is read once from `pyproject.toml`'s `project.version` field at module import time. A FastAPI middleware injects the header into every response, including errors. Only the `tinycua-backend` subproject is affected.

---

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │             FastAPI Application          │
                    │                                          │
                    │  ┌─────────────────────────────────┐     │
                    │  │   VersionMiddleware              │     │
                    │  │   - reads version at import      │     │
                    │  │   - adds X-API-Version header    │     │
                    │  │   - runs on every response       │     │
                    │  └─────────────────────────────────┘     │
                    │                                          │
                    │  ┌──────────┐  ┌──────────┐  ┌──────┐  │
                    │  │   Auth   │  │ Sessions │  │ Run  │  │
                    │  └──────────┘  └──────────┘  └──────┘  │
                    └─────────────────────────────────────────┘
                                        │
                                   [All responses include
                                    X-API-Version header]
                                        │
                                    ┌──▼───┐
                                    │Client│
                                    └──────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua_backend/main.py` | Modified | Add `VersionMiddleware` to app |
| `tinycua_backend/api/version.py` | New | Reads version from pyproject.toml, exposes as constant |
| `tinycua_backend/api/version_middleware.py` | New | FastAPI middleware that injects header |

---

## Data Model

No new data entities. No database changes.

### Version Resolution

```python
# Conceptual: how the version constant is derived
API_VERSION: str = _read_version_from_pyproject()

def _read_version_from_pyproject() -> str:
    """
    Read project.version from pyproject.toml.
    Returns "unknown" if file is missing, unreadable, or has no version field.
    """
```

---

## API / Interface Contracts

### Response Header Addition

All responses — success (2xx), redirect (3xx), client error (4xx), server error (5xx) — include:

```
X-API-Version: 0.1.0
```

No new endpoints, no request changes, no query/schema modifications.

### Error Handling

| Error Case | Behavior | Notes |
|------------|----------|-------|
| pyproject.toml not found | Version = `"unknown"` | Non-fatal, logged at WARNING |
| pyproject.toml has no `project.version` | Version = `"unknown"` | Non-fatal, logged at WARNING |
| pyproject.toml is malformed TOML | Version = `"unknown"` | Non-fatal, logged at WARNING |

---

## Implementation Phases

### Phase 1 — MVP

- [ ] Create `tinycua_backend/api/version.py` — reads and exports `API_VERSION` constant from `pyproject.toml`
- [ ] Create `tinycua_backend/api/version_middleware.py` — FastAPI middleware that adds `X-API-Version` to every response
- [ ] Modify `tinycua_backend/main.py` — import and register `VersionMiddleware`
- [ ] Write unit tests for version resolution (happy path + fallbacks)
- [ ] Write integration tests verifying header presence on success + error responses

### Phase 2 — Enhancements

*None planned. The spec explicitly scopes this to server-side only.*

---

## Technical Decisions

1. **Decision**: Middleware instead of a `@app.after_request` hook or route decorator.
   - **Reason**: FastAPI/Starlette middlewares intercept all responses (including those from exception handlers), guaranteeing the header appears on error responses without custom exception handlers.
   - **Alternatives Considered**: A custom `APIRoute` subclass — too heavy for a single header. A base `Response` model mixin — wouldn't cover errors.

2. **Decision**: Read version once at module import time, not per-request.
   - **Reason**: `pyproject.toml` is a static file deployed with the application. Reading it on every request would add unnecessary I/O. A single read at import is the simplest correct approach.

3. **Decision**: Fallback `"unknown"` instead of crashing on missing pyproject.toml.
   - **Reason**: Follows the robustness principle. The application should still serve requests even if the version file is accidentally omitted from the deployment.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| pyproject.toml missing in Docker image | Low | Medium | Fallback to `"unknown"`, log warning |
| Version changes during runtime (dev hot-reload) | Low | Low | Version is static after import; requires restart to pick up new version (acceptable) |
| Middleware ordering conflicts with other middleware | Low | Low | Register version middleware first (outermost) so header is added last |

---

## Open Questions

None.

---

## References

- Spec: `./spec.md`
