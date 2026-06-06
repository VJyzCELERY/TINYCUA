# Design Document: SessionConfig, Node Config, and Local Model Config (Milestone 1.2)

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-06

---

## Overview

This design implements the configuration layer for TinyCUA sessions and nodes. It introduces `NodeConfigBase` and its policy dataclasses (`NodeMessagePolicy`, `NodeToolPolicy`, `NodeStreamPolicy`, `NodeRetryPolicy`), system prompt building (`SystemPrompt`, `SystemPromptBuilder`), todo list (`Todo`, `TodoItem`), and local model endpoint configuration (`LocalModelConfig`). These components are consumed by nodes in later milestones to control their behavior, tool scope, retry logic, streaming, and LLM endpoint selection. No SDK public API modifications are required.

---

## Architecture

### Component Overview

```
SessionConfig (existing, extended)
  └── used by Session

NodeConfigBase (new)
  ├── NodeMessagePolicy
  ├── NodeToolPolicy
  ├── NodeStreamPolicy
  ├── NodeRetryPolicy
  └── PropagationRule (placeholder)

SystemPrompt / SystemPromptBuilder (new)
  └── used by Node to build system-role messages

Todo / TodoItem (new)
  └── used by Node session for plan-then-execute

LocalModelConfig (new)
  └── used by Node to configure LLM endpoint
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.config.session_config` | Existing | No changes needed; already matches spec |
| `tinycua.config.node_config` | New | `NodeConfigBase` and policy dataclasses |
| `tinycua.config.system_prompt` | New | `SystemPrompt` and `SystemPromptBuilder` |
| `tinycua.config.local_model` | New | `LocalModelConfig` dataclass |
| `tinycua.models.todo` | New | `Todo` and `TodoItem` |
| `tinycua.config.__init__` | Modified | Re-export new config classes |

---

## Type References

The following types are referenced in the data model. Placeholder stubs exist in `tinycua.config.types` for this milestone; concrete implementations will replace them in later milestones.

| Type | Source | Notes |
|------|--------|-------|
| `Tool` | `tinycua.config.types` | Placeholder stub; will be replaced with SDK `tinycua.agent.tools` |
| `StateObject` | `tinycua.config.types` | Placeholder stub; conceptual design in `tinycua.specs.state_objects` |
| `LLMResult` | `tinycua.config.types` | Placeholder stub; will be defined in loop milestone |
| `ValidationResult` | `tinycua.config.types` | Placeholder stub; will be defined in loop milestone |
| `ValidationError` | `tinycua.config.types` | Placeholder stub; will be defined in loop milestone |
| `PropagationRule` | `tinycua.loops.propagation` | Will be defined in propagation milestone |

---

## Data Model

### New Entities

