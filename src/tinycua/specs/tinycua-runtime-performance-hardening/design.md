# Design Document: TINYCUA Runtime Performance Hardening

**Spec**: `./spec.md`
**Status**: In Progress
**Last Updated**: 2026-06-19

---

## Overview

This hardens TINYCUA's runtime for speed and verification reliability without changing the node-graph architecture. Four phases: (1) replace the broken `run_shell_readonly` with a gated `run_shell` that the reviewer can actually verify with; (2) cap tool-result bloat via truncation, temp-file persistence, and a compact `task_inspect`; (3) make the system prompt byte-stable and enable llama.cpp `cache_prompt`; (4) cut redundant LLM calls in routing and review. Affected subprojects: `tinycua` (most files) and `tinycua-sdk` (one provider file for `cache_prompt`).

---

## Architecture

### Component Overview

```
                        ┌─────────────────────────────────────┐
                        │           TinyCUALoop               │
                        │  (orchestration_mixin, retry loop)  │
                        └───────────────┬─────────────────────┘
                                        │ tool results
                                        ▼
                          ┌─────────────────────────┐
                          │   OutputPersister (new) │  ← Phase 2
                          │  persist_if_oversized() │
                          │  enforce_turn_budget()  │
                          └────────────┬────────────┘
                                       │ compacted content → attempt_messages
                                       ▼
   ┌──────────────┐   command    ┌──────────────┐
   │  run_shell   │─────────────▶│ SafetyGate   │  ← Phase 1
   │  (gated)     │              │ (in shell.py)│
   └──────────────┘              └──────────────┘
        │ result {stdout, stderr, exit_code, exit_code_meaning, warning?}
        ▼
   head+tail truncate (50K)  ← Phase 2 (FR-008)

   TaskStateStore ──version──▶ _render_task_tree_markdown cache  ← Phase 2 (FR-014)
        │
        ▼
   task_inspect (list=compact / detail=compacted)  ← Phase 2 (FR-011/012)

   SystemPromptBuilder ──no timestamp──▶ cached per session  ← Phase 3 (FR-015/016)
   SDK chat payload ──cache_prompt: true (local)──▶ llama.cpp KV reuse  ← Phase 3 (FR-017)

   Worker/QueryAnalyst ──single forced-tool call──▶ route  ← Phase 4 (FR-019/020)
   ResultReviewer ──failure_count≥5──▶ replan not retry  ← Phase 4 (FR-021)
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `agent/tools/native/shell.py` | Modified | Add SafetyGate, exit_code_meaning, 120s/600s timeout, ANSI strip, errors="replace", head+tail truncation, `__main__` self-check |
| `agent/tools/native/shell_readonly.py` | Deleted | Replaced by gated `run_shell` |
| `agent/tools/native/ansi_strip.py` | New | `strip_ansi()` helper (or inlined in shell.py) |
| `agent/tools/native/output_persist.py` | New | `persist_if_oversized()` + `enforce_turn_budget()` |
| `config/tool_scopes.py` | Modified | Reviewer gets `run_shell` instead of `run_shell_readonly` |
| `loops/task_nodes.py` | Modified | Reviewer instruction (list-first), drop "prefer readonly" guidance, task-tree render cache |
| `loops/task_tree_rendering.py` | Modified | `_render_task_tree_markdown` cache wrapper |
| `tools/task_tools.py` | Modified | `TaskInspectTool` list/detail two-tier + compaction |
| `models/task.py` | Modified | Add `version` counter; add `snapshot_compact()` |
| `loops/tinycua_loop.py` | Modified | Wire OutputPersister at append site (line 567) |
| `loops/validation_retry_mixin.py` | Modified | Wire OutputPersister at retry-feedback site (line 1042) |
| `config/system_prompt.py` | Modified | Remove `datetime.now()` from `build_runtime_context` |
| `loops/node.py` | Modified | Cache system message per session; inject time into last user message; single-call forced-tool decision |
| `loops/worker.py` | Modified | Deterministic shortcut (1 route → skip LLM); cache tool list per label hash |
| `loops/query_analyst.py` | Modified | Single-call forced-tool decision |
| `tinycua_sdk/providers/open_ai_chat_completions.py` | Modified | Inject `cache_prompt: true` for local base_urls |

---

## Data Model

### New Entities

```python
# shell.py — pure function, no class
def _check_command_safety(command: str) -> tuple[bool, str | None, str | None]:
    """Returns (blocked, block_reason, warning).
    Hardline patterns → blocked=True. Dangerous patterns → warning set, blocked=False.
    Everything else → (False, None, None)."""

# output_persist.py
def persist_if_oversized(
    content: str, tool_call_id: str, *, threshold: int = 100_000
) -> str:
    """Write content to ./tmp/tool-results/{tool_call_id}.txt if len > threshold.
    Return <persisted-output> preview block (4K head + path + hint) if persisted,
    else return content unchanged."""

def enforce_turn_budget(
    tool_messages: list[dict], *, budget: int = 200_000
) -> list[dict]:
    """Spill largest non-persisted tool results to disk until total <= budget."""

