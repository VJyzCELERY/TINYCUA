# Tasks: TinyCUA Handoff Isolation

Implementation tasks for TinyCUA Handoff Isolation. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write unit message-contract tests for handoff isolation <!-- id: 0 -->
- [x] Write streaming/native tool parity contract test <!-- id: 1 -->
- [x] Run targeted tests — expect RED before implementation <!-- id: 2 -->

## Implementation Phase

- [x] Enforce entry-only raw input policy <!-- id: 3 -->
  - [x] Add `NodeMessagePolicy.include_input_context`
  - [x] Enable input context only for QueryAnalyst
  - [x] Stop unconditional root input replay in `_build_node_messages`
- [x] Add continuation prompts <!-- id: 4 -->
  - [x] Add base `Node.build_continuation`
  - [x] Add node-specific continuation constants
  - [x] Append continuations as assistant-role messages
- [x] Normalize handoffs and duplicate suppression <!-- id: 5 -->
  - [x] Convert QueryAnalyst route handoffs to assistant-role `NodeInput`
  - [x] Forward structured outputs as compact assistant messages
  - [x] Skip session-context entries already present in current `NodeInput`
- [x] Align task lifecycle fallback <!-- id: 6 -->
  - [x] Prefer task/digest state over raw user prompt for root task title

## Testing Phase

- [x] Run targeted unit/integration tests — expect GREEN <!-- id: 7 -->
- [x] Run Ruff on changed TinyCUA files <!-- id: 8 -->
- [x] Run broad targeted deterministic suite <!-- id: 9 -->

## Verification Phase

- [x] Run live notebook contract when deterministic tests pass <!-- id: 10 -->

---

*Task IDs enable tracking and cross-referencing*
*Last updated: 2026-06-16*
