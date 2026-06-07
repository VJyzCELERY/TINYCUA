# Tasks: TinyCUALoop SDK Integration

Implementation tasks for TinyCUALoop SDK Integration (Milestone 1.8). Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests for node-based execution (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Write unit tests for _execute_node(), message merging, tool scoping <!-- id: 1 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 2 -->

## Implementation Phase

- [ ] Add `input_context` field to Session model <!-- id: 3 -->
  - [ ] Add `input_context: list[dict[str, Any]] = field(default_factory=list)` to Session dataclass
  - [ ] Update Session docstring to document the new field
  - [ ] Add unit test for Session.input_context initialization
- [ ] Create ResponseNode terminal node <!-- id: 4 -->
  - [ ] Create `src/tinycua/tinycua/loops/response_node.py` with ResponseNode class
  - [ ] ResponseNode extends ProcessNode with `is_terminal=True`
  - [ ] ResponseNode captures final response content from LLM output
  - [ ] Export ResponseNode from `tinycua.loops.__init__`
  - [ ] Write unit tests for ResponseNode
- [ ] Implement message merging in TinyCUALoop <!-- id: 5 -->
  - [ ] In run(), merge SDK messages into root_session.input_context
  - [ ] Ensure user messages are recorded before node execution
  - [ ] Write unit test verifying input_context is populated after run()
- [ ] Implement node-based execution in TinyCUALoop.run() <!-- id: 6 -->
  - [ ] Replace direct agent._call_llm() passthrough with node queue iteration
  - [ ] Implement _execute_node() method for single node execution
  - [ ] Call agent._call_llm() for each node's LLM interaction
  - [ ] Record chat_history per node LLM call
  - [ ] Record session_context via node.record_output()
  - [ ] Handle queue advancement after each node completes
  - [ ] Handle terminal node detection (stop when is_terminal=True)
  - [ ] Write unit tests for node execution flow
- [ ] Implement tool scoping via NodeToolPolicy <!-- id: 7 -->
  - [ ] In _execute_node(), use node.config.tool_policy.resolve_tools(outer_tools)
  - [ ] Pass resolved tools to agent._call_llm() for each node
  - [ ] Write unit test verifying tool filtering per node
- [ ] Implement override_instructions passthrough <!-- id: 8 -->
  - [ ] Pass override_instructions to node.build_instruction() during message building
  - [ ] Write unit test verifying override_instructions reaches nodes
- [ ] Implement stream=True support <!-- id: 9 -->
  - [ ] Yield async iterator of SDK-compatible event dicts
  - [ ] Accumulate content deltas for final response
  - [ ] Write unit tests for streaming behavior
- [ ] Wire ResponseNode in factory <!-- id: 10 -->
  - [ ] Import ResponseNode in factory.py
  - [ ] Pass ResponseNode as default_terminal_node to TinyCUALoop
  - [ ] Update factory tests to verify terminal node wiring

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
