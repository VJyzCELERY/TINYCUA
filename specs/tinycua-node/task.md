# Tasks: TinyCUA Node Base, DecisionNode, and ProcessNode

Implementation tasks for TinyCUA Node Base, DecisionNode, and ProcessNode. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 0 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 1 -->

## Implementation Phase

- [ ] Implement `Node` base class with core fields (`node_id`, `session`, `parent`, `config`, `is_terminal`) <!-- id: 2 -->
  - [ ] Define `Node` abstract base class with required fields
  - [ ] Implement `__init__` method with proper initialization
  - [ ] Add type hints and docstrings

- [ ] Implement `ensure_session()` method <!-- id: 3 -->
  - [ ] Create session from root session if none exists
  - [ ] Adopt parent node's session if parent exists
  - [ ] Raise `ValueError` if no session available
  - [ ] Add proper error handling and validation

- [ ] Implement `build_instruction()` method <!-- id: 4 -->
  - [ ] Merge hardcoded instruction with configurable append
  - [ ] Add dynamic context support
  - [ ] Return complete instruction string

- [ ] Implement `build_messages()` method <!-- id: 5 -->
  - [ ] Integrate with `SystemPromptBuilder` for system message
  - [ ] Add session context based on `NodeMessagePolicy`
  - [ ] Build continuation messages from input
  - [ ] Return complete message list

- [ ] Implement `NodeInputLike` dispatch <!-- id: 6 -->
  - [ ] Create dispatch table for input types
  - [ ] Implement `_handle_string()` for external/internal strings
  - [ ] Implement `_handle_node_input()` for `NodeInput`
  - [ ] Implement `_handle_node_payload()` for `NodePayload`
  - [ ] Implement `_handle_message_list()` for `list[dict]`

- [ ] Implement `validate_output()` method <!-- id: 7 -->
  - [ ] Check `required_tool_calls` from `NodeRetryPolicy`
  - [ ] Validate against `required_output_schema`
  - [ ] Return `ValidationResult` with errors

- [ ] Implement `build_retry_continuation()` method <!-- id: 8 -->
  - [ ] Create assistant-role retry message
  - [ ] Include error details and attempt count
  - [ ] Use configurable retry append if provided

- [ ] Implement lifecycle hooks <!-- id: 9 -->
  - [ ] Implement `record_output(response)` method
  - [ ] Implement `propagate()` method
  - [ ] Implement `on_complete(queue, response)` method

- [ ] Implement `ProcessNode` class <!-- id: 10 -->
  - [ ] Inherit from `Node`
  - [ ] Implement `__call__` method with orchestration
  - [ ] Add retry loop with validation
  - [ ] Integrate lifecycle hooks

- [ ] Implement `DecisionNode` class <!-- id: 11 -->
  - [ ] Inherit from `ProcessNode`
  - [ ] Implement `_analysis_call()` method
  - [ ] Implement `_classification_call()` method
  - [ ] Implement `_dispatch_route()` method
  - [ ] Override `__call__` for two-step flow

- [ ] Update package exports <!-- id: 12 -->
  - [ ] Export new classes from `tinycua/loops/__init__.py`
  - [ ] Ensure proper imports in `tinycua/config/node_config.py`
  - [ ] Verify `tinycua/models/__init__.py` exports

## Testing Phase

- [ ] Run integration tests — expect GREEN (all pass) <!-- id: 13 -->
- [ ] Write unit tests for node base class <!-- id: 14 -->
  - [ ] Test `Node` instantiation and fields
  - [ ] Test `ensure_session()` with various scenarios
  - [ ] Test `build_instruction()` merging logic

- [ ] Write unit tests for process node <!-- id: 15 -->
  - [ ] Test `ProcessNode.__call__` orchestration
  - [ ] Test retry loop behavior
  - [ ] Test error handling and validation

- [ ] Write unit tests for decision node <!-- id: 16 -->
  - [ ] Test `DecisionNode.__call__` two-step flow
  - [ ] Test classification and route dispatch
  - [ ] Test error handling in classification

- [ ] Write unit tests for input dispatch <!-- id: 17 -->
  - [ ] Test each input type handler
  - [ ] Test edge cases (empty strings, invalid types)
  - [ ] Test dispatch table coverage

- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 18 -->

## Verification Phase

- [ ] Verify node can be instantiated and called <!-- id: 19 -->
- [ ] Verify session attachment works with root session <!-- id: 20 -->
- [ ] Verify session attachment works with parent node <!-- id: 21 -->
- [ ] Verify message building includes session context <!-- id: 22 -->
- [ ] Verify retry behavior on validation failure <!-- id: 23 -->
- [ ] Verify lifecycle hooks are called at appropriate points <!-- id: 24 -->

## Documentation Phase

- [ ] Update module docstrings <!-- id: 25 -->
- [ ] Add inline comments for complex logic <!-- id: 26 -->
- [ ] Update README if needed <!-- id: 27 -->

## Review and Merge

- [ ] Create pull request <!-- id: 28 -->
- [ ] Address review feedback <!-- id: 29 -->
- [ ] Merge to main branch <!-- id: 30 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*