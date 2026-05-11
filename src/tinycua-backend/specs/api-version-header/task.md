# Tasks: API Version Header

Implementation tasks for API Version Header feature. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests in `tests/integration/test_api_version_header.py` <!-- id: 0 -->
- [ ] Write unit tests in `tests/unit/test_version.py` (`test_version_read_from_pyproject`, `test_version_fallback_missing_file`, `test_version_fallback_missing_field`, `test_version_fallback_malformed_toml`) <!-- id: 1 -->
- [ ] Run integration and unit tests — expect RED (failures since no implementation yet) <!-- id: 2 -->

## Implementation Phase

- [ ] Create `tinycua_backend/api/version.py` — read `project.version` from `pyproject.toml` using `tomllib`; export `API_VERSION` constant; handle missing file, missing field, malformed TOML <!-- id: 3 -->
- [ ] Create `tinycua_backend/api/version_middleware.py` — `VersionMiddleware(BaseHTTPMiddleware)` that sets `X-API-Version` on every response via `response.headers["X-API-Version"] = API_VERSION` <!-- id: 4 -->
- [ ] Modify `tinycua_backend/main.py` — import `VersionMiddleware`, add via `app.add_middleware(VersionMiddleware)` <!-- id: 5 -->

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 6 -->
- [ ] Run unit tests — expect GREEN (all pass) <!-- id: 7 -->
- [ ] Run full test suite: `cd src/tinycua-backend && uv run pytest` <!-- id: 8 -->

## Verification Phase

- [ ] Start server locally, `curl -v http://localhost:8000/health`, verify `X-API-Version: 0.1.0` in response headers <!-- id: 9 -->
- [ ] Verify `curl -v http://localhost:8000/nonexistent` returns 404 with `X-API-Version` header <!-- id: 10 -->

## Documentation Phase

- [ ] Update API docs if auto-generated docs change <!-- id: 11 -->
- [ ] Update changelog <!-- id: 12 -->

## Review and Merge

- [ ] Create pull request <!-- id: 13 -->
- [ ] Address review feedback <!-- id: 14 -->
- [ ] Merge to base branch <!-- id: 15 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-12*
