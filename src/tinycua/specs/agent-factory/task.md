# Tasks: Agent Factory Contract (Milestone 1.1)

Implementation tasks for Agent Factory Contract. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for factory contract (see implementation-plan.md success criteria) <!-- id: 0 -->
  - [ ] test_returns_sdk_agent_instance
  - [ ] test_loop_extends_base_loop
  - [ ] test_creates_new_session_when_none
  - [ ] test_uses_provided_session
  - [ ] test_applies_session_config
  - [ ] test_empty_queue_returns_empty_string
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tinycua/config/session_config.py` with SessionConfig dataclass <!-- id: 2 -->
  - [ ] Define `SessionConfig` dataclass with compaction_strategy, max_context_messages, max_context_tokens, metadata
  - [ ] Create `tinycua/config/__init__.py` package init
- [ ] Create `tinycua/models/session.py` with Session class skeleton <!-- id: 3 -->
  - [ ] Define `Session` class with session_id, session_context, chat_history, task, todo, config
  - [ ] Create `tinycua/models/__init__.py` package init
- [ ] Create `tinycua/loops/tinycua_loop.py` with TinyCUALoop extending BaseLoop <!-- id: 4 -->
  - [ ] Import BaseLoop from tinycua_sdk
  - [ ] Implement `__init__` with root_session, session_config, max_iterations, queue placeholder
  - [ ] Implement `run()` method — merge messages into session, handle empty queue, return empty string
  - [ ] Create `tinycua/loops/__init__.py` package init
- [ ] Create `tinycua/factory.py` with `create_tinycua_agent()` function <!-- id: 5 -->
  - [ ] Implement `create_tinycua_agent(session, session_config, **agent_kwargs) -> Agent`
  - [ ] Handle `session=None` → create new Session
  - [ ] Apply session_config if provided
  - [ ] Create TinyCUALoop with session
  - [ ] Return Agent(loop=loop, **agent_kwargs)

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 6 -->
- [ ] Write unit tests for factory function <!-- id: 7 -->
  - [ ] Test default parameters
  - [ ] Test session=None creates new session
  - [ ] Test provided session is used
  - [ ] Test session_config applied
  - [ ] Test agent_kwargs pass-through
- [ ] Write unit tests for TinyCUALoop <!-- id: 8 -->
  - [ ] Test isinstance check against BaseLoop
  - [ ] Test root_session assignment
  - [ ] Test queue initialization
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 9 -->

## Verification Phase

- [ ] Verify `create_tinycua_agent()` returns usable Agent <!-- id: 10 -->
- [ ] Verify `agent.run("hello")` completes without error <!-- id: 11 -->
- [ ] Verify no SDK API modifications were made <!-- id: 12 -->

## Documentation Phase

- [ ] Update `tinycua/__init__.py` to export factory function <!-- id: 13 -->
- [ ] Add module docstrings to new files <!-- id: 14 -->

## Review and Merge

- [ ] Create pull request <!-- id: 15 -->
- [ ] Address review feedback <!-- id: 16 -->
- [ ] Merge to main branch <!-- id: 17 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-05*
