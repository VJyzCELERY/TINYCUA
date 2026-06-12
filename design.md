# Design Document: Tool Scoping

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

Tool scoping restricts which tools each TinyCUA node can use during its LLM calls. The `NodeToolPolicy` resolution mechanism exists (Milestone 1.2), but concrete tool definitions, per-node scope configurations, and the `enhanced_context_retrieval` cache behavior do not yet exist. This design defines the concrete tool scope for each of the 11 TinyCUA nodes, the shared `enhanced_context_retrieval` cache contract, and how path-specific task tool scoping is enforced.

**Note**: `TinyCUAAnalysisEffortNode` is excluded from tool scope definitions — it is a deterministic `ProcessNode` with no LLM calls. It only controls queue flow (pass counting and prepending).

---

## Architecture

### Component Overview

```
Agent(tools=[web_search, calculator, file_read, ...])   ← outer SDK tool pool
       │
       ▼
TinyCUALoop._prepare_node(node, tools)
       │
       ▼
NodeToolPolicy.resolve_tools(outer_agent_tools)
       │
       ├── node_tools (always included)
       ├── include_agent_tools = none | selected | all
       ├── allowed_agent_tool_names (for "selected" mode)
       └── denied_agent_tool_names (deny wins over allow)
       │
       ▼
resolved_tools → node.config.tool_policy produces filtered list
       │
       ▼
LLM call receives only resolved tools
```

### Affected Components

> **Path convention**: All paths in this table are Python module paths relative to the `tinycua` package root (`src/tinycua/tinycua/`). For example, `tinycua/config/tool_scopes.py` maps to `src/tinycua/tinycua/config/tool_scopes.py`.

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/config/node_config.py` | Modified | Add `NodeToolPolicy` factory methods for each node type |
| `tinycua/config/tool_scopes.py` | New | Per-node tool scope definitions and factory functions |
| `tinycua/tools/enhanced_context_retrieval.py` | New | Scoped cache + ReAct search implementation |
| `tinycua/tools/digest_information.py` | New | Structured digest output tool |
| `tinycua/tools/task_tools.py` | New | TaskInit, TaskCreate, and task mutation tools |
| `tinycua/tools/todo_tools.py` | New | Todo tracking tools |
| `tinycua/loops/tinycua_loop.py` | Modified | Wire concrete tool scopes into node preparation |
| `tests/unit/test_tool_scopes.py` | New | Per-node tool scope unit tests |
| `tests/integration/test_tool_scoping_integration.py` | New | End-to-end tool resolution integration tests |

---

## Data Model

### Tool Scope Registry

Each node type maps to a `NodeToolPolicy` definition. The registry is a module-level dictionary or factory function per node type.

**Node Tool Scope Summary** (authoritative source: `src/tinycua/docs/design/constants/tools.md`):

> **Note**: The complete tool-to-node mapping is defined in the external file above. For a full review, read `src/tinycua/docs/design/constants/tools.md` alongside this document.

| Node | Factory Function | Node Tools | Outer Tools |
|------|-----------------|------------|-------------|
| QueryAnalystNode | `query_analyst_tool_scope()` | Classification + read-only task/context inspection | none |
| InformationDigesterNode | `information_digester_tool_scope()` | `enhanced_context_retrieval`, `digest_information` | none |
| WorkerNode | `worker_tool_scope()` | Worker decision tools | none |
| TaskCreateNode | `task_create_tool_scope()` | `TaskInit`, `TaskCreate` | none |
| TaskAnalyzerNode | `task_analyzer_tool_scope(mode)` | Structural task tools; `TaskInit`/`TaskCreate` only in `task_recreation` mode | none |
| TaskAssessorNode | `task_assessor_tool_scope()` | Task assessment/read/update tools | none |
| TaskExecutorNode | `task_executor_tool_scope()` | Task execution, `enhanced_context_retrieval`, todo tools | selected |
| ResultReviewerNode | `result_reviewer_tool_scope()` | Review/decision, task result/context update | none |
| ResultAggregationNode | `result_aggregation_tool_scope()` | Aggregation/consolidation tools | none |
| ResponseNode | `response_tool_scope(allow_digest)` | Same base as TaskExecutor + final response synthesis + optional digest request | selected |
| AnalysisEffortNode | *(deterministic ProcessNode — no LLM calls, no tool scope)* | — | — |

```python
# Conceptual shape — not final implementation

TASK_EXECUTOR_TOOL_SCOPE = NodeToolPolicy(
    node_tools=[
        TaskExecuteTool(),
        TaskResultUpdateTool(),
        TodoReadTool(),
        TodoWriteTool(),
        EnhancedContextRetrievalTool(),
    ],
    include_agent_tools="selected",
    allowed_agent_tool_names=["web_search", "file_read", "calculator"],
)

RESPONSE_NODE_TOOL_SCOPE = NodeToolPolicy(
    node_tools=[
        FinalResponseSynthesisTool(),
        TodoReadTool(),
        TodoWriteTool(),
        EnhancedContextRetrievalTool(),
    ],
    include_agent_tools="selected",
    allowed_agent_tool_names=["web_search", "file_read", "calculator"],
    # Optional: InformationDigestRequestTool when allow_information_digest_request=True
)
```

### Path-Specific Task Tool Scoping

TaskAnalyzerNode's tool scope changes based on the Worker route:

```python
def task_analyzer_scope(mode: str) -> NodeToolPolicy:
    base_tools = [TaskInspectTool(), TaskUpdateTool(), TaskDecomposeTool()]
    if mode == "task_recreation":
        base_tools.extend([TaskInitTool(), TaskCreateTool()])
    # task_creation and task_reanalysis: no TaskInit/TaskCreate
    return NodeToolPolicy(
        node_tools=base_tools,
        include_agent_tools="none",
    )
```

### Enhanced Context Retrieval Cache

```python
EnhancedContextRetrievalTool:
    - Receives: session or selected session_context
    - Creates: scoped cache file (one per invocation)
    - Cache contents: selected context for that session/tool call
    - Search: ReAct-style grep/search within cache only
    - Read: paginated cache reads within cache only
    - Constraint: all operations limited to the cache file
```

---

## API / Interface Contracts

### NodeToolPolicy Factory Functions

```python
def query_analyst_tool_scope() -> NodeToolPolicy:
    """Classification + read-only task/context inspection tools."""

def information_digester_tool_scope() -> NodeToolPolicy:
    """enhanced_context_retrieval + digest_information tools."""

def worker_tool_scope() -> NodeToolPolicy:
    """Worker decision tools only."""

def task_create_tool_scope() -> NodeToolPolicy:
    """Deterministic root task creation tools (TaskInit/TaskCreate)."""

def task_analyzer_tool_scope(mode: str) -> NodeToolPolicy:
    """Structural task tools; TaskInit/TaskCreate only when mode='task_recreation'."""

def task_assessor_tool_scope() -> NodeToolPolicy:
    """Task assessment/read/update tools."""

def task_executor_tool_scope() -> NodeToolPolicy:
    """Task execution + selected outer Agent tools + enhanced_context_retrieval."""

def result_reviewer_tool_scope() -> NodeToolPolicy:
    """Review/decision + task result/context update tools."""

def result_aggregation_tool_scope() -> NodeToolPolicy:
    """Aggregation/consolidation tools."""

def response_tool_scope(allow_digest: bool = True) -> NodeToolPolicy:
    """Same base as TaskExecutor + final response synthesis + optional digest request."""
```

### Enhanced Context Retrieval Tool

```python
class EnhancedContextRetrievalTool:
    def __call__(self, session_context: list[dict], query: str) -> str:
        """
        Lazily create a scoped cache file from session_context.
        Run ReAct-style search over the cache using the query.
        Return search results from within the cache only.

        Cache file lifecycle:
        1. First call for a session: create cache, populate, search.
        2. Subsequent calls: reuse existing cache file.
        3. Cache is per-invocation scope (not shared across nodes).
        """
```

### Task Tools

```python
class TaskInitTool:
    """Initialize a new task structure. Used by TaskCreateNode and TaskAnalyzerNode (recreation mode)."""

class TaskCreateTool:
    """Create a root task in session.task. Used by TaskCreateNode and TaskAnalyzerNode (recreation mode)."""

class TaskInspectTool:
    """Read-only task inspection. Used by QueryAnalyst and TaskAssessor."""

class TaskUpdateTool:
    """Update task fields. Used by TaskExecutor, ResultReviewer, TaskAssessor."""

class TaskDecomposeTool:
    """Decompose task into subtasks. Used by TaskAnalyzerNode."""

class TaskResultUpdateTool:
    """Update task result/artifact fields. Used by TaskExecutor."""
```

### Todo Tools

```python
class TodoReadTool:
    """Read current todo list state."""

class TodoWriteTool:
    """Update todo list items."""
```

### Digest Information Tool

```python
class DigestInformationTool:
    def __call__(self, context: str, request: str | None = None) -> dict:
        """
        Produce structured digested information from context.
        Returns a DigestedInformation-compatible dict.
        """
