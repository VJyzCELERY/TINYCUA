# Implementation: TinyCUA Node Base, DecisionNode, and ProcessNode

This implementation introduces the base `Node` abstraction, `ProcessNode`, and `DecisionNode` into `tinycua.loops.node`. These classes define the shared contract for session attachment, message/instruction building, lifecycle hooks, and input dispatch that all future concrete TinyCUA nodes will inherit.

## Context

- **Spec Reference**: `./spec.md`
- **Design Reference**: `./design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [x] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| [None] | No | N/A | N/A |

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
# Test file: tests/integration/test_node_integration.py
"""Integration tests for Node, ProcessNode, and DecisionNode."""


def test_process_node_with_string_input():
    """Test that a ProcessNode subclass can be called with a string input and returns a response."""
    # Arrange
    config = NodeConfigBase()
    node = MinimalProcessNode(node_id="test-process", config=config)
    session = Session()
    node.ensure_session(session)
    
    # Act
    result = node("Hello, process this input")
    
    # Assert
    assert result is not None
    assert hasattr(result, "content")
    assert node.session is not None


def test_decision_node_with_node_input():
    """Test that a DecisionNode subclass can classify input and return a route label."""
    # Arrange
    config = NodeConfigBase()
    node = MinimalDecisionNode(node_id="test-decision", config=config)
    session = Session()
    node.ensure_session(session)
    
    # Act
    result = node(NodeInput(input_type="analysis", messages=[{"role": "user", "content": "Classify this"}]))
    
    # Assert
    assert result is not None
    assert hasattr(result, "route_label")
    assert result.route_label in ["passthrough", "worker"]


def test_session_attachment_with_root_session():
    """Test that ensure_session creates a session from root session."""
    # Arrange
    config = NodeConfigBase()
    node = MinimalProcessNode(node_id="test-session", config=config)
    root_session = Session()
    
    # Act
    session = node.ensure_session(root_session)
    
    # Assert
    assert session is not None
    assert node.session is session


def test_session_attachment_with_parent_node():
    """Test that ensure_session adopts session from parent node."""
    # Arrange
    config = NodeConfigBase()
    parent = MinimalProcessNode(node_id="parent", config=config)
    child = MinimalProcessNode(node_id="child", config=config)
    child.parent = parent
    root_session = Session()
    parent.ensure_session(root_session)
    
    # Act
    session = child.ensure_session(root_session)
    
    # Assert
    assert session is parent.session


def test_message_building_with_session_context():
    """Test that build_messages includes session context when enabled."""
    # Arrange
    config = NodeConfigBase(
        message_policy=NodeMessagePolicy(include_session_context=True)
    )
    node = MinimalProcessNode(node_id="test-messages", config=config)
    session = Session()
    session.session_context = [{"role": "assistant", "content": "Previous context"}]
    node.ensure_session(session)
    
    # Act
    messages = node.build_messages(session, "New input")
    
    # Assert
    assert len(messages) > 0
    system_msg = next(m for m in messages if m["role"] == "system")
    assert "Previous context" in system_msg["content"]


def test_retry_on_validation_failure():
    """Test that node retries when validation fails."""
    # Arrange
    config = NodeConfigBase(
        retry_policy=NodeRetryPolicy(max_attempts=3)
    )
    node = RetryTestProcessNode(node_id="test-retry", config=config)
    session = Session()
    node.ensure_session(session)
    
    # Act
    result = node("Trigger retry")
    
    # Assert
    assert result is not None
    assert node.retry_count == 3


def test_lifecycle_hooks_fire():
    """Test that record_output, propagate, and on_complete are called."""
    # Arrange
    config = NodeConfigBase()
    node = LifecycleTestProcessNode(node_id="test-lifecycle", config=config)
    session = Session()
    node.ensure_session(session)
    
    # Act
    node("Test input")
    
    # Assert
    assert node.record_output_called
    assert node.propagate_called
    assert node.on_complete_called
```

### Key Test Scenarios

- [x] **Scenario 1**: ProcessNode with string input — verifies basic LLM invocation and response handling
- [x] **Scenario 2**: DecisionNode classification — verifies two-step analysis + classification flow
- [x] **Scenario 3**: Session attachment — verifies both root session and parent node session adoption
- [x] **Scenario 4**: Message building — verifies system prompt construction with session context
- [x] **Scenario 5**: Retry behavior — verifies retry loop with validation failures
- [x] **Scenario 6**: Lifecycle hooks — verifies all hooks are called at appropriate points

## Verification Plan

### Automated Tests

- [x] Integration tests (defined above) — these must pass for implementation to be complete
- [x] Unit tests for node base, process node, decision node, input dispatch
- [x] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [x] Verify node can be instantiated and called in a minimal example
- [x] Verify session attachment works with both fresh and existing sessions

### Performance Considerations

- [x] No performance tests needed for this base abstraction layer

## Proposed Changes

### Node Module

#### [NEW] src/tinycua/tinycua/loops/node.py

- **Description**: Create the base `Node` class, `ProcessNode`, and `DecisionNode` classes
- **Dependencies**: `tinycua.config.node_config`, `tinycua.models.state_object`, `tinycua.models.session`

#### [MODIFY] src/tinycua/tinycua/loops/__init__.py

- **Description**: Export new node classes from the loops package
- **Breaking changes**: None

### Configuration

#### [MODIFY] src/tinycua/tinycua/config/node_config.py

- **Description**: Ensure `NodeConfigBase` and all policy classes are importable and properly typed
- **Breaking changes**: None

### Models

#### [MODIFY] src/tinycua/tinycua/models/__init__.py

- **Description**: Ensure `NodeInput`, `NodePayload`, and `NodeInputLike` are exported
- **Breaking changes**: None

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/loops/node.py` | New | Base `Node`, `ProcessNode`, `DecisionNode` classes |
| `tinycua/config/node_config.py` | Modify | Ensure proper imports and type exports |
| `tinycua/models/__init__.py` | Modify | Export node transport models |

## Data Model Changes

```python
# New types defined in node.py
class Node(ABC):
    node_id: str
    session: Session | None
    parent: Node | None
    config: NodeConfigBase
    is_terminal: bool

class ProcessNode(Node):
    def __call__(self, input: NodeInputLike) -> LLMResult: ...

class DecisionNode(ProcessNode):
    def __call__(self, input: NodeInputLike) -> DecisionResult: ...

# Result types
class DecisionResult:
    route_label: str
    analysis_response: LLMResult
    classification_response: LLMResult

class ValidationResult:
    is_valid: bool
    errors: list[str]
```

## API Changes

### New Endpoints

No API endpoints — this is an internal abstraction layer.

### Modified Endpoints

None.

## Dependencies

### External Dependencies

No new external dependencies required.

### Internal Dependencies

- [x] Depends on existing `tinycua.config.node_config` module
- [x] Depends on existing `tinycua.models.state_object` module
- [x] Depends on existing `tinycua.models.session` module

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `SystemPromptBuilder` integration complexity | Medium | Use existing `SystemPromptBuilder` from design docs; test with mock prompts |
| `DecisionNode` two-step flow adds latency | Low | Acceptable for prototype; future optimization can combine calls |
| `NodeInputLike` dispatch edge cases | Low | Comprehensive unit tests for each input type including edge cases |
| Session lifecycle coupling | Medium | `ensure_session()` defers session creation; test with both fresh and existing sessions |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-07*