# Design Document: API Version Header

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-05-11

---

## Overview

Add an `X-API-Version` response header to every HTTP response from the `tinycua-backend` service using FastAPI middleware. The version string is read from the project metadata at startup.

---

## Architecture

### Component Overview

```text
[Client] --> [FastAPI App] --> [VersionHeaderMiddleware] --> [Route Handler]
                            |                                    |
                            +--- adds X-API-Version header -------+
                                     |
                               (also applies to 404/500 responses via exception handlers)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `src/tinycua-backend/src/tinycua_backend/main.py` | Modified | Add middleware registration |
| `src/tinycua-backend/src/tinycua_backend/middleware/` | New | New middleware module |
| `src/tinycua-backend/src/tinycua_backend/middleware/__init__.py` | New | Package init |
| `src/tinycua-backend/src/tinycua_backend/middleware/version_header.py` | New | Middleware implementation |
| `src/tinycua-backend/tests/unit/test_api_version.py` | New | Unit tests |
| `src/tinycua-backend/pyproject.toml` | Read-only | Version source (no change) |

---

## Data Model

### New Entities _(if applicable)_

No new data entities. The `X-API-Version` header is a plain string.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
# New middleware class
class VersionHeaderMiddleware(BaseHTTPMiddleware):
    """
    Add X-API-Version header to every response.
    Version read from importlib.metadata or pyproject.toml at startup.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-API-Version"] = self.version
        return response
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| pyproject.toml missing | Header value: `unknown` | Graceful degradation |
| Malformed TOML | Header value: `unknown` | Catch parse errors |
| Middleware exception | Normal FastAPI 500 handling | Header still added by middleware wrapping |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `src/tinycua-backend/src/tinycua_backend/middleware/__init__.py`
- [ ] Create `src/tinycua-backend/src/tinycua_backend/middleware/version_header.py`
- [ ] Register middleware in `src/tinycua-backend/src/tinycua_backend/main.py`
- [ ] Write unit tests in `src/tinycua-backend/tests/unit/test_api_version.py`
- [ ] Run existing test suite to confirm no regressions

---

## Technical Decisions

1. **Decision**: Use middleware rather than a route decorator or response model.
   - **Reason**: Middleware applies to ALL routes including 404/405/500 responses. Decorators miss error responses and would require per-route duplication.
   - **Alternatives Considered**: ASGI middleware — more complex; no benefit for this simple use case.

2. **Decision**: Read version from `pyproject.toml` at import time rather than making it a build-time constant.
   - **Reason**: Simplifies development iteration; no build step needed to change the version.
   - **Alternatives Considered**: Environment variable — adds deployment complexity.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Middleware adds latency to every request | Low | Low | Middleware is a single `response.headers` assignment; sub-microsecond overhead |
| Version string changes during hot-reload | Low | Low | Read at import time; restart required to pick up new version (acceptable for dev) |

---

## References

- Spec: `./spec.md`
