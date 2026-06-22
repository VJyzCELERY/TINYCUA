# Feature Specification: TinyCUA Prototype Improvement

**Status**: Draft
**Created**: 2026-06-21
**Last Updated**: 2026-06-22
**Subproject(s) Affected**: tinycua, tinycua-sdk (no SDK API changes — consumes existing `response_format` passthrough)

---

## Problem Statement

- **Goals**: Improve the TinyCUA research prototype along four axes motivated by the five-experiment evaluation in `src/experiment/evaluation-results/report.md`:
  1. **Code cleanup** — remove dead/dormant code paths, stubs, and consolidate the 13+ scattered required-tools-per-node maps into one declarative source of truth.
  2. **Retry redesign** — preserve the unbounded "node must complete its state" guarantee (zero-exit, one-shot, no HITL) while replacing the 5-stage forcing escalation with a 2-track system: structured-output via `response_format: json_schema` for LLM-decided transitions, deterministic synthesis for no-arg tools. LLM-decided exits stay LLM-decided.
  3. **Stateful nodes** — introduce a `NodeState` enum + per-node progress tracking so node state is observable and trackable, not implicit.
  4. **Tool hardening** — fix the experiment-evidenced tool failures (raw HTML fetch, `/bin/sh` venv mismatch, workspace path normalization) and harden the other tools (task_tools coercion gap, default-approve review tool, stubbed todo, buggy context retrieval, silent python timeout clamp).
  5. **Task tree shrink** — add the ability to delete/merge tasks so the TaskAnalyzer can correct over-decomposition mid-run, reducing the runtime explosion observed in experiment-5 (13→18+ tasks, 23 executor/reviewer cycles, 4456s).
  6. **Logging** — replace `print(stderr)` with structured logging and make node state transitions + retry/recovery observable without reading stderr.

- **Gaps** (evidence from `report.md` + codebase analysis):
  - **Retry**: 3 parallel retry codepaths (loop-owned, streamed, dormant node-owned); 5-stage forcing escalation including `_judge_retry` where an LLM judge produces the tool call and the runtime injects it (the executing LLM never decides again — violates the LLM-decides philosophy); `_route_task_executor_failure_to_reviewer` is a stub that always returns `False` (dead branch); `task_executor`/`result_reviewer` get `max_attempts=25` but the unbounded `_unbounded_recovery` loop has no cycle count.
  - **Required-tools-per-node**: defined in 13+ locations with overlapping but disagreeing rules (`required_by_node`, `any_of_by_node`, `_RECOVERY_CHAINS`, `_worker_lifecycle_ready_to_terminate`, `_can_stop_after_tool_batch`, `_retry_required_tool_name`, `_required_single_tool_choice_name`, `recovery_tool_map`, `retry_required_by_node`, plus prompt strings and `NodeRetryPolicy.required_tool_calls`).
  - **Node state**: no `NodeState` enum; a node instance is stateless between calls (no `status`, `phase`, `attempt_count`, `visited_tools`). State is reconstructed every turn by re-running validators against `LLMResult.tool_calls`.
  - **`fetch_url`** (`web.py:46-83`): returns raw HTML (no markdown conversion), 100KB hard truncation, no Content-Type guard (binary comes back as mangled text), no User-Agent, no retry on 429/5xx. Experiment-2 shows the model receiving unparsable HTML and falling back to narrated summaries. opencode/hermes request markdown/structured content.
  - **`run_shell`** (`shell.py:377-387`): `/bin/sh` via `shell=True`, no `env=` passthrough, no venv activation, cwd from a ContextVar that can be `None` (inherits process cwd). Experiment-4 shows 4× `exit_code=127` from `source` not working in dash + `ModuleNotFoundError: fastapi` because venv doesn't persist across stateless subprocess calls.
  - **`context.py:32-61`**: workspace binding is opt-in via ContextVar — when unset, falls back to `Path.cwd()` (the tinycua process cwd, unrelated to the experiment worktree). This is the root cause of the `/backend/...` vs `/workspace/experiment-4/backend/...` path mismatch in experiment-4.
  - **Tool contract**: class-based tools (`task_tools`, `handoff_tools`, `routing`, `digest`, `todo`) skip the SDK coercion layer entirely — `Tool.invoke` calls `self(**kwargs)` directly (`types.py:47-49`), while `@tool`-decorated native functions get real schema-driven coercion. `TaskReviewDecisionTool` defaults `decision="approved"` — a review tool that auto-approves on omitted arg.
  - **Task tree**: `TaskStateStore` (`task.py:111-541`) has `create_task`, `decompose_task`, `transition`, `record_reviewer_decision` — **no `delete`, `remove`, `prune`, `merge`, or `reparent`**. The tree only grows. Over-decomposition cannot be corrected mid-run.
  - **`todo_tools.py:39-51`**: stub — only append-descriptions + mark-done-by-index. No update-in-place, no delete.
  - **`enhanced_context_retrieval.py:188`**: buggy index math in the empty-query fallback; unbounded cache growth (`:46-63`).
  - **`python_exec.py:17-18`**: `_DEFAULT_TIMEOUT_SECONDS = 30; _MAX_TIMEOUT_SECONDS = 30` — silent clamp, inconsistent with `run_shell` which rejects >600s.
  - **`output_persist.py:338`**: duplicated `print("output_persist.py self-check OK")`.
  - **`orchestration_mixin.py:954-989`**: `_log_recovery_cycle` uses `print(..., file=sys.stderr)` instead of `logger`.
  - **Dead/dormant code**: `ProcessNode.__call__`/`DecisionNode.__call__` retry loops (bypassed by loop-owned path), `_call_failure_route` (always False, no overrides), `Node.propagate` (no-op default), `OPEN_QUESTION` reviewer decision (commented out in enum + routing, but `ResponseNode` import kept alive with `noqa`).

- **Non-Goals**:
  - Changing the node-graph architecture (no new nodes, no new node types, no new mixins beyond what the stateful-nodes + retry-redesign require).
  - Introducing free-text markdown parsing as the state-mutation channel — the chosen mechanism is provider structured output (`response_format: json_schema`), not regex-parsed prose. The design docs' "no untrusted string parsing" invariant is preserved.
  - Removing the unbounded retry guarantee — one-shot, no HITL, zero-exit stays. The node MUST complete its state.
  - Adding HITL/approval gates to the runtime.
  - Re-running the full 4-harness comparison — verification runs only tinycua.
  - Background process registry, git checkpoint/rollback, smart-approval auxiliary LLM (predecessor non-goals still apply).
  - Full todo state machine mirroring `TaskStateStore` — todos stay a lightweight scratchpad.

- **Constraints**:
  - The agent runs one-shot (no HITL) in Docker-sandboxed benchmark containers. The node must complete its state before the queue advances (queue integrity invariant — `orchestration_mixin.py:1310-1314`).
  - Target LLM provider is local llama.cpp / LM Studio via OpenAI-compatible Chat Completions. `response_format: {"type": "json_schema", "schema": {...}}` is supported and already passed through by the SDK (`open_ai_chat_completions.py:104`, `llm_model.py:43`).
  - Per-node structured-output enablement: routing/decision nodes (query_analyst, worker) stay free-text; state-mutation nodes (task_create, task_analyzer, task_assessor, task_executor, result_reviewer) use `json_schema`.
  - LLM-decided exits stay LLM-decided: tools whose arguments carry LLM-provided content (task_result_update, task_review_decision, task_init, task_decompose, task_update, node_handoff) MUST go through the LLM, not be synthesized by the runtime. Only no-arg tools (terminate) may be deterministically synthesized.
  - Completed tasks are immutable (`task_tools.py:334`) — only pending/in_progress tasks can be shrunk/deleted/merged.
  - All changes must be test-first per the repo's TDD workflow.
  - The eval ran with structured output *disabled* (`report.md:38`) — this was a config choice. Re-enabling per-node is in scope.

---

## User Scenarios & Testing

### Primary Scenario

