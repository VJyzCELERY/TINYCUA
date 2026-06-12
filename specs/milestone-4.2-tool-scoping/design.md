# Design Document: Milestone 4.2 — Tool Scoping

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-13

---

## Overview

This design wires per-node tool policies so each TinyCUA node sees only its designed tools, implements the task/todo/digester tool functions, and verifies the shared `enhanced_context_retrieval` contract. The existing `NodeToolPolicy` dataclass and its `resolve_tools()` integration in `TinyCUALoop._prepare_node()` are the foundation — this milestone configures them per-node and implements the tools themselves.

---

## Architecture

### Component Overview

```
NodeConfigBase (per-node subclass)
  └─ NodeToolPolicy
       ├─ node_tools: list[Tool]           ← TinyCUA-specific tools
       ├─ include_agent_tools: mode        ← none | selected | all
       ├─ allowed_agent_tool_names         ← whitelist for "selected" mode
       └─ denied_agent_tool_names          ← deny list (always wins)

TinyCUALoop._prepare_node()
  └─ node.config.tool_policy.resolve_tools(outer_agent_tools) → resolved_tools
       └─ passed to agent._call_llm(tools=resolved_tools)

Tool Registry
  ├─ Task Tools (TaskInit, TaskCreate, TaskAssess, TaskExecute, TaskReview)
  ├─ Todo Tools (TodoRead, TodoUpdate)
  ├─ Digester Tools (enhanced_context_retrieval, digest_information)
  └─ Outer Agent Tools (run_shell, read_file, write_file, etc.) ← filtered by policy
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/config/node_config.py` | Modified | Add per-node config subclasses with designed tool policies |
| `tinycua/config/types.py` | Modified | Replace `Tool` placeholder with real tool protocol |
| `tinycua/tools/` (new directory) | New | Task tools, todo tools, digester tools |
| `tinycua/tools/task_tools.py` | New | TaskInit, TaskCreate, task assessment/execution/review tools |
| `tinycua/tools/todo_tools.py` | New | Todo read/update tools |
| `tinycua/tools/digester_tools.py` | New | enhanced_context_retrieval, digest_information |
| `tinycua/loops/tinycua_loop.py` | Modified | Wire per-node configs into node construction |

---

## Data Model

### Tool Protocol

Replace the placeholder `Tool(name: str)` with a proper tool protocol:

```python
class Tool(Protocol):
    name: str
    description: str
    parameters: dict  # JSON Schema for LLM tool calling

    def execute(self, **kwargs) -> str: ...

```

### Per-Node Config Subclasses

Each node gets a config subclass that pre-configures its `NodeToolPolicy`:

