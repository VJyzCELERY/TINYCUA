# Implementation: API Version Header

Add an `X-API-Version` response header to all HTTP responses from tinycua-backend by reading `project.version` from `pyproject.toml` once at import time and injecting it via a FastAPI middleware.

## Context

- **Spec Reference**: `specs/api-version-header/spec.md`
- **Design Reference**: `specs/api-version-header/design.md`
- **Priority**: P1
- **Estimated Effort**: S

## Success Criteria — Integration Tests (TDD First)

Integrations tests are written FIRST and prove the feature works end-to-end.

```python
# Test file: tests/integration/test_api_version_header.py
"""Integration tests for X-API-Version header."""

import pytest
from fastapi.testclient import TestClient


def test_health_response_includes_version_header(client: TestClient):
    """GET /health must include X-API-Version with correct value."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-API-Version" in response.headers
    assert response.headers["X-API-Version"] == "0.1.0"


def test_authenticated_endpoint_includes_version_header(client: TestClient, auth_headers: dict):
    """Authenticated API responses must include X-API-Version."""
    response = client.get("/v1/sessions", headers=auth_headers)
    assert response.status_code == 200
    assert "X-API-Version" in response.headers


def test_error_response_includes_version_header(client: TestClient):
    """Error responses (404) must include X-API-Version."""
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert "X-API-Version" in response.headers
```

### Key Test Scenarios

- [x] **Success response**: `GET /health` returns `X-API-Version` matching `pyproject.toml`'s `project.version`
- [x] **Authenticated response**: any authenticated endpoint returns `X-API-Version`
- [x] **Error response**: 404 error returns `X-API-Version`

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for `version.py` — test happy path, missing file, missing version, malformed TOML
- [x] Existing test suite — confirm no regressions: `uv run pytest`

### Manual Verification

- [x] Start server, `curl -v http://localhost:8000/health`, verify `X-API-Version: 0.1.0` in response headers

### Performance Considerations

- [x] Version is read once at import time, not per-request (confirmed by design)
- [x] No measurable overhead from middleware (single header set on `__call__`)

## Proposed Changes

### Version Reader Module

#### [NEW] `tinycua_backend/api/version.py`

- **Description**: Reads `project.version` from `pyproject.toml` at import time and exports `API_VERSION` constant.
- **Dependencies**: `tomllib` (stdlib, Python 3.11+); `pathlib`
- **Rationale**: Single source of truth for the version string, read once.

### Version Middleware

#### [NEW] `tinycua_backend/api/version_middleware.py`

- **Description**: FastAPI/Starlette `BaseHTTPMiddleware` subclass that adds `X-API-Version` header to every response.
- **Dependencies**: `tinycua_backend.api.version.API_VERSION`
- **Rationale**: Middleware is the only mechanism that guarantees header presence on ALL responses including errors.

### App Registration

#### [MODIFY] `tinycua_backend/main.py`

- **Description**: Import `VersionMiddleware` and register it via `app.add_middleware(VersionMiddleware)`.
- **Rationale**: Register the middleware so it takes effect on all routes.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua_backend/api/version.py` | New | Reads and exports `API_VERSION` constant |
| `tinycua_backend/api/version_middleware.py` | New | Middleware injecting `X-API-Version` header |
| `tinycua_backend/main.py` | Modify | Register `VersionMiddleware` |

## Data Model Changes

None.

## API Changes

No new endpoints, no modified endpoints. Every existing response gains an `X-API-Version` header.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `tomllib` | stdlib (Python 3.11+) | Parse `pyproject.toml` |

### Internal Dependencies

None.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `pyproject.toml` missing in deployment | Low | Fallback to `"unknown"`, log WARNING |
| Version field absent from `pyproject.toml` | Low | Fallback to `"unknown"` |
| Malformed TOML | Low | Fallback to `"unknown"` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-12*
