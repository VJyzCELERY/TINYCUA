# Per-Agent State

> **File:** `docs/design/state/information.md`
> **Package:** `tinycua.state.information`
> **Last Updated:** 2026-05-31

---

## Role

Each agent orchestrator owns a typed state object extending `StateObject` directly.
All state objects inherit `to_dict()`/`from_dict()` serialization from `StateObject`.

Per-agent states are stored in `Session.states` dict for persistence.

---

## `SessionTracking`

Session-level tracking stored as `Session.states["session"]`.

```python
@dataclass
class SessionTracking(StateObject):
    """Session-level tracking state."""
    last_query: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int | None] | None = None  # from response.usage events
    orchestration_phase: str | None = None            # current phase
    checkpoints: list[dict] = field(default_factory=list)
```

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
        self.state.last_result = result  # stored on SessionTracking, not here
```

Per-agent states are stored in the Session for persistence:

```python
session.set_state("query_analyst", analyst.state)
session.set_state("task_executor", executor.state)
```

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No intermediate ABC | Extends `StateObject` directly | `StateInformation` was adding unnecessary indirection |
| `last_query`/`last_result` on SessionTracking | Session-level, not per-agent | Agents don't need these individually; session tracks them |
| Serialization inherited | `StateObject.to_dict()` / `from_dict()` | No custom code needed per state class |
| Stored in Session.states | Dict keyed by agent kind | Single persistence point; session serializes everything |


---

## See also

Prev : [`StateObject` Base Class + Serialization](state_object.md) | Next : [`AgentState` Lifecycle Tracking](agent_state.md)
