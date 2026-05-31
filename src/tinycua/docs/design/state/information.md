# Per-Agent State

> **File:** `docs/design/state/information.md`
> **Package:** `tinycua.state.information`
> **Last Updated:** 2026-05-31

---

## Role

Each agent orchestrator owns a typed state object extending `StateObject` directly.
All state objects inherit `to_dict()`/`from_dict()` serialization from `StateObject`.

Each state is stored on its **own Session** via `Session.agent_state` — there is no central
`states` dict. To find an agent's state, walk the session tree to that agent's node.

---

## `SessionTracking`

Session-level tracking stored directly on `Session` fields (no separate `states["session"]` entry).

| Field | Location | Description |
|-------|----------|-------------|
| `last_query` | `AgentState` (on root session) | Last user query processed |
| `last_result` | `AgentState` (on root session) | Last orchestration result |
| `total_token_usage` | `Session.total_token_usage` | Persistent, accumulates forever, propagates upward |
| `active_token_usage` | `Session.active_token_usage` | Dynamic, based on current session_context |
| `orchestration_phase` | `AgentState.resume_target` | Current phase for resume routing |
| `checkpoints` | `Session` (via serialization of full tree) | State snapshots are the session tree itself |

---

## Per-Agent State Classes

### `QueryAnalystState`

```python
@dataclass
class QueryAnalystState(StateObject):
    mode_decision: ModeDecision | None = None
    context_enhanced_query: ContextEnhancedQuery | None = None
    classification_score: float | None = None
```

### `InformationDigesterState`

```python
@dataclass
class InformationDigesterState(StateObject):
    digested_information: DigestedInformation | None = None
    retrieval_iterations: int = 0
```

### `TaskCreatorState`

```python
@dataclass
class TaskCreatorState(StateObject):
    task_tree: Task | None = None
    selected_task_ids: list[str] = field(default_factory=list)
```

### `TaskAnalyzerState`

```python
@dataclass
class TaskAnalyzerState(StateObject):
    task_tree: Task | None = None
```

### `TaskAssessorState`

```python
@dataclass
class TaskAssessorState(StateObject):
    selected_task_ids: list[str] = field(default_factory=list)
```

### `TaskExecutorState`

```python
@dataclass
class TaskExecutorState(StateObject):
    task_result: TaskResult | None = None
    execution_attempts: int = 0
    tool_results: list[dict] = field(default_factory=list)
```

### `ResultReviewerState`

```python
@dataclass
class ResultReviewerState(StateObject):
    reviewer_decision: ReviewerDecision | None = None
    deterministic_failures: list[str] = field(default_factory=list)
    last_review_status: ReviewStatus | None = None
```

### `PrimaryAgentState`

```python
@dataclass
class PrimaryAgentState(StateObject):
    final_response: dict[str, Any] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
```

---

## Usage

Each orchestrator's `__init__` initializes its state:

```python
class QueryAnalyst(BaseAgentOrchestrator[QueryAnalystState]):
    def __init__(self, config=None):
        self.state = QueryAnalystState()

    async def run(self, ...):
        ...
        self.state.mode_decision = ModeDecision(**result)
```

State is stored on the session when the agent runs:

```python
# QueryAnalyst auto-creates its own session:
analyst = QueryAnalyst(config)
root_session.add_child(analyst.session)

# Deserialize: walk the tree to find a specific agent's state
def find_state(session: Session, agent_type: str) -> StateObject | None:
    if session.agent_state and session.agent_state.active_agent == agent_type:
        return session.agent_state
    for child in session.child_sessions:
        found = find_state(child, agent_type)
        if found:
            return found
    return None
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No intermediate ABC | Extends `StateObject` directly | `StateInformation` was adding unnecessary indirection |
| `last_query`/`last_result` on root `AgentState` | Session-level fields on root session | Root is always reachable via `session.root()` |
| Serialization inherited | `StateObject.to_dict()` / `from_dict()` | No custom code needed per state class |
| State stored per session | `Session.agent_state` on each agent's node | Walk the tree to find any agent's state; no central dict needed |
| Token tracking on Session | `total_token_usage` + `active_token_usage` on Session | Persistent total propagates upward; active resets on compaction |


---


---

## See also

Prev : [`StateObject` Base Class + Serialization](state_object.md) | Next : [`AgentState` Lifecycle Tracking](agent_state.md)
