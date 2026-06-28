# Feature Specification: TinyCUA Node Base, DecisionNode, and ProcessNode

**Status**: Draft
**Created**: 2026-06-07
**Last Updated**: 2026-06-07
**Subproject(s) Affected**: tinycua (loops/node)

---

## Problem Statement _(mandatory)_

- **Goals**: Provide a base `Node` class and two abstract subclasses — `DecisionNode` and `ProcessNode` — so that **node implementers** can **build concrete TinyCUA nodes without duplicating session, message, retry, and lifecycle logic**.
- **Gaps**: Today there is no node abstraction in `tinycua.loops`. Concrete nodes (QueryAnalyst, Worker, TaskExecutor, etc.) have no shared base to inherit from, no standardized `NodeInputLike` dispatch, and no lifecycle hook interface for validation, retry, or recording.
- **Non-Goals**: This spec does NOT cover concrete TinyCUA nodes (QueryAnalyst, Worker, TaskCreate, etc.), node queue execution, or route map dispatch. Those are implemented in later milestones.
- **Constraints**: Must work without modifying `tinycua-sdk` public APIs. Must accept `NodeInputLike` input (`str | NodeInput | NodePayload | list[dict]`). Must integrate with `NodeConfigBase` and its sub-policies (message, tool, stream, retry).

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer creates a minimal `ProcessNode` subclass, attaches it to a session, and calls it with a `NodeInputLike` value. The node builds its system prompt via `SystemPromptBuilder`, selects session context, invokes the LLM, and returns a response. A `DecisionNode` subclass performs the same flow but additionally classifies the response and dispatches a route.

### Acceptance Scenarios

1. **Given** a `ProcessNode` subclass with a hardcoded instruction, **When** it is instantiated with `NodeConfigBase` and called with `str` input, **Then** it builds a system message from the static instruction and configurable append, converts the input to an assistant-role continuation, and invokes the LLM.
2. **Given** a `DecisionNode` subclass with classification labels, **When** it is called with `NodeInputLike` input, **Then** it performs an analysis call, then a classification tool call, and returns a route label.
3. **Given** a node with `NodeRetryPolicy(max_attempts=3)`, **When** the LLM response fails validation, **Then** the node retries up to 3 times with assistant-role retry continuations.
4. **Given** a node without an attached session, **When** `ensure_session(root_session)` is called, **Then** the node creates or adopts a session from the root or parent session.
5. **Given** a node with `NodeMessagePolicy(include_session_context=True)`, **When** it builds messages, **Then** reusable session context is included in the continuation messages.

### Edge Cases

- What happens when `NodeInputLike` is an empty string? The node must reject or handle empty input gracefully.
- What happens when `ensure_session` is called before the node is attached to a parent? The node must raise a clear error.
- What happens when retry is exhausted? The node must follow `on_retry_exhausted` policy (raise, record_failure, or route_failure).
- What happens when `required_tool_calls` are missing from the response? The node must trigger a retry with a validation error.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide a base `Node` class with `node_id`, `session`, `parent`, `config`, and `is_terminal` fields.
- **FR-002**: System MUST provide `DecisionNode(ProcessNode)` that performs analysis + classification + route dispatch.
- **FR-003**: System MUST provide `ProcessNode(Node)` as the primary node type for non-decision processing.
- **FR-004**: System MUST accept `NodeInputLike = str | NodeInput | NodePayload | list[dict]` and dispatch to the correct internal handler.
- **FR-005**: System MUST build LLM messages via `SystemPromptBuilder` with static, configurable, and dynamic prompt fragments.
- **FR-006**: System MUST provide `ensure_session(root_or_parent_session)` that creates or adopts a session.
- **FR-007**: System MUST provide `build_instruction(override_instructions?)` that merges hardcoded + configurable + dynamic instruction fragments.
- **FR-008**: System MUST provide `build_messages(root_session, input)` that assembles system + conversation + continuation messages.
- **FR-009**: System MUST provide `validate_output(response)` that checks against `required_tool_calls` and `required_output_schema` from `NodeRetryPolicy`.
- **FR-010**: System MUST provide `build_retry_continuation(error)` that produces assistant-role retry messages.
- **FR-011**: System MUST provide `record_output(response)` lifecycle hook for recording node execution results.
- **FR-012**: System MUST provide `propagate()` lifecycle hook for post-execution propagation.
- **FR-013**: System MUST provide `on_complete(queue, response)` lifecycle hook for post-completion queue mutations.
- **FR-014**: System MUST use `NodeConfigBase` for all node configuration including message, tool, stream, and retry policies.
- **FR-015**: System MUST NOT modify `tinycua-sdk` public APIs.

