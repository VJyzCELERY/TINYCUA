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
  - [ ] Implement `session_id`, `parent_id`, `config`, `chat_history`, `session_context`, `task`, `todo` fields
  - [ ] Implement `compact_context()` stub (returns None for Milestone 1.1)
  - [ ] Add unit tests for Session
- [ ] Create `tinycua/loops/__init__.py` and `tinycua/loops/node_queue.py` with `NodeQueue` placeholder <!-- id: 4 -->
  - [ ] Implement `items`, `current`, `is_empty()`, `input_for_current()`, `advance()` stub
  - [ ] Add unit tests for NodeQueue placeholder

  NodeQueue placeholder contract for M1.1:
  - `items: list` — empty list (no nodes yet)
  - `current: Node | None` — returns None when empty
  - `is_empty() -> bool` — returns True
  - `input_for_current() -> dict` — returns empty dict
  - `advance() -> None` — no-op
- [ ] Create `tinycua/loops/tinycua_loop.py` with `TinyCUALoop` extending SDK `BaseLoop` <!-- id: 5 -->
  - [ ] Implement `__init__` with `root_session`, `queue`, `session_config`, `max_iterations=50`
  - [ ] Implement `run()` accepting and consuming `messages`, `tools`, `override_instructions`, `stream` parameters (FR-008)
  - [ ] Implement empty queue guard — returns empty string with warning log
  - [ ] Implement chat history recording in root session (FR-010)
  - [ ] Implement stream mode branching — returns string when `stream=False` (FR-011), async iterator when `stream=True`
  - [ ] Add unit tests for TinyCUALoop construction and run() behavior
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

## Requirement Coverage

| FR | Description | Task(s) | Status |
|----|-------------|---------|--------|
| FR-001 | Factory returns `create_tinycua_agent(...)` | #6 | TODO |
| FR-002 | Factory returns SDK Agent with TinyCUALoop | #6 | TODO |
| FR-003 | session=None creates new root Session | #6 | TODO |
| FR-004 | session provided uses provided session | #6 | TODO |
| FR-005 | SessionConfig applied to session | #6 | TODO |
| FR-006 | Local model endpoint config | Deferred | Phase 2 |
| FR-007 | TinyCUALoop extends BaseLoop | #5 | TODO |
| FR-008 | TinyCUALoop.run() consumes SDK messages | #5 | TODO |
| FR-009 | TinyCUALoop.run() calls local LLM | #5 | TODO |
| FR-010 | TinyCUALoop records chat history | #5 | TODO |
| FR-011 | TinyCUALoop preserves stream=False | #5 | TODO |

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-05*