```python
# Base remains unchanged
@dataclass
class NodeConfigBase:
    tool_policy: NodeToolPolicy = field(default_factory=lambda: NodeToolPolicy())
    message_policy: NodeMessagePolicy = field(default_factory=lambda: NodeMessagePolicy())
    stream_policy: NodeStreamPolicy = field(default_factory=lambda: NodeStreamPolicy())
    retry_policy: NodeRetryPolicy = field(default_factory=lambda: NodeRetryPolicy())
    propagation: PropagationRule | None = None
    custom_instruction_append: str | None = None
    llm_client: Callable | None = None
    metadata: dict = field(default_factory=dict)

# Per-node subclasses with designed tool scopes
@dataclass
class QueryAnalystNodeConfig(NodeConfigBase):
    allowed_labels: list[str] = field(default_factory=lambda: ["passthrough", "worker"])
    classification_schema: dict | None = None
    # Tool policy: classification + read-only task/context tools
    # node_tools: [classification_tool, task_read_tool]
    # include_agent_tools: "none"

@dataclass
class InformationDigesterNodeConfig(NodeConfigBase):
    retrieval_enabled: bool = True
    max_digest_sources: int | None = None
    digest_schema: dict | None = None
    # Tool policy: enhanced retrieval + digest tools
    # node_tools: [enhanced_context_retrieval, digest_information]
    # include_agent_tools: "none"

@dataclass
class WorkerNodeConfig(NodeConfigBase):
    worker_labels: list[str] = field(default_factory=lambda: ["task_recreation", "task_reanalysis", "proceed_execution"])
    allow_passthrough_when_child_exists: bool = True
    deterministic_prechecks: bool = True
    effort: WorkerEffort = "none"
    # Tool policy: worker decision tools only
    # node_tools: [worker_decision_tool]
    # include_agent_tools: "none"

@dataclass
class TaskCreateNodeConfig(NodeConfigBase):
    task_schema: dict | None = None
    # Tool policy: deterministic root task creation only
    # node_tools: [task_init, task_create]
    # include_agent_tools: "none"

@dataclass
class TaskExecutorNodeConfig(NodeConfigBase):
    execution_schema: dict | None = None
    allow_outer_tools: bool = True
    # Tool policy: task execution + selected outer + enhanced_context_retrieval
    # node_tools: [task_execute, task_result_update, enhanced_context_retrieval]
    # include_agent_tools: "selected"
    # allowed_agent_tool_names: ["run_shell", "read_file", "list_files", "fetch_url"]

@dataclass
class ResultReviewerNodeConfig(NodeConfigBase):
    review_labels: list[str] = field(default_factory=lambda: ["accept", "retry", "replan", "open_question"])
    review_schema: dict | None = None
    # Tool policy: review/decision tools
    # node_tools: [review_decision, task_result_update, task_context_update]
    # include_agent_tools: "none"

@dataclass
class ResponseNodeConfig(NodeConfigBase):
    allow_information_digest_request: bool = True
    final_response_schema: dict | None = None
    # Tool policy: same base as TaskExecutor + synthesis + optional digestion
    # node_tools: [task_execute, task_result_update, enhanced_context_retrieval, final_response, digest_request]
    # include_agent_tools: "selected"
    # allowed_agent_tool_names: ["run_shell", "read_file", "list_files", "fetch_url"]
```

---

## API / Interface Contracts

### enhanced_context_retrieval

```python
def enhanced_context_retrieval(
    session_context: list[dict],
    query: str,
    cache_path: str | None = None,
) -> str:
    """
    Lazily create a scoped context cache from session_context.
    Run a ReAct-style search over the cache using grep/search and paginated reads.
    Returns relevant context snippets.

    Cache lifecycle:
    - First call with a given cache_path creates the cache file.
    - Subsequent calls reuse the existing cache.
    - Cache contains only selected context for that session/tool call.
    - All search/read operations are limited to the cache.
    """
```

### Task Tools

```python
def task_init(task_description: str, session: Session) -> str:
    """Create the root task for the session. Calls TinyCUALoop task helper."""

def task_create(parent_task_id: str, description: str, session: Session) -> str:
    """Create a child task under the given parent. Calls TinyCUALoop task helper."""

def task_assess(task_id: str, assessment: str, session: Session) -> str:
    """Record assessment for a task. Calls TinyCUALoop task helper."""

def task_execute(task_id: str, action: str, result: str, session: Session) -> str:
    """Record execution result for a task. Calls TinyCUALoop task helper."""

def task_review(task_id: str, decision: str, reasoning: str, session: Session) -> str:
    """Record review decision (accept/retry/replan/open_question) for a task."""
```

### Todo Tools

```python
def todo_read(session: Session) -> str:
    """Read current todo list from the session."""

def todo_update(todo_id: str, status: str, session: Session) -> str:
    """Update a todo item's status. Propagates according to PropagationRule."""
```

### digest_information

```python
def digest_information(
    raw_context: str,
    digest_request: str | None = None,
) -> str:
    """
    Produce structured digested information from raw context.
    Returns a JSON-serialized DigestedInformation model.
    """
```

---

## Implementation Phases

### Phase 1 — Tool Protocol and Registry (required)

- [ ] Replace `Tool` placeholder in `types.py` with proper protocol (name, description, parameters, execute)
- [ ] Create `tinycua/tools/` directory with `__init__.py`
- [ ] Implement `enhanced_context_retrieval` with lazy cache creation and ReAct-style search
- [ ] Implement `digest_information` tool
- [ ] Implement task tools: `task_init`, `task_create`, `task_assess`, `task_execute`, `task_review`
- [ ] Implement todo tools: `todo_read`, `todo_update`

### Phase 2 — Per-Node Config Subclasses (required)

- [ ] Create `QueryAnalystNodeConfig` with classification + read-only task/context tool scope
- [ ] Create `InformationDigesterNodeConfig` with enhanced retrieval + digest tool scope
- [ ] Create `WorkerNodeConfig` with worker decision tool scope
- [ ] Create `TaskCreateNodeConfig` with deterministic task creation tool scope
- [ ] Create `TaskExecutorNodeConfig` with execution + selected outer + enhanced_context_retrieval scope
- [ ] Create `ResultReviewerNodeConfig` with review/decision tool scope
- [ ] Create `ResponseNodeConfig` with same base as TaskExecutor + synthesis + optional digestion

### Phase 3 — Integration and Verification (required)

- [ ] Wire per-node configs into `TinyCUALoop` node construction (or factory)
- [ ] Verify `resolve_tools()` returns correct tool sets for each node type
- [ ] Verify `enhanced_context_retrieval` works consistently across InformationDigester, TaskExecutor, and ResponseNode
- [ ] Write unit tests for each per-node tool policy
- [ ] Write integration tests for cross-consumer `enhanced_context_retrieval`
- [ ] Write integration test for TinyCUALoop end-to-end tool resolution

---

## Technical Decisions

1. **Decision**: Per-node config subclasses rather than factory functions
   - **Reason**: Matches the design in `docs/design/config/node_config.md`; subclasses are already specced and provide type safety
   - **Alternatives Considered**: Factory functions — rejected because they lose type information and don't match the documented architecture

2. **Decision**: `enhanced_context_retrieval` uses file-based scoped cache
   - **Reason**: Design doc specifies lazy cache creation with file-backed storage; ReAct-style search over cache uses grep/search within cache boundaries
   - **Alternatives Considered**: In-memory cache — rejected because design explicitly calls for file-backed scoped cache

3. **Decision**: Task tools call TinyCUALoop task helpers directly
   - **Reason**: Design doc specifies "structural task tool calls directly mutate the root `session.task` through TinyCUALoop task helpers; nodes do not return opaque mutation instructions"
   - **Alternatives Considered**: Return mutation instructions for loop application — rejected per design

4. **Decision**: Tool protocol uses `execute(**kwargs) -> str` return type
   - **Reason**: LLM tool calling expects string results; structured data should be JSON-serialized within the string
   - **Alternatives Considered**: Generic return type — rejected because it complicates LLM integration

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Task tools depend on TinyCUALoop helpers that may not be fully wired | Medium | High | Implement task tools with clear interfaces; test with mock loop helpers if needed |
| `enhanced_context_retrieval` cache may grow unbounded for large sessions | Low | Medium | Implement cache size limits and eviction per design doc |
| Per-node config subclasses may diverge from `NodeConfigBase` defaults | Low | Low | Each subclass calls `super().__init__()` and only overrides `tool_policy` |
| Missing nodes (TaskExecutor, etc.) limit verification of their tool scopes | High | Medium | Verify tool scopes via config unit tests; full integration verification deferred to later milestones |

---

## Open Questions

1. **Tool instantiation timing**: Should tools be instantiated at config creation time or lazily at first `resolve_tools()` call? Lazy instantiation avoids creating tools for nodes that are never used, but adds complexity.
   - **Current thinking**: Instantiate at config creation time for simplicity — the tool set is static per node type.

2. **Cache path convention for `enhanced_context_retrieval`**: The design mentions "scoped session-context cache file" but doesn't specify the path convention. Should it use the session ID, a hash, or a temp directory?
   - **Current thinking**: Use `./tmp/<session_id>/<node_id>_context_cache.json` for scoping.

---

## References

- Spec: `./spec.md`
- Design docs covered by this milestone:
  - `src/tinycua/docs/design/config/node_config.md` — full
  - `src/tinycua/docs/design/constants/tools.md` — full
  - `src/tinycua/docs/design/tools/task.md` — full
  - `src/tinycua/docs/design/tools/todo.md` — full
  - `src/tinycua/docs/design/tools/digester.md` — partial/enhanced retrieval behavior
- Roadmap: `https://github.com/VJyzCELERY/TINYCUA/issues/87` — Milestone 4.2
