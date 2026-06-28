# Feature Specification: TINYCUA Runtime Performance Hardening

**Status**: In Progress
**Created**: 2026-06-19
**Last Updated**: 2026-06-19
**Subproject(s) Affected**: tinycua, tinycua-sdk

---

## Problem Statement

- **Goals**: Make TINYCUA fast enough to finish WildClawBench experiment-4 (a full-stack Notion-like app build) within the 3600s benchmark timeout, and make the ResultReviewer's verification reliable (exit-code-based, not vibes-based), while preserving the existing node-graph architecture.
- **Gaps**:
  - Experiment-4 timed out at 3931s (exit 124). The ResultReviewer node alone made 209 LLM calls; 10 calls exceeded 100K input tokens with a peak of 257K — because tool results (`task_inspect` ×40, `read_file` ×23, `run_shell` output) are appended into the message list at full size with no truncation or eviction (tinycua_loop.py:567).
  - `run_shell_readonly` (the reviewer's only shell tool) uses a broad write-verb regex blocklist (`\binstall\b`, `\bcp\b`, `\btee\b`, `\brm\b`, `>`) that false-positives on legitimate verification commands like `grep "install"`. The reviewer self-censors and falls back to `read_file` + LLM-judging source text — unreliable verification.
  - The reviewer is *instructed* to call `task_inspect` for every unfinished task (task_nodes.py:91,96-97) — 40 calls in one run, each returning a verbose `asdict` blob, re-fetching a task tree already rendered into the reviewer's continuation.
  - The system prompt is rebuilt with `datetime.now()` on every node call (system_prompt.py:117-126), guaranteeing zero prompt-cache hits on any provider (local llama.cpp / LM Studio KV reuse, OpenAI prefix caching).
  - `DecisionNode` (query_analyst, worker) makes 2 LLM calls per decision (`_analysis_call` + `_classification_call`) even when the route is forced by a single required tool.
  - `run_shell` timeout is hard-capped at 30s (shell.py:19), killing `pytest`/build verification. No output truncation. Non-UTF-8 output silently drops to empty stdout.
- **Non-Goals**: Changing the node-graph architecture (no new nodes, no new tools, no new mixins). Background process registry. Git checkpoint/rollback. Smart-approval auxiliary LLM. Wiring the existing dead `SimpleCompaction` (the targeted persistence/budget fixes supersede it).
- **Constraints**:
  - The agent runs one-shot (no HITL) in Docker-sandboxed benchmark containers. Safety must come from a hardline blocklist of unrecoverable commands, not from blocking recoverable writes — the agent must still be able to delete files and kill processes it needs to.
  - Target LLM provider is local llama.cpp / LM Studio via OpenAI-compatible Chat Completions. Prompt-cache enablement must target llama.cpp's `cache_prompt` semantics while staying harmless on real OpenAI.
  - All changes must be test-first per the repo's TDD workflow. Existing tests that assert the old behavior (30s timeout cap, untruncated output, forced `task_inspect`) will be updated.

---

## User Scenarios & Testing

### Primary Scenario

A benchmark run starts experiment-4 ("build a Notion-like app"). The TaskExecutor writes files and runs commands; the ResultReviewer verifies each task by running `pytest`/`test -f`/`grep` via `run_shell` and checking `exit_code == 0` and `exit_code_meaning`, not by reading source and guessing. The reviewer sees a compact task list once, drills into specific tasks only when annotating them. Tool outputs that exceed 50K are head+tail truncated; outputs over 100K are persisted to a temp file with a preview. The system prompt is byte-stable across calls so the local LLM reuses KV cache. The run completes under 3600s.

### Acceptance Scenarios

1. **Given** the ResultReviewer node, **When** it calls `run_shell("grep -r 'def main' src/")` (a verification command), **Then** the command executes (not blocked by a write-verb regex), returns `exit_code` and `exit_code_meaning`, and the model sees both.
2. **Given** the ResultReviewer node, **When** it calls `run_shell("rm -rf /")`, **Then** the command is blocked by the hardline blocklist with a clear reason and never executes.
3. **Given** the ResultReviewer node, **When** it calls `run_shell("rm -rf ./tmp/build")` (recoverable destructive), **Then** the command executes and the result includes a `"warning": "destructive: ..."` annotation but is NOT blocked.
4. **Given** any node, **When** `run_shell` produces >50K chars of stdout, **Then** the returned stdout is head+tail truncated with a `[OUTPUT TRUNCATED - N chars omitted]` notice and is under 50K chars.
5. **Given** the retry loop, **When** a tool result's serialized content exceeds 100K chars, **Then** the full output is written to `./tmp/tool-results/{tool_call_id}.txt` and the in-message content is replaced with a `<persisted-output>` preview + file path + "use read_file with offset/limit" hint.
6. **Given** the retry loop, **When** cumulative tool-result chars in `attempt_messages` exceed 200K, **Then** the largest non-persisted results are spilled to disk until under budget.
7. **Given** the ResultReviewer node, **When** it calls `task_inspect` with no `task_id`, **Then** it receives a compact list `[{id, title, status, has_result}]` with no descriptions/results/decisions — not a full `asdict` snapshot of every task.
8. **Given** the ResultReviewer node, **When** it calls `task_inspect(task_id=X)`, **Then** it receives one task with compacted detail (last 2 reviewer_decisions, result.content/summary truncated to 200 chars, empty metadata/artifacts/children dropped).
9. **Given** any node, **When** the system prompt is built for two consecutive calls in the same session, **Then** the system message bytes are identical (no timestamp drift).
10. **Given** a local LLM provider (base_url contains localhost/127.0.0.1/host.docker.internal), **When** a chat payload is built, **Then** the payload includes `cache_prompt: true`.
11. **Given** the Worker node, **When** `state_valid_route_labels()` returns exactly one valid route, **Then** the node returns that route without any LLM call.
12. **Given** the Worker/QueryAnalyst node with a required routing tool, **When** a decision is made, **Then** exactly one LLM call is made (the forced tool call is the decision), not two.
13. **Given** a task that has failed review 5 times, **When** the ResultReviewer decides, **Then** it prefers `replan` over `retry` (no infinite executor↔reviewer ping-pong).

### Edge Cases

- `run_shell("echo reboot")` — must NOT be hardline-blocked (the `reboot` pattern is anchored to command-start positions via `_CMDPOS`, so `echo reboot` passes).
- `run_shell("grep install file")` — must NOT be blocked or warned (no broad `\binstall\b` write detection).
- `run_shell("kill 12345")` — passes with a warning (recoverable); `run_shell("kill -1")` — hardline-blocked (kills all processes).
- A command emitting non-UTF-8 bytes — `errors="replace"` replaces invalid bytes with U+FFFD, never raises or returns empty stdout.
- `task_inspect` on an empty task store — returns `{"tasks": [], "root_task_id": None}`.
- The reviewer's continuation already renders the task tree; calling `task_inspect` (list mode) returns a compact confirmation, not a redundant full snapshot.

---

## Requirements

### Functional Requirements

**Shell tool hardening (Phase 1)**

- **FR-001**: The `run_shell_readonly` tool MUST be removed. The ResultReviewer MUST use `run_shell` (the same tool the executor uses), gated by an in-tool safety function — not a separate neutered tool.
- **FR-002**: `run_shell` MUST block a hardline set of unrecoverable commands unconditionally (even in one-shot mode): `rm -rf /` and system roots, `mkfs`, `dd of=/dev/(sd|nvme|hd|...)`, `> /dev/(sd|...)`, fork bomb, `kill -1`, `shutdown`/`reboot`/`halt`/`poweroff`/`init 0|6`/`systemctl poweroff|reboot`/`telinit 0|6`, `sudo -S` password-piping. Hardline patterns MUST be anchored to command-start positions (after `;`, `&&`, `||`, `|`, `$(`, backtick, or after sudo/env wrappers) so `echo reboot` and `grep 'shutdown' log` do not false-positive.
- **FR-003**: `run_shell` MUST NOT block recoverable destructive commands (`rm -r` of non-system paths, `git push --force`, `chmod 777`, `pip install`, `cp`, `mv`, `kill <pid>`, etc.). These MUST execute and the result MUST include a `"warning": "destructive: <reason>"` annotation so the model is aware, but execution is not prevented (one-shot mode requires the agent to delete/kill as needed).
- **FR-004**: `run_shell` result MUST include `exit_code` and, for known commands with non-error non-zero exits, `exit_code_meaning` (e.g. grep=1 → "No matches found (not an error)", diff=1 → "Files differ (expected)", test=1 → "Condition evaluated to false (expected)").
- **FR-005**: `run_shell` timeout MUST default to 120s, with a max of 600s, and be agent-settable. Requests above 600s MUST be rejected with a "narrow the command" error (not silently clamped).
- **FR-006**: `run_shell` MUST strip ANSI escape codes from stdout/stderr before returning.
- **FR-007**: `run_shell` MUST decode stdout/stderr with `errors="replace"` so non-UTF-8 output never raises or yields empty stdout.

**Output/context bloat control (Phase 2)**

- **FR-008**: `run_shell` MUST head+tail truncate stdout/stderr to a 50K-char cap (≈20K head + ≈30K tail) with a `[OUTPUT TRUNCATED - N chars omitted]` notice, preserving both the command echo/context (head) and the exit/error (tail).
- **FR-009**: The retry loop MUST persist any tool result whose serialized content exceeds 100K chars to a file under `./tmp/tool-results/{tool_call_id}.txt` and replace the in-message content with a `<persisted-output>` block containing a 4K preview, the file path, and a "use read_file with offset/limit" instruction. This applies to both the live append site (tinycua_loop.py) and the retry-feedback path (validation_retry_mixin.py).
- **FR-010**: The retry loop MUST enforce a 200K-char cumulative budget on tool-result content within a single node's `attempt_messages`. When exceeded, the largest non-persisted results MUST be spilled to disk until under budget.
- **FR-011**: `task_inspect` with no `task_id` MUST return a compact list: `{"tasks": [{id, title, status, has_result}], "root_task_id": ..., "active_task_id": ...}` — no descriptions, results, reviewer_decisions, artifacts, metadata, or transition_log.
- **FR-012**: `task_inspect(task_id=X)` MUST return one task with compacted detail: `reviewer_decisions` truncated to the last 2, `result.content`/`result.summary` truncated to 200 chars, empty `metadata`/`artifacts`/`children` omitted.
- **FR-013**: The ResultReviewer instruction MUST encourage a list-first, drill-down-selectively inspect pattern — NOT force calling `task_inspect` for every unfinished task. The reviewer sees the roadmap in its continuation; `task_inspect` (list) is a lightweight confirmation, detail is on-demand.
- **FR-014**: `_render_task_tree_markdown` MUST cache its rendered output keyed on a `TaskStateStore.version` counter that increments on any mutation. Re-renders happen only when the version bumps; otherwise the cached string is returned (reduces CPU and keeps continuation bytes stable for prompt caching).

**Prompt caching (Phase 3)**

- **FR-015**: The system prompt MUST NOT include a per-call timestamp. "Current time" MUST move to the last user message so the system message is byte-stable across calls in a session.
- **FR-016**: The system message MUST be built once per session and replayed verbatim on subsequent calls (not re-assembled every call).
- **FR-017**: When the LLM provider's base_url is local (localhost, 127.0.0.1, host.docker.internal, or 0.0.0.0), the chat completions payload MUST include `cache_prompt: true`. On non-local providers this field MUST be omitted (harmless on real OpenAI).
- **FR-018**: The Worker node's tool list (rebuilt per call today via `refresh_route_options`) MUST be cached per `(node_id, hash(labels))` and identical label sets MUST reuse the same tool objects, so the tools-prefix stays byte-stable for caching.

**LLM call reduction (Phase 4)**

- **FR-019**: ~~The Worker node MUST skip the LLM call entirely when `state_valid_route_labels()` returns exactly one valid route~~ **DROPPED** — deterministic shortcut bypasses the LLM decision, violating the "let the LLM decide" contract. The worker always asks the LLM to route.
- **FR-020**: ~~For nodes with a `required_tool_calls` routing tool, the decision MUST be made in a single LLM call~~ **Already satisfied by the live loop** — `_call_node_with_retry` with `required_tool_calls` already makes exactly one LLM call where the LLM freely picks the route via the routing tool. The standalone `DecisionNode.__call__` 2-call path is not used by the benchmark loop. No change needed.
- **FR-021**: The ResultReviewer MUST track a per-task `failure_count`. When `failure_count >= 5`, the reviewer's continuation MUST surface the count as soft context (e.g. "This task has failed review 5 times; consider replan over retry") so the reviewer — which still LLM-decides — can weigh replan vs retry itself. This prevents infinite executor↔reviewer ping-pong without forcing the decision.

### Key Entities

- **SafetyGate** (new, in `shell.py`): a pure function `_check_command_safety(command) -> (blocked: bool, reason: str | None, warning: str | None)`. Hardline patterns block; dangerous patterns warn; everything else passes.
- **OutputPersister** (new, `tools/native/output_persist.py`): `persist_if_oversized(content, tool_call_id, threshold=100_000) -> str` writes oversized content to `./tmp/tool-results/` and returns the `<persisted-output>` preview block; returns the original content if under threshold.
- **TaskStateStore.version** (new field on existing entity): a monotonic int incremented on any mutation (create/transition/record_result/record_reviewer_decision), used as the cache key for `_render_task_tree_markdown`.

---

## Success Criteria — use `[ ]` checkboxes

- [ ] **Reviewer verifies with shell**: ResultReviewer can run `pytest`/`test -f`/`grep` via `run_shell` and check `exit_code` — not blocked by write-verb false positives.
- [ ] **Hardline floor holds**: `rm -rf /`, `mkfs`, `dd of=/dev/sd*`, `shutdown`, `kill -1` are blocked unconditionally; `rm -rf ./tmp/x`, `kill 12345`, `grep "install"` pass.
- [ ] **No 100K-token reviewer calls**: with the Phase 2 fixes, no single reviewer LLM call exceeds ~60K input tokens (down from 257K peak in experiment-4).
- [ ] **Prompt cache stability**: the system message bytes are identical across consecutive calls in a session; local-provider payloads include `cache_prompt: true`.
- [ ] **`task_inspect` list mode is compact**: a 10-task tree's list-mode response is under ~2K chars (vs ~7K+ today).
- [ ] **Worker shortcut fires**: when only one route is valid, zero LLM calls are made for the worker decision.
- [ ] **Experiment-4 fits in budget**: a re-run of experiment-4 completes under 3600s (target; verified by benchmark, not unit test).

---

## Testing Plan

### Unit Tests

- `test_native_tools_shell.py`: update timeout-cap test (30→120); add tests for hardline block (`rm -rf /`), warning annotation (`rm -rf ./tmp/x`), `exit_code_meaning` (grep=1), ANSI stripping, `errors="replace"`, head+tail truncation at 50K, `_CMDPOS` anchoring (`echo reboot` passes).
- `test_shell_readonly.py`: delete (the tool is removed); its meaningful assertions migrate to the new gate tests in `test_native_tools_shell.py`.
- `test_exit_code_interpretation.py` (new): cover `_interpret_exit_code` for grep/diff/find/test/curl/git and the pipeline-last-command extraction.
- `test_output_persist.py` (new): oversized content → temp file written + `<persisted-output>` preview returned; under-threshold → passthrough; 200K budget enforcement spills largest first.
- `test_task_state_store.py`: add tests for `version` increment on mutation and list-mode `snapshot_compact()`.
- `test_result_reviewer_inspect_protocol.py`: update to assert list-first inspect pattern and that the reviewer is NOT forced to inspect every task.
- `test_runtime_context_prompt.py` / `test_system_prompt.py`: assert no timestamp in system message; assert byte-stability across calls.
- `test_decision_node.py` / `test_worker_dynamic_routes.py`: single-valid-route shortcut; single-call forced-tool decision.

### Integration Tests

- `test_native_tools_shell.py` (integration): real `run_shell("echo hello")`, `run_shell("grep nomatch /nonexistent")` (assert `exit_code_meaning`), `run_shell("rm -rf /")` (assert blocked), end-to-end truncation on a 100K-output command.
- `test_tool_scoping_integration.py`: reviewer scope now includes `run_shell` (not `run_shell_readonly`).
- `test_tinycua_loop_integration.py`: oversized tool result → persisted file exists + in-message content is the preview.

### Manual Tests

- Re-run experiment-4 via the benchmark harness and confirm it completes under 3600s with the reviewer using shell-based verification.

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Phase 1 — Shell tool hardening | TODO | |
| Phase 2 — Output/context bloat control | TODO | |
| Phase 3 — Prompt caching | TODO | |
| Phase 4 — LLM call reduction | TODO | |

---

## Open Questions

_None — all four clarification questions resolved before implementation._

---

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices) — kept at the FR/behavior level
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable