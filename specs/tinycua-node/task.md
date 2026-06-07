# Tasks: TinyCUA Node Base, DecisionNode, and ProcessNode

Implementation tasks for TinyCUA Node Base, DecisionNode, and ProcessNode. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Verify ALL dependency types are importable: `NodeConfigBase`, `NodeMessagePolicy`, `NodeRetryPolicy`, `Session`, `NodeInput`, `NodePayload`, `NodeInputLike` — if `NodeInput`/`NodePayload`/`NodeInputLike` fail, create them first per ISSUE-013 <!-- id: 0 -->
- [ ] Write mock LLM classes and test helper stubs (MinimalProcessNode, MinimalDecisionNode, MockLLM, RetryTestProcessNode, LifecycleTestProcessNode) <!-- id: 1 -->
- [ ] Write integration tests (defined in implementation-plan.md) <!-- id: 2 -->
- [ ] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 3 -->
- [ ] Write unit tests for node base class <!-- id: 4 -->
- [ ] Write unit tests for process node <!-- id: 5 -->
- [ ] Write unit tests for decision node <!-- id: 6 -->
- [ ] Write unit tests for input dispatch <!-- id: 7 -->
- [ ] Run all tests — expect RED (all fail) <!-- id: 8 -->

## Implementation Phase

- [ ] Implement `Node` base class with core fields (`node_id`, `session`, `parent`, `config`, `is_terminal`) <!-- id: 9 -->
  - [ ] Define `Node` abstract base class with required fields
  - [ ] Implement `__init__` method with proper initialization
  - [ ] Add type hints and docstrings

- [ ] Implement `ensure_session()` method <!-- id: 10 -->
  - [ ] Create session from root session if none exists
  - [ ] Adopt parent node's session if parent exists
  - [ ] Raise `ValueError` if no session available
  - [ ] Add proper error handling and validation

- [ ] Implement `build_instruction()` method <!-- id: 11 -->
  - [ ] Merge hardcoded instruction with configurable append
  - [ ] Add dynamic context support
  - [ ] Return complete instruction string

- [ ] Implement `build_messages()` method <!-- id: 12 -->
  - [ ] Integrate with `SystemPromptBuilder` for system message
  - [ ] Add session context based on `NodeMessagePolicy`
  - [ ] Build continuation messages from input
  - [ ] Return complete message list

- [ ] Implement `NodeInputLike` dispatch <!-- id: 13 -->
  - [ ] Create dispatch table for input types
  - [ ] Implement `_handle_string()` for external/internal strings
  - [ ] Implement `_handle_node_input()` for `NodeInput`
  - [ ] Implement `_handle_node_payload()` for `NodePayload`
  - [ ] Implement `_handle_message_list()` for `list[dict]`

- [ ] Implement `validate_output()` method <!-- id: 14 -->
  - [ ] Check `required_tool_calls` from `NodeRetryPolicy`
  - [ ] Validate against `required_output_schema`
  - [ ] Return `ValidationResult` with errors

- [ ] Implement `build_retry_continuation()` method <!-- id: 15 -->
  - [ ] Create assistant-role retry message
  - [ ] Include error details and attempt count
  - [ ] Use configurable retry append if provided

- [ ] Implement lifecycle hooks <!-- id: 16 -->
  - [ ] Implement `record_output(response)` method
  - [ ] Implement `propagate()` method
  - [ ] Implement `on_complete(queue, response)` method

- [ ] Implement `ProcessNode` class <!-- id: 17 -->
  - [ ] Inherit from `Node`
  - [ ] Implement `__call__` method with orchestration
  - [ ] Add retry loop with validation
  - [ ] Integrate lifecycle hooks

- [ ] Implement `DecisionNode` class <!-- id: 18 -->
  - [ ] Inherit from `ProcessNode`
  - [ ] Implement `_analysis_call()` method
  - [ ] Implement `_classification_call()` method
  - [ ] Implement `_dispatch_route()` method
  - [ ] Override `__call__` for two-step flow

- [ ] Update package exports <!-- id: 19 -->
  - [ ] Export new classes from `tinycua/loops/__init__.py`
  - [ ] Ensure proper imports in `tinycua/config/node_config.py`
  - [ ] Verify `tinycua/models/__init__.py` exports

## Verification Phase

- [ ] Run all tests — expect GREEN (all pass) <!-- id: 20 -->
- [ ] Verify node can be instantiated and called <!-- id: 21 -->
- [ ] Verify session attachment works with root session <!-- id: 22 -->
- [ ] Verify session attachment works with parent node <!-- id: 23 -->
- [ ] Verify message building includes session context <!-- id: 24 -->
- [ ] Verify retry behavior on validation failure <!-- id: 25 -->
- [ ] Verify lifecycle hooks are called at appropriate points <!-- id: 26 -->

## Documentation Phase

- [ ] Update module docstrings <!-- id: 27 -->
- [ ] Add inline comments for complex logic <!-- id: 28 -->
- [ ] Update README if needed <!-- id: 29 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*