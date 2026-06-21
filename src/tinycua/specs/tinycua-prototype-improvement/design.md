# Design Document: TinyCUA Prototype Improvement

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-21

---

## Overview

This redesign hardens the TinyCUA research prototype along four axes motivated by the five-experiment evaluation (`src/experiment/evaluation-results/report.md`): it introduces a single declarative `NodeContract` (replacing 13+ scattered required-tool maps), makes node state observable via a `NodeState` enum + `NodeProgress` tracker, replaces the 5-stage retry-forcing escalation with a 2-track system (provider structured output for LLM-decided transitions, deterministic synthesis for no-arg tools), adds task-tree delete/merge so the TaskAnalyzer can correct over-decomposition mid-run, and hardens the experiment-evidenced tool failures (raw HTML fetch, `/bin/sh` venv mismatch, workspace path normalization). The key architectural decision is: **LLM-decided exits stay LLM-decided** — the runtime never synthesizes a tool call whose arguments carry LLM-provided content; it only synthesizes no-arg tools (terminate).

---

## Architecture

### Component Overview

```
                         ┌─────────────────────────────────────────────┐
                         │              TinyCUALoop                     │
                         │   (loop-owned retry — the single path)      │
                         └───────────────┬─────────────────────────────┘
                                         │
              ┌──────────────────────────┴───────────────────────────┐
              │                     Node                             │
              │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
              │  │ NodeState   │  │ NodeProgress │  │ NodeContract │  │
              │  │ (enum)     │  │ (tracker)   │  │ (declarative)│  │
              │  └─────────────┘  └──────────────┘  └──────────────┘  │
              └──────────────────────────┬───────────────────────────┘
                                         │
              ┌──────────────────────────┴───────────────────────────┐
              │            Retry (2-track, unbounded)                │
              │                                                     │
              │  Structured-output track      Deterministic track    │
              │  (LLM-decided transitions)    (no-arg tools)         │
              │  response_format: json_schema  _direct_terminate     │
              │  → validate → retry w/error    (synthesize)          │
              │  (no _judge_retry)                                  │
              └─────────────────────────────────────────────────────┘
                                         │
              ┌──────────────────────────┴───────────────────────────┐
              │                 Tools (hardened)                     │
              │  fetch_url (markdown)  run_shell (venv/bash)         │
              │  web_search (retry)   context.py (raise-if-unset)    │
              │  task_tools (coercion) todo_tools (real ops)         │
              │  TaskStateStore (delete/merge)  ToolResult envelope   │
              └─────────────────────────────────────────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `loops/node.py` | Modified | Add `NodeState`, `NodeProgress`; remove dormant `ProcessNode.__call__`/`DecisionNode.__call__` retry loops, `_call_failure_route`, `Node.propagate` no-op |
| `loops/validation_retry_mixin.py` | Modified | Remove `_judge_retry`, `_route_task_executor_failure_to_reviewer` stub, `_validate_tool_owned_task_state`'s inline maps; consult `NodeContract` |
| `loops/orchestration_mixin.py` | Modified | Replace `_unbounded_recovery`'s 5-stage escalation with 2-track; remove `_log_recovery_cycle` `print(stderr)`; consult `NodeContract` for `_RECOVERY_CHAINS` |
| `loops/prompt_protocol_mixin.py` | Modified | Remove `_required_single_tool_choice_name`, `_missing_or_required_tool_name`, `_requires_any_tool_choice`; consult `NodeContract` |
| `loops/recovery_stages_mixin.py` | Modified | Remove `_judge_retry` (the whole file likely deleted) |
| `loops/worker_runtime.py` | Modified | Remove commented `OPEN_QUESTION` branch + `ResponseNode` `noqa` import |
| `config/node_config.py` | Modified | Remove inline `required_tool_calls` overrides; build `NodeContract` per node |
| `config/types.py` | Modified | `Tool.invoke` delegates to SDK coercion for class-based tools |
| `models/task.py` | Modified | Add `delete_task`, `merge_tasks` to `TaskStateStore` |
| `tools/task_tools.py` | Modified | Add `task_shrink` tool; remove `TaskReviewDecisionTool` default-approve; fix `TaskUpdateTool` `additionalProperties` |
| `tools/todo_tools.py` | Modified | Real update-in-place, delete, status transitions |
| `agent/tools/native/web.py` | Modified | markdown conversion, Content-Type guard, UA, retry, consistent dict |
| `agent/tools/native/web_search.py` | Modified | backend-down vs no-matches, retry/backoff |
| `agent/tools/native/shell.py` | Modified | venv param, executable param, env passthrough, shell context in result |
| `agent/tools/native/context.py` | Modified | drop cwd fallback (raise), re-root absolute paths, workspace-relative reporting |
| `agent/tools/native/files.py` | Modified | assert workspace bound at session start |
| `agent/tools/native/python_exec.py` | Modified | reject >max with error, not silent clamp |
| `agent/tools/native/output_persist.py` | Modified | remove duplicate `print` |
| `tools/enhanced_context_retrieval.py` | Modified | fix index math, cache cap + eviction |
| `loops/tinycua_loop.py` | Modified | structured-output payload construction; tool coercion via SDK |
| `loops/trace_state_mixin.py` | Modified | emit `node_state_transition` + `task_tree_shrink` events |
| (new) `loops/node_contract.py` | New | `NodeContract` dataclass + per-node registry |
| (new) `agent/tools/native/tool_result.py` | New | `ToolResult` envelope dataclass |

---

## Data Model

### New Entities

```python
# Conceptual data shape (not necessarily the final class)