A benchmark run starts experiment-4 ("build a Notion-like app"). The TaskExecutor writes files under the canonical workspace root (`/workspace/experiment-4/...`) and every tool result reports paths relative to that root. The ResultReviewer verifies each task using `run_shell` with a properly activated venv and sees `exit_code == 0`, not `exit_code=127` from a `source` mismatch. When the TaskExecutor finishes a task, it emits a structured JSON payload validated against the `task_result_update` schema — no forcing loop needed because the schema-conformant output satisfies the node contract in one pass. When the TaskAnalyzer sees the task tree has grown past the effort-profiled threshold, it proactively merges an over-decomposed subtree into its parent (preserving the child's result), reducing the runtime. The run completes with zero retry exhaustion and zero path-mismatch rejections.

### Acceptance Scenarios

1. **Given** the `task_executor` node, **When** it calls `task_result_update`, **Then** the LLM emits a JSON payload validated against the `task_result_update` json_schema; if the payload violates the schema, the runtime retries with the schema error in the prompt (unbounded) — the LLM stays the decider, no judge-injection.
2. **Given** the `result_reviewer` node, **When** it decides `approve`/`needs_revision`/`rejected`/`replan`, **Then** the decision is a structured JSON payload, not a free-text tool call; `TaskReviewDecisionTool` has no default `decision` (the field is required).
3. **Given** the `terminate` tool (no LLM-decided args), **When** a node's required work is complete but the LLM didn't call `terminate`, **Then** the runtime synthesizes the terminate call deterministically (no LLM round-trip) — this is not stealing an LLM decision because terminate takes no parameters.
4. **Given** the `_unbounded_recovery` loop, **When** the LLM produces invalid structured output, **Then** the loop retries with the schema validation error as the retry signal (replacing the 5-stage escalation); there is no `_judge_retry` stage.
5. **Given** any node, **When** it is executing, **Then** its `NodeState` (phase, attempt_count, visited_tools, satisfied_requirements) is observable in the execution trace — not implicit.
6. **Given** the `run_shell` tool, **When** the reviewer calls `source .venv/bin/activate && python -c "import fastapi"`, **Then** the command runs under a shell with venv activation support and returns `exit_code == 0` (not 127).
7. **Given** the `run_shell` tool, **When** the reviewer calls a command, **Then** the result includes the shell context (cwd, whether venv is active, shell name) so the model can interpret exit codes.
8. **Given** the `fetch_url` tool, **When** the LLM fetches an HTML page, **Then** the returned content is markdown-converted (not raw HTML), with a Content-Type guard that refuses/encodes binary, a User-Agent header, and retry on 429/5xx.
9. **Given** the `fetch_url` tool, **When** the LLM fetches a page that returns an error, **Then** the result is a consistent dict shape (`{"success": False, "error": ..., ...}`), not sometimes a str and sometimes a dict.
10. **Given** the workspace binding, **When** a tool resolves a path, **Then** the workspace ContextVar MUST be set (no silent cwd fallback); if unset, the tool raises a clear error.
11. **Given** the workspace binding, **When** the LLM passes an absolute path like `/backend/api/auth/auth.py` that matches a workspace subpath, **Then** the tool re-roots it under the workspace and finds the file (not "file not found").
12. **Given** any tool result that includes a file path, **When** the path is reported back to the LLM, **Then** it is reported workspace-relative (or both absolute + relative) so the model has a stable short form to echo back.
13. **Given** the `TaskStateStore`, **When** the TaskAnalyzer decides to shrink the tree, **Then** it can delete a pending task (and its pending subtree) or merge a completed child's result into its parent, preserving the work.
14. **Given** the TaskAnalyzer, **When** the task tree exceeds the effort-profiled threshold (higher effort → more aggressive threshold), **Then** the analyzer is triggered to consider shrinking (the LLM still decides what to merge/delete — no hard pruning).
15. **Given** the class-based task tools, **When** the LLM emits `task_id="7"` as a string for an int-typed field, **Then** the SDK coercion layer converts it to `7` before the tool runs (same as `@tool`-decorated native functions).
16. **Given** the `todo_tools`, **When** the LLM updates or deletes a todo, **Then** the operation is real (update-in-place, delete), not a no-op stub.
17. **Given** the retry/recovery loop, **When** a cycle runs, **Then** the cycle is logged via `logger` (not `print(stderr)`) with structured fields (node_id, phase, attempt_count, schema_error).
18. **Given** the `ProcessNode.__call__`/`DecisionNode.__call__` retry loops, **When** the loop-owned path is active, **Then** these dormant codepaths are removed (dead code).
19. **Given** the 13+ required-tools-per-node maps, **When** a node's required tools are queried, **Then** there is exactly one declarative source (the per-node spec from milestone 1), not 13 scattered maps.

### Edge Cases

- **Structured output + local model produces invalid JSON even with `json_schema`**: retry with the schema error in the prompt, unbounded — consistent with the zero-exit guarantee. The schema error is the retry signal, same as today's validation error. (Open question Q1 in design.)
- **Task-shrink on a completed task**: refuse — completed tasks are immutable (`task_tools.py:334`). Only pending/in_progress can be shrunk.
- **Merge when child has no result yet**: the merge is a structural collapse — the child's pending state is discarded, the parent keeps its own state. No work is lost because there was no work to preserve.
- **Merge when both child and parent have results**: preserve the child's result as the parent's result if the parent has none; if both have results, concatenate summaries (the child's result becomes a footnote on the parent's result).
- **Workspace ContextVar unset on first tool call**: raise `WorkspaceNotBoundError` with a message telling the CLI/session layer to call `bind_workspace` — do not fall back to cwd.
- **`fetch_url` on a binary Content-Type (image/PDF/zip)**: refuse with `{"success": False, "error": "binary content-type <type> not supported; use read_file for local files"}` — do not return mangled text.
- **`run_shell` with `executable="/bin/bash"` requested but bash not installed**: fall back to `/bin/sh` with a warning in the result.
- **NodeState after a crash/retry**: the state persists across retries within a node's lifecycle; on node exit (terminate), the state is finalized and written to the trace.
- **Structured-output schema for a node with optional tool args**: the schema marks them as optional; the LLM may omit them; the coercion layer fills defaults.
- **TaskAnalyzer shrink threshold at low effort**: threshold is high (e.g. >15 children) — the analyzer is rarely forced to shrink; at high effort, threshold is low (e.g. >8) — the analyzer is proactively nudged to shrink.

---

## Requirements

### Functional Requirements

#### Code Cleanup (Milestone 1)

- **FR-001**: System MUST remove the dormant `ProcessNode.__call__`/`DecisionNode.__call__` retry loops (bypassed by the loop-owned `_call_node_with_retry` path).
- **FR-002**: System MUST remove the always-`False` stubs: `_route_task_executor_failure_to_reviewer`, `_requires_any_tool_choice`, `_call_failure_route` (no overrides), and the `OPEN_QUESTION` commented branch + its `ResponseNode` `noqa` import.
- **FR-003**: System MUST replace `print(..., file=sys.stderr)` in `_log_recovery_cycle` with `logger` calls.
- **FR-004**: System MUST remove the duplicated `print("output_persist.py self-check OK")` at `output_persist.py:338`.
- **FR-005**: System MUST consolidate the 13+ required-tools-per-node maps into exactly one declarative per-node spec (the `NodeContract` dataclass in milestone 2).

#### Stateful Nodes (Milestone 2)

- **FR-006**: System MUST introduce a `NodeState` enum with at minimum: `PENDING`, `EXECUTING`, `AWAITING_TOOL`, `RETRYING`, `COMPLETED`, `FAILED`.
- **FR-007**: System MUST track per-node: `phase` (NodeState), `attempt_count`, `visited_tools` (set of tool names called), `satisfied_requirements` (set of required tools satisfied), `history` (list of state transitions).
- **FR-008**: System MUST emit a trace event on every node state transition with structured fields (`node_id`, `from_state`, `to_state`, `attempt_count`, `reason`).
- **FR-009**: System MUST define a `NodeContract` dataclass per node_id declaring: required_tools (set), any_of_tools (set of sets), deterministic_tools (set — no-arg tools the runtime may synthesize), structured_output_schema (dict | None — the json_schema or None for free-text nodes).
- **FR-010**: System MUST make `NodeContract` the single source of truth consulted by: validators, retry prompt builder, tool-narrowing logic, recovery loop, and tool_choice forcing.

#### Retry Redesign (Milestone 3)

- **FR-011**: System MUST split the retry mechanism into 2 tracks:
  - **Structured-output track** (LLM-decided transitions): for nodes with a `structured_output_schema` in their `NodeContract`, the LLM call includes `response_format: {"type": "json_schema", "schema": <schema>}`. On invalid output, retry with the schema validation error as the retry signal. The LLM stays the decider.
  - **Deterministic track** (no-arg tools): for tools in `deterministic_tools` in the `NodeContract` (currently only `terminate`), the runtime may synthesize the call without an LLM round-trip.
- **FR-012**: System MUST remove the `_judge_retry` stage as a primary retry path. **Updated (FR-060)**: `_judge_retry` is re-enabled as the **absolute final retry stage** (3 attempts) after structured-output (15) and focused retry (10) budgets are exhausted. The judge now sees the FULL session context (system prompt, continuation, task under review, outcome report, roadmap, trimmed tool results) — not just the last response. It makes an informed injection, not a blind guess. The "LLM-decided exits stay LLM-decided" philosophy is preserved: the model gets 25 chances first, and the judge only fires when the model is truly stuck.
- **FR-013**: System MUST merge `_tightening_retry` into the structured-output track (single-tool + json_schema is the natural retry step).
- **FR-014**: System MUST keep the unbounded recovery loop (no max-cycle count) — the zero-exit, one-shot, no-HITL guarantee is preserved. A node MUST complete its state before the queue advances.
- **FR-015**: System MUST fail fast with a clear diagnostic when a node repeatedly emits schema-invalid output (e.g. >10 consecutive schema failures) — not to bound the loop, but to surface a stuck model for observability. The loop continues.
- **FR-016**: System MUST enable structured output per-node: state-mutation nodes (task_create, task_analyzer, task_assessor, task_executor, result_reviewer) use `json_schema`; routing/decision nodes (query_analyst, worker) stay free-text.
- **FR-017**: System MUST build the per-node json_schema from the tool's type hints via the existing `type_to_json_schema` (`sdk/schema.py:14`) — no hand-written schemas.

#### Task Tree Shrink (Milestone 4)

- **FR-018**: `TaskStateStore` MUST support `delete_task(task_id)` that removes a task and its pending subtree, re-links siblings, and bumps version. Completed tasks are immutable — deletion raises.
- **FR-019**: `TaskStateStore` MUST support `merge_tasks(child_id, parent_id)` that collapses a child into its parent. If the child has a result and the parent does not, the child's result becomes the parent's result (preserve work). If both have results, concatenate summaries. The child's pending subtree is discarded.
- **FR-020**: System MUST expose a `task_shrink` tool to the TaskAnalyzer that supports delete + merge operations with an LLM-provided rationale.
- **FR-021**: System MUST apply the shrink threshold per the worker effort profile: low effort → high threshold (e.g. >15 pending children before triggering a shrink-prompt), high effort → low threshold (e.g. >8). The LLM still decides what to merge/delete — no hard pruning.
- **FR-022**: System MUST emit a trace event on task-tree shrink with structured fields (`node_id`, `action` (delete|merge), `task_id`, `affected_ids`, `rationale`, `new_tree_size`).
- **FR-023**: System MUST guard: only pending/in_progress tasks can be shrunk; completed/failed tasks are immutable history.

#### Tool Hardening — Experiment-Evidenced (Milestone 5)

- **FR-024**: `fetch_url` MUST convert HTML to markdown before returning (via `html2text` dependency). Binary Content-Types (image/PDF/zip) MUST be refused with a clear error, not returned as mangled text.
- **FR-025**: `fetch_url` MUST send a User-Agent header. MUST retry on 429/5xx with exponential backoff (max 3 retries).
- **FR-026**: `fetch_url` MUST return a consistent dict shape (`{"success": bool, "content": str | None, "error": str | None, "url": str, "content_type": str, "status": int}`) on both success and failure — not sometimes str, sometimes dict.
- **FR-027**: `web_search` MUST distinguish backend-down (`success: False, error: "searxng unreachable: ..."`) from no-matches (`success: True, results: [], note: "no matches found"`).
- **FR-028**: `web_search` MUST retry on timeout/connection-error with exponential backoff (max 3 retries).
- **FR-029**: `run_shell` MUST support a `venv` parameter that prepends `source <venv>/bin/activate &&` (or the POSIX `. <venv>/bin/activate &&`) to the command. The venv activation is per-call (subprocess stateless) — documented in the result.
- **FR-030**: `run_shell` MUST support an optional `executable` parameter (default `/bin/sh`, allow `/bin/bash`). If bash is requested but not installed, fall back to `/bin/sh` with a warning.
- **FR-031**: `run_shell` MUST pass `env=` to `subprocess.Popen` (inherit + augment, not bare inherit) so PATH/PYTHONPATH can be augmented per-call.
- **FR-032**: `run_shell` result MUST include the shell context (`cwd`, `shell` name, `venv_active` bool) so the model can interpret exit codes.
- **FR-033**: `context.py` MUST drop the `workspace is None` cwd fallback — `resolve_workspace_path` MUST raise `WorkspaceNotBoundError` if the ContextVar is unset, not silently use `Path.cwd()`.
- **FR-034**: `context.py` MUST re-root absolute paths that match a workspace subpath (heuristic: if `workspace / path` exists, prefer it).
- **FR-035**: `context.py` MUST canonicalize reported paths to workspace-relative in tool results (or both absolute + relative) so the model has a stable short form.
- **FR-036**: `files.py` MUST assert at session start that the workspace is bound before any file tool call.

#### Tool Hardening — Other Tools (Milestone 6)

- **FR-037**: Class-based task tools MUST route through the SDK coercion layer (`decorators.py:_coerce_arg`) — not call `self(**kwargs)` directly. `tinycua.config.types.Tool.invoke` MUST delegate to the SDK coercion path.
- **FR-038**: `TaskReviewDecisionTool` MUST make `decision` a required parameter (no default `"approved"`).
- **FR-039**: `TaskUpdateTool` MUST remove `additionalProperties: True` for metadata — use a typed `metadata: dict[str, str]` with explicit schema, not a wide-open accept.
- **FR-040**: `enhanced_context_retrieval` MUST fix the buggy index math at `:188` and add a cache size cap + eviction (e.g. LRU, max 100 entries).
- **FR-041**: `python_exec` MUST reject requested timeouts > `_MAX_TIMEOUT_SECONDS` with a clear error (like `run_shell` does at `shell.py:362-372`), not silently clamp.
- **FR-042**: `todo_tools` MUST implement real operations: update-in-place (edit description/status by index), delete (by index), status transitions. It stays a lightweight scratchpad (no transition-guarded state machine mirroring `TaskStateStore`).
- **FR-043**: System MUST introduce a `ToolResult` envelope (`success: bool`, `error: str | None`, `output: Any`, `metadata: dict`) that all tools return. The loop serializes this to the model consistently.

#### Logging (Milestone 7)

- **FR-044**: System MUST replace all `print(stderr)` in the loops with `logger` calls with structured fields.
- **FR-045**: System MUST emit structured trace events for: node state transition, retry attempt with schema error, tool call with result shape, recovery cycle entry, task-tree shrink event.
- **FR-046**: System MUST make retry/recovery observable without reading stderr — the trace events go to the execution trace and the logger.
- **FR-047**: All non-decision nodes (TaskAnalyzer, TaskAssessor, TaskExecutor, ResultReviewer, ResultAggregation, InformationDigester) MUST be instructed to explore with read-only tools (web_search, fetch_url, read_file, list_files, search_files, run_shell) before fulfilling their role. Exploration is permissive and role-scoped: the analyzer explores to ground decomposition in current reality, the assessor to verify the roadmap covers current reality, the reviewer to verify the executor's claims, aggregation to verify task results, the executor to plan before making changes. The execution boundary is preserved structurally — planning/review nodes only have `EXPLORATORY_AGENT_TOOLS` (no write tools), so they cannot produce the deliverable. Decision nodes (QueryAnalyst, Worker) are excluded.
- **FR-048**: The mission block (`_render_mission_block`) MUST render a structured `{context}\n{query}` block: the InformationDigester's `context_summary` + `key_points` as context first, followed by the original request and hard constraints. Empty sections MUST be omitted (no empty headers). The digester's `context_summary` and `key_points` MUST be stored on the root task metadata (`mission_context`, `mission_key_points`) by `_apply_task_lifecycle_marker` so they travel with the mission to every downstream node.

#### Loop Reliability (Milestone 8)

Evidence: experiment-2 trace analysis (`src/experiment/results/tinycua/experiment-2/logs/`). The replan loop never reset `consecutive_failures` and had no cap, so a task that the reviewer kept sending back (5+ times) re-fired `replan_triggered` on every subsequent rejection (counter climbed 5→7→9 with threshold 5). Each replan was vacuous — `decompose_task` is idempotent on a parent with existing children, so the executor reran the same task, re-researched, and re-appended content. The 45-min runtime and 100KB duplicated report were loop iterations, not model verbosity.

- **FR-049**: When `schedule_replan` fires, the runtime MUST insert a synthetic `replan_boundary` entry into the task's `reviewer_decisions` audit trail. The `consecutive_failures` derived counter MUST break on `replan_boundary` entries (not just on `approved`), so the failure baseline resets when a replan is triggered. The full audit trail is preserved — no history is lost.
- **FR-050**: The runtime MUST cap replans per task via a `max_replans` setting derived from the worker effort profile: `none=0, low=1, medium=3, high=6`. When a task's replan count reaches the cap, the next reviewer send-back MUST force-approve the task with rationale `"replan budget exhausted (effort={effort}, cap={max_replans})."` rather than queue another replan. This bounds the loop without violating the zero-exit guarantee.
- **FR-051**: `schedule_replan` MUST be non-vacuous: when the active task already has children and the analyzer confirms the plan is unchanged (via a `plan_unchanged` metadata flag set by `task_update`), the runtime MUST skip re-queueing the executor and reviewer against the same task — the plan did not change, so re-execution would only duplicate work. The analyzer MAY instead call `task_shrink` to restructure the plan (only unfinished tasks can be shrunk; completed tasks remain immutable per FR-023).
- **FR-052**: `str_replace` MUST distinguish zero-match from multi-match errors. When `old_string` matches in 2+ places and `replace_all=False`, the error MUST state `"Found N matches for old_string. Provide more context in old_string to disambiguate, or set replace_all=True to replace all N."` — not the generic whitespace error. The generic `"Could not find old_string"` error is reserved for zero-match cases.
- **FR-053**: The `result_reviewer` missing-tool heuristic (`_missing_or_required_tool_name`) MUST return the actually-missing tool, not pattern-match on substrings in the error text. The `_validate_result_reviewer_inspects_after_decision` error MUST NOT contain the substring `task_review_decision` (rephrased to `"ResultReviewer must call task_inspect after the review decision is recorded."`). `task_inspect` MUST be in the heuristic's candidate tuple, placed before `task_review_decision`.
- **FR-054**: The `task_analyzer` instruction MUST tell the model to call `terminate` after `task_decompose` or `task_update` succeeds. The continuation MUST NOT instruct the model to call `task_inspect` first (the roadmap is already in context via `build_continuation`); `task_inspect` does not satisfy the analyzer's state-tool contract and traps the model into a retry-exhausted cycle.
- **FR-055**: The `task_analyzer` node's `max_attempts` MUST be raised from the default 3 to 10 (between the default and the executor/reviewer's 25), so a prose-prone model has enough attempts to land the state-tool call.
- **FR-056**: The `result_reviewer` MUST act as a general sanity-checker for common LLM messes — generic across artifact types (code, report, data, anything): (a) duplicate/repeated content (detect via `run_shell` grep/wc/sort|uniq -c against the artifact), (b) hallucinated claims (entities, versions, scores that don't verify), (c) structural inconsistency (artifact claims N sections but has M). This is prompt-only guidance — the reviewer LLM decides which checks apply based on the artifact type. No hardcoded artifact-specific structure rules.
- **FR-057**: `needs_revision` and `rejected` are unified into a single send-back routing path. `rejected` is an alias for `needs_revision` — both send the task back for rework and increment `consecutive_failures` identically. There is no terminal-failure path for `rejected`; the `TaskReviewDecisionTool` description MUST document the aliasing.
- **FR-058**: `append_file` and `write_file` MUST return a `diff_preview` (the first ~500 chars of the appended/written content, with a leading marker) and `new_file_size` in their result dict, so the model can see what was added without re-reading the full file. `str_replace` MUST return a real unified-diff snippet (via `difflib.unified_diff`, first ~500 chars) instead of just `new_string[:200]`.
- **FR-059**: The `result_reviewer` MUST include validation evidence in every `task_review_decision` rationale. For `approved`: `[validated]: <command+result confirming the outcome>`. For `needs_revision`/`rejected`/`replan`: `[finding]: <issue> [validate]: <runnable command the executor can use to verify the fix>`. A validator in `validation_retry_mixin.py` enforces this — missing or malformed rationale triggers a retry with a clear error. The `rationale` parameter on `TaskReviewDecisionTool` is required and its description documents the format. Generic across artifact types (code, research, data, anything). Reviewer guidance is extracted into `node_guidance.py` so it evolves independently of node plumbing.
- **FR-060**: The recovery loop MUST use per-method budgets with diminishing allocation: structured-output retry (15), focused retry (10), judge retry (3) = 30 total per node invocation. When all budgets are exhausted, the node MUST re-enter (re-dispatch with fresh `build_messages`, clearing accumulated context) — unlimited re-entries, no force-approve. Only `_direct_terminate` is allowed as a forced action (when terminate is the only missing tool). The `_structured_output_retry` MUST include full session context (system prompt, continuation, task under review, outcome report, roadmap) via `_build_recovery_messages` — not a bare user message. The `_build_recovery_messages` MUST include trimmed one-line summaries of previous tool results (via `summarize_tool_result` in `node_guidance.py`) so the model knows what its commands returned without re-running them.
- **FR-061**: `NodeContract` is the single source of truth for node requirements (`required_tools`, `any_of_tools`, `requires_terminate`, `early_stop_tool`, `goal`, `success_criteria`, `tool_rationale`, `additional_recovery_tools`). All runtime validators, recovery chains, and tool maps are derived from `_NODE_CONTRACTS` at module level (`TERMINATED_NODE_IDS`, `REQUIRED_TOOLS_BY_NODE`, `ANY_OF_TOOLS_BY_NODE`, `RECOVERY_CHAINS`, `RECOVERY_TOOL_MAP`). Ad-hoc maps in mixins are deleted — drift between contract and runtime is impossible.
- **FR-062**: `NodeProgress` is the live per-node state tracker, persisted on `session.node_progress[node_id]` (shared by reference across parent/child sessions). Validators consult `progress.satisfied_requirements` (merged with current `tool_results`) instead of re-scanning ephemeral metadata. Progress survives node reconstruction (fresh node instances read from the session). Progress is cleaned up when a node completes (`session.node_progress.pop(node_id)` — don't store done nodes).
- **FR-063**: `accumulated_tool_results` persists on `NodeProgress` across recovery re-entries (unlimited). Fresh dispatches reset progress (including `accumulated_tool_results`). Recovery stages (`_structured_output_retry`, `_recovery_retry`, `_judge_retry`) return partial results (successful tool calls that don't fully satisfy validation) so the orchestration loop accumulates and advances to the next missing prerequisite. The no-progress guard skips a stage when the model re-calls an existing tool (detected via `stage_tool_history` — only fires when a tool succeeded but no new tool key was added). `_call_node_with_retry` preserves `accumulated_tool_results` on recovery re-entry and resets it on fresh dispatch.
- **FR-064**: `NodeContract` carries `goal`, `success_criteria`, `tool_rationale`. These are injected into the system message as dynamic context (cache-safe — goes in the suffix, not the cached prefix). The model knows its fulfillment criteria and WHY each tool is required — not just "call X" but "call X because Y."
- **FR-065**: Continuation injects a `## Your Progress This Session` block showing satisfied + missing tools + steps-to-done. Appears only when `satisfied_requirements` is non-empty (after at least one tool has succeeded). For `any_of` groups: if any group is satisfied, alternatives are NOT listed as missing.
- **FR-066**: Recovery messages are goal-oriented: `## Node Goal` + progress block + `## Why {missing} Is Required` (rationale from contract) + `## Recent Recovery Attempts` (stage_tool_history, last 5) + directive. The model always knows its state, its fulfillment criteria, and what it already tried during recovery.

### Key Entities

- **NodeState** (enum): PENDING, EXECUTING, AWAITING_TOOL, RETRYING, COMPLETED, FAILED. Lives on the `Node` instance.
- **NodeContract** (dataclass): per-node_id declaration of `required_tools`, `any_of_tools`, `deterministic_tools`, `structured_output_schema`. The single source of truth replacing the 13+ scattered maps.
- **NodeProgress** (dataclass): per-node runtime tracking — `phase`, `attempt_count`, `visited_tools`, `satisfied_requirements`, `history`. Lives on the `Node` instance.
- **ToolResult** (dataclass): envelope for all tool returns — `success`, `error`, `output`, `metadata`. Replaces the per-tool ad-hoc dict shapes.
- **WorkspaceNotBoundError** (exception): raised when a tool resolves a path but the workspace ContextVar is unset.

---

## Success Criteria

- [ ] **Zero retry exhaustion on experiment-4**: no `retry_exhausted attempts=25` warnings in a re-run of experiment-4 with tinycua.
- [ ] **Zero exit_code=127 from venv/source mismatch on experiment-4**: no `exit_code=127` caused by `source` failing in `/bin/sh`.
- [ ] **Zero path-mismatch rejections on experiment-4**: no reviewer checking `/backend/...` when the executor wrote `/workspace/experiment-4/backend/...`.
- [ ] **fetch_url returns markdown not raw HTML**: a fetch of an HTML page returns markdown-converted content, verified by a unit test asserting `<title>` tags are stripped and `<h1>` becomes `# `.
- [ ] **TaskReviewDecisionTool has no default approve**: calling `TaskReviewDecisionTool()` without `decision` raises, verified by a unit test.
- [ ] **Single required-tools source**: `grep -rn "task_result_update" src/tinycua/tinycua/loops/validation_retry_mixin.py src/tinycua/tinycua/loops/orchestration_mixin.py src/tinycua/tinycua/loops/prompt_protocol_mixin.py` shows the tool name only in the `NodeContract` declaration and nowhere as a hardcoded per-node map.
- [ ] **NodeState observable**: the execution trace for a re-run of experiment-4 contains `node_state_transition` events with `from_state`, `to_state`, `attempt_count`.
- [ ] **Task tree shrink works**: a unit test creates a parent with 10 pending children, calls `merge_tasks(child, parent)`, and asserts the child's result (if any) is preserved on the parent and the child is removed.
- [ ] **Effort-profiled shrink threshold**: a unit test asserts that at `effort=high`, the threshold is lower than at `effort=low`.
- [ ] **Structured output on task_executor**: a unit test asserts the `task_executor` LLM call payload includes `response_format: {"type": "json_schema", "schema": ...}` matching the `task_result_update` schema.
- [ ] **No _judge_retry in the codebase**: `grep -rn "_judge_retry" src/tinycua/` returns zero matches.
- [ ] **No ProcessNode.__call__ retry loop**: the dormant retry loop in `node.py:740-813` is removed.
- [ ] **Experiment-5 runtime < baseline 4456s**: a re-run of experiment-5 with tinycua completes in less than 4456s (the over-decomposition is corrected by task-tree shrink).
- [ ] **All 5 tinycua experiments pass with zero exit**: re-running all 5 tinycua experiments produces exit code 0 for each (the zero-exit guarantee holds).
- [ ] **WorkspaceNotBoundError raised when unset**: a unit test calls `resolve_workspace_path("foo")` without binding and asserts `WorkspaceNotBoundError`.
- [ ] **ToolResult envelope**: all tools return a `ToolResult` (or dict matching the envelope); the loop serializes it consistently.
- [ ] **todo_tools real operations**: a unit test updates a todo in-place and deletes one, asserting the operations are real (not no-ops).
- [ ] **Replan loop is bounded**: a stub-model integration test forces the reviewer to always return `needs_revision`; the runtime caps replans at `max_replans` (effort-profiled) and force-approves instead of looping forever. Total executor invocations ≤ `max_replans + 1`.
- [ ] **`consecutive_failures` resets on replan**: a unit test asserts that after `schedule_replan` inserts a `replan_boundary` entry, the derived `consecutive_failures` counter returns to 0.
- [ ] **`str_replace` multi-match error is actionable**: a unit test asserts that 2 matches with `replace_all=False` returns `"Found 2 matches..."` (not the whitespace error), and 2 matches with `replace_all=True` succeeds.
- [ ] **Reviewer does not double-invoke `task_review_decision`**: a unit test asserts the inspect-after-decision retry message mentions `task_inspect`, not `task_review_decision`.
- [ ] **Analyzer prompt includes `terminate` instruction**: a snapshot test asserts the analyzer instruction contains "call terminate" and does NOT instruct calling `task_inspect` first.
- [ ] **File tools return diff/preview**: unit tests assert `append_file`, `write_file`, and `str_replace` result dicts contain `diff_preview` and (for append/write) `new_file_size`.

---

## Testing Plan

### Unit Tests

- `NodeState` / `NodeProgress`: state transitions, history append, observability.
- `NodeContract`: single-source-of-truth — validators, retry, recovery all consult it.
- `TaskStateStore.delete_task`: pending subtree removal, sibling re-link, version bump; refusal on completed.
- `TaskStateStore.merge_tasks`: child-result-preserved-on-parent, both-have-results-concatenate, pending-subtree-discard.
- `task_shrink` tool: delete + merge via the tool, with rationale capture.
- Effort-profiled threshold: low vs high effort produces different thresholds.
- `fetch_url`: markdown conversion, binary refusal, UA header, retry on 429/5xx, consistent dict shape.
- `web_search`: backend-down vs no-matches distinction, retry on timeout.
- `run_shell`: venv activation, executable selection, env passthrough, shell context in result.
- `context.py`: `WorkspaceNotBoundError` when unset, re-root absolute paths, workspace-relative reporting.
- `TaskReviewDecisionTool`: no default decision (raises on omit).
- `TaskUpdateTool`: no `additionalProperties: True` for metadata.
- `enhanced_context_retrieval`: fixed index math, cache eviction.
- `python_exec`: reject >max with error, not silent clamp.
- `todo_tools`: update-in-place, delete.
- `ToolResult` envelope: all tools return it.
- Structured-output retry: schema-invalid → retry with schema error (unbounded).
- `_judge_retry` removed: grep assertion.

### Integration Tests

- Full experiment-4 re-run with tinycua: zero retry exhaustion, zero exit_code=127, zero path mismatches.
- Full experiment-5 re-run with tinycua: task-tree shrink fires, runtime < 4456s.
- All 5 experiments re-run with tinycua: zero exit each.
- NodeState trace events present in the execution trace.
- Structured-output payloads validated against schema in the loop.

### Manual Tests

- Inspect the experiment-4 transcript to confirm: no `/backend/...` path checks, venv-activated shell commands, structured task_result_update payloads.
- Inspect the experiment-5 transcript to confirm: task-tree shrink events, reduced executor/reviewer cycles.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Milestone 1 — Code cleanup | TODO | |
| Milestone 2 — Stateful nodes | TODO | |
| Milestone 3 — Retry redesign | TODO | |
| Milestone 4 — Task tree shrink | TODO | |
| Milestone 5 — Tool hardening — experiment-evidenced | TODO | |
| Milestone 6 — Tool hardening — other tools | TODO | |
| Milestone 7 — Logging | TODO | |
| Milestone 8 — Loop reliability | Done | FR-049..FR-058 shipped: replan boundary reset + max_replans effort cap, non-vacuous replan via plan_unchanged, str_replace multi-match error, reviewer heuristic fix, analyzer terminate prompt + max_attempts=10, reviewer sanity-checker, needs_revision/rejected unification, file-tool diff/preview |

---

## Open Questions

1. **Structured-output failure mode**: when the LLM produces invalid JSON even with `json_schema`, the runtime retries with the schema error (unbounded). Is a "stuck model" diagnostic after N consecutive schema failures (FR-015) sufficient, or do we need a fallback to free-text tool calls after a very high N?
   - **Owner**: @christopher-sebastian
   - **Target**: 2026-06-21
   - **Status**: Decided
   - **Proposed Answer**: Retry with schema error, unbounded (option a). FR-015 adds a diagnostic for observability but does not bound the loop. Consistent with the zero-exit philosophy.

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable