# Tasks: Agent Factory Contract (Milestone 1.1)

Implementation tasks for Agent Factory Contract (Milestone 1.1). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tinycua/config/__init__.py` and `tinycua/config/session_config.py` with `SessionConfig` dataclass <!-- id: 2 -->
  - [ ] Define `compaction_strategy`, `max_context_messages`, `max_context_tokens`, `metadata` fields
  - [ ] Add unit tests for SessionConfig
- [ ] Create `tinycua/models/__init__.py` and `tinycua/models/session.py` with `Session` class <!-- id: 3 -->
  - [ ] Implement `session_id`, `parent_id`, `session_config`, `chat_history`, `session_context`, `agent_state`, `task`, `todo` fields
  - [ ] Implement `compact_context()` stub (returns None for Milestone 1.1)
  - [ ] Add unit tests for Session
- [ ] Create `tinycua/loops/__init__.py` and `tinycua/loops/node_queue.py` with `NodeQueue` placeholder <!-- id: 4 -->
  - [ ] Implement `items`, `current`, `is_empty()`, `input_for_current()`, `advance()` stub
  - [ ] Add unit tests for NodeQueue placeholder
- [ ] Create `tinycua/loops/tinycua_loop.py` with `TinyCUALoop` extending SDK `BaseLoop` <!-- id: 5 -->
  - [ ] Implement `__init__` with `root_session`, `queue`, `session_config`
  - [ ] Implement `run()` with empty queue guard (returns empty string)
  - [ ] Add unit tests for TinyCUALoop construction
- [ ] Create `tinycua/factory.py` with `create_tinycua_agent()` function <!-- id: 6 -->
  - [ ] Implement session creation when `session=None`
  - [ ] Implement SessionConfig application
  - [ ] Implement `**agent_kwargs` pass-through to SDK Agent
  - [ ] Add unit tests for factory function

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 7 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 8 -->
- [ ] Run linter: `cd src/tinycua && uv run ruff check .` <!-- id: 9 -->
- [ ] Run type checker: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 10 -->

## Verification Phase

- [ ] Verify `create_tinycua_agent()` returns Agent with TinyCUALoop <!-- id: 11 -->
- [ ] Verify SessionConfig is applied to session <!-- id: 12 -->
- [ ] Verify `agent.run("hello")` executes without SDK changes <!-- id: 13 -->

## Documentation Phase

- [ ] Update `src/tinycua/README.md` with factory usage example <!-- id: 14 -->

## Review and Merge

- [ ] Create pull request <!-- id: 15 -->
- [ ] Address review feedback <!-- id: 16 -->
- [ ] Merge to main branch <!-- id: 17 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-05*
