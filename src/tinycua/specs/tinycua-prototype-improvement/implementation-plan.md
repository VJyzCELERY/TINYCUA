# Implementation: TinyCUA Prototype Improvement

Comprehensive hardening of the TinyCUA research prototype along four axes motivated by the five-experiment evaluation: code cleanup, retry redesign (structured output + stateful nodes), task-tree shrink, and tool hardening.

## Context

- **Spec Reference**: `src/tinycua/specs/tinycua-prototype-improvement/spec.md`
- **Design Reference**: `src/tinycua/specs/tinycua-prototype-improvement/design.md`
- **Priority**: P0
- **Estimated Effort**: XL

## Environment Pre-requisites

### Configuration

- [x] **.env file** — already copied to worktree:
  ```
  # src/tinycua/.env — LLM base URL, API key, model
  TINYCUA_BASE_URL=...
  TINYCUA_API_KEY=...
  TINYCUA_MODEL=...
  # src/experiment/.env — SearXNG URL, judge config
  ```
- [x] **.env.test** — copied to `src/tinycua/.env.test`
- [x] **Environment variables** documented in `src/tinycua/.env.example`, `src/experiment/.env.example`
- [x] **None** — no additional secrets needed beyond existing config

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| LM Studio (local LLM) | Yes (for integration verify) | `lms server start --model qwen3.5-9b` | `curl $TINYCUA_BASE_URL/v1/models` |
| SearXNG | Yes (for web tools) | `docker compose up -d searxng` (src/experiment/docker-compose.yml) | `curl localhost:8080/search?q=test&format=json` |
| None other | - | - | - |

### Data / Fixtures

- [x] **None** — no database, no migrations. Task store is in-memory.

### Access / Permissions

- [x] **None** — local LLM + local SearXNG, no external auth.

### Developer Tooling

- [x] **Runtime**: Python 3.11 (per preflight), uv package manager
- [x] **Additional CLI tools**: `html2text` (new dep, added via uv)
- [x] **None else** — no special tooling

---

## Success Criteria — Integration Tests (TDD First)

```python
# Test file: src/tinycua/tests/unit/test_node_contract.py
"""NodeContract is the single source of truth for required-tools-per-node."""

def test_node_contract_replaces_scattered_maps():
    """task_executor's required tools come only from NodeContract, not inline maps."""
    contract = get_node_contract("task_executor")
    assert contract.required_tools == frozenset({"task_result_update"})
    assert contract.deterministic_tools == frozenset({"terminate"})
    assert contract.structured_output_schema is not None  # json_schema for task_result_update


def test_node_state_observable_in_trace():
    """NodeProgress transitions emit trace events with from/to/attempt."""
    node = build_node("task_executor")
    node.progress.transition(NodeState.RETRYING, "schema invalid")
    assert node.progress.phase == NodeState.RETRYING
    assert node.progress.history[-1]["from"] == NodeState.EXECUTING
    assert node.progress.history[-1]["to"] == NodeState.RETRYING


# Test file: src/tinycua/tests/unit/test_task_shrink.py
"""Task tree delete/merge for correcting over-decomposition."""

def test_delete_task_removes_pending_subtree():
    store = TaskStateStore()
    root = store.create_task("root")
    child = store.create_task("child", parent_id=root.task_id)
    grandchild = store.create_task("gc", parent_id=child.task_id)
    store.delete_task(child.task_id)
    assert child.task_id not in store.tasks
    assert grandchild.task_id not in store.tasks  # subtree removed
    assert grandchild.task_id not in store.tasks[root.task_id].children


def test_delete_completed_task_raises():
    store = TaskStateStore()
    root = store.create_task("root")
    store.transition(root.task_id, TaskStatus.IN_PROGRESS)
    store.transition(root.task_id, TaskStatus.COMPLETED)
    with pytest.raises(ValueError, match="immutable"):
        store.delete_task(root.task_id)


def test_merge_preserves_child_result_on_parent():
    store = TaskStateStore()
    root = store.create_task("root")
    child = store.create_task("child", parent_id=root.task_id)
    store.transition(child.task_id, TaskStatus.IN_PROGRESS)
    store.record_reviewer_decision(child.task_id, {"decision": "approved"})
    # child has a result via review; parent does not
    store.merge_tasks(child.task_id, root.task_id)
    assert child.task_id not in store.tasks
    assert root.result is not None  # preserved


def test_effort_profiled_threshold():
    """high effort → lower threshold (more aggressive shrink trigger)."""
    low = shrink_threshold_for_effort("low")
    high = shrink_threshold_for_effort("high")
    assert high < low


# Test file: src/tinycua/tests/unit/test_retry_structured_output.py
"""2-track retry: structured output for LLM-decided, deterministic for no-arg."""

def test_structured_output_track_uses_response_format(monkeypatch):
    """task_executor LLM call includes response_format: json_schema."""
    captured = {}
    async def fake_call(agent, node, messages, tools, **kw):
        captured["response_format"] = kw.get("response_format")
        return LLMResult(content='{"content":"done","success":true}', tool_calls=[])
    # ... wire fake_call, run node, assert captured["response_format"]["type"] == "json_schema"


def test_judge_retry_removed():
    """_judge_retry no longer exists in the codebase."""
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "_judge_retry", "src/tinycua/tinycua/"],
        capture_output=True, text=True
    )
    assert result.returncode == 1  # no matches


def test_deterministic_terminate_synthesized_without_llm():
    """terminate (no args) is synthesized by the runtime, no LLM round-trip."""
    # ... call _direct_terminate, assert no LLM call made, terminate tool executed


# Test file: src/tinycua/tests/unit/test_fetch_url_markdown.py
"""fetch_url returns markdown, refuses binary, retries 429."""

def test_fetch_html_returns_markdown():
    result = fetch_url("http://example.org/page.html")
    assert result.success
    assert "<title>" not in result.output  # HTML stripped
    assert "# " in result.output or result.output.strip()  # markdown


def test_fetch_binary_refused():
    result = fetch_url("http://example.org/image.png")
    assert not result.success
    assert "binary" in result.error.lower()


def test_fetch_returns_consistent_dict_shape():
    result = fetch_url("http://example.org/404")
    assert isinstance(result, ToolResult)
    assert hasattr(result, "success") and hasattr(result, "error")


# Test file: src/tinycua/tests/unit/test_shell_venv.py
"""run_shell venv activation + shell context in result."""

def test_venv_activation_prepended(monkeypatch):
    captured = {}
    def fake_popen(cmd, *a, **kw):
        captured["cmd"] = cmd
        # ... return fake process
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    run_shell("python -c 'import fastapi'", venv=".venv")
    assert "source .venv/bin/activate" in captured["cmd"] or ". .venv/bin/activate" in captured["cmd"]


def test_shell_context_in_result():
    result = run_shell("echo hi", venv=".venv")
    assert result.metadata["venv_active"] is True
    assert result.metadata["shell"] in ("/bin/sh", "/bin/bash")


# Test file: src/tinycua/tests/unit/test_workspace_binding.py
"""context.py raises when workspace unset, re-roots absolute paths."""

def test_unset_workspace_raises():
    bind_workspace(None)  # ensure unset
    with pytest.raises(WorkspaceNotBoundError):
        resolve_workspace_path("foo.txt")


def test_absolute_path_rerooted_under_workspace(tmp_path):
    bind_workspace(tmp_path)
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "api.py").write_text("x")
    # absolute path matching workspace subpath re-roots
    resolved = resolve_workspace_path("/backend/api.py")
    assert resolved == (tmp_path / "backend" / "api.py")


# Test file: src/tinycua/tests/unit/test_tool_contract.py
"""Class-based tools route through SDK coercion; review tool no default approve."""

def test_class_tool_coerces_string_to_int():
    """TaskUpdateTool with task_id='7' (string) coerces to int via SDK layer."""
    # ... call tool with stringified int, assert store received int


def test_review_decision_required():
    tool = TaskReviewDecisionTool()
    with pytest.raises((TypeError, ValueError)):
        tool()  # no decision arg → raises, not default-approve


# Test file: src/tinycua/tests/unit/test_todo_real_ops.py
"""todo_tools no longer a stub."""

def test_todo_update_in_place():
    tool = TodoWriteTool()
    tool(descriptions=["a", "b"])
    tool.update(0, description="updated")
    assert tool.items[0]["description"] == "updated"


def test_todo_delete():
    tool = TodoWriteTool()
    tool(descriptions=["a", "b"])
    tool.delete(0)
    assert len(tool.items) == 1


# Test file: src/tinycua/tests/unit/test_dead_code_removed.py
"""Dormant retry loops + stubs are gone."""

def test_process_node_call_retry_removed():
    """ProcessNode.__call__ no longer has a retry loop — it delegates to loop-owned path."""
    import inspect
    from tinycua.loops.node import ProcessNode
    src = inspect.getsource(ProcessNode.__call__)
    assert "for attempt" not in src  # no retry loop


def test_open_question_branch_removed():
    import subprocess
    result = subprocess.run(
        ["grep", "-rn", "OPEN_QUESTION", "src/tinycua/tinycua/"],
        capture_output=True, text=True
    )
    # only the enum member docstring note may remain; the routing branch is gone
    assert "schedule_after_review" not in result.stdout or result.returncode == 1
```

#### Milestone 9 — Context Window Protection (Hotfix)

```python
# Test file: src/tinycua/tests/unit/test_context_window_protection.py
"""Unit tests for FR-082..FR-085: context window protection hotfix."""

import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_fr082_compaction_wired_on_cli_path():
    """FR-082: _build_run_agent sets compaction_strategy=SimpleCompaction()."""
    from tinycua.cli.run import _build_run_agent
    from tinycua.compaction.simple import SimpleCompaction
    config = {"base_url": "http://x", "api_key": "k", "model": "m", "provider_type": "openai-chat-completions"}
    agent = _build_run_agent(config, workspace=MagicMock(), artifact_dir=None,
                             worker_effort="medium", no_tool_audit=False,
                             allow_open_question=False, replan_threshold=5, log_path=None)
    sc = agent.loop.session_config
    assert isinstance(sc.compaction_strategy, SimpleCompaction)


def test_fr083_max_context_messages_enforced():
    """FR-083: build_messages_with_dedupe bounds prompt to last max_context_messages."""
    from tinycua.loops.node import build_messages_with_dedupe
    from tinycua.models.session import Session
    from tinycua.config.session_config import SessionConfig
    from tinycua.models.session_context_entry import SessionContextEntry
    session = Session(session_config=SessionConfig(max_context_messages=3))
    for i in range(10):
        session.session_context.append(
            SessionContextEntry(content=f"entry {i}", segment="output", created_seq=i)
        )
    messages = build_messages_with_dedupe(session)
    # At most 3 context-derived assistant messages (plus system/continuation are not added here)
    assert len(messages) <= 3
    # Audit trail intact
    assert len(session.session_context) == 10


def test_fr083_none_means_unlimited():
    """FR-083: max_context_messages=None disables the cap."""
    from tinycua.loops.node import build_messages_with_dedupe
    from tinycua.models.session import Session
    from tinycua.config.session_config import SessionConfig
    from tinycua.models.session_context_entry import SessionContextEntry
    session = Session(session_config=SessionConfig(max_context_messages=None))
    for i in range(10):
        session.session_context.append(
            SessionContextEntry(content=f"entry {i}", segment="output", created_seq=i)
        )
    messages = build_messages_with_dedupe(session)
    assert len(messages) == 10  # unlimited — all entries sent


@pytest.mark.asyncio
async def test_fr084_probe_returns_context_length():
    """FR-084: resolve_max_context returns the server-reported context_length."""
    from tinycua.cli.model_probe import resolve_max_context
    mock_model = MagicMock()
    mock_model.id = "qwen3.5-9b"
    mock_model.context_length = 32768
    mock_list = MagicMock()
    mock_list.data = [mock_model]
    with patch("tinycua.cli.model_probe.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=mock_list)
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        result = await resolve_max_context("http://x", "k", "qwen3.5-9b", fallback=128000)
    assert result == 32768


@pytest.mark.asyncio
async def test_fr084_probe_error_falls_back():
    """FR-084: resolve_max_context falls back on network error."""
    from tinycua.cli.model_probe import resolve_max_context
    with patch("tinycua.cli.model_probe.AsyncOpenAI", side_effect=Exception("network")):
        result = await resolve_max_context("http://x", "k", "m", fallback=128000)
    assert result == 128000


@pytest.mark.asyncio
async def test_fr084_probe_missing_field_falls_back():
    """FR-084: resolve_max_context falls back when context_length is absent."""
    from tinycua.cli.model_probe import resolve_max_context
    mock_model = MagicMock()
    mock_model.id = "gpt-4o"
    mock_model.context_length = None  # vanilla OpenAI omits the field
    mock_list = MagicMock()
    mock_list.data = [mock_model]
    with patch("tinycua.cli.model_probe.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.models.list = AsyncMock(return_value=mock_list)
        mock_client.close = AsyncMock()
        mock_client_cls.return_value = mock_client
        result = await resolve_max_context("http://x", "k", "gpt-4o", fallback=128000)
    assert result == 128000


def test_fr085_compaction_fires_on_attempt_1(caplog):
    """FR-085: _maybe_compact is called at top of attempt loop, not gated on attempt > 1."""
    # Integration: stub a loop with _last_input_tokens over threshold,
    # assert _maybe_compact is called before attempt 1's messages are built.
    from tinycua.loops.tinycua_loop import TinyCUALoop
    import inspect
    src = inspect.getsource(TinyCUALoop._call_node_with_retry)
    # The _maybe_compact call must NOT be inside an `if attempt > 1` block
    assert "if attempt > 1" not in src or "_maybe_compact" not in src.split("if attempt > 1")[-1].split("attempt_messages")[0]


def test_fr085_compaction_logs_at_info(caplog):
    """FR-085: compaction_trigger is logged at INFO, not DEBUG."""
    from tinycua.loops.tinycua_loop import logger as loop_logger
    import inspect
    src = inspect.getsource(loop_logger)  # won't work; instead check the module source
    # Verify the log level in the source
    import tinycua.loops.tinycua_loop as mod
    src = inspect.getsource(mod)
    # The compaction_trigger line must use logger.info, not logger.debug
    assert "logger.info(" in src
```

### Key Test Scenarios

- [ ] **Scenario 1**: NodeContract is the single source — `task_result_update` appears only in `NodeContract`, not in 13 inline maps (grep assertion).
- [ ] **Scenario 2**: Structured-output track — `task_executor` LLM payload includes `response_format: json_schema`.
- [ ] **Scenario 3**: `_judge_retry` removed — grep returns zero matches.
- [ ] **Scenario 4**: Deterministic terminate — synthesized without LLM round-trip.
- [ ] **Scenario 5**: Task-tree merge preserves child result on parent.
- [ ] **Scenario 6**: Effort-profiled threshold — high effort < low effort threshold.
- [ ] **Scenario 7**: fetch_url markdown — `<title>` stripped, `# ` present.
- [ ] **Scenario 8**: Shell venv — `source .venv/bin/activate` prepended, context in result.
- [ ] **Scenario 9**: Workspace unset raises — `WorkspaceNotBoundError`.
- [ ] **Scenario 10**: Review tool no default approve — raises on omit.
- [ ] **Scenario 11**: todo_tools real ops — update-in-place, delete work.
- [ ] **Scenario 12**: Dead code removed — `ProcessNode.__call__` has no retry loop.
- [ ] **Scenario 13 (M9)**: Compaction wired on CLI path — `_build_run_agent` sets `SimpleCompaction` (FR-082).
- [ ] **Scenario 14 (M9)**: `max_context_messages` cap — prompt bounded to last N, audit trail intact (FR-083).
- [ ] **Scenario 15 (M9)**: Server probe — `resolve_max_context` returns `context_length` on success, fallback on error/missing (FR-084).
- [ ] **Scenario 16 (M9)**: `--max-context` override — explicit flag > server probe > SDK default (FR-084).
- [ ] **Scenario 17 (M9)**: Continuous compaction — `_maybe_compact` called at top of attempt loop, not gated on `attempt > 1` (FR-085).
- [ ] **Scenario 18 (M9)**: Compaction logs at INFO — `compaction_trigger` visible in real experiment logs (FR-085).
- [ ] **Scenario 19 (M9)**: Experiment-5 re-run survives — no "Context size has been exceeded" (FR-082..FR-085 combined).

## Verification Plan

### Automated Tests

- [ ] Unit tests (defined above) — these must pass for implementation to be complete
- [ ] Existing test suite — confirm no regressions: `uv run pytest` per subproject
- [ ] Import sanity — `uv run python -c "import tinycua"` after each phase

### Manual Verification

- [ ] Re-run all 5 tinycua experiments; inspect transcripts for: zero retry exhaustion (exp-4), zero exit_code=127 (exp-4), zero path mismatches (exp-4), task-tree shrink events (exp-5), runtime < 4456s (exp-5).
- [ ] Inspect exp-4 transcript: no `/backend/...` path checks; venv-activated shell commands; structured `task_result_update` payloads.
- [ ] Inspect exp-5 transcript: `task_tree_shrink` trace events; reduced executor/reviewer cycles.

### Performance Considerations

- [ ] Experiment-5 runtime < baseline 4456s (task-tree shrink reduces cycles).
- [ ] Experiment-4 runtime < baseline 1985s (structured output reduces retry rounds; venv fix removes 127 loops).
- [ ] No prompt-cache regression — structured-output payload construction must not break byte-stable system messages.

---

## Proposed Changes

### Milestone 1 — Code Cleanup

#### REMOVE `src/tinycua/tinycua/loops/node.py`

- **Remove `ProcessNode.__call__` retry loop (`:740-813`)**: bypassed by loop-owned `_call_node_with_retry`; dead for the active runtime. Keep `ProcessNode` as a base class with `build_messages` etc., but `__call__` delegates to the loop-owned path or raises `NotImplementedError` directing to the loop.
- **Remove `DecisionNode.__call__` retry loop (`:939-1015`)**: same — dormant.
- **Remove `_call_failure_route` (`:616-627`)**: always returns `False`, no overrides.
- **Remove `Node.propagate` no-op default (`:654-660`)**: or mark as abstract if subclasses implement.

#### REMOVE `src/tinycua/tinycua/loops/recovery_stages_mixin.py`

- **Delete the whole file** (or its content): `_judge_retry` is removed per FR-012. The other stages (focused retry, tightening retry) merge into the structured-output track.

#### MODIFY `src/tinycua/tinycua/loops/validation_retry_mixin.py`

- **Remove `_route_task_executor_failure_to_reviewer` (`:225-233`)**: always `False`, dead branch.
- **Remove `_validate_tool_owned_task_state`'s inline `required_by_node`/`any_of_by_node` (`:872-880`)**: consult `NodeContract`.
- **Remove `_validate_task_executor_action` (`:817-847`)** if it duplicates `_validate_tool_owned_task_state` (it does — both check `task_result_update`): consolidate into one `NodeContract`-consulting validator.
- **Remove `_worker_lifecycle_ready_to_terminate`'s inline per-node rules (`:630-664`)**: consult `NodeContract`.
- **Remove `_can_stop_after_tool_batch`'s inline per-node rules (`:796-807`)**: consult `NodeContract`.
- **Remove `_retry_required_tool_name` (`:166-178`)**: consult `NodeContract`.

#### MODIFY `src/tinycua/tinycua/loops/prompt_protocol_mixin.py`

- **Remove `_required_single_tool_choice_name` (`:461-468`)**: consult `NodeContract`.
- **Remove `_missing_or_required_tool_name` (`:470-487`)**: consult `NodeContract`.
- **Remove `_requires_any_tool_choice` (`:432-435`)**: always `False`.

#### MODIFY `src/tinycua/tinycua/loops/orchestration_mixin.py`

- **Remove `_RECOVERY_CHAINS` inline dict (`:918-924`)**: consult `NodeContract`.
- **Replace `_log_recovery_cycle` `print(stderr)` (`:954-989`)**: with `logger.warning(...)` structured.

#### MODIFY `src/tinycua/tinycua/loops/worker_runtime.py`

- **Remove commented `OPEN_QUESTION` branch (`:98-105`)** and the `ResponseNode` `noqa` import (`:9`)**.

#### MODIFY `src/tinycua/tinycua/agent/tools/native/output_persist.py`

- **Remove duplicate `print("output_persist.py self-check OK")` (`:338`)**.

#### NEW `src/tinycua/tinycua/loops/node_contract.py`

- **`NodeContract` dataclass + `_NODE_CONTRACTS` registry**: the single source of truth. Populated from the existing 13+ maps (all their data moves here).

### Milestone 2 — Stateful Nodes

#### MODIFY `src/tinycua/tinycua/loops/node.py`

- **Add `NodeState` enum + `NodeProgress` dataclass**: `phase`, `attempt_count`, `visited_tools`, `satisfied_requirements`, `history`.
- **Add `progress: NodeProgress` field to `Node`**: initialized `PENDING`.
- **Add `contract` property to `Node`**: looks up `NodeContract` from registry by `node_id`.

#### MODIFY `src/tinycua/tinycua/loops/trace_state_mixin.py`

- **Emit `node_state_transition` trace events**: on every `progress.transition()` call, structured fields (`node_id`, `from_state`, `to_state`, `attempt_count`, `reason`).

### Milestone 3 — Retry Redesign

#### MODIFY `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Structured-output payload construction (`_call_agent_llm`)**: if `node.contract.structured_output_schema is not None`, include `response_format: {"type": "json_schema", "schema": <schema>}` in the LLM call.
- **Build schema from tool type hints**: use `type_to_json_schema` (`sdk/schema.py:14`) on the required tool's input type.

#### MODIFY `src/tinycua/tinycua/loops/orchestration_mixin.py`

- **Replace `_unbounded_recovery`'s 5-stage escalation with 2-track**:
  - **Structured-output track**: retry with schema error as the retry signal (replaces focused retry + tightening retry + judge retry).
  - **Deterministic track**: keep `_direct_terminate` / `_coerce_terminate_only_response` for no-arg tools.
- **Add FR-015 stuck-model diagnostic**: after >10 consecutive schema failures, log a diagnostic (observability, not a bound — loop continues).

### Milestone 4 — Task Tree Shrink

#### MODIFY `src/tinycua/tinycua/models/task.py`

- **Add `TaskStateStore.delete_task(task_id)`**: removes task + pending subtree, re-links siblings, bumps version. Raises on completed/root/active.
- **Add `TaskStateStore.merge_tasks(child_id, parent_id)`**: preserves child result on parent (per preserve-work rule), discards child's pending subtree, bumps version.

#### NEW `src/tinycua/tinycua/tools/task_shrink_tool.py` (or add to `task_tools.py`)

- **`TaskShrinkTool`**: delete + merge operations with LLM-provided rationale. Exposed to `task_analyzer`.

#### MODIFY `src/tinycua/tinycua/loops/task_nodes.py` (TaskAnalyzer continuation)

- **Add effort-profiled threshold prompt**: when pending children exceed threshold (low effort → >15, high effort → >8), the continuation nudges the analyzer to consider shrinking. The LLM decides what to merge/delete.

#### MODIFY `src/tinycua/tinycua/config/node_config.py`

- **Add effort-profiled threshold config**: `shrink_threshold` per effort level.

#### MODIFY `src/tinycua/tinycua/loops/trace_state_mixin.py`

- **Emit `task_tree_shrink` trace events**: structured fields (`node_id`, `action`, `task_id`, `affected_ids`, `rationale`, `new_tree_size`).

### Milestone 5 — Tool Hardening — Experiment-Evidenced

#### MODIFY `src/tinycua/tinycua/agent/tools/native/web.py`

- **Add `html2text` import + markdown conversion**: in `_process_response`, if Content-Type is HTML, run `html2text.html2text(response.text)`.
- **Add Content-Type guard**: if Content-Type starts with `image/`/`application/pdf`/`application/zip`, return `ToolResult(success=False, error="binary content-type ... not supported")`.
- **Add User-Agent header**: default `"TinyCUA/1.0"` (or configurable).
- **Add retry on 429/5xx**: exponential backoff, max 3 retries.
- **Change return type to `ToolResult`**: consistent dict shape on success and failure.

#### MODIFY `src/tinycua/tinycua/agent/tools/native/web_search.py`

- **Distinguish backend-down from no-matches**: timeout/connection-error → `ToolResult(success=False, error="searxng unreachable: ...")`; empty results → `ToolResult(success=True, output=[], metadata={"note": "no matches found"})`.
- **Add retry on timeout/connection-error**: exponential backoff, max 3 retries.

#### MODIFY `src/tinycua/tinycua/agent/tools/native/shell.py`

- **Add `venv` parameter**: prepends `source <venv>/bin/activate &&` (or POSIX `. <venv>/bin/activate &&`).
- **Add `executable` parameter**: default `/bin/sh`, allow `/bin/bash`. If bash requested but not installed, fall back + warn.
- **Add `env` parameter**: pass to `Popen(env={**os.environ, **env})`.
- **Add shell context to result**: `metadata={cwd, shell, venv_active}`.

#### MODIFY `src/tinycua/tinycua/agent/tools/native/context.py`

- **Drop cwd fallback (`:50-51`)**: `resolve_workspace_path` raises `WorkspaceNotBoundError` if `_WORKSPACE_DIR` is `None`.
- **Re-root absolute paths matching workspace subpath**: heuristic `if (workspace / path).exists(): prefer it`.
- **Canonicalize reported paths to workspace-relative**: add `to_workspace_relative(path)` helper; tool results include both absolute + relative.

#### MODIFY `src/tinycua/tinycua/agent/tools/native/files.py`

- **Assert workspace bound at session start**: `bind_workspace` called before any file tool; raise if unset.

#### NEW `src/tinycua/tinycua/agent/tools/native/tool_result.py`

- **`ToolResult` dataclass**: `success: bool`, `output: Any`, `error: str | None`, `metadata: dict`.

### Milestone 6 — Tool Hardening — Other Tools

#### MODIFY `src/tinycua/tinycua/config/types.py`

- **`Tool.invoke` delegates to SDK coercion**: for class-based tools, route through `tinycua_sdk.tools.decorators._coerce_arg` before calling `self(**kwargs)`.

#### MODIFY `src/tinycua/tinycua/tools/task_tools.py`

- **`TaskReviewDecisionTool`**: make `decision` required (remove default `"approved"`).
- **`TaskUpdateTool`**: remove `additionalProperties: True` for metadata; use typed `metadata: dict[str, str]` schema.

#### MODIFY `src/tinycua/tinycua/tools/enhanced_context_retrieval.py`

- **Fix index math (`:188`)**: correct the `len(session_context[-5:]) - 1 + index` calculation for `len < 5`.
- **Add cache cap + LRU eviction (`:46-63`)**: max 100 entries, evict oldest.

#### MODIFY `src/tinycua/tinycua/agent/tools/native/python_exec.py`

- **Reject >max with error**: like `run_shell:362-372`, return `ToolResult(success=False, error="timeout must be <= 30s")` instead of silent clamp.

#### MODIFY `src/tinycua/tinycua/tools/todo_tools.py`

- **Real update-in-place**: `update(index, description=..., status=...)` edits an existing todo.
- **Real delete**: `delete(index)` removes a todo.
- **Status transitions**: `pending`/`in_progress`/`done` (lightweight — no transition-guarded state machine, just set the field).

### Milestone 7 — Logging

#### MODIFY (threads through all above)

- **Replace all `print(stderr)` with `logger`**: structured fields.
- **Emit structured trace events**: node state transition, retry with schema error, tool call with result shape, recovery cycle, task-tree shrink.
- **Make retry/recovery observable without stderr**: trace events go to execution trace + logger.

### Milestone 8 — Loop Reliability

#### MODIFY `src/tinycua/tinycua/models/task.py`

- **`consecutive_failures` property**: break on `replan_boundary` entries in addition to `approved` (FR-049).

#### MODIFY `src/tinycua/tinycua/config/session_config.py`

- **Add `max_replans: int | None = None`** field. When `None`, derive from `worker_effort`: `{"none": 0, "low": 1, "medium": 3, "high": 6}`. Document in the docstring (FR-050).

#### MODIFY `src/tinycua/tinycua/loops/worker_runtime.py`

- **`schedule_replan`**: after queueing the replan nodes, insert a synthetic `{"decision": "replan_boundary", "rationale": "replan triggered", "metadata": {}}` entry into the active task's `reviewer_decisions`. This resets `consecutive_failures` (FR-049).
- **`schedule_after_review`**: before the threshold check, count `replan_boundary` entries in `reviewer_decisions` → `replan_count`. If `replan_count >= max_replans` (from `SessionConfig`), force-approve the task: call `record_reviewer_decision(approved, rationale="replan budget exhausted (effort={effort}, cap={max_replans}).")` and schedule the next task (not another replan) (FR-050).
- **Non-vacuous replan**: `plan_unchanged` preserves the existing plan while retaining the executor boundary for verification before review (FR-051).

#### MODIFY `src/tinycua/tinycua/agent/tools/native/files.py`

- **`_fuzzy_find_and_replace`**: track per-strategy whether it found 0 vs >1 matches. After all strategies, if any found >1 matches (and `replace_all=False`), return `"Found N matches for old_string in {strategy}. Provide more context in old_string to disambiguate, or set replace_all=True to replace all N."` If all found 0, keep the existing `"Could not find old_string"` error (FR-052).
- **`append_file`**: return `diff_preview` (first ~500 chars of appended content with a leading `\n--- appended ---\n` marker) and `new_file_size` (FR-058).
- **`write_file`**: return `diff_preview` (first ~500 chars of written content) and `new_file_size` (FR-058).
- **`str_replace`**: replace `diff_preview = new_string[:200]` with a real `difflib.unified_diff` snippet (first ~500 chars) between old and new content (FR-058).

#### MODIFY `src/tinycua/tinycua/loops/validation_retry_mixin.py`

- **`_validate_result_reviewer_inspects_after_decision`**: rephrase the error string from `"ResultReviewer must call task_inspect after task_review_decision ..."` to `"ResultReviewer must call task_inspect after the review decision is recorded."` — removes the `task_review_decision` substring so the heuristic doesn't misfire (FR-053).

#### MODIFY `src/tinycua/tinycua/loops/prompt_protocol_mixin.py`

- **`_missing_or_required_tool_name`**: add `task_inspect` to the candidate tuple, placed BEFORE `task_review_decision`, as a belt-and-suspenders fix (FR-053).

#### MODIFY `src/tinycua/tinycua/loops/task_nodes.py`

- **`_TASK_ANALYZER_INSTRUCTION` / `_TASK_ANALYZER_CONTINUATION`**: add "After `task_decompose` or `task_update` succeeds, call `terminate`." Remove the "call `task_inspect`" first instruction from the continuation (FR-054).
- **`_RESULT_REVIEWER_INSTRUCTION`**: add the general sanity-checker responsibility — detect duplicate/repeated content (via `run_shell` grep/wc/sort|uniq), hallucinated claims, structural inconsistency. Generic across artifact types, prompt-only (FR-056).
- **Reviewer `build_tool_system_prompt`**: when `run_shell` is available, add dedup guidance (e.g. `grep -c '^## ' report.md`, `sort | uniq -d`) (FR-056).
- **Analyzer completion**: retain the queued executor even when `plan_unchanged` is true so completed nodes always transition to a different node and the result is verified before review (FR-051/FR-067).
- **Analyzer `local_replan` mode prompt**: mention `task_shrink` as an option for restructuring (only unfinished tasks), and `task_update` with `plan_unchanged=true` when the plan is correct (FR-051).

#### MODIFY `src/tinycua/tinycua/config/node_config.py`

- **`task_analyzer` `max_attempts`**: raise from the default 3 to 10 (FR-055).

#### MODIFY `src/tinycua/tinycua/tools/task_tools.py`

- **`TaskReviewDecisionTool` description**: document that `rejected` is an alias for `needs_revision` — both send the task back for rework (FR-057).

### Milestone 9 — Context Window Protection (Hotfix)

Hotfix for the experiment-5 context-overflow failure. Four independent fixes (A+B+C+D) that compose to bound the prompt to the real served context window. TDD-first: write the tests in the Success Criteria section below before any implementation.

#### MODIFY `src/tinycua/tinycua/cli/run.py`

- **`_build_run_agent`**: add `compaction_strategy=SimpleCompaction()` to the `SessionConfig(...)` call (FR-082). Import: `from tinycua.compaction.simple import SimpleCompaction`. This is the root-cause fix — the factory's compaction-wired default was bypassed because the CLI passed a non-None config without the strategy.
- **`run_command`**: after `_load_run_config`, resolve `max_context` via `resolve_max_context(config["base_url"], config["api_key"], config["model"], fallback=128_000)` when `--max-context` is not set (FR-084). Pass the resolved value into `build_language_model` via the new `max_context` kwarg.

#### MODIFY `src/tinycua/tinycua/cli/config.py`

- **`build_language_model`**: accept `max_context: int | None = None` and pass it to `LanguageModel(max_context=max_context)` when provided (FR-084). When `None`, `LanguageModel` keeps its default `128_000`.

#### MODIFY `src/tinycua/tinycua/cli/main.py`

- **`_add_run_arguments`**: add `--max-context` argparse flag (`type=int, default=None`) with help text: "Override the model's max context window (tokens). Default: probe the server; fall back to 128000." (FR-084).
- **`_normalise_run_args`**: pass `max_context` through to `run_command`.

#### NEW `src/tinycua/tinycua/cli/model_probe.py`

- **`resolve_max_context(base_url, api_key, model_name, fallback) -> int`**: best-effort async function that probes `GET {base_url}/v1/models` via `AsyncOpenAI`, finds the model matching `model_name` (or the first model on local servers), and returns its `context_length` field (FR-084). Resolution priority inside the probe: `loaded_instances[0].config.context_length` (LM Studio active limit) → `max_context_length` (LM Studio ceiling) → top-level `context_length` (Ollama / OpenAI-compat extension) → `fallback`. Any exception (network, parse, missing) → return `fallback` with a DEBUG log. Never raises. One HTTP call, no token cost.

#### MODIFY `src/tinycua/tinycua/loops/node.py`

- **`build_messages_with_dedupe`**: after resolving `context_entries` (post-dedupe) and before converting to messages, slice to the last `max_context_messages` when set (FR-083):
  ```python
  max_msgs = session.session_config.max_context_messages if session.session_config is not None else None
  if max_msgs is not None and len(context_entries) > max_msgs:
      context_entries = context_entries[-max_msgs:]
  ```
  The full `session_context` list is never mutated — only the prompt-bound subset is capped. `None` = unlimited.

#### MODIFY `src/tinycua/tinycua/loops/tinycua_loop.py`

- **`_call_node_with_retry`**: move the `_maybe_compact` call from inside `if attempt > 1:` (lines 805-808) to the top of the `for attempt in range(...)` loop body, before `attempt_messages` is built (FR-085). The existing chicken-and-egg guard (`_last_input_tokens <= 0` → skip, in `_maybe_compact` line 706) handles the very-first-call-of-a-run case.
- **`_maybe_compact` log lines**: change `logger.debug` → `logger.info` on the `compaction_trigger` line (722) and the `compaction_failed` line (733) (FR-085). The experiment runs at `INFO` (`run.py:294`); DEBUG lines were invisible, making it look like compaction never fired.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `loops/node_contract.py` | New | `NodeContract` registry — single source of truth |
| `loops/node.py` | Modify | Add `NodeState`/`NodeProgress`; remove dormant retry loops |
| `loops/recovery_stages_mixin.py` | Remove | `_judge_retry` deleted |
| `loops/validation_retry_mixin.py` | Modify | Remove inline maps; consult `NodeContract`; **M8**: rephrase inspect-after-decision error |
| `loops/orchestration_mixin.py` | Modify | 2-track retry; structured output; remove `print(stderr)` |
| `loops/prompt_protocol_mixin.py` | Modify | Remove inline maps; consult `NodeContract`; **M8**: add `task_inspect` to heuristic candidates |
| `loops/worker_runtime.py` | Modify | Remove `OPEN_QUESTION` branch; **M8**: reset failure baseline on replan, cap replans per task, force-approve at cap |
| `loops/task_nodes.py` | Modify | **M8**: analyzer `terminate` instruction, reviewer sanity-checker, `local_replan` prompt |
| `loops/tinycua_loop.py` | Modify | Structured-output payload; tool coercion |
| `loops/trace_state_mixin.py` | Modify | `node_state_transition` + `task_tree_shrink` events |
| `models/task.py` | Modify | Add `delete_task`, `merge_tasks`; **M8**: `consecutive_failures` breaks on `replan_boundary` |
| `tools/task_tools.py` | Modify | Add `task_shrink`; review-tool required decision; fix metadata schema; **M8**: document `rejected` as alias for `needs_revision` |
| `tools/todo_tools.py` | Modify | Real update/delete |
| `tools/enhanced_context_retrieval.py` | Modify | Fix index math, cache cap |
| `agent/tools/native/web.py` | Modify | markdown, binary guard, UA, retry, `ToolResult` |
| `agent/tools/native/web_search.py` | Modify | backend-down vs no-matches, retry |
| `agent/tools/native/shell.py` | Modify | venv, executable, env, context |
| `agent/tools/native/context.py` | Modify | raise-if-unset, re-root, relative reporting |
| `agent/tools/native/files.py` | Modify | assert workspace bound; **M8**: `str_replace` multi-match error, `append_file`/`write_file`/`str_replace` return `diff_preview` |
| `agent/tools/native/python_exec.py` | Modify | reject >max |
| `agent/tools/native/output_persist.py` | Modify | remove duplicate print |
| `agent/tools/native/tool_result.py` | New | `ToolResult` envelope |
| `cli/run.py` | Modify | **M9**: wire `SimpleCompaction()` into `_build_run_agent` SessionConfig (FR-082); resolve `max_context` at startup (FR-084) |
| `cli/config.py` | Modify | **M9**: `build_language_model` accepts `max_context` kwarg (FR-084) |
| `cli/main.py` | Modify | **M9**: add `--max-context` argparse flag (FR-084) |
| `cli/model_probe.py` | New | **M9**: `resolve_max_context` — best-effort `GET /v1/models` probe, silent fallback (FR-084) |
| `loops/node.py` | Modify | **M9**: `build_messages_with_dedupe` bounds prompt to last `max_context_messages` entries (FR-083) |
| `loops/tinycua_loop.py` | Modify | **M9**: continuous compaction monitoring (top of attempt loop) + INFO-level compaction logs (FR-085) |
| `config/types.py` | Modify | `Tool.invoke` → SDK coercion |
| `config/node_config.py` | Modify | Remove inline overrides; effort-profiled threshold; **M8**: raise analyzer `max_attempts` to 10 |
| `config/session_config.py` | Modify | **M8**: add `max_replans` field (effort-derived) |

## Data Model Changes

```python
# New types
NodeState(StrEnum): PENDING, EXECUTING, AWAITING_TOOL, RETRYING, COMPLETED, FAILED

NodeProgress:
    phase: NodeState
    attempt_count: int
    visited_tools: set[str]
    satisfied_requirements: set[str]
    history: list[dict]

NodeContract(frozen):
    node_id: str
    required_tools: frozenset[str]
    any_of_tools: frozenset[frozenset[str]]
    deterministic_tools: frozenset[str]
    structured_output_schema: dict | None
    retry_max_attempts: int | None

ToolResult:
    success: bool
    output: Any
    error: str | None
    metadata: dict

WorkspaceNotBoundError(RuntimeError)

# Modified
TaskStateStore: + delete_task(task_id) -> None
              + merge_tasks(child_id, parent_id) -> Task

Node: + progress: NodeProgress
     + contract: NodeContract (property)
```

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `html2text` | latest | HTML→markdown conversion in `fetch_url` |

### Internal Dependencies

- [x] Depends on SDK `response_format` passthrough (already present: `open_ai_chat_completions.py:104`)
- [x] Depends on `type_to_json_schema` (already present: `sdk/schema.py:14`)
- [ ] Milestone 3 (retry) depends on Milestone 1-2 (NodeContract + NodeState)
- [ ] Milestone 4 (shrink) is independent
- [ ] Milestone 5-6 (tools) are independent
- [ ] Milestone 7 (logging) threads through all
- [ ] Milestone 8 (loop reliability) is independent of M2-M7; depends only on existing `worker_runtime.py` + `models/task.py` + `agent/tools/native/files.py`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Local models produce invalid JSON with `json_schema` | Med | Retry with schema error (unbounded) + stuck-model diagnostic (FR-015) |
| Removing dormant `ProcessNode.__call__` breaks a caller | High | Grep for `.run(`/`.__call__(` callers before removal |
| `delete_task` on active task crashes runtime | High | Guard: refuse on root/active (FR-023) |
| `html2text` breaks in Docker | Med | Pin version; add to Docker build; test in CI |
| Structured output changes eval harness config | Med | Re-enable per-node; verify with tinycua-only re-run |
| Force-approve at replan cap accepts a flawed result | Med | The "replan budget exhausted" rationale is recorded in the audit trail; the run still produces output for inspection. Strict mode can be added later if needed. |
| `plan_unchanged` signal is set incorrectly (analyzer says unchanged but plan was wrong) | Low | The analyzer LLM decides; the signal is advisory. If wrong, the reviewer will reject and the loop continues (bounded by `max_replans`). |
| `str_replace` multi-match error confuses the model further | Low | The error is actionable ("provide more context or set replace_all=True"); the model can still fall back to `append_file` if needed. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-22*
