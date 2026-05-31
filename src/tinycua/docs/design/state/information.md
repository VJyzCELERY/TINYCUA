# State Information

> **File:** `docs/design/state/information.md`
> **Package:** `tinycua.state.information`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Role

`StateInformation` is an abstract base dataclass for per-agent structured runtime state.
Each agent orchestrator defines a concrete subclass with fields specific to that agent's domain.

State is **persistent** across `run()` calls — it lives on the orchestrator instance.
The loop receives a direct reference during Agent construction and reads/writes state
during execution. Since it's a reference, changes are visible immediately — even if
the stream is interrupted mid-way.

---

## Class Hierarchy

```python
from abc import ABC
from dataclasses import dataclass, field
from typing import Any

from tinycua.state import (
    ContextEnhancedQuery, ModeDecision,
    DigestedInformation, Task, TaskResult,
    ReviewerDecision, ReviewStatus, WorkerResult,
)


@dataclass
class StateInformation(ABC):
    """Abstract base for per-agent structured runtime state.

    Fields common to all agents. Subclasses add domain-specific fields.
    """
    session_id: str | None = None
    chat_history: list[dict] = field(default_factory=list)
    last_query: dict[str, Any] = field(default_factory=dict)
    last_result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Streaming accumulation (populated during Agent.run(stream=True))
    accumulated_text: list[str] = field(default_factory=list)
    token_usage: dict[str, int | None] | None = None
    iteration_count: int = 0
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

### `SessionState` (TinyCUA)

```python
@dataclass
class SessionState(StateInformation):
    active_agent: str | None = None          # which orchestrator is mid-execution
    orchestration_phase: str | None = None   # current phase: query_analysis, worker, etc.
    mode_decision: ModeDecision | None = None
    context_enhanced_query: ContextEnhancedQuery | None = None
    digested_information: DigestedInformation | None = None
    task_tree: Task | None = None
    worker_results: list[WorkerResult] = field(default_factory=list)
    checkpoints: list[dict] = field(default_factory=list)
```

---

## Usage

State is set by the orchestrator after `agent.run()` stream ends:

```python
class QueryAnalyst(BaseAgentOrchestrator[QueryAnalystState]):
    state: QueryAnalystState  # typed

    def __init__(self, config):
        self.state = QueryAnalystState()

    async def run(self, user_query, ...):
        agent = Agent(..., loop=QueryAnalystLoop(state=self.state))
        text_parts = []
        async for event in agent.run(query=..., stream=True):
            if event["type"] == "response.output_text.delta":
                text_parts.append(event["delta"])
            yield event
        raw = "".join(text_parts)
        result = json.loads(raw)
        self.state.mode_decision = ModeDecision(**result.get("mode_decision", {}))
        self.state.last_result = result
        # self.state.mode_decision.mode → "primary_agent" (typed access)
```

The loop also reads/writes state during execution (e.g., `self.state.retrieval_iterations += 1`
in `InformationDigestionLoop`).

`save_state(store)` serializes `self.state` to the `store` backend.
`restore_state(store)` hydrates it back.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ABC with per-agent subclasses | `StateInformation` + concrete classes | Typed, auto-completing; no dict access |
| M1 typed objects | `ModeDecision`, `Task`, etc. | Consistency with existing state module |
| Generic typing | `BaseAgentOrchestrator[S: StateInformation]` | `self.state.field_name` autocompletes |
| Streaming fields in base | `accumulated_text`, `token_usage`, `iteration_count` | Common across all agents; populated during stream |
| State survives interruption | Reference passed to loop, not copied | Loop writes to same object; partial state visible after error/cancel |
