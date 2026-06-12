# Implementation: TinyCUA ResponseNode — Optional Information Digestion Request

Formalizes the integration contract between `TinyCUAResponseNode` and `TinyCUAInformationDigesterNode`. When `ResponseNode` determines accumulated context is insufficient for a quality final response, it suspends the queue, prepends an `InformationDigesterNode` (with `parent=ResponseNode`), the digester gathers and digests additional context, propagates the digest back to the parent's `session_context`, and the queue advances so `ResponseNode` resumes synthesis.

## Context

- **Spec Reference**: `./spec.md` — TinyCUA ResponseNode — Optional Information Digestion Request
- **Design Reference**: `./design.md` — ResponseNode optional information digestion request
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — no special configuration dependencies. Metadata keys (`digester_enabled`, `max_digest_attempts`, `sufficiency_threshold`) are dynamic and provided via `NodeConfigBase.metadata`.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [Python runtime] | Yes | `cd src/tinycua && uv run` | `uv run python -c "import tinycua"` |

- [x] **None** — no external services needed for unit/integration tests.

### Data / Fixtures

- [x] **None** — no data or fixtures needed. Tests use in-memory mocks and synthetic `Session` objects.

### Access / Permissions

- [x] **None** — no special access required.

### Developer Tooling

- [x] **Runtime**: Python 3.12+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required.

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

The test code is defined in `src/tinycua/tests/integration/test_response_node_integration.py` (12,496 bytes). Four test functions cover the critical paths:

- `test_digester_suspension` — end-to-end: `__call__` with insufficient context → `on_complete` triggers suspension → digester produces digest → digest propagates → response node resumes and synthesizes final response.
- `test_direct_synthesis_no_digestion` — sufficient context bypasses digestion entirely.
- `test_max_digest_attempts_enforced` — guard prevents infinite suspend/resume loops.
- `test_digester_enabled_false_fallback` — falls through to tool-based gathering.

### Key Test Scenarios

- [x] **Scenario 1**: Digester suspension — `__call__` with insufficient context sets `_needs_digestion`, `on_complete` triggers suspension, digester produces digest, digest propagates, response resumes and synthesizes.
- [x] **Scenario 2**: Direct synthesis — sufficient context bypasses digestion entirely.
- [x] **Edge case**: `max_digest_attempts` guard prevents infinite suspend/resume loops.
- [x] **Edge case**: `digester_enabled=False` falls through to tool-based gathering.

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for `ResponseNode` — test context sufficiency, suspension, continuation, retry, normalization
- [x] Unit tests for `InformationDigesterNode` — test fresh session creation, digest production, parent propagation
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify `ResponseContext` dataclass builds correctly from session data
- [x] Verify `on_complete` correctly dispatches based on `_needs_digestion` flag
- [x] Verify `InformationDigesterNode.on_complete` propagates digest to parent's session_context and calls `queue.advance()`

### Performance Considerations

- [x] No performance concerns — single-threaded queue model, no concurrent digestion possible.

## Proposed Changes

### loops/response_node.py

#### Modified (documenting existing implementation) src/tinycua/tinycua/loops/response_node.py

- **Three-phase execution in `__call__`**: Phase 1 builds `ResponseContext`, Phase 2 checks sufficiency (sufficient → synthesize, insufficient + digester → set flag, insufficient + no digester → tools), Phase 3 normalizes output.
- **`on_complete` digester trigger**: Checks `_needs_digestion` flag and calls `_suspend_for_digestion` when True.
- **`_suspend_for_digestion`**: Creates `TinyCUAInformationDigesterNode(parent=self)` and calls `queue.suspend_current_and_prepend`. Guards with `max_digest_attempts` (default 3).
- **`_check_context_sufficiency`**: Primary check (aggregated result with task_summaries or final_context) + secondary check (session_context size >= configurable threshold).
- **`_gather_context_via_tools`**: Placeholder returning context unchanged; full implementation deferred to M4.2.
- **`_synthesize_response`**: Delegates to inherited `ProcessNode.__call__` for LLM invocation; falls back to configurable message on error.
- **Rationale**: Implements the full response node lifecycle per spec FR-001 through FR-009.

#### Modified (documenting existing implementation) src/tinycua/tinycua/loops/information_digester.py

- **Fresh session creation**: `__call__` creates a new `Session()` if none exists, never inherits from parent (FR-005).
- **Digest production**: `_produce_digest` builds context text, invokes LLM, parses response into `DigestedInformation`.
- **Parent propagation in `on_complete`**: Appends digest output to `parent.session_context` and calls `queue.advance()` (FR-006).
- **Enhanced context retrieval placeholder**: `_invoke_enhanced_retrieval` returns empty list; full ReAct-style search deferred to M4.2.
- **Rationale**: Implements the digester integration contract per spec FR-005 through FR-006.

### No New Files

No new source files are needed. The implementation modifies existing `response_node.py` and `information_digester.py`. No changes to `loops/__init__.py`, `config/node_config.py`, or `models/digested_information.py`.

### No Breaking Changes

All modifications are backward-compatible. The `ResponseNode` and `InformationDigesterNode` APIs remain unchanged. Metadata keys are additive and optional with sensible defaults.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `loops/response_node.py` | Modify | Three-phase execution, digester suspension, max-attempts guard, context sufficiency check |
| `loops/information_digester.py` | Modify | Fresh session, parent propagation, digest production, enhanced retrieval placeholder |
| `loops/__init__.py` | No Change | Public exports unchanged |
| `config/node_config.py` | No Change | Metadata keys are dynamic, no schema changes |
| `models/digested_information.py` | No Change | `DigestedInformation` dataclass already defined |

## Data Model Changes

No new data models. Existing entities are sufficient:

`ResponseContext` is defined in `src/tinycua/tinycua/loops/response_node.py`. `DigestedInformation` is defined in `src/tinycua/tinycua/models/digested_information.py`.

## API Changes

### New Endpoints

None — this is internal node behavior, not an API surface.

### Modified Endpoints

None — the `ProcessNode` contract (`__call__`, `on_complete`) is unchanged.

## Dependencies

### External Dependencies

None — no new external packages required.

### Internal Dependencies

- [x] Depends on `TinyCUAInformationDigesterNode` (Milestone 2.5) — already implemented
- [x] Depends on `ResultAggregationNode` (Milestone 3.4) — already implemented
- [x] Depends on `NodeQueue.suspend_current_and_prepend` — already implemented
- [ ] Blocks: Full `EnhancedContextRetrieval` implementation (Milestone 4.2)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Infinite suspend/resume loop (digester → insufficient → digester → ...) | High | `max_digest_attempts` guard (default 3) prevents looping |
| Digester pollutes parent session context | Medium | Digester creates a fresh session; only the final digest output is propagated to the parent |
| Queue mutation (`suspend_current_and_prepend`) fails | High | `on_complete` handles `queue=None` gracefully; all mutation is in a single call |
| `_gather_context_via_tools` is a placeholder | Low | Falls back to existing context; synthesis produces a warning-logged response with whatever context is available |
| Digest is empty/malformed on propagation | Medium | ResponseNode re-evaluates sufficiency; if still insufficient, another digestion cycle may be attempted (up to max) |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-12*
