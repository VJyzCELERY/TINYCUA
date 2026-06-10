# Design Document: TaskExecutor and ResultReviewer Nodes

**Spec**: `./spec.md`
**Status**: Reviewed — Ready for Implementation (2026-06-11)
**Last Updated**: 2026-06-10

---

## Overview

This design introduces `TinyCUATaskExecutorNode` (ReAct-style task execution) and `TinyCUAResultReviewerNode` (result evaluation with accept/retry/replan/open_question decisions) into `tinycua.loops`, adds `ReviewerRetryState` to track retry failure counts, wires the executor→reviewer path through `AnalysisEffortNode` and `WorkerNode`, and replaces the no-op stubs on `TinyCUALoop` with real reviewer-decision handlers. The design follows `src/tinycua/docs/design/loops/task_executor.md`, `src/tinycua/docs/design/loops/result_reviewer.md`, and `src/tinycua/docs/design/models/reviewer_decision.md`.

---

## Architecture

### Component Overview

```
AnalysisEffortNode / WorkerNode._route_proceed_execution()
  │
  ├── spawn TaskExecutor
  └── spawn ResultReviewer
        │
        ▼
  ┌─────────────────────┐
  │  TaskExecutor        │  ProcessNode
  │  (ReAct execution)   │  receives active task (read-only)
  │  → produces TaskResult│
  └─────────┬───────────┘
            │ on_complete → advance queue
            ▼
  ┌─────────────────────┐
  │  ResultReviewer      │  ProcessNode
  │  (evaluate result)   │  decides accept/retry/replan/open_question
  │  → ReviewerDecision  │
  └─────────┬───────────┘
            │ on_complete → queue mutation based on decision
            ├── accept  → update task status, recompute next active task
            ├── retry   → advance to TaskExecutor (same task)
            ├── replan  → spawn TaskAssessor + TaskAnalyzer → TaskExecutor
            └── open_question → keep ResultReviewer active + mandatory_passthrough

Edge case: If TaskAssessor finds no unfinished tasks in the local region, TaskAnalyzer is skipped and the flow goes directly to TaskExecutor (per TaskAssessor contract).

TinyCUALoop
  ├── _reviewer_retry_state: ReviewerRetryState
  ├── _on_reviewer_accept(active_task) → bool     [already implemented]
  ├── _on_reviewer_retry(active_task) → None      [was no-op, now real]
  ├── _on_reviewer_replan(active_task) → None     [was no-op, now real]
  └── _on_reviewer_open_question(active_task) → None [was no-op, now real]
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua/loops/task_executor.py` | New | TaskExecutorNode ProcessNode |
| `tinycua/loops/result_reviewer.py` | New | ResultReviewerNode ProcessNode |
| `tinycua/models/reviewer_decision.py` | New | ReviewerRetryState dataclass (retry failure tracking) |
| `tinycua/loops/analysis_effort.py` | Modified | `_spawn_task_executor()` replaces stub |
| `tinycua/loops/worker.py` | Modified | `_route_proceed_execution()` replaces stub |
| `tinycua/loops/tinycua_loop.py` | Modified | `_on_reviewer_retry/replan/open_question` become real |
| `tinycua/loops/__init__.py` | Modified | Export new node classes |

---

## Data Model

### ReviewerRetryState

```python
@dataclass
class ReviewerRetryState:
    """Tracks retry failure count for the current active task.

    Stored on TinyCUALoop. Reset on accept. Default threshold: 5.
    Distinct from NodeRetryPolicy.max_attempts which controls
    LLM call retries within a single node invocation.
    """
    retry_count: int = 0
    threshold: int = 5

    def increment(self) -> int:
        """Increment retry count and return new value."""
        self.retry_count += 1
        return self.retry_count

    def reset(self) -> None:
        """Reset retry count to 0 (called on accept)."""
        self.retry_count = 0

    def is_threshold_reached(self) -> bool:
        """Check if retry count has reached the threshold."""
        return self.retry_count >= self.threshold

    def can_retry(self) -> bool:
        """Check if another retry is allowed."""
        return not self.is_threshold_reached()
```

### TaskExecutor Execution Result

TaskExecutor produces an `LLMResult` whose content is a structured execution summary. The `on_complete` method extracts or constructs a `TaskResult` from the LLM output and the active task reference.

```python
# Conceptual flow in TaskExecutor.__call__:
active_task = input.metadata.get("active_task")  # injected via NodeInput metadata
if active_task is None:
    raise NodeExecutionError("No active task provided")
llm_result = super().__call__(input)  # ReAct execution via LLM
task_result = TaskResult(
    task_id=active_task.task_id,
    execution_status="succeeded" if llm_result succeeded else "failed",
    summary=llm_result.content,
)
```

### ResultReviewer Decision Extraction

ResultReviewer uses LLM to evaluate the execution result and classify into one of four outcomes. The `on_complete` method dispatches based on the decision.

```python
# Conceptual flow in ResultReviewer.__call__:
llm_result = super().__call__(input)  # LLM evaluates result
decision = _extract_decision(llm_result)  # parse ReviewerOutcome from LLM
reviewer_decision = ReviewerDecision(
    outcome=decision,
    rationale=llm_result.content,
)
```

---

## API / Interface Contracts

### TinyCUATaskExecutorNode

```python
class TinyCUATaskExecutorNode(ProcessNode):
    """ProcessNode for ReAct-style execution of the current active task.

    Only node that may execute task actions and produce execution results.

    Attributes:
        node_id: Always "task_executor" by default.
        max_react_iterations: Maximum ReAct loops per task (default 10).
    """

    def __init__(
        self,
        node_id: str = "task_executor",
        config: NodeConfigBase,
        max_react_iterations: int = 10,
    ) -> None:
        """Initialize TaskExecutorNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            max_react_iterations: Max ReAct iterations per task execution.
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=(
                "You are a task executor. Execute the current active task "
                "using available tools. Follow a ReAct pattern: observe the "
                "task state, think about what to do, act using tools, and "
                "observe the result. Continue until the task is complete or "
                "you are blocked."
            ),
        )
        self.max_react_iterations = max_react_iterations

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute the active task using ReAct-style processing.

        The active task reference is injected via NodeInput metadata.
        Executes the task using available tools and produces a TaskResult.

        Args:
            input: NodeInput containing the active task reference.

        Returns:
            LLMResult with execution summary.

        Raises:
            NodeExecutionError: If no active task is provided or execution fails.
        """
        # Extract active task from NodeInput metadata
        active_task = input.metadata.get("active_task")
        if active_task is None:
            raise NodeExecutionError("No active task provided")

        # Obtain tools from session
        tools = self._session.get_tools()

        # ReAct loop with iteration cap
        messages = self._build_initial_messages(active_task)
        iteration = 0
        while iteration < self.max_react_iterations:
            iteration += 1

            # Invoke LLM with tools
            llm_result = self._agent._call_llm(messages, tools)

            # Process tool calls if present
            if llm_result.tool_calls:
                tool_results = self._execute_tools(llm_result.tool_calls, tools)
                messages.extend(self._format_tool_results(tool_results))
            else:
                # No tool calls — task execution complete
                break

            # Check for context retrieval needs
            if self._needs_context(active_task, llm_result):
                context = self._enhanced_context_retrieval(active_task, self._session)
                messages.append({"role": "context", "content": context})

        if iteration >= self.max_react_iterations:
            logger.warning(f"TaskExecutor reached max iterations ({self.max_react_iterations})")

        # Propagate active_task so ResultReviewer.on_complete can access it
        llm_result.metadata["active_task"] = active_task
        return llm_result

    def _build_initial_messages(self, active_task: Task) -> list[dict]:
        """Build initial message list for ReAct execution.

        Includes system instruction and task description.
        Tools are passed separately to _call_llm.

        Args:
            active_task: The active task to execute.

        Returns:
            List of message dicts for LLM invocation.
        """
        return [{"role": "user", "content": active_task.description}]

    def _needs_context(self, active_task: Task, llm_result: LLMResult) -> bool:
        """Check if enhanced context retrieval is needed.

        Returns True if the LLM signals it needs more context
        or if the task has a context_required flag.

        Args:
            active_task: The active task.
            llm_result: The LLM result to evaluate.

        Returns:
            True if enhanced context is needed.
        """
        return False  # Implementation detail — configurable

    def _enhanced_context_retrieval(self, active_task: Task, session: Session) -> str:
        """Retrieve additional context for task execution.

        Implements FR-006. Uses session's context retrieval pipeline.

        Args:
            active_task: The active task.
            session: The current session.

        Returns:
            Additional context string.
        """
        return session.retrieve_context(active_task)  # Placeholder

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Advance queue after execution completes.

        Queue behavior: default advancement to next node (ResultReviewer).
        No explicit queue mutation needed — the queue runner advances automatically
        after __call__ returns. The spawner (AnalysisEffortNode._spawn_task_executor)
        seeds [TaskExecutor, ResultReviewer] in order.

        Args:
            queue: The node queue (advanced after execution).
            response: The execution summary response.
        """
        pass  # Default ProcessNode.on_complete is sufficient
```

### TinyCUAResultReviewerNode

```python
class TinyCUAResultReviewerNode(ProcessNode):
    """ProcessNode that evaluates TaskExecutor output and decides
    accept/retry/replan/open_question.

    Quality gate between execution and response.

    Attributes:
        node_id: Always "result_reviewer" by default.
    """

    def __init__(
        self,
        node_id: str = "result_reviewer",
        config: NodeConfigBase,
        loop=None,
    ) -> None:
        """Initialize ResultReviewerNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration.
            loop: The TinyCUALoop instance. Injected by spawner after construction
                  to enable callback dispatch (accept/retry/replan/open_question).
        """
        super().__init__(
            node_id=node_id,
            config=config,
            instruction=(
                "You are a result reviewer. Evaluate the execution result "
                "of the current task. Determine if the task was completed "
                "successfully (accept), needs re-execution (retry), needs "
                "replanning (replan), or requires user input (open_question). "
                "Respond with exactly one word: accept, retry, replan, or open_question."
            ),
        )
        self._loop = loop

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Evaluate the execution result and decide accept/retry/replan/open_question.

        Args:
            input: NodeInput containing the execution result and active task context.

        Returns:
            LLMResult with the review decision.
        """
        # Call LLM to evaluate the result
        llm_result = super().__call__(input)

        # Parse decision from LLM output
        decision = self._extract_decision(llm_result.content)

        # Fallback to retry if parsing fails
        if decision is None:
            logger.warning(f"ResultReviewer could not parse decision: {llm_result.content}")
            decision = ReviewerOutcome.RETRY
            rationale = f"Parse failure: {llm_result.content}"
        else:
            rationale = llm_result.content

        reviewer_decision = ReviewerDecision(
            outcome=decision,
            rationale=rationale,
        )

        # Return LLMResult with structured decision
        return LLMResult(
            content=reviewer_decision.model_dump_json(),
            metadata={"reviewer_decision": reviewer_decision},
        )

    def _extract_decision(self, llm_output: str) -> ReviewerOutcome | None:
        """Extract ReviewerOutcome from LLM output using word-boundary matching.

        Args:
            llm_output: Raw LLM output string.

        Returns:
            Matched ReviewerOutcome or None if no match found.
        """
        import re
        match = re.fullmatch(r'\s*(accept|retry|replan|open_question)\s*', llm_output, re.IGNORECASE)
        if match:
            return ReviewerOutcome(match.group(1).lower())
        return None

    def on_complete(self, queue: NodeQueue, response: LLMResult) -> None:
        """Dispatch based on reviewer decision.

        Queue behavior:
        - accept: advance (loop handles task status update + next active task)
        - retry: advance to TaskExecutor (same task)
        - replan: spawn TaskAssessor + TaskAnalyzer + TaskExecutor
        - open_question: keep ResultReviewer active

        Args:
            queue: The node queue (may be mutated based on decision).
            response: The review decision response.
        """
        reviewer_decision = response.metadata.get("reviewer_decision")
        if reviewer_decision is None:
            return

        decision = reviewer_decision.outcome
        active_task = response.metadata.get("active_task")

        if decision == ReviewerOutcome.ACCEPT:
            self._loop._on_reviewer_accept(active_task)
            # Queue advances to terminal node automatically
        elif decision == ReviewerOutcome.RETRY:
            self._loop._on_reviewer_retry(active_task)
            # Queue advances to TaskExecutor automatically (same task)
        elif decision == ReviewerOutcome.REPLAN:
            self._loop._on_reviewer_replan(active_task)
            # on_complete owns queue mutation — _on_reviewer_replan has no queue param
            queue.clear_after_current()
            task_assessor = TaskAssessor(scope=active_task.region)
            task_analyzer = TaskAnalyzer(mode="local_replan", init_enabled=False)
            task_executor = TinyCUATaskExecutorNode(config=self.config)
            queue.spawn_after_current([task_assessor, task_analyzer, task_executor])
            queue.ensure_terminal(self._loop.default_terminal_node)
        elif decision == ReviewerOutcome.OPEN_QUESTION:
            self._loop._on_reviewer_open_question(active_task)
            # Queue behavior: keep ResultReviewer active (Milestone 3.3)
```

### TinyCUALoop Reviewer Handlers (Replacements for Stubs)

```python
class TinyCUALoop(BaseLoop):
    _reviewer_retry_state: ReviewerRetryState  # NEW

    def _on_reviewer_retry(self, active_task: Task) -> None:
        """Handle retry decision: increment retry count, preserve active task.

        If threshold reached, logs a warning. Callers should check
        can_retry() before re-queuing TaskExecutor.

        Args:
            active_task: The active task to preserve (NOT modified here).
        """
        self._reviewer_retry_state.increment()
        if not self._reviewer_retry_state.can_retry():
            self._logger.warning(
                "Retry threshold reached for task %s — no further retries allowed",
                active_task.task_id,
            )

    def _on_reviewer_replan(self, active_task: Task) -> None:
        """Handle replan decision: preserve active task, log event.

        The caller (ResultReviewer.on_complete) handles queue mutation:
        - clear_after_current()
        - spawn TaskAssessor(scope=active_task.region)
        - spawn TaskAnalyzer(mode=local_replan, init_enabled=False)
        - spawn TinyCUATaskExecutorNode
        - ensure_terminal(terminal_node)

        This handler only logs and preserves the active task (by doing nothing
        to it). See ResultReviewer.on_complete (design.md:396-408) for the
        full dispatch implementation.

        Args:
            active_task: The active task to preserve (NOT modified here).
        """
        self._logger.info(f"Replan requested for task {active_task.task_id}")

    def _on_reviewer_open_question(self, active_task: Task) -> None:
        """Handle open_question decision: preserve active task, log event.

        MandatoryPassthrough routing is deferred to Milestone 3.3.
        """
        self._logger.info(
            "open_question for task %s — mandatory_passthrough deferred to Milestone 3.3",
            active_task.task_id,
        )

    def _on_reviewer_accept(self, active_task: Task) -> bool:
        """Handle accept decision: reset retry counter, mark task done.

        Already implemented in Milestone 3.1 (sets active_task.status = 'done').
        Updated in this milestone to also reset the retry counter.
        """
        self._reviewer_retry_state.reset()
        # Existing implementation in Milestone 3.1 handles task status update

    def get_reviewer_retry_state(self) -> ReviewerRetryState:
        """Return the current reviewer retry state."""
        return self._reviewer_retry_state
```

### AnalysisEffortNode._spawn_task_executor (Updated)

```python
def _spawn_task_executor(self, queue: NodeQueue) -> None:
    """Spawn TaskExecutor and ResultReviewer, ensure terminal response path.

    Creates TinyCUATaskExecutorNode and TinyCUAResultReviewerNode,
    spawns them after the current position, ensuring terminal response
    path is maintained.

    Args:
        queue: The node queue to mutate.
    """
    from tinycua.loops.task_executor import TinyCUATaskExecutorNode
    from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode

    task_executor = TinyCUATaskExecutorNode(
        node_id="task_executor", config=self.config,
    )
    result_reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=self.config,
    )
    # Inject loop reference so on_complete can dispatch reviewer decisions
    result_reviewer._loop = self._loop
    queue.spawn_after_current([task_executor, result_reviewer])
    queue.ensure_terminal(self.default_response_node)
```

### WorkerNode._route_proceed_execution (Updated)

