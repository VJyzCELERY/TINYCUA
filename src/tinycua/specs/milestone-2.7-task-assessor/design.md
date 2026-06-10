# Design Document: TinyCUATaskAssessorNode

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-10

---

## Overview

This design document describes the `TinyCUATaskAssessorNode`, a concrete `ProcessNode` that evaluates the task tree and selects unfinished tasks for decomposition or reanalysis. The node operates in two modes: effort-loop mode for full-tree assessment during upfront planning, and reviewer-replan mode for local-region assessment during execution-time recovery. The implementation integrates with the existing `AnalysisEffortNode` queue mechanics and follows the TinyCUA node contract.

---

## Architecture

### Component Overview

```
AnalysisEffortNode
  → [TaskAssessor, TaskAnalyzer] pairs prepended to queue
    → TaskAssessor evaluates task tree
    → If tasks selected: TaskAnalyzer decomposes
    → If no tasks selected: skip TaskAnalyzer
  → When pass_limit reached: TaskExecutor spawned
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.loops.task_assessor` | New | Core TaskAssessorNode implementation |
| `tinycua.config.node_config` | Modified (Phase 2) | Add `TinyCUATaskAssessorNodeConfig` |
| `tinycua.loops.analysis_effort` | Modified | Integrate TaskAssessor prepending |
| `tinycua.loops.node` | Unchanged | ProcessNode base class |
| `tinycua.loops.node_queue` | Unchanged | Queue mechanics |

---

## Data Model

### New Entities _(if applicable)_

```python
# Conceptual data shape (not necessarily the final class)
TaskAssessmentResult:
    selected_task_ids: list[str]    # Task IDs selected for processing
    mode: str                       # "effort_loop" or "reviewer_replan"
    tree_state_summary: str         # Brief summary of task tree state
    metadata: dict                  # Additional assessment metadata
```

### Schema Changes _(if applicable)_

- **Phase 2 (deferred)**: `TinyCUATaskAssessorNodeConfig` with fields:
  - `assessment_schema: dict | None` — Optional schema for structured assessment output
  - `allow_task_updates: bool = True` — Whether node can update task status during assessment
- **MVP (Phase 1)**: No config subclass — uses base `NodeConfigBase` directly.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

```python
class TinyCUATaskAssessorNode(ProcessNode):
    """ProcessNode for task tree evaluation and selection.
    
    Evaluates the task tree and selects unfinished tasks for processing.
    Operates in two modes:
    - effort_loop: Evaluates full tree, selects unfinished tasks (default).
    - reviewer_replan: Local-region assessment for replan (future).
    """
    
    def __init__(
        self,
        node_id: str = "task_assessor",
        config: NodeConfigBase | None = None,
        mode: str = "effort_loop",
    ) -> None:
        """Initialize TaskAssessorNode.
        
        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            mode: Assessment mode. "effort_loop" evaluates full tree.
        """
    
    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute task assessment.
        
        Calls the LLM to evaluate the task tree and select unfinished tasks.
        Parses the response to extract selected task IDs.
        
        Args:
            input: The node input containing task context.
            
        Returns:
            The LLM response with task assessment.
        """
    
    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Advance queue after task assessment.
        
        If tasks were selected, the queue advances to TaskAnalyzer.
        If no tasks selected, skip TaskAnalyzer and advance back to
        AnalysisEffortNode (design contract: no wasted LLM invocations).
        
        Args:
            queue: The node queue (will be advanced).
            response: The LLM response from task assessment.
        """
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Malformed LLM response | Log warning, treat as empty selection | Graceful degradation |
| Empty task tree | Return empty selection | Normal operation |
| Invalid task IDs | Log warning, filter invalid IDs | Robust parsing |
| LLM service failure (timeout/API error) | Propagate per policy or retry | Use existing LLM retry/backoff policy |
| Unexpected response structure | Log warning, treat as empty selection | Valid JSON but wrong shape |
| LLM rate limiting | Backoff/retry or propagate | Respect rate limit headers |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [ ] ~~Create `TinyCUATaskAssessorNodeConfig` in `tinycua.config.node_config`~~ (deferred to Phase 2 per Schema Changes section)
- [ ] Implement `TinyCUATaskAssessorNode` class with effort-loop mode
- [ ] Implement LLM response parsing for task ID extraction
- [ ] Implement `on_complete` queue advancement logic
- [ ] Add unit tests for node initialization, `__call__`, and `on_complete`
- [ ] Add integration tests with `AnalysisEffortNode`

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- [ ] Implement reviewer-replan mode for local-region assessment
- [ ] Add structured assessment output via `assessment_schema`
- [ ] Add task status update capabilities during assessment

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

Document key decisions and the reasoning behind them:

1. **Decision**: Use LLM-based assessment rather than deterministic task tree traversal.
   - **Reason**: Task assessment may require semantic understanding of task completeness that simple status checks cannot provide. The LLM can evaluate whether tasks are truly "unfinished" based on context.
   - **Alternatives Considered**: Deterministic status checking — rejected because it may miss nuanced task completion states.

2. **Decision**: Parse LLM response as JSON list of task IDs.
   - **Reason**: Provides structured output that can be directly consumed by TaskAnalyzer. Allows for clear contract between nodes.
   - **Alternatives Considered**: Free-text parsing — rejected because it introduces ambiguity and parsing complexity.

3. **Decision**: Skip TaskAnalyzer when no tasks selected.
   - **Reason**: Design contract specifies "no wasted LLM invocations." Skipping unnecessary analysis passes improves efficiency.
   - **Alternatives Considered**: Always run TaskAnalyzer — rejected because it violates the efficiency requirement.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM produces inconsistent task ID format | Medium | Medium | Robust parsing with fallback to empty selection |
| Task tree structure changes during assessment | Low | Low | Assessment uses snapshot of task tree state |
| Performance impact from LLM calls | Medium | Low | Effort-loop mode limits assessment passes via pass_limit |

---

## Open Questions _(optional)_

Design-level questions not yet resolved:

1. **Assessment Schema Flexibility**: Should the assessment schema be fully configurable or have required fields?
   - Current thinking: Make it configurable with sensible defaults, allowing nodes to customize output format.

2. **Reviewer-Replan Integration**: How should local-region assessment interact with active task selection?
   - Current thinking: Focus on active task and immediate children/parent context, defer to future milestone.

---

## References

- Spec: `./spec.md` — relative path from this design.md to its spec.md
- Design docs: `src/tinycua/docs/design/loops/task_assessor.md` — Target architecture
- Related designs:
  - `src/tinycua/docs/design/loops/analysis_effort.md` — Effort loop integration
  - `src/tinycua/docs/design/loops/task_analyzer.md` — TaskAnalyzer consumption
  - `src/tinycua/docs/design/loops/node.md` — Node contract and hierarchy
  - `src/tinycua/docs/design/config/node_config.md` — Node configuration
