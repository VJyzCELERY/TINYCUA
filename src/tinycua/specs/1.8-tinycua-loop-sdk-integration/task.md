# Tasks: TinyCUALoop SDK Integration

Implementation tasks for TinyCUALoop SDK Integration (Milestone 1.8). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for node-based execution (defined in implementation-plan.md) <!-- id: 0 -->
  - Verify: `cd src/tinycua && uv run pytest tests/integration/test_tinycua_loop_integration.py --collect-only`
- [ ] Write unit tests for _execute_node(), message merging, tool scoping <!-- id: 1 -->
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_tinycua_loop.py --collect-only`
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->
  - Verify: `cd src/tinycua && uv run pytest tests/integration/test_tinycua_loop_integration.py` (expect failures)

## Implementation Phase

<!-- Design-to-task mapping (design Phase 1 items → task IDs):
  #1 Create TinyCUALoop class → #6 (node-based execution in run())
  #2 run() stream=False → #6 (run() with node queue iteration)
  #3 run() stream=True → #9
  #4 Create root session → #3 (input_context), #5 (message merging)
  #5 Message merging → #5
  #6 Queue bootstrapping with terminal node → #4 (ResponseNode), #10 (factory wiring)
  #7 Node execution loop with _call_llm() → #6
  #8 Record chat history → #6 (subtask)
  #9 Record session context → #6 (subtask)
  Note: #7 (tool scoping) and #8 (override_instructions) are implicit in design item #7.
-->

- [ ] Add `input_context` field to Session model <!-- id: 3 | design: "Create root session with input_context, chat_history, session_context" -->
  - [ ] Add `input_context: list[dict[str, Any]] = field(default_factory=list)` to Session dataclass
  - [ ] Update Session docstring to document the new field
  - [ ] Add unit test for Session.input_context initialization
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_session.py -k input_context`
- [ ] Create ResponseNode terminal node <!-- id: 4 | design: "Implement queue bootstrapping with terminal node guarantee" -->
  - [ ] Create `src/tinycua/tinycua/loops/response_node.py` with ResponseNode class
  - [ ] ResponseNode extends ProcessNode with `is_terminal=True`
  - [ ] ResponseNode captures final response content from LLM output
  - [ ] Export ResponseNode from `tinycua.loops.__init__`
  - [ ] Write unit tests for ResponseNode
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_response_node.py`
- [ ] Implement message merging in TinyCUALoop <!-- id: 5 | design: "Implement message merging into root session" -->
  - [ ] In run(), merge SDK messages into root_session.input_context
  - [ ] Ensure user messages are recorded before node execution
  - [ ] Write unit test verifying input_context is populated after run()
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_tinycua_loop.py -k input_context`
- [ ] Implement node-based execution in TinyCUALoop.run() <!-- id: 6 | design: "Create TinyCUALoop class extending BaseLoop", "Implement run() stream=False", "Add node execution loop with agent._call_llm() integration", "Record chat history per node LLM call", "Record selected session context" -->
  - [ ] Replace direct agent._call_llm() passthrough with node queue iteration
  - [ ] Implement _execute_node() method for single node execution
  - [ ] Call agent._call_llm() for each node's LLM interaction
  - [ ] Record chat_history per node LLM call
  - [ ] Record session_context via node.record_output()
  - [ ] Handle queue advancement after each node completes
  - [ ] Handle terminal node detection (stop when is_terminal=True)
  - [ ] Write unit tests for node execution flow
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_tinycua_loop.py -k execute_node`
- [ ] Implement tool scoping via NodeToolPolicy <!-- id: 7 | design: implicit in "Add node execution loop with agent._call_llm() integration" -->
  - [ ] In _execute_node(), use node.config.tool_policy.resolve_tools(outer_tools)
  - [ ] Pass resolved tools to agent._call_llm() for each node
  - [ ] Write unit test verifying tool filtering per node
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_tinycua_loop.py -k tool`
- [ ] Implement override_instructions passthrough <!-- id: 8 | design: implicit in "Add node execution loop with agent._call_llm() integration" -->
  - [ ] Pass override_instructions to node.build_instruction() during message building
  - [ ] Write unit test verifying override_instructions reaches nodes
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_tinycua_loop.py -k override`
- [ ] Implement stream=True support <!-- id: 9 | design: "Implement run() method with stream=True support" -->
  - [ ] Yield async iterator of SDK-compatible event dicts
  - [ ] Accumulate content deltas for final response
  - [ ] Write unit tests for streaming behavior
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_tinycua_loop.py -k stream`
- [ ] Wire ResponseNode in factory <!-- id: 10 | design: "Implement queue bootstrapping with terminal node guarantee" -->
  - [ ] Import ResponseNode in factory.py
  - [ ] Pass ResponseNode as default_terminal_node to TinyCUALoop
  - [ ] Update factory tests to verify terminal node wiring
  - Verify: `cd src/tinycua && uv run pytest tests/unit/test_factory.py`

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 11 -->
- [ ] Run unit tests for all modified/new modules <!-- id: 12 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 13 -->
- [ ] Verify no regressions in existing tests <!-- id: 14 -->

## Verification Phase

- [ ] Verify `create_tinycua_agent(...).run(query)` executes with minimal node queue <!-- id: 15 -->
- [ ] Verify chat_history is populated with user + assistant messages <!-- id: 16 -->
- [ ] Verify session_context is populated with node outputs <!-- id: 17 -->
- [ ] Verify input_context contains merged SDK messages <!-- id: 18 -->

## Documentation Phase

- [ ] Update Status Tracker in spec.md to reflect completed items <!-- id: 19 -->
- [ ] Update design.md Phase 1 checkboxes <!-- id: 20 -->

<!-- PR creation, review, and merge are handled by /review-loop and merge workflows — not part of implementation tasks. -->

## Phase 2 — Enhancements (post-MVP)

- [ ] Implement node lifecycle events in streaming mode <!-- id: 24 -->
  - [ ] Yield node.started and node.completed events during streaming
  - [ ] Update spec FR-009 to document node lifecycle events
  - [ ] Write unit tests for node lifecycle event streaming
- [ ] Integrate monitor hooks <!-- id: 25 -->
  - [ ] Add optional monitor hook integration for loop execution observability
  - [ ] Write unit tests for monitor hook callbacks
- [ ] Implement advanced error handling and recovery <!-- id: 26 -->
  - [ ] Add retry policies and recovery strategies beyond basic propagation
  - [ ] Write unit tests for error recovery scenarios

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-08*