```python
# Conceptual data shapes — final classes defined in implementation

NodeMessagePolicy:
    include_chat_history: bool = False
    include_session_context: bool = True
    max_context_messages: int | None = None
    dedupe_by_origin_record_id: bool = True
    continuation_role: str = "assistant"  # Internal node handoffs are assistant-role messages

NodeToolPolicy:
    node_tools: list[Tool] = []
    include_agent_tools: Literal["none", "selected", "all"] = "none"
    allowed_agent_tool_names: list[str] = []
    denied_agent_tool_names: list[str] = []

NodeStreamPolicy:
    visible_to_user: bool = True
    emit_internal_events: bool = True
    include_node_metadata: bool = True
    final_response_only: bool = False

NodeRetryPolicy:
    max_attempts: int = 3
    required_tool_calls: list[str] = []
    required_output_schema: dict | type[StateObject] | None = None
    validation_fn: Callable[[LLMResult], ValidationResult] | None = None
    retry_continuation_builder: Callable[[ValidationError, int], str] | None = None
    on_retry_exhausted: Literal["raise", "record_failure", "route_failure"] = "record_failure"

NodeConfigBase:
    custom_instruction_append: str | None = None
    custom_continuation_append: str | None = None
    custom_retry_append: str | None = None
    propagation: PropagationRule = None  # placeholder
    tool_policy: NodeToolPolicy = NodeToolPolicy()
    stream_policy: NodeStreamPolicy = NodeStreamPolicy()
    retry_policy: NodeRetryPolicy = NodeRetryPolicy()
    message_policy: NodeMessagePolicy = NodeMessagePolicy()
    metadata: dict = {}

SystemPrompt:
    priority: int
    kind: Literal["static", "configurable", "dynamic"]
    content: str
    metadata: dict = {}

SystemPromptBuilder:
    fragments: list[SystemPrompt]
    add_static(content: str) -> None
    add_configurable_append(content: str) -> None
    add_dynamic_context(content: str) -> None
    build() -> dict  # {"role": "system", "content": str}

Todo:
    items: list[TodoItem]          # maintained in insertion order
    max_items: int = 20
    append(description: str) -> None   # auto-assigns order = len(items) before append
    mark_done(index: int) -> None      # raises IndexError if invalid
    next_pending() -> TodoItem | None  # returns first item with status="pending"

TodoItem:
    description: str
    status: Literal["pending", "done"]
    order: int                    # auto-assigned on append(); insertion order index (0-based)
    metadata: dict = {}

LocalModelConfig:
    base_url: str  # e.g., "http://localhost:11434/v1"
    model: str  # e.g., "llama3"
    api_key: str | None = None
    timeout: float = 30.0
    temperature: float = 0.7
    max_tokens: int | None = None
```

### Schema Changes

- None. This milestone creates new modules; no existing schemas are modified.

---

## API / Interface Contracts

### NodeConfigBase

```python
@dataclass
class NodeConfigBase:
    """
    Base configuration for all TinyCUA nodes.

    Provides append-only customization fields and policy objects.
    """

    custom_instruction_append: str | None = None
    custom_continuation_append: str | None = None
    custom_retry_append: str | None = None
    propagation: Any = None  # PropagationRule placeholder
    tool_policy: NodeToolPolicy = field(default_factory=NodeToolPolicy)
    stream_policy: NodeStreamPolicy = field(default_factory=NodeStreamPolicy)
    retry_policy: NodeRetryPolicy = field(default_factory=NodeRetryPolicy)
    message_policy: NodeMessagePolicy = field(default_factory=NodeMessagePolicy)
    metadata: dict[str, Any] = field(default_factory=dict)
```

### NodeToolPolicy Resolution

```python
def resolve_tools(
    self,
    outer_agent_tools: list[Tool] | None = None,
) -> list[Tool]:
    """
    Resolve allowed tools according to policy.

    Resolution order:
    1. Start with node_tools.
    2. If include_agent_tools="none", include no outer tools.
    3. If "selected", include outer tools whose names are in allowed_agent_tool_names.
    4. If "all", include all outer tools except those in denied_agent_tool_names.
    5. Deny wins over allow when a tool name appears in both lists.
    """
```

### SystemPromptBuilder.build()

```python
def build(self) -> dict[str, str]:
    """
    Build a single system-role message from fragments.

    Fragments are ordered by explicit priority, then merged into one string.
    Returns: {"role": "system", "content": merged_content}
    """
```

### Todo

```python
class Todo:
    def append(self, description: str) -> None:
        """Add a new pending item at the end. Auto-assigns order = len(items) before append.
        Raises ValueError if max_items exceeded."""

    def mark_done(self, index: int) -> None:
        """Mark item at index as done. Raises IndexError if invalid."""

    def next_pending(self) -> TodoItem | None:
        """Return next pending item or None."""
```

### LocalModelConfig

