# Feature Specification: API Version Header

**Status**: Draft
**Created**: 2026-05-11
**Last Updated**: 2026-05-11
**Subproject(s) Affected**: tinycua-backend

---

## Quick Guidelines

- This spec describes a server-side middleware change only.
- No client-side or SDK changes required.
- No breaking changes to existing API responses.

---

## Problem Statement _(mandatory)_

- **Goals**: Provide API consumers with a consistent way to identify the running API version so they can adapt client behavior and troubleshoot compatibility issues.
- **Gaps**: The backend currently has no mechanism for clients to programmatically determine which version of the API is deployed. Clients must rely on out-of-band communication or trial-and-error.
- **Non-Goals**: This spec does not cover semantic versioning strategy, API deprecation policies, or version negotiation (Accept header / URL prefix routing). It only adds a passive version advertisement header.
- **Constraints**: Must not break existing endpoints or alter response bodies. Must work for all routes (including error responses). Must not introduce new dependencies.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A client calls any backend endpoint (e.g., `GET /api/v1/health`). The response includes an `X-API-Version` header with the current version string. The client reads this header and logs it for diagnostics.

### Acceptance Scenarios

1. **Given** a running backend, **When** a client sends a request to any route, **Then** the response includes an `X-API-Version` header with a non-empty value.
2. **Given** a running backend, **When** a client sends a request to a nonexistent route (404), **Then** the error response also includes the `X-API-Version` header.
3. **Given** the version string is defined in `pyproject.toml`, **When** the server starts, **Then** the header value matches the project version.

### Edge Cases

- What happens if `pyproject.toml` is missing or malformed? The header should fall back to `unknown`.
- What happens during exception handling (500 errors)? The header should still be present via middleware.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The backend MUST add an `X-API-Version` response header to every HTTP response.
- **FR-002**: The header value MUST be derived from the project version defined in `src/tinycua-backend/pyproject.toml`.
- **FR-003**: If the project version cannot be read, the header MUST fall back to the string `unknown`.
- **FR-004**: The implementation MUST use Starlette/FastAPI middleware to ensure the header is applied to all routes and error responses.
- **FR-005**: A unit test MUST verify the header is present and matches the expected version.
- **FR-006**: A unit test MUST verify the fallback behavior when the version source is unavailable.

### Key Entities _(include if feature involves data)_

- **X-API-Version header**: An HTTP response header carrying the API version string.

---

## Success Criteria _(mandatory)_

- **Header present**: Every response (success, 404, 500) includes `X-API-Version`.
- **Version matches**: The header value equals the `project.version` from `pyproject.toml` for the backend subproject.
- **Tests pass**: `uv run pytest tests/unit/test_api_version.py -v` exits 0.
- **No regressions**: `uv run pytest tests/ -v` exits 0 with no new failures.

---

## Testing Plan _(mandatory)_

### Unit Tests

- Test that middleware adds the header to a mock GET request.
- Test that the header value matches the version string from `pyproject.toml`.
- Test that the header falls back to `unknown` when the version file is missing.

### Integration Tests

- Run the existing integration suite to confirm no regressions.

### Manual Tests _(if applicable)_

- Start the server with `uv run uvicorn tinycua_backend.main:app` and curl an endpoint to verify the header.

---

## Open Questions _(optional)_

1. **Should the header be added to WebSocket upgrade responses?**
   - **Owner**: project maintainers
   - **Target**: before implementation
   - **Status**: Decided
   - **Answer**: No, WebSocket upgrades are out of scope.

---

## Review Checklist

- [x] No implementation details that require a specific patch shape
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
