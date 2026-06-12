# Tasks: TinyCUA ResponseNode — Optional Information Digestion Request

Implementation tasks for TinyCUA ResponseNode — Optional Information Digestion Request. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
  - [ ] `test_digester_suspension` — end-to-end: __call__ → on_complete → digester → resume
  - [ ] `test_direct_synthesis_no_digestion` — sufficient context bypasses digestion
  - [ ] `test_max_digest_attempts_enforced` — guard prevents infinite loops
  - [ ] `test_digester_enabled_false_fallback` — falls through to tool gathering
- [ ] Write unit tests for ResponseNode components <!-- id: 1 -->
  - [ ] `TestResponseContext` — dataclass fields
  - [ ] `TestTinyCUAResponseNodeInit` — constructor, initial state
  - [ ] `TestCheckContextSufficiency` — primary + secondary checks
  - [ ] `TestSynthesizeResponse` — LLM delegation, fallback on error
  - [ ] `TestSuspendForDigestion` — digester creation, max-attempts guard
  - [ ] `TestGatherContextViaTools` — placeholder returns context
  - [ ] `TestRetryCompliance` — retry exhaustion fallback
  - [ ] `TestContinuationRouting` — MandatoryPassthrough delivery
  - [ ] `TestOnComplete` — flag-based dispatch
  - [ ] `TestToolPolicyCompliance` — same toolset as TaskExecutor
  - [ ] `TestTerminalNormalization` — output always string
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [ ] Implement `_check_context_sufficiency` in `ResponseNode` <!-- id: 3 -->
  - [ ] Primary check: `aggregated_result` present with `task_summaries` or `final_context`
  - [ ] Secondary check: `session_context` size >= configurable `sufficiency_threshold`
- [ ] Implement three-phase execution in `ResponseNode.__call__` <!-- id: 4 -->
  - [ ] Phase 1: Build `ResponseContext` from session + input
  - [ ] Phase 2: Check sufficiency → synthesize directly, or set `_needs_digestion` flag, or fall through to tools
  - [ ] Phase 3: Normalize terminal output to string
- [ ] Implement `on_complete` digester trigger <!-- id: 5 -->
  - [ ] Check `_needs_digestion` flag
  - [ ] Call `_suspend_for_digestion` when True
  - [ ] No-op when False (queue advances normally)
- [ ] Implement `_suspend_for_digestion` <!-- id: 6 -->
  - [ ] Check `max_digest_attempts` guard (default 3)
  - [ ] Create `TinyCUAInformationDigesterNode(parent=self)` via local import
  - [ ] Call `queue.suspend_current_and_prepend([digester])`
  - [ ] Increment `_digest_attempts` counter
- [ ] Implement `_gather_context_via_tools` placeholder <!-- id: 7 -->
  - [ ] Return context unchanged (placeholder for M4.2)
  - [ ] Log placeholder invocation
- [ ] Implement `_synthesize_response` <!-- id: 8 -->
  - [ ] Handle missing LLM client → return fallback message
  - [ ] Delegate to inherited `ProcessNode.__call__` for LLM invocation
  - [ ] Catch `NodeExecutionError` → return fallback
  - [ ] Catch unexpected exceptions → return fallback (unless `strict_mode`)
- [ ] Implement `_handle_continuation` <!-- id: 9 -->
  - [ ] Consume `_continuation_payload`
  - [ ] Check sufficiency → synthesize or return acknowledgement
- [ ] Implement `InformationDigesterNode` fresh session <!-- id: 10 -->
  - [ ] Create new `Session()` in `__call__` if none exists
  - [ ] Never inherit parent's session
- [ ] Implement `InformationDigesterNode` digest production <!-- id: 11 -->
  - [ ] `_produce_digest` builds context text and invokes LLM
  - [ ] `_parse_digest_response` parses JSON into `DigestedInformation`
  - [ ] `_produce_fallback` preserves user query
- [ ] Implement `InformationDigesterNode.on_complete` parent propagation <!-- id: 12 -->
  - [ ] Append digest to `parent.session_context`
  - [ ] Call `queue.advance()` to resume parent

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
  - [ ] `cd src/tinycua && uv run pytest tests/integration/test_response_node_integration.py -v`
- [ ] Run unit tests — expect all pass <!-- id: 14 -->
  - [ ] `cd src/tinycua && uv run pytest tests/unit/test_response_node.py -v`
- [ ] Run full test suite — confirm no regressions <!-- id: 15 -->
  - [ ] `cd src/tinycua && uv run pytest`

## Verification Phase

- [ ] Verify `_needs_digestion` flag is set when context is insufficient and digester enabled <!-- id: 16 -->
- [ ] Verify `on_complete` triggers `_suspend_for_digestion` when `_needs_digestion=True` <!-- id: 17 -->
- [ ] Verify `max_digest_attempts` guard prevents infinite loops <!-- id: 18 -->
- [ ] Verify `digester_enabled=False` falls through to `_gather_context_via_tools` <!-- id: 19 -->
- [ ] Verify `InformationDigesterNode` creates fresh session <!-- id: 20 -->
- [ ] Verify digest propagation to parent's `session_context` <!-- id: 21 -->
- [ ] Verify `queue.advance()` is called after digest propagation <!-- id: 22 -->

## Documentation Phase

- [ ] Update spec status tracker with implementation notes <!-- id: 23 -->
- [ ] No API documentation changes (internal node behavior only) <!-- id: 24 -->

## Review and Merge

- [ ] Create pull request <!-- id: 25 -->
- [ ] Address review feedback <!-- id: 26 -->
- [ ] Merge to main branch <!-- id: 27 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-12*
