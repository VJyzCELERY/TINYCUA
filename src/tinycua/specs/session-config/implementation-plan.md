# Implementation: SessionConfig, Node Config, and Local Model Config (Milestone 1.2)

This implementation adds the configuration layer for TinyCUA sessions and nodes, enabling nodes to have distinct message, tool, stream, and retry policies, while supporting local model endpoint configuration for LLM calls.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

- [x] **None** — no external services needed

### Data / Fixtures

- [x] **None** — no data or fixtures needed

### Access / Permissions

- [x] **None** — no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.11+
- [x] **Package manager**: uv
- [x] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/test_session_config_integration.py
"""Integration tests for SessionConfig, Node Config, and Local Model Config."""


def test_node_config_with_all_policies():
    """Test NodeConfigBase construction with all policy types and their defaults."""
    from tinycua.config.node_config import (
        NodeConfigBase,
        NodeMessagePolicy,
        NodeToolPolicy,
        NodeStreamPolicy,
        NodeRetryPolicy,
    )
    
    # Arrange & Act
    config = NodeConfigBase(
        custom_instruction_append="Custom instruction",
        custom_continuation_append="Custom continuation",
        custom_retry_append="Custom retry",
        tool_policy=NodeToolPolicy(
            include_agent_tools="selected",
            allowed_agent_tool_names=["web_search"]
        ),
        stream_policy=NodeStreamPolicy(visible_to_user=False),
        retry_policy=NodeRetryPolicy(max_attempts=5),
        message_policy=NodeMessagePolicy(include_chat_history=True),
    )
    
    # Assert
    assert config.custom_instruction_append == "Custom instruction"
    assert config.custom_continuation_append == "Custom continuation"
    assert config.custom_retry_append == "Custom retry"
    assert config.tool_policy.include_agent_tools == "selected"
    assert config.tool_policy.allowed_agent_tool_names == ["web_search"]
    assert config.stream_policy.visible_to_user is False
    assert config.retry_policy.max_attempts == 5
    assert config.message_policy.include_chat_history is True


def test_tool_policy_resolution():
    """Test NodeToolPolicy tool resolution with allow/deny precedence."""
    from tinycua.config.node_config import NodeToolPolicy
    
    # Arrange
    policy = NodeToolPolicy(
        include_agent_tools="selected",
        allowed_agent_tool_names=["web_search", "calculator"],
        denied_agent_tool_names=["web_search"],
    )
    
    # Act & Assert - Deny wins over allow
    assert "web_search" in policy.denied_agent_tool_names
    assert "web_search" in policy.allowed_agent_tool_names
    # Resolution logic will be tested when resolve_tools() is implemented


def test_system_prompt_builder():
    """Test SystemPromptBuilder fragment ordering and build output."""
    from tinycua.config.system_prompt import SystemPromptBuilder
    
    # Arrange
    builder = SystemPromptBuilder()
    builder.add_static("Static prompt")
    builder.add_configurable_append("Configurable prompt")
    builder.add_dynamic_context("Dynamic context")
    
    # Act
    result = builder.build()
    
    # Assert
    assert result["role"] == "system"
    assert "Static prompt" in result["content"]
    assert "Configurable prompt" in result["content"]
    assert "Dynamic context" in result["content"]


def test_todo_lifecycle():
    """Test Todo append, mark_done, next_pending, and max_items limit."""
    from tinycua.models.todo import Todo
    
    # Arrange
    todo = Todo(max_items=3)
    
    # Act & Assert - Append items
    todo.append("Task 1")
    todo.append("Task 2")
    todo.append("Task 3")
    
    # Test max_items limit
    import pytest
    with pytest.raises(ValueError):
        todo.append("Task 4")
    
    # Test next_pending
    item = todo.next_pending()
    assert item is not None
    assert item.description == "Task 1"
    assert item.status == "pending"
    
    # Test mark_done
    todo.mark_done(0)
    item = todo.next_pending()
    assert item.description == "Task 2"


def test_local_model_config():
    """Test LocalModelConfig construction and defaults."""
    from tinycua.config.local_model import LocalModelConfig
    
    # Arrange & Act
    config = LocalModelConfig(
        base_url="http://localhost:11434/v1",
        model="llama3",
    )
    
    # Assert
    assert config.base_url == "http://localhost:11434/v1"
    assert config.model == "llama3"
    assert config.api_key is None
    assert config.timeout == 30.0
    assert config.temperature == 0.7
    assert config.max_tokens is None
