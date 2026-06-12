# Tasks: TinyCUA ResponseNode — Optional Information Digestion Request

Implementation tasks for TinyCUA ResponseNode — Optional Information Digestion Request. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
  - [x] `test_digester_suspension` — end-to-end: __call__ → on_complete → digester → resume
  - [x] `test_direct_synthesis_no_digestion` — sufficient context bypasses digestion
  - [x] `test_max_digest_attempts_enforced` — guard prevents infinite loops
  - [x] `test_digester_enabled_false_fallback` — falls through to tool gathering
- [x] Write unit tests for ResponseNode components <!-- id: 1 -->
  - [x] `TestResponseContext` — dataclass fields
  - [x] `TestTinyCUAResponseNodeInit` — constructor, initial state
  - [x] `TestCheckContextSufficiency` — primary + secondary checks
  - [x] `TestSynthesizeResponse` — LLM delegation, fallback on error
  - [x] `TestSuspendForDigestion` — digester creation, max-attempts guard
  - [x] `TestGatherContextViaTools` — placeholder returns context
  - [x] `TestRetryCompliance` — retry exhaustion fallback
  - [x] `TestContinuationRouting` — MandatoryPassthrough delivery
  - [x] `TestOnComplete` — flag-based dispatch
  - [x] `TestToolPolicyCompliance` — same toolset as TaskExecutor
  - [x] `TestTerminalNormalization` — output always string
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [x] Implement `_check_context_sufficiency` in `ResponseNode` <!-- id: 3 -->
  - [x] Primary check: `aggregated_result` present with `task_summaries` or `final_context`
  - [x] Secondary check: `session_context` size >= configurable `sufficiency_threshold`
- [x] Implement three-phase execution in `ResponseNode.__call__` <!-- id: 4 -->
  - [x] Phase 1: Build `ResponseContext` from session + input
  - [x] Phase 2: Check sufficiency → synthesize directly, or set `_needs_digestion` flag, or fall through to tools
  - [x] Phase 3: Normalize terminal output to string
- [x] Implement `on_complete` digester trigger <!-- id: 5 -->
  - [x] Check `_needs_digestion` flag
  - [x] Call `_suspend_for_digestion` when True
  - [x] No-op when False (queue advances normally)
- [x] Implement `_suspend_for_digestion` <!-- id: 6 -->
  - [x] Check `max_digest_attempts` guard (default 3)
  - [x] Create `TinyCUAInformationDigesterNode(parent=self)` via local import
  - [x] Call `queue.suspend_current_and_prepend([digester])`
  - [x] Increment `_digest_attempts` counter
- [x] Implement `_gather_context_via_tools` placeholder <!-- id: 7 -->
  - [x] Return context unchanged (placeholder for M4.2)
  - [x] Log placeholder invocation
- [x] Implement `_synthesize_response` <!-- id: 8 -->
  - [x] Handle missing LLM client → return fallback message
  - [x] Delegate to inherited `ProcessNode.__call__` for LLM invocation
  - [x] Catch `NodeExecutionError` → return fallback
  - [x] Catch unexpected exceptions → return fallback (unless `strict_mode`)
- [x] Implement `_handle_continuation` <!-- id: 9 -->
  - [x] Consume `_continuation_payload`
  - [x] Check sufficiency → synthesize or return acknowledgement
- [x] Implement `InformationDigesterNode` fresh session <!-- id: 10 -->
  - [x] Create new `Session()` in `__call__` if none exists
  - [x] Never inherit parent's session
- [x] Implement `InformationDigesterNode` digest production <!-- id: 11 -->
  - [x] `_produce_digest` builds context text and invokes LLM
  - [x] `_parse_digest_response` parses JSON into `DigestedInformation`
  - [x] `_produce_fallback` preserves user query
- [x] Implement `InformationDigesterNode.on_complete` parent propagation <!-- id: 12 -->
  - [x] Append digest to `parent.session_context`
  - [x] Call `queue.advance()` to resume parent

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
  - [x] `cd src/tinycua && uv run pytest tests/integration/test_response_node_integration.py -v`
- [x] Run unit tests — expect all pass <!-- id: 14 -->
  - [x] `cd src/tinycua && uv run pytest tests/unit/test_response_node.py -v`
- [x] Run full test suite — confirm no regressions <!-- id: 15 -->
  - [x] `cd src/tinycua && uv run pytest`

## Verification Phase

- [x] Verify `_needs_digestion` flag is set when context is insufficient and digester enabled <!-- id: 16 -->
- [x] Verify `on_complete` triggers `_suspend_for_digestion` when `_needs_digestion=True` <!-- id: 17 -->
- [x] Verify `max_digest_attempts` guard prevents infinite loops <!-- id: 18 -->
- [x] Verify `digester_enabled=False` falls through to `_gather_context_via_tools` <!-- id: 19 -->
- [x] Verify `InformationDigesterNode` creates fresh session <!-- id: 20 -->
- [x] Verify digest propagation to parent's `session_context` <!-- id: 21 -->
- [x] Verify `queue.advance()` is called after digest propagation <!-- id: 22 -->

## Documentation Phase

- [x] Update spec status tracker with implementation notes <!-- id: 23 -->
- [x] No API documentation changes (internal node behavior only) <!-- id: 24 -->

## Review and Merge

- [x] Create pull request <!-- id: 25 -->
- [ ] Address review feedback <!-- id: 26 -->
- [ ] Merge to main branch <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-12*
