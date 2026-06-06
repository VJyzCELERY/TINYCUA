# Feature Specification: SessionConfig, Node Config, and Local Model Config (Milestone 1.2)

**Status**: Draft
**Created**: 2026-06-06
**Last Updated**: 2026-06-06
**Subproject(s) Affected**: tinycua

---

## Problem Statement _(mandatory)_

- **Goals**: Provide the configuration layer for TinyCUA sessions and nodes, enabling nodes to have distinct message, tool, stream, and retry policies, while supporting local model endpoint configuration for LLM calls.
- **Gaps**: Today only a minimal `SessionConfig` exists. Nodes lack per-node configuration, policy dataclasses, system prompt building, and local model endpoint configuration. The architecture design docs define these components but they are not yet implemented.
- **Non-Goals**: Concrete node implementations, compaction strategy implementations, node execution logic, WildClawBench integration.
- **Constraints**: Must not modify `tinycua-sdk` public APIs. Must follow design docs in `src/tinycua/docs/design/`. Configuration must be dataclass-based, immutable after construction where possible, and support append-only customization.

---

## User Scenarios & Testing _(mandatory)_

### Primary Scenario

A developer constructing a TinyCUA node creates a `NodeConfigBase` (or its subclass) with appropriate policies (`NodeMessagePolicy`, `NodeToolPolicy`, `NodeStreamPolicy`, `NodeRetryPolicy`). The node uses `SystemPromptBuilder` to assemble system prompt fragments from hardcoded constants, config appendices, and dynamic context. The node resolves tool scope via `NodeToolPolicy`. The node's session uses `SessionConfig` for context limits and compaction strategy. The node's LLM calls are directed to a local model endpoint configured via `LocalModelConfig`.

### Acceptance Scenarios

1. **Given** a `SessionConfig` with `max_context_messages=50`, **When** a node checks session config, **Then** the limit is respected.
2. **Given** a `NodeConfigBase` with custom `instruction_append` and `continuation_append`, **When** the node builds its system prompt, **Then** the appends are appended to the hardcoded constants.
3. **Given** a `NodeToolPolicy` with `include_agent_tools="selected"` and `allowed_agent_tool_names=["web_search"]`, **When** the node resolves tools, **Then** only `web_search` from outer agent tools is included.
4. **Given** a `NodeRetryPolicy` with `max_attempts=3`, **When** a node fails validation twice, **Then** a third attempt is allowed; on third failure, exhaustion behavior triggers.
5. **Given** a `LocalModelConfig` with `base_url="http://localhost:11434/v1"` and `model="llama3"`, **When** a node makes an LLM call, **Then** the call is directed to that endpoint.
6. **Given** a `Todo` with three items, **When** a node marks the first item done, **Then** `next_pending()` returns the second item.
7. **Given** a `SystemPromptBuilder` with static, configurable, and dynamic fragments, **When** `build()` is called, **Then** a single system-role message is produced with content merged in priority order.

### Edge Cases

- What happens when `NodeToolPolicy` has a tool name in both allow and deny lists? Deny wins.
- What happens when `NodeRetryPolicy.max_attempts` is 0? No retries; immediate exhaustion.
- What happens when `LocalModelConfig.base_url` is unreachable? The node's LLM call raises a connection error (propagated).
- What happens when `Todo.max_items` is exceeded? `append()` raises `ValueError`.
- What happens when `SystemPromptBuilder.build()` has no fragments? Returns empty system message.

---

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST provide `SessionConfig` dataclass with fields: `compaction_strategy`, `max_context_messages`, `max_context_tokens`, `metadata`.
- **FR-002**: System MUST provide `NodeConfigBase` dataclass with fields: `custom_instruction_append`, `custom_continuation_append`, `custom_retry_append`, `propagation`, `tool_policy`, `stream_policy`, `retry_policy`, `message_policy`, `metadata`.
- **FR-003**: System MUST provide `NodeMessagePolicy` dataclass with fields: `include_chat_history`, `include_session_context`, `max_context_messages`, `dedupe_by_origin_record_id`, `continuation_role`.
- **FR-004**: System MUST provide `NodeToolPolicy` dataclass with fields: `node_tools`, `include_agent_tools`, `allowed_agent_tool_names`, `denied_agent_tool_names`.
- **FR-005**: System MUST provide `NodeStreamPolicy` dataclass with fields: `visible_to_user`, `emit_internal_events`, `include_node_metadata`, `final_response_only`.
- **FR-006**: System MUST provide `NodeRetryPolicy` dataclass with fields: `max_attempts`, `required_tool_calls`, `required_output_schema`, `validation_fn`, `retry_continuation_builder`, `on_retry_exhausted`.
- **FR-007**: System MUST provide `SystemPrompt` dataclass with fields: `priority`, `kind`, `content`, `metadata`.
- **FR-008**: System MUST provide `SystemPromptBuilder` class with methods: `add_static()`, `add_configurable_append()`, `add_dynamic_context()`, `build()`.
- **FR-009**: System MUST provide `Todo` class with methods: `append()`, `mark_done()`, `next_pending()`.
- **FR-010**: System MUST provide `TodoItem` dataclass with fields: `description`, `status`, `order`, `metadata`.
- **FR-011**: System MUST provide `LocalModelConfig` dataclass with fields: `base_url`, `model`, `api_key`, `timeout`, `temperature`, `max_tokens`.
- **FR-012**: `NodeConfigBase` MUST support append-only customization: `custom_instruction_append`, `custom_continuation_append`, `custom_retry_append`.
- **FR-013**: `NodeToolPolicy` MUST resolve tools according to resolution order: start with node_tools, apply include_agent_tools rule, deny wins over allow.
- **FR-014**: `NodeRetryPolicy` MUST support exhaustion behaviors: `raise`, `record_failure`, `route_failure`.
- **FR-015**: `Todo` MUST enforce `max_items` limit (default 20) and raise `ValueError` when exceeded.
- **FR-016**: `SystemPromptBuilder.build()` MUST return a single system-role message dict with content merged in priority order.
- **FR-017**: `LocalModelConfig` MUST be usable by nodes to configure LLM endpoint for their calls.

### Key Entities _(include if feature involves data)_

- **SessionConfig**: Session-level configuration — compaction strategy, context limits, metadata.
- **NodeConfigBase**: Base node configuration — append-only customization, policies, propagation rule.
- **NodeMessagePolicy**: Controls message selection and formatting for node LLM calls.
- **NodeToolPolicy**: Controls tool scope resolution for node LLM calls.
- **NodeStreamPolicy**: Controls streaming behavior for node LLM calls.
- **NodeRetryPolicy**: Controls retry behavior, validation, and exhaustion handling.
- **SystemPrompt**: A single prompt fragment with priority and kind.
- **SystemPromptBuilder**: Assembles fragments into one system-role message.
- **Todo**: Per-session linear plan-then-execute list.
- **TodoItem**: Single todo item with status.
- **LocalModelConfig**: Local model endpoint configuration for node LLM calls.

---

## Success Criteria _(mandatory)_ — use `[ ]` checkboxes

- [ ] **SessionConfig exists**: `SessionConfig` dataclass with documented fields and defaults.
- [ ] **NodeConfigBase exists**: `NodeConfigBase` dataclass with all policy fields.
- [ ] **NodeMessagePolicy exists**: `NodeMessagePolicy` dataclass with documented fields.
- [ ] **NodeToolPolicy exists**: `NodeToolPolicy` dataclass with documented fields.
- [ ] **NodeStreamPolicy exists**: `NodeStreamPolicy` dataclass with documented fields.
- [ ] **NodeRetryPolicy exists**: `NodeRetryPolicy` dataclass with documented fields.
- [ ] **SystemPrompt exists**: `SystemPrompt` dataclass with documented fields.
- [ ] **SystemPromptBuilder exists**: `SystemPromptBuilder` class with documented methods.
- [ ] **Todo exists**: `Todo` class with `append`, `mark_done`, `next_pending`.
- [ ] **TodoItem exists**: `TodoItem` dataclass with documented fields.
- [ ] **LocalModelConfig exists**: `LocalModelConfig` dataclass with documented fields.
- [ ] **Append-only customization works**: `NodeConfigBase` appends are concatenated to constants.
- [ ] **Tool policy resolution works**: Deny wins over allow; selection works.
- [ ] **Retry policy exhaustion works**: `max_attempts` respected; exhaustion behavior triggers.
- [ ] **Todo limit enforced**: `append()` raises `ValueError` when `max_items` exceeded.
- [ ] **System prompt builder works**: `build()` returns single system message.
- [ ] **Config tests pass**: Unit tests for all config dataclasses and policies.
- [ ] **Local model config usable**: `LocalModelConfig` can be used by nodes.

---

## Testing Plan _(mandatory)_

### Unit Tests

- `SessionConfig` defaults and custom values.
- `NodeConfigBase` construction with all policies.
- `NodeMessagePolicy` defaults and custom values.
- `NodeToolPolicy` resolution order (allow/deny precedence).
- `NodeStreamPolicy` defaults and custom values.
- `NodeRetryPolicy` defaults, custom values, exhaustion behaviors.
- `SystemPrompt` construction.
- `SystemPromptBuilder` fragment ordering and `build()` output.
- `Todo` append, mark_done, next_pending, max_items limit.
- `TodoItem` construction.
- `LocalModelConfig` construction and defaults.
- Append-only customization concatenation.

### Integration Tests

- `NodeConfigBase` with real policies used in a mock node context.
- `SystemPromptBuilder` used to generate system message for a mock LLM call.
- `LocalModelConfig` passed to a node and used to configure LLM client.

### Manual Tests _(if applicable)_

- Verify `LocalModelConfig` works with a real local model endpoint (e.g., Ollama).

---

## Status Tracker _(optional)_

| Item | Status | Notes |
|------|--------|-------|
| SessionConfig | TODO | Already exists; verify fields match spec |
| NodeConfigBase | TODO | New dataclass |
| NodeMessagePolicy | TODO | New dataclass |
| NodeToolPolicy | TODO | New dataclass |
| NodeStreamPolicy | TODO | New dataclass |
| NodeRetryPolicy | TODO | New dataclass |
| SystemPrompt | TODO | New dataclass |
| SystemPromptBuilder | TODO | New class |
| Todo | TODO | New class |
| TodoItem | TODO | New dataclass |
| LocalModelConfig | TODO | New dataclass |
| Unit tests | TODO | |
| Integration tests | TODO | |

---

## Open Questions _(optional)_

1. **PropagationRule type**: The design doc references `PropagationRule` but it's defined in `loops/propagation.md`. Should we define a placeholder type or import from a future module?
   - **Owner**: TBD
   - **Target**: TBD
   - **Status**: Discussion
   - **Proposed Answer**: Use `Any` placeholder for now; concrete implementation in later milestone.

2. **LocalModelConfig vs SDK Agent config**: Should `LocalModelConfig` be a separate dataclass or map to SDK Agent's `llm_model` parameter?
   - **Owner**: TBD
   - **Target**: TBD
   - **Status**: Discussion
   - **Proposed Answer**: Keep separate; `LocalModelConfig` is node-level, SDK Agent config is outer-level. Nodes may override endpoint.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable