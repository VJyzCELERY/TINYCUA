# Design Document: TinyCUA Prototype Improvement

**Spec**: `./spec.md`
**Status**: Draft
**Last Updated**: 2026-06-22

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
| `loops/validation_retry_mixin.py` | Modified | Remove `_judge_retry`, `_route_task_executor_failure_to_reviewer` stub, `_validate_tool_owned_task_state`'s inline maps; consult `NodeContract`; **M8**: rephrase `_validate_result_reviewer_inspects_after_decision` error to not contain `task_review_decision` substring |
| `loops/orchestration_mixin.py` | Modified | Replace `_unbounded_recovery`'s 5-stage escalation with 2-track; remove `_log_recovery_cycle` `print(stderr)`; consult `NodeContract` for `_RECOVERY_CHAINS` |
| `loops/prompt_protocol_mixin.py` | Modified | Remove `_required_single_tool_choice_name`, `_missing_or_required_tool_name`, `_requires_any_tool_choice`; consult `NodeContract`; **M8**: add `task_inspect` to `_missing_or_required_tool_name` candidate tuple before `task_review_decision` |
| `loops/recovery_stages_mixin.py` | Modified | Remove `_judge_retry` (the whole file likely deleted) |
| `loops/worker_runtime.py` | Modified | Remove commented `OPEN_QUESTION` branch + `ResponseNode` `noqa` import; **M8**: reset `consecutive_failures` on replan via boundary marker, cap replans per task via `max_replans` effort mapping, force-approve at cap |
| `config/node_config.py` | Modified | Remove inline `required_tool_calls` overrides; build `NodeContract` per node; **M8**: raise `task_analyzer` `max_attempts` from 3 to 10 |
| `config/session_config.py` | Modified | **M8**: add `max_replans: int \| None` field (derived from `worker_effort` when None: `none=0, low=1, medium=3, high=6`) |
| `models/task.py` | Modified | Add `delete_task`, `merge_tasks` to `TaskStateStore`; **M8**: `consecutive_failures` breaks on `replan_boundary` entries |
| `tools/task_tools.py` | Modified | Add `task_shrink` tool; remove `TaskReviewDecisionTool` default-approve; fix `TaskUpdateTool` `additionalProperties`; **M8**: document `rejected` as alias for `needs_revision` in `TaskReviewDecisionTool` description |
| `tools/todo_tools.py` | Modified | Real update-in-place, delete, status transitions |
| `agent/tools/native/web.py` | Modified | markdown conversion, Content-Type guard, UA, retry, consistent dict |
| `agent/tools/native/web_search.py` | Modified | backend-down vs no-matches, retry/backoff |
| `agent/tools/native/shell.py` | Modified | venv param, executable param, env passthrough, shell context in result |
| `agent/tools/native/context.py` | Modified | drop cwd fallback (raise), re-root absolute paths, workspace-relative reporting |
| `agent/tools/native/files.py` | Modified | assert workspace bound at session start; **M8**: `str_replace` distinguishes zero-match vs multi-match errors; `append_file`/`write_file`/`str_replace` return `diff_preview` + `new_file_size` |
| `agent/tools/native/python_exec.py` | Modified | reject >max with error, not silent clamp |
| `agent/tools/native/output_persist.py` | Modified | remove duplicate `print` |
| `tools/enhanced_context_retrieval.py` | Modified | fix index math, cache cap + eviction |
| `loops/tinycua_loop.py` | Modified | structured-output payload construction; tool coercion via SDK |
| `loops/task_nodes.py` | Modified | **M8**: analyzer instruction adds `terminate` call, drops `task_inspect`-first trap; analyzer `on_complete` skips queued executor when `plan_unchanged` metadata is set; reviewer instruction adds general sanity-checker responsibility; `build_tool_system_prompt` adds dedup guidance; `local_replan` analyzer mode prompt mentions `task_shrink` option + `plan_unchanged` signal |
| `loops/trace_state_mixin.py` | Modified | emit `node_state_transition` + `task_tree_shrink` events |
| (new) `loops/node_contract.py` | New | `NodeContract` dataclass + per-node registry |
| (new) `agent/tools/native/tool_result.py` | New | `ToolResult` envelope dataclass |
| `cli/run.py` | Modified | **M9**: wire `compaction_strategy=SimpleCompaction()` into `_build_run_agent` SessionConfig (FR-082); call `resolve_max_context` at startup and pass resolved `max_context` into `build_language_model` (FR-084) |
| `cli/config.py` | Modified | **M9**: `build_language_model` accepts optional `max_context: int \| None` and passes it to `LanguageModel(max_context=...)` (FR-084) |
| `cli/main.py` | Modified | **M9**: add `--max-context` argparse flag (FR-084) |
| (new) `cli/model_probe.py` | New | **M9**: `resolve_max_context(base_url, api_key, model_name, fallback) -> int` — best-effort `GET /v1/models` probe, silent fallback on any failure (FR-084) |
| `loops/node.py` | Modified | **M9**: `build_messages_with_dedupe` bounds `session_context` entries sent to the LLM to the last `max_context_messages` (FR-083); full `session_context` list never mutated |
| `loops/tinycua_loop.py` | Modified | **M9**: move `_maybe_compact` call to top of attempt loop (continuous monitoring, FR-085); promote compaction trigger/failure log lines from DEBUG to INFO (FR-085) |

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

### Phase 7 — Loop Reliability (Milestone 8)

- [ ] **Reset failure baseline on replan**: `schedule_replan` inserts a synthetic `{"decision": "replan_boundary"}` entry into `reviewer_decisions`; `consecutive_failures` breaks on `replan_boundary` (not just `approved`)
- [ ] **Cap replans per task**: add `max_replans` to `SessionConfig` (derived from `worker_effort`: `none=0, low=1, medium=3, high=6`); in `schedule_after_review`, when `replan_count >= max_replans`, force-approve with "replan budget exhausted" rationale instead of queueing another replan
- [ ] **Non-vacuous replan**: when the analyzer confirms `plan_unchanged` (via `task_update` metadata), the analyzer's `on_complete` removes the queued executor — the plan did not change, re-execution would duplicate work. The reviewer is kept to re-judge the existing result. The analyzer MAY call `task_shrink` to restructure instead
- [ ] **`str_replace` error fix**: distinguish zero-match from multi-match in `_fuzzy_find_and_replace`; return `"Found N matches..."` when >1 matches and `replace_all=False`
- [ ] **Reviewer missing-tool heuristic fix**: rephrase `_validate_result_reviewer_inspects_after_decision` error to not contain `task_review_decision`; add `task_inspect` to `_missing_or_required_tool_name` candidates
- [ ] **Analyzer prompt fix**: add "after `task_decompose`/`task_update` succeeds, call `terminate`"; remove `task_inspect`-first instruction from continuation
- [ ] **Analyzer `max_attempts`**: raise from 3 to 10
- [ ] **Reviewer sanity-checker**: add general LLM-mess detection responsibility to reviewer instruction (dedup, hallucination, structural inconsistency) — prompt-only, generic across artifact types
- [ ] **Unify `needs_revision`/`rejected`**: document `rejected` as alias in `TaskReviewDecisionTool` description; both share the same routing path
- [ ] **File-tool diff/preview**: `append_file`/`write_file` return `diff_preview` + `new_file_size`; `str_replace` returns a real unified-diff snippet

### Phase 8 — Context Window Protection (Milestone 9 — Hotfix)

Hotfix for the experiment-5 context-overflow failure. Four independent fixes; A+B+C+D compose to bound the prompt to the real served context window.

- [ ] **A. Wire compaction into the CLI run path (FR-082)**: `cli/run.py` `_build_run_agent` adds `compaction_strategy=SimpleCompaction()` to the `SessionConfig`. The factory's compaction-wired default was bypassed because the CLI passed a non-None config without the strategy — making `_maybe_compact`/`compact_context` dead code on the production path.
- [ ] **B. Enforce `max_context_messages` cap (FR-083)**: `loops/node.py` `build_messages_with_dedupe` slices `context_entries` to `[-max_context_messages:]` before converting to messages. The full `session_context` list (audit trail) is never mutated — only the prompt-bound subset is capped. When compaction fires, the windowed entries are folded into a summary via `compact_context` before the cap applies. `None` = unlimited.
- [ ] **C. Probe server for real `max_context` (FR-084)**: new `cli/model_probe.py` with `resolve_max_context(base_url, api_key, model_name, fallback) -> int`. Probes `GET {base_url}/v1/models` once at startup; LM Studio/Ollama expose `context_length` per model. Resolution: (1) explicit `--max-context` CLI flag, (2) server-reported `context_length`, (3) SDK default `128_000`. Best-effort — any failure falls back silently. The compaction threshold (`compaction_threshold * max_context`, float 0-1 default 0.7) then tracks the real wall.
- [ ] **D. Continuous monitoring + INFO logs (FR-085)**: `loops/tinycua_loop.py` moves the `_maybe_compact` call from `if attempt > 1` to the top of the attempt loop (runs on attempt 1 too, gated on `_last_input_tokens > 0`). Promotes the `compaction_trigger` and `compaction_failed` log lines from DEBUG to INFO so they surface in real experiment logs.

> **Note**: Phase 8 fixes are independent of Phases 1-7 and can be implemented in parallel. A+B are the minimum to stop the bleed; C makes the threshold meaningful; D adds continuous monitoring + observability. All four ship together as the hotfix.

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

7. **Decision**: Planning/review nodes explore before their role duty; digested context travels with the mission as `{context}\n{query}`.
   - **Reason**: Experiment-2 showed the 9B model anchored on "2024-2025" when scoping a "current frontier LLMs" research task, despite seeing `Today: 2026-06-21` in the system prompt. Two root causes: (a) the TaskAnalyzer's instruction forbade exploration ("Do not execute work here"), so it decomposed from training-data priors; (b) the InformationDigester's comprehensive research was dropped — only `original_query + constraints` reached the mission block, so the analyzer had no first-layer findings to ground its decomposition. The fix: all non-decision nodes get permissive, role-scoped exploration framing (analyzer explores to scope tasks, assessor to verify the roadmap, reviewer to verify claims, aggregation to verify task results, executor before making changes); the digester's `context_summary + key_points` are stored on the root task and rendered by `_render_mission_block` as a structured `{context}\n{query}` block so every downstream node sees the first-layer exploration findings. The execution boundary is preserved structurally — `EXPLORATORY_AGENT_TOOLS` has no write tools, so planning/review nodes still cannot produce the deliverable. Exploration is bounded by the soft "2-4 searches" hint in the digester + the `_MAX_TOOL_CONTINUATIONS=6` loop cap + the 3s `web_search` rate limit.
   - **Alternatives Considered**: (a) Prescriptive "use 2026 in queries" directive in the system prompt — rejected (too rigid, doesn't generalize, the user explicitly wanted a behavior not a hardcoded year). (b) Let only the analyzer search — rejected (the assessor and reviewer also benefit from exploring their respective concerns; exploration is a universal non-eager behavior). (c) Carry the full `session_context` (audit trail) into LLM messages — rejected (it's an audit trail, not LLM-reusable; the mission block is the right vehicle for first-layer findings). (d) Keep the digester's research in `session_context` only and give the analyzer `enhanced_context_retrieval` — rejected (the analyzer's role is planning, not context retrieval; the mission block already travels to every node that needs it, no extra tool needed).

8. **Decision**: Reset `consecutive_failures` on replan via a synthetic `replan_boundary` entry in `reviewer_decisions`, not a dedicated counter field.
   - **Reason**: The derived `consecutive_failures` property (`models/task.py:113-133`) already walks `reviewer_decisions` backwards and breaks on `approved`. Adding a `replan_boundary` sentinel and breaking on it too keeps the audit trail as the single source of truth — no separate counter to keep in sync, no dataclass migration. The full decision history (including the boundary markers) stays observable.
   - **Alternatives Considered**: (a) A dedicated `replans_per_task: int` field incremented by `schedule_replan` — rejected (duplicates the audit trail, needs a dataclass migration, can drift). (b) Truncate `reviewer_decisions` on replan — rejected (loses audit history, violates observability).

9. **Decision**: Cap replans per task via an effort-profiled `max_replans` (`none=0, low=1, medium=3, high=6`); at cap, force-approve with "replan budget exhausted" rationale.
   - **Reason**: Experiment-2 showed the replan loop climb 5→7→9 with threshold 5 and no backstop — the same task was re-executed 5+ times, re-researching and re-appending duplicate content, for 45 minutes. A cap bounds the loop without violating the zero-exit guarantee (the task still completes, just with a note that the replan budget was exhausted). Effort-profiled mapping mirrors the existing `analysis_effort` pass-limit pattern (`task_nodes.py:1104`: `none=0, low=1, medium=2, high=3`) — higher effort allows more replans. Force-approve (not fail-the-task) keeps the run producing output.
   - **Alternatives Considered**: (a) Fixed cap regardless of effort — rejected (doesn't adapt to task complexity; a high-effort research task may legitimately need more replans than a low-effort one). (b) Fail the task at cap — rejected (strict; aborts the run in strict mode; the user preferred force-approve so the experiment still produces output). (c) No cap, rely on the model to eventually approve — rejected (experiment-2 evidence: the model kept rejecting for 5+ cycles).

10. **Decision**: Make replans non-vacuous via a `plan_unchanged` signal; the analyzer MAY `task_shrink` instead.
   - **Reason**: `decompose_task` is idempotent on a parent with existing children (`models/task.py:195-209`) — it silently returns the existing children and discards the analyzer's new subtasks. So a replan that routes to the analyzer and then back to the executor reruns the same task, re-researches, and re-appends content. The `plan_unchanged` metadata flag (set by `task_update` when the analyzer confirms the existing plan) lets `schedule_replan` skip the executor re-run. When the plan IS wrong, the analyzer can `task_shrink` (delete/merge unfinished tasks — completed tasks are immutable per FR-023) to actually restructure. Making `task_shrink` required was rejected — it should be an option, not a mandate.
   - **Alternatives Considered**: (a) Require `task_shrink` on every replan after the first — rejected (too rigid; the plan may be correct and only execution was flawed). (b) Make `decompose_task` non-idempotent (overwrite existing children) — rejected (would lose the existing plan's progress and completed children).

11. **Decision**: Reviewer as a general sanity-checker for LLM messes — prompt-only, generic across artifact types.
   - **Reason**: Experiment-2's duplicated 100KB report (8+ "## Conclusion"/"## Key Insights" sections, SWE-bench mentioned 76 times) was a structural mess the reviewer could have caught but wasn't told to look for. Hardcoding "report structure" rules would be too specific (the reviewer also reviews code, data, anything). A generic responsibility — detect duplicate/repeated content (grep/wc/sort|uniq), hallucinated claims (verify entities), structural inconsistency (claimed N sections but has M) — lets the reviewer LLM decide which checks apply based on the artifact type. Prompt-only keeps it adaptable; a deterministic pre-check was rejected for coupling the reviewer to file-artifact assumptions.
   - **Alternatives Considered**: (a) Deterministic pre-check in `_reviewer_context_blocks` that runs `grep -c '^## '` on detected artifacts — rejected (couples the reviewer to file-artifact assumptions; doesn't generalize to code/data). (b) Hardcoded "no duplicate section headers" rule — rejected (too specific to markdown reports).

12. **Decision**: Unify `needs_revision` and `rejected` into one routing path; `rejected` is an alias.
   - **Reason**: Experiment-2 showed both decisions increment `consecutive_failures` identically and route through the same `schedule_after_review` branch (`worker_runtime.py:87`). Having two names for the same behavior confused the model and the design. `rejected` becomes an alias for `needs_revision` — both send the task back for rework. No terminal-failure path is added (the user explicitly chose to merge them, citing "from original design being rejected means there is a needed revision").
   - **Alternatives Considered**: (a) Make `rejected` a terminal failure (kill the task) — rejected by the user (Q3). (b) Keep them separate with different routing — rejected (no behavioral difference existed anyway; the separation was accidental complexity).

13. **Decision (M9)**: Probe the server for `max_context` at startup instead of trusting the SDK's `128_000` default.
   - **Reason**: Experiment-5 failed because the served `qwen3.5-9b` was loaded with a context much smaller than the SDK's 128K default, so the compaction threshold (`0.7 × 128000 = 89.6K`) never fired before the real wall. LM Studio's `GET /v1/models` exposes the real `context_length` per model (confirmed via the LM Studio REST API docs: `loaded_instances[0].config.context_length` for the active limit, `max_context_length` for the model ceiling; the OpenAI-compatible `/v1/models` endpoint also populates `context_length` on LM Studio and Ollama). Probing once at startup makes the `0.7 × max_context` threshold track the real wall automatically — the user's 262K setting would be honored, a model loaded at 32K would correctly trigger compaction at 22.4K. The probe is best-effort with a silent fallback to the SDK default, so non-LM-Studio servers (vanilla OpenAI cloud, which omits the field) and down servers do not regress.
   - **Alternatives Considered**: (a) Hardcode per-model context sizes — rejected (brittle, doesn't track the loaded instance limit which can be smaller than the model's max to save VRAM). (b) Env-config only (`TINYCUA_MAX_CONTEXT`) — kept as the `--max-context` override knob for debugging and for servers that misreport, but not the primary source since the server knows the real value. (c) Probe on every call — rejected (one startup probe is enough; the loaded context doesn't change mid-run unless the server is reconfigured, which is out of scope).

14. **Decision (M9)**: Bound `session_context` at message-build time, not by mutating `session_context` itself.
   - **Reason**: `session_context` is the cross-node audit accumulator (appended by `append_output_entry`, propagated up by `propagation.py`). Mutating it to enforce `max_context_messages` would lose the audit trail and break propagation. Instead, `build_messages_with_dedupe` slices the prompt-bound subset to `[-max_context_messages:]` — the full list stays intact for audit/trace, only the LLM-visible prompt is bounded. Compaction (`compact_context`) does mutate `session_context` by replacing the windowed entries with a summary, but that's a deliberate summary operation, not a cap. The cap and compaction compose: compaction summarizes the dropped tail first, the cap keeps the recent working set.
   - **Alternatives Considered**: (a) Mutate `session_context` to the last N entries — rejected (loses the audit trail; breaks `chat_history` consistency and propagation). (b) Token-based cap instead of message-count — rejected (message-count is a simpler hard ceiling that doesn't require a token counter; the token-based compaction threshold is the primary bound, the message cap is the independent backstop).

15. **Decision (M9)**: Continuous compaction monitoring at the top of every attempt loop iteration.
   - **Reason**: The previous trigger (`attempt > 1` only) meant the first attempt of a new node could blow the window before any compaction ran. The user's requirement: "compaction should monitor ongoing progress and trigger whenever the session exceeds the threshold, not just at the start." Moving `_maybe_compact` to the top of the attempt loop (before messages are built) achieves this — after every LLM call returns usage (`_track_input_tokens`), the next attempt's top-of-loop check sees the updated count and compacts if over threshold. The existing chicken-and-egg guard (`_last_input_tokens <= 0` → skip) already handles the very-first-call-of-a-run case, so the `attempt > 1` gate was unnecessarily narrow.
   - **Alternatives Considered**: (a) Probe token count before every LLM call via a separate tokenization call — rejected (extra latency, requires a tokenizer, the provider already reports usage after the call). (b) Compact only at node boundaries — rejected (a single node attempt can grow the prompt past the wall via tool continuations; the within-attempt bounds `evict_superseded_file_reads`/`enforce_turn_budget` handle tool results but not `session_context`).

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
| Server probe adds startup latency / fails on non-LM-Studio | Low | Low | Best-effort with silent fallback (FR-084); one cheap `GET /v1/models`, no token cost. Tested explicitly for success, error, and missing-field cases. |
| `max_context_messages` cap drops context the model needed | Low | Med | Cap keeps the *last* N (recent = relevant). Compaction summarizes the dropped tail first (FR-082). `None` = unlimited escape hatch. Monitor via INFO logs. |
| Compaction LLM call itself fails (model overloaded mid-run) | Med | Med | `compact_context` catches and logs at INFO (FR-085); the `max_context_messages` cap is the independent backstop that doesn't depend on an LLM call succeeding. |
| Continuous compaction thrashes (fires every attempt) | Low | Low | `compaction_keep_recent=5` preserves the working set; threshold is 70% of real context, not 50%. Monitor via the new INFO logs; raise `compaction_keep_recent` if the working set proves too small. |

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