# task.py — new field + method on existing TaskStateStore
@dataclass
class TaskStateStore:
    # ... existing fields ...
    version: int = 0           # monotonic; bumped on every mutation
    _render_cache: tuple[int, str] | None = field(default=None, repr=False)

    def snapshot_compact(self) -> dict:
        """Return {root_task_id, active_task_id, tasks: [{id,title,status,has_result}]}."""
```

### Schema Changes

- `TaskStateStore` gains a `version: int` (default 0). Every mutating method (`create_task`, `transition`, `record_result`, `record_reviewer_decision`, `decompose_task`, `add_artifact`) increments `version += 1`. The existing `_ordered_task_ids` invalidation already happens on structural change; `version` covers *all* mutations (status transitions too, which is needed because the render includes status).
- `run_shell` result dict gains optional keys: `exit_code_meaning` (str | absent), `warning` (str | absent). Existing keys (`stdout, stderr, exit_code, timed_out, error`) unchanged → backward compatible.

---

## API / Interface Contracts

### New / Modified Functions

```python
# shell.py
@tool
def run_shell(command: str, timeout: int = 120) -> dict[str, Any]:
    """Execute a shell command with safety gating and bounded output.
    Hardline commands (rm -rf /, mkfs, shutdown, ...) are blocked.
    Recoverable destructive commands execute with a 'warning' annotation.
    Returns {stdout, stderr, exit_code, timed_out, error, exit_code_meaning?, warning?}.
    Timeout: default 120s, max 600s; >600 rejected."""

# task_tools.py — TaskInspectTool.__call__
def __call__(self, *, task_id: str | None = None, summary: bool = False) -> dict[str, Any]:
    """task_id=None → compact list (FR-011). task_id=X → compacted detail (FR-012).
    summary=True → list mode even with task_id (just {id,title,status,has_result})."""
