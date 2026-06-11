# Tasks: TinyCUAResponseNode

Implementation tasks for Milestone 3.5 — TinyCUAResponseNode. Check off items as completed.

## Pre-Implementation

- [x] Resolve spec/design open questions (sufficiency definition, digester default behavior) <!-- id: -2 -->
- [x] Update spec/design with decided answers <!-- id: -1 -->
- [x] Verify implementation readiness: dependencies available, docs finalized, cross-references consistent <!-- id: -0.5 -->

## TDD Phase (Tests First)

- [x] Write integration tests for TinyCUAResponseNode (defined in implementation-plan.md) <!-- id: 0 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

### Task 1: ResponseContext helper and context sufficiency check <!-- id: 2 -->

- [x] Add `ResponseContext` dataclass with fields: `aggregated_result`, `session_context`, `latest_output`, `continuation_payload` <!-- id: 2a -->
- [x] Add `_check_context_sufficiency(self, context: ResponseContext) -> bool` method — analyze context size/completeness, return True if sufficient <!-- id: 2b -->
- [x] Add configurable sufficiency threshold support via `NodeConfig.metadata` <!-- id: 2c -->
- [x] Write unit tests for `ResponseContext` construction and sufficiency check <!-- id: 2d -->

### Task 2: Direct synthesis path <!-- id: 3 -->

- [x] Implement `_synthesize_response(self, context: ResponseContext) -> LLMResult` — build LLM input from aggregated context and produce final response <!-- id: 3a -->
- [x] Ensure `__call__` routes to direct synthesis when context is sufficient <!-- id: 3b -->
- [x] Write unit tests for direct synthesis with sufficient context <!-- id: 3c -->

### Task 3: Digester suspension path <!-- id: 4 -->

- [x] Implement `_suspend_for_digestion(self, context: ResponseContext, queue: NodeQueue) -> None` — suspend via `queue.suspend_current_and_prepend([TinyCUAInformationDigesterNode(parent=self)])` <!-- id: 4a -->
- [x] Wire suspension into `__call__` — when context insufficient and `digester_enabled=True` (via `config.metadata`), set `_needs_digestion` flag; actual suspension via `on_complete` prepends TinyCUAInformationDigesterNode <!-- id: 4b -->
- [x] Add `max_digest_attempts` counter to prevent infinite loops <!-- id: 4c -->
- [x] Implement resume flow — when digest returns, re-check sufficiency and synthesize <!-- id: 4d -->
- [x] Write unit tests for digester suspension path <!-- id: 4e -->

### Task 4: Direct tool fallback <!-- id: 5 -->

- [x] Implement `_gather_context_via_tools(self, context: ResponseContext) -> ResponseContext` — use allowed tools to gather additional context <!-- id: 5a -->
- [x] Wire tool fallback into `__call__` — when digester unavailable and context insufficient, use tools directly <!-- id: 5b -->
- [x] Ensure same base toolset as TaskExecutor via `NodeToolPolicy(include_agent_tools="all")` <!-- id: 5c -->
- [x] Write unit tests for direct tool fallback <!-- id: 5d -->

### Task 5: Terminal normalization <!-- id: 6 -->

- [x] Ensure `__call__` always returns `LLMResult` with string `content` <!-- id: 6a -->
- [x] Handle non-string LLM results by converting to string <!-- id: 6b -->
- [x] Write unit tests for terminal output normalization <!-- id: 6c -->

### Task 6: Retry compliance <!-- id: 7 -->

- [x] Integrate with existing `NodeRetryPolicy` — ensure retry loop covers all three phases <!-- id: 7a -->
- [x] Implement fallback message on retry exhaustion — return configurable fallback string instead of raising <!-- id: 7b -->
- [x] Write unit tests for retry exhaustion fallback <!-- id: 7c -->

### Task 7: Continuation routing <!-- id: 8 -->

- [x] Add `_continuation_payload` attribute for MandatoryPassthrough data <!-- id: 8a -->
- [x] Implement consolidated continuation behavior — when continuation payload is set, deliver response without LLM rerouting <!-- id: 8b -->
- [x] Wire loop's `_execute_node` to handle ResponseNode continuation routing <!-- id: 8c -->
- [x] Write unit tests for continuation routing <!-- id: 8d -->

### Task 8: Loop integration <!-- id: 9 -->

- [x] Update `tinycua_loop.py` imports and references to use `TinyCUAResponseNode` <!-- id: 9a -->
- [x] Wire `_route_to_aggregation` to spawn `TinyCUAResponseNode` as terminal <!-- id: 9b -->
- [x] Handle suspension/resume flow in loop's `_execute_node` for terminal nodes <!-- id: 9c -->
- [x] Update `__init__.py` exports <!-- id: 9d -->
- [x] Write integration tests for full queue lifecycle with ResponseNode <!-- id: 9e -->

## Testing Phase

- [x] Run integration tests — expect GREEN (all pass) <!-- id: 10 -->
- [x] Run unit tests for all ResponseNode components <!-- id: 11 -->
- [x] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 12 -->

## Verification Phase

- [x] Verify context sufficiency check correctly identifies sufficient vs. insufficient context <!-- id: 13 -->
- [x] Verify digester suspension path does not create infinite loops <!-- id: 14 -->
- [x] Verify tool fallback uses same toolset as TaskExecutor <!-- id: 15 -->
- [x] Verify retry exhaustion returns fallback message, not an exception <!-- id: 16 -->
- [x] Verify terminal output is always a normalized string <!-- id: 17 -->
- [x] Verify continuation routing delivers continuation without LLM rerouting <!-- id: 18 -->

## Documentation Phase

- [ ] Update `CHANGELOG.md` with Milestone 3.5 entry <!-- id: 19 -->
- [ ] Update `src/tinycua/docs/design/loops/response.md` with implementation details and decisions <!-- id: 20 -->
- [ ] Update `src/tinycua/docs/design/loops/` index if applicable <!-- id: 20b -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-12*
