## Summary

### Spec / Design References

- **Spec**: `specs/test-api-version/spec.md`
- **Design**: `specs/test-api-version/design.md`

### Problem

The backend currently has no mechanism for clients to programmatically determine which version of the API is deployed. Clients must rely on out-of-band communication or trial-and-error.

### Solution

Add an `X-API-Version` response header to every HTTP response via FastAPI middleware. The version string is read from `pyproject.toml` at startup with a fallback to `unknown`.

### Scope

In scope:
- FR-001: X-API-Version header on every response
- FR-002: Version derived from pyproject.toml
- FR-003: Fallback to unknown
- FR-004: Middleware-based implementation
- FR-005: Unit test for header presence
- FR-006: Unit test for fallback behavior

Out of scope:
- WebSocket upgrade responses
- Semantic versioning strategy
- Version negotiation via Accept header

## How to Test

1. Run the test suite:
   ```bash
   cd src/tinycua-backend && uv run pytest tests/unit/test_api_version.py -v
   ```
   - Expected: All tests pass (header present, version matches, fallback works)

2. Run lint:
   ```bash
   cd src/tinycua-backend && uv run ruff check .
   ```
   - Expected: All checks passed!

## Review Notes

- `src/tinycua-backend/src/tinycua_backend/middleware/version_header.py` — Middleware implementation, check error handling
- `src/tinycua-backend/tests/unit/test_api_version.py` — Test coverage for normal and fallback paths

## Related Issues

- None