```

---

## Implementation Phases

### Phase 1 — Tool Scope Definitions (required)

- [ ] Create `tinycua/config/tool_scopes.py` with factory functions for all 11 node types
- [ ] Implement path-specific `task_analyzer_tool_scope(mode)` with mode-dependent TaskInit/TaskCreate
- [ ] Implement `response_tool_scope(allow_digest)` with optional information-digestion request capability
- [ ] Wire tool scopes into node initialization in `TinyCUALoop` or node constructors

### Phase 2 — Concrete Tool Stubs (required)

- [ ] Create `tinycua/tools/task_tools.py` with TaskInit, TaskCreate, TaskInspect, TaskUpdate, TaskDecompose, TaskResultUpdate stubs
- [ ] Create `tinycua/tools/todo_tools.py` with TodoRead, TodoWrite stubs
- [ ] Create `tinycua/tools/enhanced_context_retrieval.py` with scoped cache + ReAct search stub
- [ ] Create `tinycua/tools/digest_information.py` with structured digest output stub

### Phase 3 — Integration and Tests (required)

- [ ] Create `tests/unit/test_tool_scopes.py` — test each node's tool scope matches design
- [ ] Create `tests/integration/test_tool_scoping_integration.py` — test `_prepare_node()` resolves correctly
- [ ] Test path-specific task tool scoping (creation, recreation, reanalysis)
- [ ] Test `enhanced_context_retrieval` cache creation and isolation

> **Note**: Phase 2 tool implementations are stubs that satisfy the interface contract. Full tool behavior is implemented in later milestones.

---

## Technical Decisions

1. **Decision**: Use factory functions rather than class-based scope definitions.
   - **Reason**: Simpler to test, easier to parameterize (e.g., `task_analyzer_tool_scope(mode)`), matches the existing `NodeToolPolicy` dataclass pattern.
   - **Alternatives Considered**: Class-per-scope — rejected because it adds indirection without benefit for a prototype.

2. **Decision**: Tool scopes are defined at module level in `tool_scopes.py`, not embedded in node classes.
   - **Reason**: Keeps tool scope definitions centralized and testable independently of node logic. Nodes remain unaware of their own tool scope — `TinyCUALoop` resolves tools before calling nodes.
   - **Alternatives Considered**: Node-owned scope — rejected because it couples node implementation to tool resolution and complicates testing.

3. **Decision**: `enhanced_context_retrieval` uses per-call cache files, not shared cache.
   - **Reason**: Simpler isolation model — no cache invalidation concerns, no cross-node cache pollution. Each invocation gets a clean, scoped context.
   - **Alternatives Considered**: Shared session-scoped cache — rejected for prototype complexity; can be optimized later.

4. **Decision**: Task tools are stubs that call `session.task` mutation helpers directly.
   - **Reason**: Matches the design contract that "structural task tool calls directly mutate root session.task through TinyCUALoop task helpers." Stubs satisfy the interface without implementing full task tree mutation logic.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tool scope definitions drift from design docs | Low | High | Unit tests verify each node's scope against the design doc table |
| `enhanced_context_retrieval` cache files accumulate | Medium | Low | Cache files are in `./tmp/` which is auto-cleaned; can add TTL later |
| Path-specific task tool scoping mode is not propagated correctly | Medium | Medium | Integration test verifies mode-dependent scope through `_prepare_node()` |
| Placeholder `Tool` class lacks fields needed by concrete tools | Low | Low | Tool stubs use `name` and `description` fields; extend as needed |

---

## Open Questions _(optional)_

1. **Should tool scope factory functions be importable from a public `tinycua.tools` package?**
   - Current thinking: Yes, for testability and external configuration.

2. **Should `enhanced_context_retrieval` support multiple search strategies beyond ReAct?**
   - Current thinking: Not in this milestone. Keep it as ReAct-style search; extend later if needed.

---

## References

- Spec: [./spec.md](./spec.md)
- Design docs covered:
  - `src/tinycua/docs/design/config/node_config.md` — full
  - `src/tinycua/docs/design/constants/tools.md` — full
  - `src/tinycua/docs/design/tools/task.md` — full
  - `src/tinycua/docs/design/tools/todo.md` — full
  - `src/tinycua/docs/design/tools/digester.md` — partial/enhanced retrieval behavior
- Existing implementation:
  - `tinycua/config/node_config.py` — NodeToolPolicy (Milestone 1.2)
  - `tinycua/config/types.py` — Tool placeholder
  - `tinycua/loops/tinycua_loop.py` — `_prepare_node()` integration point