```python
@dataclass
class LocalModelConfig:
    """
    Configuration for local model endpoint.

    Used by nodes to configure LLM client for their calls.
    """
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 30.0
    temperature: float = 0.7
    max_tokens: int | None = None
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| `Todo.append()` when `max_items` exceeded | `ValueError("Todo max items exceeded")` | |
| `Todo.mark_done()` invalid index | `IndexError("Invalid todo index")` | |
| `NodeToolPolicy` unknown `include_agent_tools` | `ValueError("Invalid include_agent_tools value")` | |
| `NodeRetryPolicy.max_attempts` < 0 | `ValueError("max_attempts must be >= 0")` | 0 means no retries, immediate exhaustion |
| `LocalModelConfig.base_url` unreachable | `ConnectionError` at runtime | Not validated at construction |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] Create `tinycua/config/node_config.py` with `NodeConfigBase`, `NodeMessagePolicy`, `NodeToolPolicy`, `NodeStreamPolicy`, `NodeRetryPolicy`
- [ ] Create `tinycua/config/system_prompt.py` with `SystemPrompt`, `SystemPromptBuilder`
- [ ] Create `tinycua/config/local_model.py` with `LocalModelConfig`
- [ ] Create `tinycua/models/todo.py` with `Todo`, `TodoItem`
- [ ] Update `tinycua/config/__init__.py` to re-export new classes
- [ ] Write unit tests for all new config classes
- [ ] Write unit tests for Todo and TodoItem
- [ ] Write unit tests for SystemPromptBuilder

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Add per-node config subclasses (e.g., `TinyCUAQueryAnalystNodeConfig`) — deferred to node milestones
- [ ] Add `PropagationRule` concrete type — deferred to propagation milestone

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Use `Any` placeholder for `PropagationRule` in `NodeConfigBase`.
   - **Reason**: `PropagationRule` is defined in `loops/propagation.md` and will be implemented in a later milestone. Using `Any` avoids circular imports and keeps this milestone focused on config.
   - **Alternatives Considered**: Define a stub `PropagationRule` class — rejected because it would need to be replaced later.

2. **Decision**: `NodeToolPolicy.include_agent_tools` uses string literals instead of enum.
   - **Reason**: Simpler; no enum import needed; matches design doc representation.
   - **Alternatives Considered**: Python Enum — rejected because it adds complexity without benefit for three values.

3. **Decision**: `Todo` uses list index for `mark_done()` instead of item ID.
   - **Reason**: Simpler for flat list; no ID generation needed; matches design doc contract.
   - **Alternatives Considered**: Use item IDs — rejected because it adds complexity for a simple linear list.

4. **Decision**: `SystemPromptBuilder.build()` returns a dict, not a message object.
   - **Reason**: Matches the expected LLM message format; nodes can directly use it in message lists.
   - **Alternatives Considered**: Return a `SystemPrompt` object — rejected because nodes need a dict for LLM calls.

5. **Decision**: `LocalModelConfig` is separate from SDK Agent config.
   - **Reason**: Nodes may override the endpoint; SDK Agent config is outer-level. Keeping separate allows per-node endpoint configuration.
   - **Alternatives Considered**: Map to SDK Agent's `llm_model` — rejected because it conflates levels.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `PropagationRule` placeholder causes type errors later | Low | Low | Use `Any`; replace in later milestone |
| `NodeToolPolicy` resolution order misunderstood | Medium | Medium | Clear docstrings and unit tests covering precedence |
| `Todo` max_items limit too restrictive | Low | Low | Default 20 is generous; configurable per session |
| `LocalModelConfig` fields insufficient for some providers | Medium | Low | Use `**kwargs` for extra fields in future |
| `SystemPromptBuilder` priority ordering edge cases | Low | Medium | Test with duplicate priorities; document stable sort |

---

## Open Questions _(optional)_

1. **PropagationRule type**: Should we define a placeholder protocol or just `Any`?
   - **Status**: Decided
   - **Decision**: Use `Any`; concrete implementation in propagation milestone.

2. **NodeToolPolicy.tool_tools type**: Should `node_tools` be `list[Tool]` or `list[dict]`?
   - **Status**: Decided
   - **Decision**: Use `list[Tool]` where `Tool` is the SDK Tool type; nodes will resolve actual tool objects.

---

## References

- Spec: `./spec.md`
- Design: `src/tinycua/docs/design/config/node_config.md`
- Design: `src/tinycua/docs/design/config/session_config.md`
- Design: `src/tinycua/docs/design/models/todo.md`
- Design: `src/tinycua/docs/design/loops/node.md`
- Issue: https://github.com/VJyzCELERY/TINYCUA/issues/87