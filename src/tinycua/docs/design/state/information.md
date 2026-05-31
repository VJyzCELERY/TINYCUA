# State Information

> **File:** `docs/design/state/information.md`
> **Package:** `tinycua.state.information`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`StateInformation` is an abstract base dataclass for per-agent structured runtime state.
Each agent wrapper defines a concrete subclass with fields specific to that agent's domain,
using M1 typed state objects (not raw dicts). The wrapper's `self.state` attribute is a
typed instance of the subclass.

---

## Class Hierarchy

```python
from abc import ABC
from dataclasses import dataclass, field
from tinycua.state import (
    ContextEnhancedQuery, ModeDecision,
    DigestedInformation, Task, TaskResult,
    ReviewerDecision, ReviewStatus, WorkerResult,
)


@dataclass
class StateInformation(ABC):
    """Abstract base for per-agent structured runtime state."""
    session_id: str | None = None
    chat_history: list[dict] = field(default_factory=list)
    last_query: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## Per-Agent Subclasses

### `QueryAnalystState`

```python
@dataclass
class QueryAnalystState(StateInformation):
    mode_decision: ModeDecision | None = None
    context_enhanced_query: ContextEnhancedQuery | None = None
    classification_score: float | None = None
```

### `InformationDigesterState`

```python
@dataclass
class InformationDigesterState(StateInformation):
    digested_information: DigestedInformation | None = None
    retrieval_iterations: int = 0
```

### `TaskAnalyzerState`

```python
@dataclass
class TaskAnalyzerState(StateInformation):
    task_tree: Task | None = None
```

### `TaskAssessorState`

```python
@dataclass
class TaskAssessorState(StateInformation):
    selected_task_ids: list[str] = field(default_factory=list)
```

### `TaskExecutorState`

```python
@dataclass
class TaskExecutorState(StateInformation):
    task_result: TaskResult | None = None
    execution_attempts: int = 0
    tool_results: list[dict] = field(default_factory=list)
```

### `ResultReviewerState`

```python
@dataclass
class ResultReviewerState(StateInformation):
    reviewer_decision: ReviewerDecision | None = None
    deterministic_failures: list[str] = field(default_factory=list)
    last_review_status: ReviewStatus | None = None
```

### `PrimaryAgentState`

```python
@dataclass
class PrimaryAgentState(StateInformation):
    final_response: dict[str, Any] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
```

---

## Usage

```python
class QueryAnalyst(BaseAgentWrapper[QueryAnalystState]):
    state: QueryAnalystState  # typed

    def __init__(self, config):
        super().__init__(config, state_factory=QueryAnalystState)

    async def run(self, ...):
        ...
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        # self.state.mode_decision.mode → "primary_agent" (typed access)
```

`save_state(store)` serializes `self.state` to the `store` backend.
`restore_state(store)` hydrates it back.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ABC with per-agent subclasses | `StateInformation` + concrete classes | Typed, auto-completing; no `self.state["mode_decision"]` dict access |
| M1 typed objects | `ModeDecision`, `Task`, etc. | Consistency with existing state module; no raw dicts |
| Generic typing | `BaseAgentWrapper[S: StateInformation]` | `self.state.field_name` works with autocomplete |
| Own package | `tinycua.state.information` | Co-located with other state types (M1 objects) |
