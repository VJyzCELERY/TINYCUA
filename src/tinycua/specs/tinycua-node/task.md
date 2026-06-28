# Tasks: TinyCUA Node Base, DecisionNode, and ProcessNode

Implementation tasks for TinyCUA Node Base, DecisionNode, and ProcessNode. Check off items as completed.

## TDD Phase (Tests First)

- [x] Verify ALL dependency types are importable: `NodeConfigBase`, `NodeMessagePolicy`, `NodeRetryPolicy`, `Session`, `NodeInput`, `NodePayload`, `NodeInputLike` — if `NodeInput`/`NodePayload`/`NodeInputLike` fail, create them first per ISSUE-013 <!-- id: 0 -->
- [x] Write mock LLM classes and test helper stubs (MinimalProcessNode, MinimalDecisionNode, MockLLM, RetryTestProcessNode, LifecycleTestProcessNode) <!-- id: 1 -->
- [x] Write integration tests (defined in implementation-plan.md) <!-- id: 2 -->
- [x] Run integration tests — expect RED (failures) since no implementation yet <!-- id: 3 -->
- [x] Write unit tests for node base class <!-- id: 4 -->
- [x] Write unit tests for process node <!-- id: 5 -->
- [x] Write unit tests for decision node <!-- id: 6 -->
- [x] Write unit tests for input dispatch <!-- id: 7 -->
- [x] Run all tests — expect RED (all fail) <!-- id: 8 -->

## Implementation Phase

- [x] Implement `Node` base class with core fields (`node_id`, `session`, `parent`, `config`, `is_terminal`) <!-- id: 9 -->
  - [x] Define `Node` abstract base class with required fields
  - [x] Implement `__init__` method with proper initialization
  - [x] Add type hints and docstrings

- [x] Implement `ensure_session()` method <!-- id: 10 -->
  - [x] Create session from root session if none exists
  - [x] Adopt parent node's session if parent exists
  - [x] Raise `ValueError` if no session available
  - [x] Add proper error handling and validation

- [x] Implement `build_instruction()` method <!-- id: 11 -->
  - [x] Merge hardcoded instruction with configurable append
  - [x] Add dynamic context support
  - [x] Return complete instruction string

- [x] Implement `build_messages()` method <!-- id: 12 -->
  - [x] Integrate with `SystemPromptBuilder` for system message
  - [x] Add session context based on `NodeMessagePolicy`
  - [x] Build continuation messages from input
  - [x] Return complete message list

- [x] Implement `NodeInputLike` dispatch <!-- id: 13 -->
  - [x] Create dispatch table for input types
  - [x] Implement `_handle_string()` for external/internal strings
  - [x] Implement `_handle_node_input()` for `NodeInput`
  - [x] Implement `_handle_node_payload()` for `NodePayload`
  - [x] Implement `_handle_message_list()` for `list[dict]`

- [x] Implement `validate_output()` method <!-- id: 14 -->
  - [x] Check `required_tool_calls` from `NodeRetryPolicy`
  - [x] Validate against `required_output_schema`
  - [x] Return `ValidationResult` with errors

- [x] Implement `build_retry_continuation()` method <!-- id: 15 -->
  - [x] Create assistant-role retry message
  - [x] Include error details and attempt count
  - [x] Use configurable retry append if provided

- [x] Implement lifecycle hooks <!-- id: 16 -->
  - [x] Implement `record_output(response)` method
  - [x] Implement `propagate()` method
  - [x] Implement `on_complete(queue, response)` method

- [x] Implement `ProcessNode` class <!-- id: 17 -->
  - [x] Inherit from `Node`
  - [x] Implement `__call__` method with orchestration
  - [x] Add retry loop with validation
  - [x] Integrate lifecycle hooks

- [x] Implement `DecisionNode` class <!-- id: 18 -->
  - [x] Inherit from `ProcessNode`
  - [x] Implement `_analysis_call()` method
  - [x] Implement `_classification_call()` method
  - [x] Implement `_dispatch_route()` method
  - [x] Override `__call__` for two-step flow

- [x] Add `llm_client` to `NodeConfigBase` <!-- id: 19 -->
  - [x] Add `llm_client: Callable | None = None` field to `NodeConfigBase` dataclass
  - [x] Import `Callable` from `typing` in `node_config.py`
  - [x] Update design.md to document LLM client injection pattern

- [x] Define `LLMResult` with proper fields <!-- id: 20 -->
  - [x] Add `content: str` field to `LLMResult` dataclass
  - [x] Add `role: str` field (default: "assistant")
  - [x] Add `tool_calls: list[dict]` field (default: empty list)
  - [x] Add `metadata: dict[str, str]` field (default: empty dict)
  - [x] Update design.md to document `LLMResult` fields

- [x] Update package exports <!-- id: 21 -->
  - [x] Export new classes from `tinycua/loops/__init__.py`
  - [x] Ensure proper imports in `tinycua/config/node_config.py`
  - [x] Verify `tinycua/models/__init__.py` exports

## Verification Phase

- [x] Run all tests — expect GREEN (all pass) <!-- id: 22 -->
- [x] Verify node can be instantiated and called <!-- id: 23 -->
- [x] Verify session attachment works with root session <!-- id: 24 -->
- [x] Verify session attachment works with parent node <!-- id: 25 -->
- [x] Verify message building includes session context <!-- id: 26 -->
- [x] Verify retry behavior on validation failure <!-- id: 27 -->
- [x] Verify lifecycle hooks are called at appropriate points <!-- id: 28 -->

## Documentation Phase

- [x] Update module docstrings <!-- id: 29 -->
- [x] Add inline comments for complex logic <!-- id: 30 -->
- [x] Update README if needed <!-- id: 31 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-06-07*
