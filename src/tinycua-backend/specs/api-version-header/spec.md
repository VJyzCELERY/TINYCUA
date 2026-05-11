# Feature Specification: API Version Header

**Status**: Draft
**Created**: 2026-05-12
**Last Updated**: 2026-05-12
**Subproject(s) Affected**: tinycua-backend

---

## Problem Statement

- **Goals**: Provide an `X-API-Version` response header on every HTTP response so that callers (SDK, frontend, integrations) can programmatically determine which version of the backend served the request.
- **Gaps**: Today there is no mechanism for a client to discover the backend version at runtime. The version is hardcoded in `main.py` (`version="0.1.0"`) and also defined in `pyproject.toml` (`project.version`), but neither is surfaced to callers via HTTP headers.
- **Non-Goals**: Client-side SDK changes. Adding the version to request bodies, query parameters, or non-response-headers. Any UI (frontend) changes. Reading the version from any source other than `pyproject.toml`.
- **Constraints**: The version MUST be read from `pyproject.toml` (`project.version`) at import time, NOT hardcoded. The header MUST be present on ALL responses including error responses. The header key MUST be `X-API-Version`. Backward compatible — no existing endpoint signatures change.

---

## User Scenarios & Testing

### Primary Scenario

A client (SDK, frontend, or curl) makes any request to the backend and receives an `X-API-Version` header whose value matches the `project.version` in `pyproject.toml`.

### Acceptance Scenarios

1. **Given** a running tinycua-backend instance, **When** a client sends `GET /health`, **Then** the response includes header `X-API-Version` with value equal to `pyproject.toml`'s `project.version`.
2. **Given** a running tinycua-backend instance, **When** a client sends an authenticated request to any API endpoint (e.g. `GET /v1/sessions`), **Then** the response includes header `X-API-Version`.
3. **Given** a running tinycua-backend instance, **When** a client sends a request that results in an error (e.g. `GET /nonexistent`), **Then** the error response includes header `X-API-Version`.

### Edge Cases

- What happens when `pyproject.toml` is missing or unreadable? The system SHOULD fall back to `"unknown"`, not crash at import.
- What happens when `pyproject.toml` has no `project.version` field? The system SHOULD fall back to `"unknown"`.
- What happens when the version is an empty string? The system SHOULD fall back to `"unknown"`.

---

## Requirements

### Functional Requirements

- **FR-001**: The backend MUST read `project.version` from `pyproject.toml` at startup.
- **FR-002**: Every HTTP response MUST include the `X-API-Version` header.
- **FR-003**: The header value MUST equal the version string from `pyproject.toml`.
- **FR-004**: If the version cannot be read, the system MUST fall back to `"unknown"` and continue serving without crashing.
- **FR-005**: The version MUST be read once at import time (not recomputed per-request).

### Key Entities

- **API Version Header**: An HTTP response header (`X-API-Version`) on every response.
- **pyproject.toml**: The single source of truth for the backend version string.

---

## Success Criteria

- [ ] **All responses include header**: Every endpoint response (success + error) includes `X-API-Version`.
- [ ] **Value matches pyproject.toml**: Header value equals `pyproject.toml`'s `project.version`.
- [ ] **Graceful fallback**: Missing or invalid `pyproject.toml` results in `"unknown"`, not a crash.
- [ ] **No performance regression**: Version read is a one-time operation at module load, not per-request.

---

## Testing Plan

### Unit Tests

- Version is read correctly from `pyproject.toml` when the file exists and has `project.version`.
- Version falls back to `"unknown"` when `pyproject.toml` is missing.
- Version falls back to `"unknown"` when `pyproject.toml` lacks `project.version`.
- Version is read at import time (not per-request).

### Integration Tests

- `GET /health` response includes `X-API-Version` header with correct value.
- Authenticated API endpoint responses include `X-API-Version` header.
- Error responses (404, 401, 500) include `X-API-Version` header.

### Manual Tests

- Start the server, hit any endpoint with `curl -v`, verify `X-API-Version` appears in response headers.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Version reader from pyproject.toml | TODO | |
| Middleware to inject header on all responses | TODO | |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions

*None.*

---

## Review Checklist

- [x] No implementation details
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