### Key Entities _(include if feature involves data)_

- **Node**: Base class for all TinyCUA nodes. Holds `node_id`, `session`, `parent`, `config`, and lifecycle methods.
- **ProcessNode**: Primary node type for non-decision processing. Inherits from `Node`.
- **DecisionNode**: Node type that performs analysis + classification + route dispatch. Inherits from `ProcessNode`.
- **NodeInput**: Trusted internal transport object carrying structured data between nodes.
- **NodePayload**: Trusted internal transport object carrying structured payloads.
- **NodeInputLike**: Union type (`str | NodeInput | NodePayload | list[dict]`) accepted by all nodes.
- **LLMResult**: Return type from LLM invocations. Defined in `tinycua.config.types`. Contains the assistant's response content and metadata.
- **ValidationResult**: Return type of `validate_output()`. Contains `is_valid: bool` and `errors: list[str]` indicating validation failures.
- **DecisionResult**: Return type of `DecisionNode.__call__()`. Contains `route_label: str`, `analysis_response: LLMResult`, and `classification_response: LLMResult` for observability and downstream debugging.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **Base Node instantiable**: A `Node` subclass can be instantiated with `node_id` and `NodeConfigBase`.
- [ ] **ProcessNode callable**: A minimal `ProcessNode` subclass can be called with `NodeInputLike` and returns a response.
- [ ] **DecisionNode callable**: A minimal `DecisionNode` subclass can be called, classify a response, and return a route label.
- [ ] **Session attachment works**: `ensure_session()` creates or adopts a session from root/parent.
- [ ] **Message building works**: `build_messages()` produces correct system + conversation + continuation message list.
- [ ] **Retry works**: Given `max_attempts=3` and validation failure, node makes exactly 3 LLM calls before raising `NodeExecutionError`.
- [ ] **Lifecycle hooks fire**: `record_output()` called once after LLM response, `propagate()` called once after record, `on_complete()` called once after propagate. All three are called in order.
- [ ] **No SDK API changes**: All implementation lives in `tinycua.loops.node` without modifying `tinycua-sdk`.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `test_node_base.py`: Test `Node` base class instantiation, session attachment, and lifecycle hook dispatch.
- `test_process_node.py`: Test `ProcessNode` with mock LLM — message building, input dispatch, validation, retry.
- `test_decision_node.py`: Test `DecisionNode` with mock LLM — analysis call, classification, route dispatch.
- `test_node_input.py`: Test `NodeInputLike` dispatch for `str`, `NodeInput`, `NodePayload`, and `list[dict]`.
- `test_node_config.py`: Test `NodeConfigBase` integration — message, tool, stream, and retry policy behavior.

### Integration Tests

- Test that `ProcessNode` and `DecisionNode` integrate with `SystemPromptBuilder` to produce correct message lists.
- Test that `ensure_session()` works with both `Session` and parent `Node` session.

### Manual Tests _(if applicable)_

- None required for this milestone.

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| Base Node class | TODO | |
| ProcessNode class | TODO | |
| DecisionNode class | TODO | |
| NodeInputLike dispatch | TODO | |
| SystemPromptBuilder integration | TODO | |
| Session attachment | TODO | |
| Lifecycle hooks | TODO | |
| Unit tests | TODO | |

---

## Open Questions _(optional)_

1. **DecisionNode two-step process**: Should the analysis call and classification call be separate LLM invocations, or combined into one call with tool use?
   - **Status**: Decided — Two separate calls per `docs/design/loops/node.md` design (analysis call → verdict/classification tool call). This aligns with the existing architecture where analysis and classification have distinct system prompts and tool configurations.

2. **DecisionNode return type**: Should `DecisionNode` return a `DecisionResult` dataclass or just the route label string?
   - **Status**: Decided — Return a `DecisionResult` dataclass with `route_label`, `analysis_response`, and `classification_response` for observability and downstream debugging.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices beyond what's in the design docs)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
