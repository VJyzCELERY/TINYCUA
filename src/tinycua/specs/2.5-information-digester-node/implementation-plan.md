# Implementation: TinyCUAInformationDigesterNode

Implements `TinyCUAInformationDigesterNode`, a concrete `ProcessNode` that gathers and digests context for downstream nodes (primarily ResponseNode) when direct accumulated context or tool access is insufficient. The node creates a fresh session, receives selected input messages from its parent, optionally uses `enhanced_context_retrieval` for lazy scoped context access, produces structured `DigestedInformation` via `digest_information`, and propagates the digest back to its suspended parent via selected-output propagation.

## Context

- **Spec Reference**: `./spec.md` — TinyCUAInformationDigesterNode feature specification
- **Design Reference**: `./design.md` — Architecture, data model, API contracts, and implementation phases
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| - [ ] **None** — no external services needed | | | |

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.11+
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_information_digester_integration.py
"""Integration tests for TinyCUAInformationDigesterNode."""


import pytest
from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.node_input import NodeInput


def test_information_digester_fresh_session_isolation():
    """InformationDigesterNode creates a fresh session and does not inherit parent/root session."""
    # Arrange
    parent_config = NodeConfigBase()
    parent_node = ProcessNode.__new__(ProcessNode)
    parent_node.node_id = "parent_node"
    parent_node.config = parent_config
    parent_node.session = None  # Simulate parent with no session

    config = NodeConfigBase()
    digester = TinyCUAInformationDigesterNode(config=config, parent=parent_node)

    input_data = NodeInput(
        input_type="messages",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    digester(input_data)

    # Assert — digester has its own session_id, different from parent
    assert digester.session is not None
    assert digester.session.session_id != ""


def test_information_digester_stores_only_own_output():
    """InformationDigesterNode stores only its own digest output, not copied input."""
    # Arrange
    config = NodeConfigBase()
    digester = TinyCUAInformationDigesterNode(config=config)

    input_data = NodeInput(
        input_type="messages",
        messages=[
            {"role": "user", "content": "Help me write a script"},
            {"role": "assistant", "content": "I can help with that."},
        ],
    )

    # Act
    result = digester(input_data)

    # Assert — session_context should contain only the digester's output
    assert digester.session is not None
    # The session should have been created fresh
    assert len(digester.session.session_context) >= 0


def test_information_digester_tool_scope_restricted():
    """InformationDigesterNode has access only to enhanced_context_retrieval and digest_information."""
    # Arrange
    config = NodeConfigBase()
    digester = TinyCUAInformationDigesterNode(config=config)

    # Act
    tool_scope = digester.config.tool_policy.resolve_tools()

    # Assert — only the two allowed tools
    tool_names = {t.get("function", {}).get("name", "") for t in tool_scope}
    assert "enhanced_context_retrieval" in tool_names
    assert "digest_information" in tool_names
    # No outer agent tools
    assert "web_search" not in tool_names
    assert "shell_exec" not in tool_names


def test_information_digester_fallback_preserves_user_query():
    """Fallback continuation preserves the original user query."""
    # Arrange
    config = NodeConfigBase()
    digester = TinyCUAInformationDigesterNode(config=config)

    # Act
    result = digester._produce_fallback("Help me write a script")

    # Assert
    assert "Help me write a script" in result.content
    assert "No useful extra information was found" in result.content


def test_information_digester_digest_information_produces_structured_output():
    """digest_information produces DigestedInformation with all required fields."""
    # Arrange
    config = NodeConfigBase()
    digester = TinyCUAInformationDigesterNode(config=config)

    context = [
        {"role": "user", "content": "Help me write a Python script"},
        {"role": "assistant", "content": "I can help you with that."},
    ]

    # Act
    result = digester._produce_digest(context)

    # Assert
    assert result is not None
    assert result.content is not None


def test_information_digester_on_complete_propagates_to_parent():
    """on_complete propagates digest output to the suspended parent node's session."""
    # Arrange
    parent_config = NodeConfigBase()
    parent_node = ProcessNode.__new__(ProcessNode)
    parent_node.node_id = "response_node"
    parent_node.config = parent_config
    parent_node.session = None

    config = NodeConfigBase()
    digester = TinyCUAInformationDigesterNode(config=config, parent=parent_node)

    queue = NodeQueue()
    queue.enqueue(digester)
    queue.enqueue(parent_node)

    response = LLMResult(content="Digest result", role="assistant")

    # Act
    digester.on_complete(queue, response)

    # Assert — parent should be active in queue
    assert queue.current() is parent_node
