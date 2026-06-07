# Tasks: TinyCUALoop SDK Integration (Milestone 1.8)

Implementation tasks for TinyCUALoop SDK Integration (Milestone 1.8). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Create `tinycua/loops/tinycua_loop.py` with TinyCUALoop extending SDK BaseLoop <!-- id: 2 -->
  - [ ] Implement `__init__` with `root_session` and `node_queue`
  - [ ] Implement `run()` method with stream=False support
  - [ ] Implement `run()` method with stream=True support
  - [ ] Add unit tests for TinyCUALoop construction and run() behavior
- [ ] Create root session with input_context, chat_history, session_context <!-- id: 3 -->
  - [ ] Implement session creation when `session=None`
  - [ ] Implement `input_context` field for merged SDK messages
  - [ ] Add unit tests for Session fields
- [ ] Implement message merging into root session <!-- id: 4 -->
  - [ ] Merge SDK messages into `root_session.input_context` at run() start
  - [ ] Add unit tests for message merging behavior
- [ ] Implement queue bootstrapping with terminal node guarantee <!-- id: 5 -->
  - [ ] Ensure `NodeQueue` contains a terminal `ResponseNode` at queue end
  - [ ] Implement stub `ProcessNode` as placeholder entry node (replaced by QueryAnalyst in Milestone 2.1)
  - [ ] Add unit tests for queue bootstrapping
- [ ] Add node execution loop with agent._call_llm() integration <!-- id: 6 -->
  - [ ] Iterate through `NodeQueue`, calling `agent._call_llm()` per node
  - [ ] Record chat history per node LLM call
  - [ ] Record selected session context
  - [ ] Add unit tests for node execution loop
- [ ] Ensure stream=True returns async iterator of SDK-compatible event dicts <!-- id: 7 -->
  - [ ] Implement async iterator yield of SDK event dicts
  - [ ] Add unit tests for stream=True behavior
- [ ] Ensure QueryAnalyst is at queue front (or equivalent entry node) <!-- id: 8 -->
  - [ ] Stub entry node placed at queue front when QueryAnalyst not yet implemented
  - [ ] Add unit tests for entry node placement

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 9 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 10 -->
- [ ] Run linter: `cd src/tinycua && uv run ruff check .` <!-- id: 11 -->
- [ ] Run type checker: `cd src/tinycua && uv run mypy tinycua/` <!-- id: 12 -->

## Verification Phase

- [ ] Verify `Agent(loop=TinyCUALoop(...)).run(query)` executes without SDK API changes <!-- id: 13 -->
- [ ] Verify minimal queue with stub node and terminal ResponseNode completes <!-- id: 14 -->
- [ ] Verify stream=False returns final string <!-- id: 15 -->
- [ ] Verify stream=True returns async iterator <!-- id: 16 -->

## Documentation Phase

- [ ] Update `src/tinycua/README.md` with TinyCUALoop usage example <!-- id: 17 -->

## Review and Merge

- [ ] Create pull request <!-- id: 18 -->
- [ ] Address review feedback <!-- id: 19 -->
- [ ] Merge to main branch <!-- id: 20 -->

## Requirement Coverage

| FR | Description | Task(s) | Status |
|----|-------------|---------|--------|
| FR-001 | TinyCUALoop extends BaseLoop | #2 | TODO |
| FR-002 | TinyCUALoop implements run() | #2 | TODO |
| FR-003 | TinyCUALoop creates and owns root session | #3 | TODO |
| FR-004 | TinyCUALoop owns NodeQueue | #2 | TODO |
| FR-005 | TinyCUALoop merges SDK messages into root session | #4 | TODO |
| FR-006 | TinyCUALoop calls agent._call_llm() | #6 | TODO |
| FR-007 | TinyCUALoop records chat history | #6 | TODO |
| FR-008 | TinyCUALoop preserves stream=False behavior | #7 | TODO |
| FR-009 | TinyCUALoop preserves stream=True behavior | #7 | TODO |
| FR-010 | TinyCUALoop ensures terminal ResponseNode | #5 | TODO |
| FR-011 | TinyCUALoop ensures QueryAnalyst at queue front | #8 | TODO |

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