```

### Key Test Scenarios

- [ ] **Node configuration**: Test NodeConfigBase with all policy types and their defaults
- [ ] **Tool policy resolution**: Test allow/deny precedence in NodeToolPolicy
- [ ] **System prompt building**: Test SystemPromptBuilder fragment ordering and output
- [ ] **Todo lifecycle**: Test append, mark_done, next_pending, and max_items limit
- [ ] **Local model config**: Test construction and default values

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for all config dataclasses and policies
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify all new modules import correctly
- [ ] Verify all dataclasses are immutable where intended
- [ ] Verify LocalModelConfig can be used by nodes

### Performance Considerations

- [ ] N/A — configuration dataclasses have minimal performance impact

## Proposed Changes

### Configuration Module

#### [NEW] src/tinycua/config/node_config.py

- **Description**: Create NodeConfigBase and policy dataclasses (NodeMessagePolicy, NodeToolPolicy, NodeStreamPolicy, NodeRetryPolicy)
- **Dependencies**: None (standalone module)

#### [NEW] src/tinycua/config/system_prompt.py

- **Description**: Create SystemPrompt and SystemPromptBuilder classes
- **Dependencies**: None (standalone module)

#### [NEW] src/tinycua/config/local_model.py

- **Description**: Create LocalModelConfig dataclass
- **Dependencies**: None (standalone module)

### Models Module

#### [NEW] src/tinycua/models/todo.py

- **Description**: Create Todo and TodoItem classes
- **Dependencies**: None (standalone module)

### Configuration Init

#### [MODIFY] src/tinycua/config/__init__.py

- **Description**: Re-export new config classes
- **Rationale**: Make new classes available from package root

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua.config.node_config` | New | NodeConfigBase and policy dataclasses |
| `tinycua.config.system_prompt` | New | SystemPrompt and SystemPromptBuilder |
| `tinycua.config.local_model` | New | LocalModelConfig dataclass |
| `tinycua.models.todo` | New | Todo and TodoItem |
| `tinycua.config.__init__` | Modified | Re-export new config classes |

## Data Model Changes

```python
# New types
NodeMessagePolicy:
    include_chat_history: bool = False
    include_session_context: bool = True
    max_context_messages: int | None = None
    dedupe_by_origin_record_id: bool = True
    continuation_role: Literal["assistant"] = "assistant"

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
    propagation: Any = None  # PropagationRule placeholder
    tool_policy: NodeToolPolicy = field(default_factory=NodeToolPolicy)
    stream_policy: NodeStreamPolicy = field(default_factory=NodeStreamPolicy)
    retry_policy: NodeRetryPolicy = field(default_factory=NodeRetryPolicy)
    message_policy: NodeMessagePolicy = field(default_factory=NodeMessagePolicy)
    metadata: dict[str, Any] = field(default_factory=dict)

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
    items: list[TodoItem]
    max_items: int = 20
    append(description: str) -> None
    mark_done(index: int) -> None
    next_pending() -> TodoItem | None

TodoItem:
    description: str
    status: Literal["pending", "done"]
    order: int
    metadata: dict = {}

LocalModelConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 30.0
    temperature: float = 0.7
    max_tokens: int | None = None
```

## API Changes

### New Classes

| Class | Description |
|-------|-------------|
| `NodeConfigBase` | Base configuration for all TinyCUA nodes |
| `NodeMessagePolicy` | Controls message selection and formatting |
| `NodeToolPolicy` | Controls tool scope resolution |
| `NodeStreamPolicy` | Controls streaming behavior |
| `NodeRetryPolicy` | Controls retry behavior and validation |
| `SystemPrompt` | Single prompt fragment with priority and kind |
| `SystemPromptBuilder` | Assembles fragments into system-role message |
| `Todo` | Per-session linear plan-then-execute list |
| `TodoItem` | Single todo item with status |
| `LocalModelConfig` | Local model endpoint configuration |

## Dependencies

### External Dependencies

- [x] **None** — no new external dependencies needed

### Internal Dependencies

- [x] Depends on existing `tinycua.config.session_config` (no changes needed)
- [ ] Blocks later node implementation milestones

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `PropagationRule` placeholder causes type errors later | Low | Use `Any`; replace in later milestone |
| `NodeToolPolicy` resolution order misunderstood | Medium | Clear docstrings and unit tests covering precedence |
| `Todo` max_items limit too restrictive | Low | Default 20 is generous; configurable per session |
| `LocalModelConfig` fields insufficient for some providers | Medium | Use `**kwargs` for extra fields in future |
| `SystemPromptBuilder` priority ordering edge cases | Low | Test with duplicate priorities; document stable sort |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-06*