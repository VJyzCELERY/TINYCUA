# Implementation: Tool Scoping (Milestone 4.2)

Implement per-node tool scoping so that every TinyCUA node sees only the tools it is authorized to use, with shared `enhanced_context_retrieval` cache behavior working correctly for its consumers.

> **Path convention**: All paths in this document are repo-absolute paths relative to the workspace root. For example, `src/tinycua/tinycua/config/tool_scopes.py` maps to the actual file location in the repository.

## Context

- **Spec Reference**: [./spec.md](./spec.md)
- **Design Reference**: [./design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies

### Running Services

- [ ] **None** — no external services needed

### Data / Fixtures

- [ ] **None** — no data or fixtures needed

### Access / Permissions

- [ ] **None** — no special access required

### Developer Tooling

- [ ] **Runtime**: Python 3.12+
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

```python
# Test file: src/tinycua/tests/integration/test_tool_scoping_integration.py
"""Integration tests for tool scoping — Milestone 4.2."""


def test_task_executor_receives_correct_tools():
    """TaskExecutor node receives task tools + selected outer tools + enhanced_context_retrieval."""
    # Arrange
    loop = TinyCUALoop(...)
    agent_tools = [MockTool("web_search"), MockTool("calculator"), MockTool("file_read")]
    task_executor_node = TinyCUATaskExecutorNode(...)

    # Act
    resolved = loop._prepare_node(task_executor_node, agent_tools)

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_execute" in tool_names
    assert "task_result_update" in tool_names
    assert "enhanced_context_retrieval" in tool_names
    assert "web_search" in tool_names
    assert "calculator" in tool_names
    assert "file_read" in tool_names


def test_task_analyzer_excludes_task_init_in_creation_mode():
    """TaskAnalyzerNode in task_creation mode does NOT receive TaskInit/TaskCreate."""
    # Arrange
    policy = task_analyzer_tool_scope(mode="task_creation")

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_init" not in tool_names
    assert "task_create" not in tool_names
    assert "task_inspect" in tool_names
    assert "task_update" in tool_names
    assert "task_decompose" in tool_names


def test_task_analyzer_includes_task_init_in_recreation_mode():
    """TaskAnalyzerNode in task_recreation mode DOES receive TaskInit/TaskCreate."""
    # Arrange
    policy = task_analyzer_tool_scope(mode="task_recreation")

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_init" in tool_names
    assert "task_create" in tool_names
    assert "task_inspect" in tool_names


def test_response_node_includes_enhanced_context_retrieval():
    """ResponseNode receives final response tools + enhanced_context_retrieval."""
    # Arrange
    policy = response_tool_scope(allow_digest=True)

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "final_response_synthesis" in tool_names
    assert "enhanced_context_retrieval" in tool_names


def test_information_digester_scope():
    """InformationDigesterNode receives only enhanced_context_retrieval + digest_information."""
    # Arrange
    policy = information_digester_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "enhanced_context_retrieval" in tool_names
    assert "digest_information" in tool_names
    assert len(tool_names) == 2


def test_enhanced_context_retrieval_caches_per_session():
    """enhanced_context_retrieval lazily creates and reuses cache per session scope."""
    # Arrange
    tool = EnhancedContextRetrievalTool()
    session_context = [{"role": "user", "content": "Test context"}]

    # Act
    result1 = tool(session_context=session_context, query="test")
    result2 = tool(session_context=session_context, query="test")

    # Assert
    assert result1 is not None
    assert result2 is not None
    # Cache file should be reused (same cache path)


def test_enhanced_context_retrieval_isolated_per_invocation():
    """Two different invocation scopes get independent caches."""
    # Arrange
    tool1 = EnhancedContextRetrievalTool()
    tool2 = EnhancedContextRetrievalTool()
    context1 = [{"role": "user", "content": "Context A"}]
    context2 = [{"role": "user", "content": "Context B"}]

    # Act
    result1 = tool1(session_context=context1, query="test")
    result2 = tool2(session_context=context2, query="test")

    # Assert
    assert result1 is not None
    assert result2 is not None
    # Each tool invocation gets its own cache


def test_deny_wins_over_allow_for_outer_tools():
    """denied_agent_tool_names takes precedence over include_agent_tools='selected'."""
    # Arrange
    policy = NodeToolPolicy(
        node_tools=[],
        include_agent_tools="selected",
        allowed_agent_tool_names=["web_search", "calculator"],
        denied_agent_tool_names=["calculator"],
    )
    outer_tools = [MockTool("web_search"), MockTool("calculator"), MockTool("file_read")]

    # Act
    resolved = policy.resolve_tools(outer_tools)

    # Assert
    tool_names = [t.name for t in resolved]
    assert "web_search" in tool_names
    assert "calculator" not in tool_names
    assert "file_read" not in tool_names


def test_node_tools_always_included_even_if_denied():
    """Node tools are always included even if their names appear in denied_agent_tool_names."""
    # Arrange
    node_tool = MockTool("web_search")
    policy = NodeToolPolicy(
        node_tools=[node_tool],
        include_agent_tools="none",
        denied_agent_tool_names=["web_search"],
    )
    outer_tools = [MockTool("web_search"), MockTool("calculator")]

    # Act
    resolved = policy.resolve_tools(outer_tools)

    # Assert
    tool_names = [t.name for t in resolved]
    assert "web_search" in tool_names  # Node tool is always included
    assert "calculator" not in tool_names


def test_empty_allowed_list_includes_no_outer_tools():
    """include_agent_tools='selected' with empty allowed list includes no outer tools."""
    # Arrange
    policy = NodeToolPolicy(
        node_tools=[MockTool("task_execute")],
        include_agent_tools="selected",
        allowed_agent_tool_names=[],
    )
    outer_tools = [MockTool("web_search"), MockTool("calculator")]

    # Act
    resolved = policy.resolve_tools(outer_tools)

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_execute" in tool_names
    assert "web_search" not in tool_names
    assert "calculator" not in tool_names


def test_query_analyst_receives_classification_and_read_only_tools():
    """QueryAnalystNode receives classification + read-only task/context inspection tools, no mutation tools."""
    # Arrange
    policy = query_analyst_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_inspect" in tool_names
    assert "task_update" not in tool_names
    assert "task_init" not in tool_names


def test_task_create_receives_root_creation_tools_only():
    """TaskCreateNode receives deterministic root task creation tools (TaskInit/TaskCreate) only."""
    # Arrange
    policy = task_create_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_init" in tool_names
    assert "task_create" in tool_names
    assert "task_inspect" not in tool_names
    assert "task_update" not in tool_names


def test_task_assessor_receives_assessment_tools():
    """TaskAssessorNode receives task assessment/read/update tools."""
    # Arrange
    policy = task_assessor_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_inspect" in tool_names
    assert "task_update" in tool_names
    assert "task_init" not in tool_names


def test_worker_receives_decision_tools_only():
    """WorkerNode receives worker decision tools only."""
    # Arrange
    policy = worker_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert len(tool_names) > 0  # Has decision tools
    assert "task_execute" not in tool_names


def test_result_reviewer_receives_review_and_update_tools():
    """ResultReviewerNode receives review/decision + task result/context update tools."""
    # Arrange
    policy = result_reviewer_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_result_update" in tool_names
    assert "task_init" not in tool_names


def test_result_aggregation_receives_aggregation_tools():
    """ResultAggregationNode receives aggregation/consolidation tools."""
    # Arrange
    policy = result_aggregation_tool_scope()

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert len(tool_names) > 0
    assert "task_execute" not in tool_names


def test_task_analyzer_excludes_task_init_in_reanalysis_mode():
    """TaskAnalyzerNode in task_reanalysis mode does NOT receive TaskInit/TaskCreate."""
    # Arrange
    policy = task_analyzer_tool_scope(mode="task_reanalysis")

    # Act
    resolved = policy.resolve_tools([])

    # Assert
    tool_names = [t.name for t in resolved]
    assert "task_init" not in tool_names
    assert "task_create" not in tool_names
    assert "task_inspect" in tool_names
    assert "task_update" in tool_names
    assert "task_decompose" in tool_names
```

### Key Test Scenarios

- [x] **Scenario 1**: TaskExecutor receives correct tool mix (task tools + selected outer tools + enhanced_context_retrieval)
- [x] **Scenario 2**: TaskAnalyzerNode path-specific scoping (creation vs recreation vs reanalysis modes)
- [x] **Scenario 3**: enhanced_context_retrieval cache isolation and reuse
- [x] **Scenario 4**: Deny-wins-over-allow behavior for outer tools
- [x] **Scenario 5**: Node tools always included even if denied
- [x] **Edge case**: Empty allowed_agent_tool_names list

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each node's tool scope configuration
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify that a TinyCUA agent with tool scoping configured can run through the QueryAnalyst → Worker → TaskCreate → TaskAnalyzer → TaskExecutor → ResultReviewer → Response path with correct tool visibility at each step

### Performance Considerations

- [ ] No performance impact expected — tool scope resolution is a simple list filter operation

## Proposed Changes

### Tool Scope Definitions

#### [NEW] src/tinycua/tinycua/config/tool_scopes.py

- **Description**: Per-node tool scope definitions and factory functions for all 11 TinyCUA node types
- **Dependencies**: `tinycua.config.node_config.NodeToolPolicy`, concrete tool stubs

#### [MODIFY] src/tinycua/tinycua/config/node_config.py

- **Description**: Add import for tool_scopes module, ensure NodeToolPolicy dataclass supports all required fields
- **Breaking changes if any**: None

### Concrete Tool Stubs

#### [NEW] src/tinycua/tinycua/tools/task_tools.py

- **Description**: TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate tool stubs
- **Dependencies**: `tinycua.config.types.Tool`

#### [NEW] src/tinycua/tinycua/tools/todo_tools.py

- **Description**: TodoRead, TodoWrite tool stubs
- **Dependencies**: `tinycua.config.types.Tool`

#### [NEW] src/tinycua/tinycua/tools/enhanced_context_retrieval.py

- **Description**: Scoped cache + ReAct search implementation for context retrieval
- **Dependencies**: `tinycua.config.types.Tool`, filesystem operations

#### [NEW] src/tinycua/tinycua/tools/digest_information.py

- **Description**: Structured digest output tool stub
- **Dependencies**: `tinycua.config.types.Tool`

### Integration

#### [MODIFY] src/tinycua/tinycua/loops/tinycua_loop.py

- **Description**: Wire concrete tool scopes into node preparation via `_prepare_node()`
- **Breaking changes if any**: None

### Tests

#### [NEW] src/tinycua/tests/unit/test_tool_scopes.py

- **Description**: Per-node tool scope unit tests

#### [NEW] src/tinycua/tests/integration/test_tool_scoping_integration.py

- **Description**: End-to-end tool resolution integration tests

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `src/tinycua/tinycua/config/tool_scopes.py` | New | Per-node tool scope factory functions |
| `src/tinycua/tinycua/tools/task_tools.py` | New | Task mutation tool stubs |
| `src/tinycua/tinycua/tools/todo_tools.py` | New | Todo tracking tool stubs |
| `src/tinycua/tinycua/tools/enhanced_context_retrieval.py` | New | Scoped context cache + ReAct search |
| `src/tinycua/tinycua/tools/digest_information.py` | New | Structured digest output |
| `src/tinycua/tinycua/loops/tinycua_loop.py` | Modified | Wire tool scopes into node preparation |

## Data Model Changes

```python
# No new data model changes — extends existing NodeToolPolicy with factory functions
# Tool stubs use existing Tool placeholder from config/types.py
```

## API Changes

### New Endpoints

None — this is an internal implementation change.

### Modified Endpoints

None — this is an internal implementation change.

## Dependencies

### External Dependencies

None — uses existing project dependencies only.

### Internal Dependencies

- [x] Depends on Milestone 1.2 (NodeToolPolicy resolution mechanism)
- [x] Blocks Milestone 4.3 (Tool retry/validation) and 4.4 (Tool streaming)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tool scope definitions drift from design docs | High | Unit tests verify each node's scope against the design doc table |
| `enhanced_context_retrieval` cache files accumulate | Low | Cache files are in `./tmp/` which is auto-cleaned; can add TTL later |
| Path-specific task tool scoping mode is not propagated correctly | Medium | Integration test verifies mode-dependent scope through `_prepare_node()` |
| Placeholder `Tool` class lacks fields needed by concrete tools | Low | Tool stubs use `name` and `description` fields; extend as needed |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-13*