```python
def _route_proceed_execution(
    self, queue: NodeQueue, result: DecisionResult,
) -> None:
    """Ensure terminal response path and spawn executor+reviewer.

    Spawns TaskExecutor and ResultReviewer after current position,
    ensuring terminal response path is maintained.

    Args:
        queue: The node queue (may be mutated to spawn executor+reviewer).
        result: The decision result.
    """
    from tinycua.loops.task_executor import TinyCUATaskExecutorNode
    from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode

    queue.clear_after_current()

    task_executor = TinyCUATaskExecutorNode(
        node_id="task_executor", config=self.config,
    )
    result_reviewer = TinyCUAResultReviewerNode(
        node_id="result_reviewer", config=self.config,
    )
    # Inject loop reference so on_complete can dispatch reviewer decisions
    result_reviewer._loop = self._loop
    queue.spawn_after_current([task_executor, result_reviewer])
    queue.ensure_terminal(self.default_response_node)
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| TaskExecutor invoked with no active task | `NodeExecutionError("No active task provided")` | Contract violation — loop must inject active task |
| TaskExecutor LLM call fails | Standard `NodeRetryPolicy` retry | If exhausted, `NodeExecutionError` raised |
| ResultReviewer cannot parse decision | Falls back to `retry` | Prevents infinite replan loops |
| Retry threshold reached | Reviewer must accept or escalate | `_on_reviewer_retry` logs warning |
| Replan but no unfinished tasks found | Skip analyzer, go to TaskExecutor | Per TaskAssessor contract — no code change needed |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

> **⚠️ EXECUTION ORDER**: This checklist is a feature summary grouped by component.
> Do NOT follow it as an execution plan. For TDD-first execution order, see `task.md`
> "TDD Phase (Tests First)" section — tests MUST be written before implementation.

- [x] Create `tinycua/models/reviewer_decision.py` with `ReviewerRetryState` dataclass
- [x] Create `tinycua/loops/task_executor.py` with `TinyCUATaskExecutorNode`
- [x] Create `tinycua/loops/result_reviewer.py` with `TinyCUAResultReviewerNode`
- [x] Update `tinycua/loops/__init__.py` to export new node classes
- [x] Add `_reviewer_retry_state` to `TinyCUALoop.__init__`
- [x] Implement `TinyCUALoop._on_reviewer_retry()` (replace no-op)
- [x] Implement `TinyCUALoop._on_reviewer_replan()` (replace no-op)
- [x] Implement `TinyCUALoop._on_reviewer_open_question()` (replace no-op)
- [x] Update `TinyCUALoop._on_reviewer_accept()` to reset retry counter
- [x] Update `AnalysisEffortNode._spawn_task_executor()` (replace stub)
- [x] Update `WorkerNode._route_proceed_execution()` (replace stub)
- [x] Write unit tests for TaskExecutorNode, ResultReviewerNode, ReviewerRetryState
- [x] Write unit tests for updated loop handlers and spawning logic

### Phase 2 — Enhancements _(post-MVP, only if spec explicitly includes it)_

- None for this milestone. MandatoryPassthrough routing for open_question is deferred to Milestone 3.3.

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Store `ReviewerRetryState` on `TinyCUALoop` rather than on `Session`.
   - **Reason**: Consistent with `root_task` and `_active_task_id` being on the loop. Retry state is execution state, not session data. The loop is the mutation boundary.
   - **Alternatives Considered**: Store on `Session` — rejected because session is a data container that may be serialized; retry state is transient execution state.

2. **Decision**: TaskExecutor is a `ProcessNode` (not a `DecisionNode`).
   - **Reason**: TaskExecutor performs a single LLM call (ReAct execution), not a two-step analysis+classification flow. The LLM call produces an execution result, not a route label. The `ProcessNode` lifecycle (build → validate → LLM → retry → record → propagate) is sufficient.
   - **Alternatives Considered**: DecisionNode — rejected because no classification step is needed; the execution result is the output, not a route label.

3. **Decision**: ResultReviewer is a `ProcessNode` (not a `DecisionNode`).
   - **Reason**: ResultReviewer makes a single decision (accept/retry/replan/open_question) from the LLM output. While it classifies into four outcomes, the classification is embedded in the LLM instruction (not a separate classification call). A single LLM call with structured output is simpler than a two-step flow.
   - **Alternatives Considered**: DecisionNode with two-step classification — rejected for complexity; the reviewer's decision is a single judgment call, not a two-phase analysis.

4. **Decision**: Replan spawns `TaskAssessor + TaskAnalyzer` directly without `AnalysisEffortNode`.
   - **Reason**: The design doc explicitly states "replan MUST NOT spawn AnalysisEffortNode, MUST NOT run Worker-owned effort-gated upfront TaskAnalysisLoop. It is a local execution-time recovery path." Replan is a targeted fix, not a full re-analysis cycle.
   - **Alternatives Considered**: Route through AnalysisEffortNode — rejected per design doc constraint.

5. **Decision**: Use a separate `max_react_iterations` for TaskExecutor ReAct depth, distinct from `NodeRetryPolicy.max_attempts`.
   - **Reason**: `NodeRetryPolicy.max_attempts` controls LLM call retries within a single node invocation (e.g., if the LLM produces invalid output). `max_react_iterations` controls how many tool-call loops occur within a single task execution. These are orthogonal concerns.
   - **Alternatives Considered**: Reuse `NodeRetryPolicy.max_attempts` — rejected because conflating two different retry mechanisms would make tuning impossible.

6. **Decision**: TaskExecutor `on_complete` always advances the queue (ResultReviewer is next in queue).
   - **Reason**: The queue is seeded with `[TaskExecutor, ResultReviewer]` by the spawner. TaskExecutor completing means it's done; the queue advances to ResultReviewer naturally.
   - **Alternatives Considered**: TaskExecutor explicitly spawns ResultReviewer — rejected for unnecessary complexity; the queue already has the correct ordering.

7. **Decision**: `_execute_node` uses `agent._call_llm()` as fallback when `node.config.llm_client` is None (architectural constraint).
   - **Reason**: `SessionConfig` does not set `llm_client` by default. When the loop's `_execute_node` runs a ProcessNode (e.g., TaskExecutor, ResultReviewer) whose config lacks `llm_client`, it falls back to `agent._call_llm()` instead of delegating to `node.__call__()`. This means the node's custom logic (TaskExecutor's ReAct loop, ResultReviewer's decision parsing) is bypassed — the loop performs a plain LLM call and returns raw metadata. A defensive warning log at `tinycua_loop.py:474-480` detects this bypass and emits a warning when a node overrides `ProcessNode.__call__` but the config lacks `llm_client`.
   - **Alternatives Considered**: Inject `llm_client` into all node configs — rejected because spawner nodes (AnalysisEffortNode, WorkerNode) create nodes without `llm_client` by design; the loop-level fallback keeps the execution model simple for standard nodes while allowing advanced nodes to opt into full `__call__` behavior by including `llm_client` on their config.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ReAct loop in TaskExecutor may not converge | Medium | High | `max_react_iterations` cap (default 10); log warning on iteration limit |
| LLM may not produce parseable reviewer decision | Medium | Medium | Fallback to `retry` when decision cannot be parsed; log warning |
| Retry threshold too aggressive for complex tasks | Low | Medium | Configurable threshold via `ReviewerRetryState`; document tuning guidance |
| Replan path spawns assessor but no tasks selected | Low | Low | Per TaskAssessor contract: if no tasks selected, skip analyzer, go to executor |
| Worker._route_proceed_execution stub replacement breaks existing tests | Low | Medium | Run full test suite after replacement; ensure backward compatibility |
| TaskExecutor mutates active task (contract violation) | Low | High | Enforce read-only access pattern; unit test verifies task is not mutated |
| `_execute_node` fallback bypasses node custom logic when `llm_client` is None | Medium | Medium | Warning log at `tinycua_loop.py:474-480` detects bypass; documented as intentional architectural constraint (Decision #7). Nodes that require custom logic should include `llm_client` on their config. |

---

## Open Questions _(optional)_

1. **TaskExecutor tool execution model**: Should TaskExecutor use the SDK's tool execution pipeline (agent._call_llm with tools) or a custom ReAct loop?
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Resolution**: Use the SDK's tool execution pipeline via `agent._call_llm(messages, tools)` which handles tool call dispatch and result accumulation. TaskExecutor builds the messages and tools, calls the agent, and interprets the final result. This avoids duplicating tool execution logic.

2. **ResultReviewer decision parsing**: Should the reviewer use a tool call (structured output) or free-text parsing to extract the decision?
   - **Owner**: @VJyzCELERY
   - **Status**: Resolved
   - **Resolution**: Use free-text parsing with word-boundary matching (consistent with DecisionNode classification pattern). The LLM is instructed to respond with exactly one of: accept, retry, replan, open_question. Fallback to retry on parse failure.

---

## References

- Spec: `./spec.md`
- Design docs:
  - `src/tinycua/docs/design/loops/task_executor.md` — TaskExecutor node architecture
  - `src/tinycua/docs/design/loops/result_reviewer.md` — ResultReviewer node architecture
  - `src/tinycua/docs/design/models/reviewer_decision.md` — ReviewerDecision model
  - `src/tinycua/docs/design/loops/tinycua_loop.md` — TinyCUALoop execution flow
  - `src/tinycua/docs/design/models/task.md` — Task model and active task handoff protocol
- Existing specs:
  - `specs/tinycua-task-lifecycle/spec.md` — Task lifecycle models (completed, Milestone 3.1)
  - `specs/tinycua-task-analyzer/spec.md` — TaskAnalyzerNode (completed, Milestone 2.6)
- Issue: [#87](https://github.com/VJyzCELERY/TINYCUA/issues/87) — Milestone 3.2
