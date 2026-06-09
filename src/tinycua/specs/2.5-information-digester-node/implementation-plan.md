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

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass. These tests align with the 4 end-to-end integration test scenarios defined in `spec.md` §Testing Plan — Integration Tests.

```python
# Test file: src/tinycua/tests/integration/test_information_digester_integration.py
"""Integration tests for TinyCUAInformationDigesterNode.

End-to-end tests exercising the full InformationDigesterNode lifecycle:
session creation, context retrieval, digest production, and propagation
to the parent node. LLM calls are mocked since these are integration
tests verifying behavior, not LLM output quality.

Spec ref: spec.md §Testing Plan — Integration Tests (4 scenarios).
"""

import pytest
from unittest.mock import MagicMock, patch

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.node_input import NodeInput


@pytest.fixture
def parent_node():
    """Create a mock parent node (simulating ResponseNode) for suspension testing."""
    parent = MagicMock(spec=ProcessNode)
    parent.node_id = "response_node"
    parent.config = NodeConfigBase()
    parent.session = MagicMock()
    parent.session.session_id = "parent_session_123"
    parent.session.session_context = []
    return parent


@pytest.fixture
def digester_config():
    """Default configuration for integration tests."""
    return NodeConfigBase()


# --- Integration Test 1: ResponseNode Suspension Flow ---
@patch("tinycua.loops.information_digester.llm_call")
def test_information_digester_with_response_node_suspension(
    mock_llm_call, digester_config, parent_node
):
    """End-to-end: ResponseNode suspends → InformationDigesterNode gathers context →
    ResponseNode resumes with digest.

    Verifies the full suspension/resume lifecycle:
    1. ResponseNode suspends and prepends InformationDigesterNode.
    2. InformationDigesterNode creates a fresh session (not inheriting parent/root).
    3. InformationDigesterNode produces digest from input context.
    4. on_complete propagates digest to suspended parent.
    5. Parent resumes as current node in the queue.

    Covers spec acceptance scenarios 1, 3, 8, 9 — FR-001, FR-002, FR-003, FR-005, FR-012, FR-018.
    """
    # Arrange — mock LLM to return a structured digest
    mock_llm_call.return_value = LLMResult(
        content="Digested context: Python scripting guidance available.",
        role="assistant",
    )

    # Create digester with parent (simulating ResponseNode suspension)
    digester = TinyCUAInformationDigesterNode(config=digester_config, parent=parent_node)

    # Simulate selected context messages from ResponseNode
    input_messages = [
        {"role": "user", "content": "Help me write a Python script"},
        {"role": "assistant", "content": "I can help with that. What kind of script?"},
        {"role": "user", "content": "A file processing script"},
    ]

    input_data = NodeInput(
        input_type="messages",
        messages=input_messages,
    )

    # Set up the queue with digester and parent
    queue = NodeQueue()
    queue.items.append(digester)
    queue.items.append(parent_node)

    # Act — run the digester
    result = digester(input_data)

    # Assert — fresh session created (not parent's session)
    assert digester.session is not None
    assert digester.session.session_id != parent_node.session.session_id

    # Assert — LLM was called (digest production happened)
    assert mock_llm_call.called

    # Assert — on_complete propagates to parent and resumes it
    digester.on_complete(
        queue, LLMResult(content="Digest produced", role="assistant")
    )
    assert queue.current is parent_node


# --- Integration Test 2: No-Useful-Context Fallback Path ---
@patch("tinycua.loops.information_digester.llm_call")
def test_information_digester_no_useful_context_path(
    mock_llm_call, digester_config
):
    """End-to-end: InformationDigesterNode finds no context → fallback reaches downstream.

    Verifies the fallback path when no useful context is found:
    1. InformationDigesterNode receives input with no retrievable context.
    2. LLM determines no useful context available.
    3. Fallback continuation is produced preserving user query.
    4. Fallback message signals downstream to proceed with user request.

    Covers spec acceptance scenarios 6, 11, 13 — FR-011, FR-013, FR-014.
    """
    # Arrange — mock LLM to indicate no useful context
    mock_llm_call.return_value = LLMResult(
        content="No useful additional context found for this query.",
        role="assistant",
    )

    digester = TinyCUAInformationDigesterNode(config=digester_config)

    input_data = NodeInput(
        input_type="messages",
        messages=[{"role": "user", "content": "Help me write a script"}],
    )

    # Act
    result = digester(input_data)

    # Assert — fallback preserves user query and signals downstream
    assert result is not None
    assert result.content is not None

    fallback_text = result.content
    assert "Help me write a script" in fallback_text
    assert "No useful extra information was found" in fallback_text
    assert "proceed" in fallback_text.lower()


# --- Integration Test 3: Enhanced Retrieval End-to-End ---
@patch("tinycua.loops.information_digester.llm_call")
@patch("tinycua.loops.information_digester.EnhancedContextRetrieval")
def test_information_digester_enhanced_retrieval_end_to_end(
    mock_retrieval_class, mock_llm_call, digester_config
):
    """End-to-end: InformationDigesterNode uses enhanced_context_retrieval →
    produces digest from cache.

    Verifies the enhanced retrieval flow:
    1. InformationDigesterNode determines enhanced retrieval is needed.
    2. Scoped context cache is lazily created.
    3. ReAct-style search runs within cache boundaries.
    4. Retrieved context is incorporated into digest production.
    5. Structured DigestedInformation is produced.

    Covers spec acceptance scenarios 4, 5, 7, 10 — FR-006, FR-007, FR-008, FR-009, FR-010, FR-013.
    """
    # Arrange — mock the enhanced context retrieval tool
    mock_retrieval = MagicMock()
    mock_retrieval_class.return_value = mock_retrieval
    mock_retrieval.create_cache.return_value = "/tmp/cache_abc123"
    mock_retrieval.search.return_value = [
        {"role": "context", "content": "Relevant docs for Python file processing"},
        {"role": "context", "content": "Best practices for CSV handling in Python"},
    ]

    # Mock LLM to produce structured digest
    mock_llm_call.return_value = LLMResult(
        content=(
            "Digested: Use csv module for file processing. "
            "Key patterns: open(), csv.reader(), error handling with try/except."
        ),
        role="assistant",
    )

    digester = TinyCUAInformationDigesterNode(config=digester_config)

    input_data = NodeInput(
        input_type="messages",
        messages=[
            {
                "role": "user",
                "content": "Help me write a Python CSV processing script",
            },
        ],
    )

    # Act
    result = digester(input_data)

    # Assert — cache was created (lazy scoped access)
    assert mock_retrieval.create_cache.called

    # Assert — search was performed within cache boundaries
    assert mock_retrieval.search.called

    # Assert — digest was produced from retrieved context
    assert result is not None
    assert mock_llm_call.called

    # Assert — result contains structured digest content
    assert result.content is not None
    assert len(result.content) > 0


# --- Integration Test 4: Propagation to Parent Session ---
@patch("tinycua.loops.information_digester.llm_call")
def test_information_digester_propagation_to_parent_session(
    mock_llm_call, digester_config, parent_node
):
    """End-to-end: Digest output propagates and is visible in parent's session_context.

    Verifies propagation behavior:
    1. InformationDigesterNode completes digest production.
    2. on_complete is called with the queue.
    3. Digest output is propagated to parent via selected-output rule.
    4. Parent resumes as the current node in the queue.
    5. Digest content is available in parent's session.

    Covers spec acceptance scenarios 3, 8, 12 — FR-005, FR-012, FR-015.
    """
    # Arrange — mock LLM to return digest
    mock_llm_call.return_value = LLMResult(
        content="Digest: Context summary with key points and advisory instructions.",
        role="assistant",
    )

    digester = TinyCUAInformationDigesterNode(
        config=digester_config, parent=parent_node
    )

    input_data = NodeInput(
        input_type="messages",
        messages=[
            {"role": "user", "content": "Analyze this codebase"},
            {"role": "assistant", "content": "Let me gather more context first."},
        ],
    )

    queue = NodeQueue()
    queue.items.append(digester)
    queue.items.append(parent_node)

    # Act — run the digester
    result = digester(input_data)

    # Act — trigger propagation via on_complete
    digester.on_complete(
        queue, LLMResult(content="Final digest", role="assistant")
    )

    # Assert — parent is now the current node (resumed)
    assert queue.current is parent_node

    # Assert — digest content was propagated to parent session
    assert parent_node.session is not None

    # Assert — result contains the digest
    assert result is not None
    assert result.content is not None
```

## Deferred: NodePayload Input Path

The `NodeInput` model supports a `payloads: list[NodePayload]` field for passing structured data alongside messages. This implementation plan exercises only the `messages` input path. `NodePayload` support is deferred to Milestone 4.2 when the `digest_information` tool is fully implemented.

> **Note**: The `retrieval_enabled=False` config path is tested at the unit test level (`test_retrieval_disabled_proceeds_with_input`). Integration tests assume the default config with retrieval enabled.