class NodeState(StrEnum):
    PENDING = "pending"
    EXECUTING = "executing"
    AWAITING_TOOL = "awaiting_tool"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class NodeProgress:
    """Per-node runtime tracking. Lives on the Node instance."""
    phase: NodeState = NodeState.PENDING
    attempt_count: int = 0
    visited_tools: set[str] = field(default_factory=set)  # tool names called
    satisfied_requirements: set[str] = field(default_factory=set)  # required tools satisfied
    history: list[dict[str, Any]] = field(default_factory=list)  # state transitions

    def transition(self, to: NodeState, reason: str) -> None:
        self.history.append({"from": self.phase, "to": to, "reason": reason,
                             "attempt": self.attempt_count})
        self.phase = to

@dataclass(frozen=True)
class NodeContract:
    """Single declarative source of truth for a node's tool/state contract.
    Replaces the 13+ scattered required-tool maps. One per node_id."""
    node_id: str
    required_tools: frozenset[str]              # ALL must be called successfully
    any_of_tools: frozenset[frozenset[str]]     # one set of which must be satisfied
    deterministic_tools: frozenset[str]        # no-arg tools the runtime may synthesize
    structured_output_schema: dict[str, Any] | None  # json_schema for response_format, or None for free-text
    retry_max_attempts: int | None             # None = unbounded (the default)

@dataclass
class ToolResult:
    """Envelope for all tool returns. Replaces per-tool ad-hoc dict shapes."""
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

class WorkspaceNotBoundError(RuntimeError):
    """Raised when a tool resolves a path but the workspace ContextVar is unset."""
```

### Schema Changes

- **`TaskStateStore`**: add `delete_task(task_id) -> None` (raises on completed) and `merge_tasks(child_id, parent_id) -> Task` (preserves child result on parent if parent has none). Both bump `version`.
- **`Node`**: add `progress: NodeProgress` field; add `contract: NodeContract` property (looked up from the registry by `node_id`).
- **`Task`**: no schema change — existing fields suffice; `delete_task` removes the entry + re-links siblings; `merge_tasks` moves `result`/`reviewer_decisions` to parent if applicable.
- **No migration** — the task store is session-local and ephemeral (in-memory dict); no persistent data to migrate.

---

## API / Interface Contracts

### New / Modified Functions

```python
# TaskStateStore.delete_task — new
def delete_task(self, task_id: str) -> None:
    """Remove a task and its pending subtree, re-link siblings, bump version.
    Raises ValueError if the task is COMPLETED (immutable) or not found.
    If the task is the active_task or root_task, raise (cannot shrink the root).
    """

# TaskStateStore.merge_tasks — new
def merge_tasks(self, child_id: str, parent_id: str) -> Task:
    """Collapse a child into its parent.
    - If child has a result and parent does not: parent.result = child.result.
    - If both have results: parent.result.summary += "\\n\\nMerged from <child>: " + child.result.summary.
    - Child's pending subtree is discarded.
    - Child is removed from parent.children.
    - Bumps version.
    Raises ValueError if child == parent, or either is COMPLETED.
    Returns the updated parent.
    """