```

### Error Handling

| Error Case | Response | Notes |
|------------|----------|-------|
| Hardline command match | `{exit_code: -1, error: "BLOCKED (hardline): <reason>"}` | Never executes |
| Timeout > 600s requested | `{exit_code: -1, error: "timeout > 600s; narrow the command"}` | Before Popen |
| `task_inspect` unknown task_id | `{error: "Task X not found."}` | Unchanged |
| Persist write fails (disk full) | Return original content untruncated + log warning | Never lose data; fall back to head+tail truncation only |

---

## Implementation Phases

### Phase 1 — Shell tool hardening (MVP for verification reliability)

- [ ] Add `strip_ansi()` (new `ansi_strip.py` or inline).
- [ ] Add `_interpret_exit_code()` to `shell.py` (copy hermes terminal_tool.py:1610-1671).
- [ ] Add `_check_command_safety()` with hardline + dangerous pattern lists (copy hermes approval.py:255-277 for hardline; curated subset for dangerous).
- [ ] Modify `run_shell`: 120s/600s timeout, `errors="replace"`, ANSI strip, head+tail truncation (50K), gate call, `exit_code`/`exit_code_meaning`/`warning` in result.
- [ ] Add `__main__` self-check block.
- [ ] Delete `shell_readonly.py`; update `tool_scopes.py` (reviewer → `run_shell`); update `task_nodes.py:546-547` guidance.
- [ ] Update `test_native_tools_shell.py`; delete `test_shell_readonly.py`; add `test_exit_code_interpretation.py`.

### Phase 2 — Output/context bloat control

- [ ] New `output_persist.py` with `persist_if_oversized()` + `enforce_turn_budget()`.
- [ ] Wire into `tinycua_loop.py:567` and `validation_retry_mixin.py:1042`.
- [ ] Add `version` to `TaskStateStore`; bump on all mutations.
- [ ] Add `snapshot_compact()`; modify `TaskInspectTool` for list/detail two-tier + compaction.
- [ ] Cache `_render_task_tree_markdown` on version.
- [ ] Update reviewer instruction (`task_nodes.py:86-100`) to list-first pattern.
- [ ] Update `test_task_state_store.py`, `test_result_reviewer_inspect_protocol.py`; add `test_output_persist.py`.

### Phase 3 — Prompt caching

- [ ] Remove `datetime.now()` from `build_runtime_context` (system_prompt.py:117-126); inject time into last user message in `node.py`.
- [ ] Cache system message per session in `node.py:277-292`.
- [ ] Add `cache_prompt: true` to local-provider payloads in `open_ai_chat_completions.py:670-685`.
- [ ] Cache tool list per `(node_id, hash(labels))` in `worker.py`.
- [ ] Update `test_runtime_context_prompt.py`, `test_system_prompt.py`.

### Phase 4 — LLM call reduction (resilience)

- [ ] `failure_count` tracking + soft-context surfacing (>=5 → reviewer sees the count, still LLM-decides) in `task_nodes.py` reviewer + `task.py`.
- [ ] Update `test_result_reviewer_inspect_protocol.py`.

> **Note**: FR-019 (deterministic worker shortcut) and FR-020 (forced single-call decision) were dropped during implementation. FR-019 bypasses the LLM decision (violates "let the LLM decide"); the live loop already satisfies FR-020 via `_call_node_with_retry` + `required_tool_calls` (one call, LLM freely picks the route via the routing tool — confirmed: query_analyst and worker each made exactly 1 LLM call in experiment-4). The standalone `DecisionNode.__call__` 2-call path is not used by the benchmark loop, so changing it risks breaking it for zero benchmark benefit.

---

## Technical Decisions

1. **Decision**: Warn-don't-block for recoverable destructive commands.
   - **Reason**: One-shot prompting target — the agent must delete files and kill processes it needs to without friction. A blocklist that false-positives on `rm -rf ./tmp/build` would recreate the `run_shell_readonly` problem. The hardline floor (unrecoverable only) is the safety net; everything else runs with a warning annotation.
   - **Alternatives Considered**: Block-by-default + `TINYCUA_YOLO` toggle (hermes-style) — rejected because the benchmark always runs one-shot; a toggle adds config-for-a-value-that-never-changes.

2. **Decision**: Merge `run_shell_readonly` into `run_shell` via an in-tool gate function, not a separate tool.
   - **Reason**: The read/write distinction is per-command, not per-tool. A separate readonly tool forced the broad regex that caused the false positives. One tool + one gate function is simpler and lets the reviewer use the same capable shell.
   - **Alternatives Considered**: Command-prefix allowlist for the reviewer (`ls/cat/grep/test/...` only) — rejected because `python -c "..."` verification still false-positives on an allowlist, and the gate is more flexible.

3. **Decision**: Persist oversized tool results in a session-owned system temporary directory behind opaque handles rather than truncating aggressively.
   - **Reason**: Head+tail truncation alone loses the middle; the producing node may need the full output. Handle-based `read_tool_result(char_offset, char_limit)` preserves access, avoids workspace disclosure, and rejects sibling-node access.
   - **Alternatives Considered**: Workspace files + `read_file` — rejected because workspace tools expose the result to other nodes. LLM summarization — rejected because it adds an LLM call.

4. **Decision**: `task_inspect` list mode returns `[{id,title,status,has_result}]`, not the full snapshot.
   - **Reason**: The 40-call sprawl in experiment-4 came from the model full-inspecting every task. A compact list lets it scan once and drill down only into tasks it wants to annotate. The continuation already has the full tree as markdown.
   - **Alternatives Considered**: Force exactly one `task_inspect` (full snapshot) per review — rejected (still verbose; the version-cached render already gives fresh state in the continuation).

5. **Decision**: Move the timestamp out of the system prompt to the last user message.
   - **Reason**: `datetime.now()` in the system message (system_prompt.py:117) guarantees zero prompt-cache hits on every provider. Putting "Current time" in the user turn keeps the system prefix byte-stable. Highest-leverage caching change, 5 lines.
   - **Alternatives Considered**: Drop the timestamp entirely — rejected (the model benefits from knowing the date for time-sensitive tasks; user-turn injection is free).

6. **Decision**: Single-call forced-tool decision for routing nodes.
   - **Reason**: `DecisionNode` does `_analysis_call` + `_classification_call` (2 round-trips). For nodes with a required routing tool, the tool call *is* the classification — the analysis call is redundant. One call with `tool_choice` forced to the routing tool, read the label from args. Halves routing cost.
   - **Alternatives Considered**: Keep two calls for "better reasoning" — rejected (the forced tool already constrains output; the analysis prose is discarded anyway).

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hardline regex false-positives on legitimate commands | Low | High (blocks verification) | `_CMDPOS` anchoring (after `;`/`&&`/`\|`/`$(`/backtick/sudo/env); test `echo reboot`, `grep 'shutdown' log` pass |
| Output persistence writes fail (disk full) | Low | Med | Fall back to returning original content (never lose data); head+tail truncation still applies as a second line |
| `task_inspect` compact list omits a field the reviewer needs | Med | Low | Detail mode (`task_id=X`) still returns the full compacted task; the reviewer drills down when needed |
| Removing timestamp breaks a test that asserts its presence | Med | Low | Update `test_runtime_context_prompt.py` to assert time is in the user turn, not the system message |
| `cache_prompt: true` rejected by a strict OpenAI-compatible server | Low | Low | Only injected for local base_urls (localhost/127.0.0.1/host.docker.internal); real OpenAI never sees it |
| Single-call decision reduces routing accuracy | Low | Med | Only applied to nodes with a `required_tool_calls` constraint (forced schema-validated output); general DecisionNode keeps 2 calls |

---

## Open Questions

_None._

---

## References

- Spec: `./spec.md`
- Related designs: `../native_tools/design.md` (original shell/file tool design), `../tinycua-architecture/` (node-graph architecture)
- External references (read during research, not bundled):
  - hermes-agent `tools/approval.py:255-277` (hardline patterns), `tools/terminal_tool.py:1610-1671` (`_interpret_exit_code`), `tools/tool_output_limits.py` (truncation constants), `tools/tool_result_storage.py` (persistence pattern)
  - llama.cpp `--cache-prompt` / `cache_prompt` request field (KV reuse for identical prefixes)
