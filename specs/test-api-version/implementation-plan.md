# Implementation: API Version Header

Add an `X-API-Version` response header to every HTTP response from the `tinycua-backend` service, derived from the project version in `pyproject.toml`, using FastAPI middleware.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Proposed Changes

### Middleware Module

#### [NEW] `src/tinycua-backend/src/tinycua_backend/middleware/__init__.py`

- **[Description]**: Create package init for the new middleware module
- **[Rationale]**: Required to make `middleware/` a Python package

#### [NEW] `src/tinycua-backend/src/tinycua_backend/middleware/version_header.py`

- **[Description]**: Implement `VersionHeaderMiddleware` class extending `BaseHTTPMiddleware` that reads the version from `pyproject.toml` at import time and adds `X-API-Version` to every response
- **[Rationale]**: Middleware ensures header is applied to all routes including error responses (404/500)

### Application Entry Point

#### [MODIFY] `src/tinycua-backend/src/tinycua_backend/main.py`

- **[Description of change]**: Register `VersionHeaderMiddleware` on the FastAPI app instance
- **[Rationale]**: Middleware must be wired into the application to take effect

### Tests

#### [NEW] `src/tinycua-backend/tests/unit/test_api_version.py`

- **[Description]**: Unit tests verifying the middleware adds the header, matches project version, and falls back to `unknown`
- **[Dependencies]**: middleware module

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `src/tinycua-backend/src/tinycua_backend/main.py` | Modify | Add middleware registration |
| `src/tinycua-backend/src/tinycua_backend/middleware/` | New | New package for middleware modules |
| `src/tinycua-backend/src/tinycua_backend/middleware/__init__.py` | New | Package init |
| `src/tinycua-backend/src/tinycua_backend/middleware/version_header.py` | New | Middleware implementation |
| `src/tinycua-backend/tests/unit/test_api_version.py` | New | Unit tests |
| `src/tinycua-backend/pyproject.toml` | Read-only | Version source (no change) |

## Data Model Changes

No new data entities. The `X-API-Version` header is a plain string.

## API Changes

### New Endpoints

None.

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| ALL | ALL | Added `X-API-Version` response header |

## Verification Plan

### Automated Tests

- [ ] Unit tests for `VersionHeaderMiddleware` — verify header present on mock GET request
- [ ] Unit test — verify header value matches `pyproject.toml` version
- [ ] Unit test — verify fallback to `unknown` when version source is unavailable
- [ ] Integration test — run existing test suite to confirm no regressions

### Manual Verification

- [ ] Start server with `uv run uvicorn tinycua_backend.main:app` and curl an endpoint to verify the header

### Performance Considerations

- [ ] Middleware adds a single `response.headers` assignment; sub-microsecond overhead, no measurable performance impact

## Rollout Strategy

1. **Phase 1** (MVP): Implement middleware, register in app, write unit tests
2. **Phase 2** (Verification): Run full test suite, manual curl verification
3. **Phase 3** (Merge): Create PR, review, merge

## Dependencies

### External Dependencies

None. Uses only standard library and FastAPI/Starlette primitives already present.

### Internal Dependencies

- [ ] Depends on `src/tinycua-backend/pyproject.toml` existing with a valid `project.version`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Middleware adds latency to every request | Low | Single header assignment; sub-microsecond overhead |
| Version string changes during hot-reload | Low | Read at import time; restart required |
| pyproject.toml missing or malformed | Low | Graceful fallback to `unknown` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-11*