# resolve_workspace_path — modified
def resolve_workspace_path(path: str) -> Path:
    """Resolve a path under the canonical workspace root.
    Raises WorkspaceNotBoundError if _WORKSPACE_DIR is unset (no cwd fallback).
    Re-roots absolute paths that match a workspace subpath.
    """

# NodeContract registry — new
_NODE_CONTRACTS: dict[str, NodeContract] = {
    "task_create": NodeContract(
        node_id="task_create",
        required_tools=frozenset({"task_init"}),
        any_of_tools=frozenset(),
        deterministic_tools=frozenset({"terminate"}),
        structured_output_schema=type_to_json_schema(TaskInitInput),  # from tool type hints
        retry_max_attempts=None,  # unbounded
    ),
    "task_executor": NodeContract(
        node_id="task_executor",
        required_tools=frozenset({"task_result_update"}),
        any_of_tools=frozenset(),
        deterministic_tools=frozenset({"terminate"}),
        structured_output_schema=type_to_json_schema(TaskResultUpdateInput),
        retry_max_attempts=None,
    ),
    "result_reviewer": NodeContract(
        node_id="result_reviewer",
        required_tools=frozenset({"task_review_decision"}),
        any_of_tools=frozenset(),
        deterministic_tools=frozenset({"terminate"}),
        structured_output_schema=type_to_json_schema(TaskReviewDecisionInput),
        retry_max_attempts=None,
    ),
    # ... task_analyzer (any_of {task_decompose, task_update} + task_shrink),
    # ... task_assessor (required node_handoff), query_analyst/worker (free-text, None schema)
}

# fetch_url — modified
def fetch_url(url: str, method: str = "GET", headers: dict | None = None,
              timeout: int = 30, max_size: int = 102400) -> ToolResult:
    """Returns ToolResult(success, output=markdown_str | None, error, metadata={url, content_type, status}).
    Converts HTML→markdown via html2text. Refuses binary. Retries 429/5xx (max 3)."""

# run_shell — modified
def run_shell(command: str, *, timeout: int = 120, venv: str | None = None,
               executable: str = "/bin/sh", env: dict[str, str] | None = None,
               workspace: str | None = None) -> ToolResult:
    """Returns ToolResult(success, output=stdout, error, metadata={exit_code, cwd, shell, venv_active}).
    If venv set, prepends activation. If executable requested but missing, falls back + warns."""
```

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Workspace ContextVar unset | `WorkspaceNotBoundError` | Tool raises; CLI/session must bind before first call |
| `delete_task` on COMPLETED | `ValueError("Task <id> is completed and immutable")` | Consistent with existing decompose guard |
| `delete_task` on root/active | `ValueError("Cannot shrink root or active task")` | Runtime integrity |
| `merge_tasks(child == parent)` | `ValueError("Cannot merge a task into itself")` | |
| `fetch_url` binary Content-Type | `ToolResult(success=False, error="binary content-type ... not supported")` | |
| `run_shell` bash requested but not installed | `ToolResult(success=True, output=..., metadata={shell: "/bin/sh", warning: "bash not found, fell back"})` | |
| Structured-output schema invalid | Retry with schema error in prompt (unbounded) | FR-011; no `_judge_retry` |

---

## Implementation Phases

### Phase 1 — Code Cleanup + Stateful Nodes (Milestones 1-2)

- [ ] Add `NodeState` enum + `NodeProgress` dataclass to `loops/node.py`
- [ ] Add `NodeContract` dataclass + registry to (new) `loops/node_contract.py`; populate from existing 13+ maps
- [ ] Wire `Node.progress` + `Node.contract`; emit `node_state_transition` trace events
- [ ] Remove dormant `ProcessNode.__call__`/`DecisionNode.__call__` retry loops
- [ ] Remove stubs: `_route_task_executor_failure_to_reviewer`, `_requires_any_tool_choice`, `_call_failure_route`, `OPEN_QUESTION` branch + `ResponseNode` import
- [ ] Replace `_log_recovery_cycle` `print(stderr)` with `logger`
- [ ] Remove duplicate `print` in `output_persist.py:338`
- [ ] Replace all inline required-tool maps with `NodeContract` lookups

### Phase 2 — Retry Redesign (Milestone 3)

- [ ] Add structured-output track to `_unbounded_recovery`: build `response_format` from `NodeContract.structured_output_schema`
- [ ] Remove `_judge_retry` (delete `recovery_stages_mixin.py` or its content)
- [ ] Merge `_tightening_retry` into structured-output track
- [ ] Keep deterministic track (`_direct_terminate`, `_coerce_terminate_only_response`)
- [ ] Add FR-015 "stuck model" diagnostic after >10 consecutive schema failures (observability, not a bound)
- [ ] Enable structured output per-node in `tinycua_loop._call_agent_llm` based on `NodeContract`

### Phase 3 — Task Tree Shrink (Milestone 4)

- [ ] Add `TaskStateStore.delete_task` + `TaskStateStore.merge_tasks`
- [ ] Add `task_shrink` tool (delete + merge with rationale)
- [ ] Add effort-profiled threshold (low effort → >15, high effort → >8) to TaskAnalyzer continuation
- [ ] Emit `task_tree_shrink` trace events

### Phase 4 — Tool Hardening — Experiment-Evidenced (Milestone 5)

- [ ] `fetch_url`: add `html2text` dep, markdown conversion, Content-Type guard, UA, retry, `ToolResult` shape
- [ ] `web_search`: backend-down vs no-matches, retry/backoff
- [ ] `run_shell`: venv param, executable param, env passthrough, shell context in result
- [ ] `context.py`: drop cwd fallback (raise), re-root absolute paths, workspace-relative reporting
- [ ] `files.py`: assert workspace bound at session start

### Phase 5 — Tool Hardening — Other Tools (Milestone 6)

- [ ] Route class-based tools through SDK coercion (`config/types.py:Tool.invoke`)
- [ ] `TaskReviewDecisionTool`: make `decision` required
- [ ] `TaskUpdateTool`: remove `additionalProperties: True` for metadata
- [ ] `enhanced_context_retrieval`: fix index math, cache cap + LRU eviction
- [ ] `python_exec`: reject >max with error
- [ ] `todo_tools`: real update-in-place, delete, status transitions
- [ ] Introduce `ToolResult` envelope; all tools return it

### Phase 6 — Logging (Milestone 7)

- [ ] Replace remaining `print(stderr)` with `logger` (ties into Phase 1)
- [ ] Emit structured trace events: node state transition, retry with schema error, tool call with result shape, recovery cycle, task-tree shrink
- [ ] Make retry/recovery observable without reading stderr

> **Note**: Phases 3, 4, 5 are largely independent and can be parallelized. Phase 2 depends on Phase 1 (NodeContract). Phase 6 threads through all.

---

## Technical Decisions

1. **Decision**: Use provider structured output (`response_format: json_schema`) for LLM-decided transitions, not free-text markdown parsing.
   - **Reason**: The design docs explicitly reject untrusted string parsing (`state_object.md`: "no untrusted string parsing for internal transport"). Structured output via the API keeps the typed contract — the LLM emits JSON validated against a schema, not prose we regex-parse. Local models are unreliable at markdown adherence too; json_schema is a harder constraint via the API.
   - **Alternatives Considered**: (a) Free-text markdown blocks parsed into typed payloads — rejected because it conflicts with the no-string-parsing invariant and local models struggle with markdown schemas as much as tool calls. (b) Keep tool-call forcing but reduce stages — rejected because it doesn't address the root cause (local models ignoring `tool_choice="required"`).

2. **Decision**: Keep the unbounded retry loop; remove `_judge_retry` only.
   - **Reason**: The zero-exit, one-shot, no-HITL guarantee requires that a node completes its state. Bounding the loop would violate this. But `_judge_retry` (LLM judge produces the call, runtime injects) takes the decision away from the executing LLM — it violates "LLM-decided exits stay LLM-decided." The structured-output track replaces it: the LLM retries with the schema error, staying the decider.
   - **Alternatives Considered**: Bound the loop at N — rejected (violates zero-exit). Keep `_judge_retry` as a last resort — rejected (violates LLM-decides philosophy).

3. **Decision**: Deterministic synthesis only for no-arg tools (terminate).
   - **Reason**: Synthesizing a tool call with LLM-provided arguments steals the LLM's decision. Terminate takes no parameters — synthesizing it is not stealing a decision, just closing the node. This is the bright line.
   - **Alternatives Considered**: Allow synthesis for low-stakes tools — rejected (the bright line is arg-presence, not stakes).

4. **Decision**: Task-shrink threshold is effort-profiled + LLM-decided (no hard pruning).
   - **Reason**: Hard pruning would lose work and violates "preserve work" (your answer 2). Effort-profiled threshold (low effort → high threshold, high effort → low) nudges the analyzer to be more proactive at higher effort without forcing cuts. The LLM decides what to merge/delete.
   - **Alternatives Considered**: Fixed threshold — rejected (doesn't adapt to task complexity). Pure LLM-decided with no threshold — rejected (the analyzer won't proactively shrink without a trigger).

5. **Decision**: Add `html2text` dependency for fetch_url markdown conversion.
   - **Reason**: Raw HTML is unusable for the model (experiment-2 evidence). Stdlib tag-stripping loses structure (tables, code blocks, lists). `html2text` is small, maintained, handles tables/code/lists.
   - **Alternatives Considered**: stdlib heuristic (strip tags, keep text) — rejected (loses structure the model needs).

6. **Decision**: `WorkspaceNotBoundError` raises instead of cwd fallback.
   - **Reason**: The cwd fallback (`context.py:50-51`) is the root cause of the experiment-4 path mismatch. Silently using `Path.cwd()` (the tinycua process cwd, unrelated to the experiment worktree) produces wrong-path checks. Raising forces the session/CLI to bind explicitly.
   - **Alternatives Considered**: Keep fallback + add a warning — rejected (the model can't see warnings in tool results; a hard error is clearer).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Local models produce invalid JSON even with `json_schema` | Med | Med | Retry with schema error (unbounded) + FR-015 stuck-model diagnostic for observability. The structured-output constraint is harder than free-text, so failure rate should drop vs today's tool-call forcing. |
| `html2text` adds a dependency that breaks in Docker | Low | Med | Pin version in `pyproject.toml`; add to Docker image build; test in CI. |
| Removing dormant `ProcessNode.__call__` breaks a non-loop-owned caller | Low | High | Grep for `.run(` / `.__call__(` callers before removal; the loop-owned path is the active one (`_call_node_with_retry`). |
| `delete_task` on the active task crashes the runtime | Med | High | Guard: refuse to delete root or active task (FR-023); the analyzer must transition the task away from active first. |
| Structured output changes break the eval harness config | Med | Med | The eval ran with structured output disabled (`report.md:38`); re-enabling per-node is a config change documented in the spec. Verify with a tinycua-only re-run. |
| Task-shrink loses work the model needed later | Low | Med | "Preserve work" rule (merge keeps results); completed tasks are immutable; only pending subtrees are discardable. |
| Effort-profiled threshold values are wrong (too aggressive/conservative) | Med | Low | Make thresholds configurable in `node_config.py`; tune after the experiment-5 re-run. |

---

## Open Questions

1. **`task_shrink` tool scope**: should it be available to `task_analyzer` only, or also to `result_reviewer` (e.g. when the reviewer sees a hopelessly over-decomposed tree and decides to replan + shrink)?
   - **Current thinking**: `task_analyzer` only — the analyzer owns tree structure. The reviewer can `replan` which routes back to the analyzer, which then shrinks. Keeps ownership clear.

---

## References

- Spec: `./spec.md`
- Predecessor spec: `src/tinycua/specs/tinycua-runtime-performance-hardening/spec.md` (Phase 1-4 hardening, In Progress)
- Upstream constraints: `src/tinycua/specs/tinycua-runtime-invariants/spec.md`, `src/tinycua/specs/tinycua-finalize-prototype-runtime/spec.md`
- Evaluation evidence: `src/experiment/evaluation-results/report.md`
- SDK structured-output capability: `src/tinycua-sdk/tinycua_sdk/providers/open_ai_chat_completions.py:104`, `src/tinycua-sdk/tinycua_sdk/agent/llm_model.py:43`, `src/tinycua-sdk/tinycua_sdk/tools/schema.py:14`
- Tool analysis (deep-dive): the four explore-agent reports in this session's context.