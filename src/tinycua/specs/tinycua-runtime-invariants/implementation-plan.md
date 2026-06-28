# Implementation: TinyCUA Runtime Invariants

Make the TinyCUA prototype trustworthy by proving runtime behavior against the immutable source-of-truth docs, not by adding prompt heuristics. The work removes forced behavior, preserves analyzer-owned task roadmaps, enforces legal routes/tool scopes/context propagation, keeps `src/tinycua/docs/design/**` and `src/tinycua-sdk/**` untouched, and splits oversized TinyCUA source files.

## Context

- **Spec Reference**: `./spec.md`
  - Zero-tolerance gates: `./spec.md:25-68`
  - Functional requirements: `./spec.md:203-229`
  - Prohibited patterns: `./spec.md:242-255`
  - Success criteria: `./spec.md:259-275`
  - Testing plan: `./spec.md:279-299`
- **Design Reference**: `./design.md`
  - Architecture overview: `./design.md:19-37`
  - Exact source-of-truth references: `./design.md:38-72`
  - Required route proofs: `./design.md:92-133`
  - Interface contracts and errors: `./design.md:149-181`
  - Implementation phases: `./design.md:185-208`
- **Immutable source of truth**: `src/tinycua/docs/design/**` — no edits.
- **Protected SDK**: `src/tinycua-sdk/**` — no edits.
- **Priority**: P0
- **Estimated Effort**: XL

## Environment Pre-requisites

### Configuration

- [ ] **None** — invariant tests use local/scripted LLM doubles and pytest temp dirs.

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | No | N/A | N/A |

### Data / Fixtures

- [ ] **None** — tests build their own temp workspaces and scripted node outputs.

### Access / Permissions

- [ ] **None** — no network credentials needed for invariant tests.

### Developer Tooling

- [ ] **Runtime**: Python via `cd src/tinycua && uv run`.
- [ ] **Package manager**: `uv`.
- [ ] **No new dependencies** — use stdlib/pytest fixtures already present.

---

## Source-of-Truth Invariant Map

Every implementation task must cite at least one spec requirement and at least one source-of-truth design reference below. If code and docs disagree, code loses.

| Invariant | Spec | Source-of-truth docs |
|-----------|------|----------------------|
| Loop is orchestration/transport only | `./spec.md:205-219` | `src/tinycua/docs/design/loops/tinycua_loop.md:8-15`, `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:86-94` |
| Node-owned prompts/messages/retry/output/completion | `./spec.md:211-212` | `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node.md:29-64`, `src/tinycua/docs/design/loops/node.md:88-105`, `src/tinycua/docs/design/loops/node.md:216-220` |
| `node.on_complete()` owns queue transitions | `./spec.md:210`, `./spec.md:218` | `src/tinycua/docs/design/loops/tinycua_loop.md:51-54`, `src/tinycua/docs/design/loops/node_queue.md:44-47` |
| QueryAnalyst is entry and routes only worker/uncertain/passthrough | `./spec.md:224-226` | `src/tinycua/docs/design/loops/query_analyst.md:6-11`, `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/query_analyst.md:132-135` |
| Passthrough route ends at ResponseNode | `./spec.md:184-185`, `./spec.md:224-226` | `src/tinycua/docs/design/loops/query_analyst.md:57-65`, `src/tinycua/docs/design/loops/query_analyst.md:83-93`, `src/tinycua/docs/design/loops/response.md:60-90` |
| Worker route includes Digester, Worker, TaskCreate/Analyzer, AnalysisEffort, Executor, Reviewer, Aggregation, Response | `./spec.md:186`, `./spec.md:226` | `src/tinycua/docs/design/loops/query_analyst.md:83-101`, `src/tinycua/docs/design/loops/information_digester.md:84-100`, `src/tinycua/docs/design/loops/worker.md:75-89`, `src/tinycua/docs/design/loops/task_create.md:36-44`, `src/tinycua/docs/design/loops/analysis_effort.md:30-53`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91`, `src/tinycua/docs/design/loops/node.md:173-214` |
| Impossible task routes are rejected | `./spec.md:210`, `./spec.md:226-227`, `./spec.md:271-273` | `src/tinycua/docs/design/loops/task_analyzer.md:53-61`, `src/tinycua/docs/design/loops/task_executor.md:44-52`, `src/tinycua/docs/design/loops/result_reviewer.md:56-91` |
| TaskAnalyzer owns task tree mutations; no caps/heuristics | `./spec.md:208-210`, `./spec.md:246-249`, `./spec.md:261-262` | `src/tinycua/docs/design/loops/task_analyzer.md:6-17`, `src/tinycua/docs/design/loops/task_analyzer.md:23-42`, `src/tinycua/docs/design/models/task.md:10-28`, `src/tinycua/docs/design/tools/task.md:19-28` |
| TaskExecutor executes only active task; then ResultReviewer | `./spec.md:213-214`, `./spec.md:226` | `src/tinycua/docs/design/loops/task_executor.md:6-24`, `src/tinycua/docs/design/loops/task_executor.md:31-52`, `src/tinycua/docs/design/models/task.md:54-91` |
| ResultReviewer is execution quality gate | `./spec.md:226-227` | `src/tinycua/docs/design/loops/result_reviewer.md:6-18`, `src/tinycua/docs/design/loops/result_reviewer.md:39-91` |
| ResponseNode is terminal/suspendable final synthesis | `./spec.md:224-226` | `src/tinycua/docs/design/loops/response.md:6-18`, `src/tinycua/docs/design/loops/response.md:31-58`, `src/tinycua/docs/design/loops/response.md:60-90` |
| Internal context is assistant/internal and segmented/deduped | `./spec.md:215-216`, `./spec.md:228-229` | `src/tinycua/docs/design/loops/node.md:66-73`, `src/tinycua/docs/design/loops/node.md:83-86`, `src/tinycua/docs/design/loops/propagation.md:30-70`, `src/tinycua/docs/design/loops/propagation.md:79-109`, `src/tinycua/docs/design/loops/propagation.md:116-135` |
| Tool scopes are node-specific; only executor/response get arbitrary action tools | `./spec.md:213-214`, `./spec.md:228`, `./spec.md:274` | `src/tinycua/docs/design/tools/task.md:5-18`, `src/tinycua/docs/design/loops/information_digester.md:13-18`, `src/tinycua/docs/design/loops/information_digester.md:52-58`, `src/tinycua/docs/design/loops/task_executor.md:31-43`, `src/tinycua/docs/design/loops/response.md:31-58` |
| One-shot traceability is required | `./spec.md:224`, `./spec.md:270` | `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/tinycua_loop.md:62-65`, `src/tinycua/docs/design/loops/node_queue.md:85-101` |
| 1000+ LOC TinyCUA source files fail acceptance | `./spec.md:63-68`, `./spec.md:220-221`, `./spec.md:269` | `src/tinycua/docs/design/loops/tinycua_loop.md:21-40`, `src/tinycua/docs/design/loops/node.md:25-27`, `src/tinycua/docs/design/loops/node_queue.md:25-47`, `src/tinycua/docs/design/loops/propagation.md:30-70` |
| Protected docs and SDK remain untouched | `./spec.md:16-19`, `./spec.md:44-57`, `./spec.md:264` | User gate plus all source-of-truth references above |

---

## Success Criteria — Tests First

Write these tests before implementation changes. They may need small test helpers, but no new framework and no external services.

### Integration test skeletons

```python
# Test file: tests/integration/test_runtime_invariant_route_matrix.py
"""Route matrix proves source-of-truth TinyCUA paths."""

import pytest


@pytest.mark.asyncio
async def test_passthrough_run_ends_at_response_node(scripted_agent_factory, tmp_path):
    """Spec: ./spec.md:185, ./spec.md:224-226.
    Source: query_analyst.md:57-65, query_analyst.md:83-93, response.md:60-90.
    """
    agent = scripted_agent_factory(route="passthrough", workspace=tmp_path)

    result = await agent.run("hello")

    assert result.strip()
    assert agent.loop.trace_node_ids() == ["query_analyst", "response"]
    assert agent.loop.trace_node_ids()[-1] == "response"


@pytest.mark.asyncio
async def test_worker_route_reaches_reviewer_before_aggregation_and_response(scripted_agent_factory, tmp_path):
    """Spec: ./spec.md:186, ./spec.md:226.
    Source: worker.md:75-89, analysis_effort.md:30-53,
    task_executor.md:44-52, result_reviewer.md:56-91.
    """
    agent = scripted_agent_factory(route="worker", worker_effort="medium", workspace=tmp_path)

    await agent.run("Create a project roadmap")
    node_ids = agent.loop.trace_node_ids()

    assert node_ids[0] == "query_analyst"
    assert "information_digester" in node_ids
    assert "worker" in node_ids
    assert "analysis_effort" in node_ids
    assert "task_executor" in node_ids
    assert "result_reviewer" in node_ids
    assert node_ids.index("task_executor") < node_ids.index("result_reviewer")
    assert "result_aggregation" in node_ids
    assert node_ids[-1] == "response"


@pytest.mark.asyncio
async def test_impossible_task_routes_are_rejected(illegal_route_agent_factory, tmp_path):
    """Spec: ./spec.md:195-196, ./spec.md:226, ./spec.md:272.
    Source: task_analyzer.md:53-61, task_executor.md:44-52,
    result_reviewer.md:56-91.
    """
    agent = illegal_route_agent_factory(workspace=tmp_path)

    with pytest.raises(RuntimeError, match="illegal route|invalid transition"):
        await agent.run("force analyzer to response")

    assert not agent.loop.trace_has_transition("task_analyzer", "response")
    assert not agent.loop.trace_has_transition("task_create", "response")
    assert not agent.loop.trace_has_transition("task_executor", "response")
```

```python
# Test file: tests/integration/test_runtime_invariant_failure_recovery.py
"""Weak/malformed node output self-recovers without route skipping."""

import pytest


@pytest.mark.asyncio
async def test_each_internal_node_bad_once_recovers_through_same_node(bad_once_agent_factory, tmp_path):
    """Spec: ./spec.md:179, ./spec.md:187, ./spec.md:227.
    Source: tinycua_loop.md:36-38, tinycua_loop.md:67-84, node.md:216-220.
    """
    agent = bad_once_agent_factory(workspace=tmp_path)

    await agent.run("Create a multi-step implementation plan")

    assert agent.loop.trace_node_ids()[-1] == "response"
    assert agent.loop.retry_count_by_node()["task_analyzer"] >= 1
    assert agent.loop.trace_has_transition("task_executor", "result_reviewer")
    assert not agent.loop.trace_has_transition("task_analyzer", "response")
```

```python
# Test file: tests/integration/test_run_agent_traceability.py
"""One-shot script emits auditable runtime artifacts."""

import subprocess
from pathlib import Path


def test_run_agent_script_prints_trace_task_tree_workspace_and_artifacts(tmp_path):
    """Spec: ./spec.md:224, ./spec.md:270.
    Source: tinycua_loop.md:21-40, tinycua_loop.md:62-65, node_queue.md:85-101.
    """
    result = subprocess.run(
        [
            "uv", "run", "python", "./scripts/run_agent.py",
            "--dir", str(tmp_path / "workspace"),
            "--prompt", "hello",
            "--stream",
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0
    assert "=== TRACE ===" in result.stdout
    assert "=== FINAL RESPONSE ===" in result.stdout
    assert "=== TASK TREE ===" in result.stdout
    assert "=== WORKSPACE FILES ===" in result.stdout
    assert "=== ARTIFACTS ===" in result.stdout
```

### Unit test skeletons

```python
# Test file: tests/unit/test_runtime_invariant_task_decomposition.py
"""TaskAnalyzer-owned roadmaps are preserved exactly."""


def test_task_decompose_preserves_all_subtasks(session_task_tools):
    """Spec: ./spec.md:180, ./spec.md:208-210, ./spec.md:262.
    Source: task_analyzer.md:23-31, models/task.md:10-28, tools/task.md:19-28.
    """
    root_id = session_task_tools.init("Any complex task")
    subtasks = [f"Task {index}" for index in range(25)]

    result = session_task_tools.decompose(root_id, subtasks)

    assert result["success"] is True
    assert len(result["child_task_ids"]) == len(subtasks)
    assert [session_task_tools.get(child_id).title for child_id in result["child_task_ids"]] == subtasks
```

```python
# Test file: tests/unit/test_runtime_invariant_tool_scopes.py
"""Tool scopes match design docs."""


def test_information_digester_has_only_digest_read_tools(resolve_tools):
    """Spec: ./spec.md:188, ./spec.md:228, ./spec.md:274.
    Source: information_digester.md:13-18, information_digester.md:52-58.
    """
    tool_names = resolve_tools("information_digester")

    assert "enhanced_context_retrieval" in tool_names
    assert "digest_information" in tool_names
    assert "task_init" not in tool_names
    assert "task_decompose" not in tool_names
    assert "task_result_update" not in tool_names
    assert "write_file" not in tool_names
    assert "edit_file" not in tool_names
    assert "run_shell" not in tool_names
    assert "run_python" not in tool_names


def test_only_executor_and_response_have_arbitrary_write_execute_tools(all_node_ids, resolve_tools):
    """Spec: ./spec.md:214, ./spec.md:228, ./spec.md:274.
    Source: task_executor.md:31-43, response.md:31-58, tools/task.md:5-18.
    """
    action_tools = {"write_file", "edit_file", "run_shell", "run_python"}

    for node_id in set(all_node_ids) - {"task_executor", "response"}:
        assert action_tools.isdisjoint(resolve_tools(node_id))
```

```python
# Test file: tests/unit/test_runtime_invariant_context_propagation.py
"""Node context is segmented, deduped, and internal-role safe."""


def test_internal_handoff_is_not_recreated_as_user_message(context_handoff_fixture):
    """Spec: ./spec.md:215-216, ./spec.md:228-229, ./spec.md:266, ./spec.md:275.
    Source: node.md:66-73, node.md:83-86, propagation.md:30-70, propagation.md:79-109.
    """
    next_messages = context_handoff_fixture.next_node_messages()

    internal_messages = [m for m in next_messages if m.get("metadata", {}).get("internal")]
    assert internal_messages
    assert all(message["role"] == "assistant" for message in internal_messages)
    assert not any(message["role"] == "user" and message.get("metadata", {}).get("internal") for message in next_messages)


def test_forwarded_context_is_selected_output_not_wholesale_prior_context(context_handoff_fixture):
    """Spec: ./spec.md:189, ./spec.md:229, ./spec.md:275.
    Source: propagation.md:30-70, propagation.md:94-109, propagation.md:116-135.
    """
    forwarded = context_handoff_fixture.forwarded_to_next_node()

    assert forwarded.origin_record_ids == set(forwarded.selected_output_origin_ids)
    assert forwarded.duplicated_origin_ids == set()
    assert not forwarded.contains_full_prior_context_dump
```

```python
# Test file: tests/unit/test_runtime_invariant_source_guards.py
"""Source-size guard for oversized dumping grounds."""

from pathlib import Path


def test_tinycua_source_files_do_not_exceed_1000_lines_without_user_exception():
    """Spec: ./spec.md:63-68, ./spec.md:220-221, ./spec.md:269.
    Source: tinycua_loop.md:21-40, node.md:25-27, node_queue.md:25-47,
    propagation.md:30-70.
    """
    oversized = [
        path for path in Path("tinycua").rglob("*.py")
        if len(path.read_text().splitlines()) > 1000
    ]

    assert oversized == []
```

```python
# Script file: scripts/check_runtime_policy_guidance.py
"""Audit runtime code for spec-guidance violations; this is not a pytest test."""

from pathlib import Path


FORBIDDEN_GUIDANCE_PATTERNS = [
    "minimal runnable vertical-slice",
    "_one_shot_app_subtasks",
    "MAX_DECOMPOSE_SUBTASKS",
    '"maxItems": 3',
]


def main() -> int:
    text = "\n".join(path.read_text() for path in Path("tinycua").rglob("*.py"))
    found = [pattern for pattern in FORBIDDEN_GUIDANCE_PATTERNS if pattern in text]
    if found:
        print("Runtime policy-guidance audit found forbidden patterns:")
        for pattern in found:
            print(f"- {pattern}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Key Test Scenarios

- [ ] **Traceable one-shot entry**: `run_agent.py` prints node trace, tool activity, final response, task tree, workspace files, and artifacts. Spec: `./spec.md:224`, `./spec.md:270`; source: `tinycua_loop.md:62-65`.
- [ ] **Passthrough route**: `User_Query -> QueryAnalyst -> ResponseNode`. Spec: `./spec.md:185`; source: `query_analyst.md:57-65`, `query_analyst.md:83-93`, `response.md:60-90`.
- [ ] **Worker route**: includes InformationDigester, Worker, planning, effort, executor, reviewer, aggregation, response. Spec: `./spec.md:186`, `./spec.md:226`; source: `worker.md:75-89`, `analysis_effort.md:30-53`, `result_reviewer.md:56-91`.
- [ ] **Failure recovery**: malformed outputs retry/correct same node. Spec: `./spec.md:187`, `./spec.md:227`; source: `tinycua_loop.md:67-84`, `node.md:216-220`.
- [ ] **Impossible routes rejected**: no TaskAnalyzer/TaskCreate/TaskExecutor skip to ResponseNode. Spec: `./spec.md:195-196`, `./spec.md:226`, `./spec.md:272`; source: `task_analyzer.md:53-61`, `task_executor.md:44-52`.
- [ ] **Tool scopes**: InformationDigester has no task/action tools; only TaskExecutor/ResponseNode have arbitrary action tools. Spec: `./spec.md:214`, `./spec.md:228`, `./spec.md:274`; source: `information_digester.md:52-58`, `task_executor.md:31-43`, `response.md:31-58`.
- [ ] **Context isolation**: no wholesale duplicated prior messages; internal handoffs are assistant/internal. Spec: `./spec.md:215-216`, `./spec.md:228-229`, `./spec.md:275`; source: `node.md:66-73`, `propagation.md:30-70`, `propagation.md:94-109`.
- [ ] **Policy-guidance audit**: standalone script, not pytest, reports prompt-category heuristics, hardcoded task titles, task caps, or analyzer rewrites. Spec: `./spec.md:29-42`, `./spec.md:246-249`, `./spec.md:261-262`; source: `task_analyzer.md:23-31`, `models/task.md:10-28`.
- [ ] **No 1000+ LOC files**: all TinyCUA Python source files below 1000 LOC unless user-approved. Spec: `./spec.md:63-68`, `./spec.md:269`.

---

## Verification Plan

### Automated Tests

- [ ] Route matrix — `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_route_matrix.py -q`
- [ ] Failure recovery — `cd src/tinycua && uv run pytest tests/integration/test_runtime_invariant_failure_recovery.py -q`
- [ ] One-shot traceability — `cd src/tinycua && uv run pytest tests/integration/test_run_agent_traceability.py -q`
- [ ] Task decomposition — `cd src/tinycua && uv run pytest tests/unit/test_runtime_invariant_task_decomposition.py -q`
- [ ] Tool scopes — `cd src/tinycua && uv run pytest tests/unit/test_runtime_invariant_tool_scopes.py -q`
- [ ] Context propagation — `cd src/tinycua && uv run pytest tests/unit/test_runtime_invariant_context_propagation.py -q`
- [ ] Source-size guard — `cd src/tinycua && uv run pytest tests/unit/test_runtime_invariant_source_guards.py -q`
- [ ] Policy-guidance audit script — `cd src/tinycua && uv run python scripts/check_runtime_policy_guidance.py`
- [ ] Full unit suite — `cd src/tinycua && uv run pytest tests/unit -q`
- [ ] Full integration suite — `cd src/tinycua && uv run pytest tests/integration -q`
- [ ] Ruff — `cd src/tinycua && uv run ruff check tinycua tests scripts/run_agent.py`

### Manual Verification

- [ ] `git diff -- src/tinycua/docs/design` is empty.
- [ ] `git diff -- src/tinycua-sdk` is empty.
- [ ] `cd src/tinycua && uv run python scripts/run_agent.py --prompt "hello" --stream` shows QueryAnalyst -> ResponseNode and trace sections.
- [ ] `cd src/tinycua && uv run python scripts/run_agent.py --prompt "Create a multi-step implementation plan" --worker-effort medium --stream` shows legal worker path, executor before reviewer, and terminal ResponseNode.

### Performance Considerations

- [ ] No performance target is added. Large task trees may be slow; do not truncate. If needed later, batch scheduling while preserving every analyzer-created task. Spec: `./spec.md:193-194`, `./spec.md:208`.

---

## Proposed Changes

### Phase 0 — Source and Policy Audit

#### [NEW] `src/tinycua/tests/unit/test_runtime_invariant_source_guards.py`

- **Description**: Add a pytest guard for 1000+ LOC TinyCUA Python source files only.
- **Rationale**: Oversized source files are an acceptance failure. Spec: `./spec.md:63-68`, `./spec.md:220-221`, `./spec.md:269`; source: `tinycua_loop.md:21-40`, `node.md:25-27`.

#### [NEW] `src/tinycua/scripts/check_runtime_policy_guidance.py`

- **Description**: Add a standalone script, not a pytest test, that audits runtime code for explicit spec-guidance violations such as known forced-behavior strings and task caps.
- **Rationale**: Policy from the spec is guidance, not a pytest behavior test. Spec: `./spec.md:29-42`, `./spec.md:242-255`, `./spec.md:261-262`.

#### [CHECK] Protected paths

- **Description**: Verify `git diff -- src/tinycua/docs/design` and `git diff -- src/tinycua-sdk` stay empty before every commit.
- **Rationale**: Explicit acceptance gate. Spec: `./spec.md:16-19`, `./spec.md:44-57`, `./spec.md:264`.

### Phase 1 — Tests First

#### [NEW] `src/tinycua/tests/integration/test_runtime_invariant_route_matrix.py`

- **Description**: Add legal passthrough/worker route tests plus impossible-route negative tests.
- **Rationale**: Trustworthiness is route proof, not happy-path output. Spec: `./spec.md:224-227`, `./spec.md:271-272`; source: `query_analyst.md:83-101`, `worker.md:75-89`, `task_executor.md:44-52`, `result_reviewer.md:56-91`, `response.md:60-90`.

#### [NEW] `src/tinycua/tests/integration/test_runtime_invariant_failure_recovery.py`

- **Description**: Script every internal node to emit one invalid/missing contract output, then verify same-node retry/correction and legal completion.
- **Rationale**: LLM weakness must not become route skipping or forced content. Spec: `./spec.md:179`, `./spec.md:187`, `./spec.md:227`, `./spec.md:273`; source: `tinycua_loop.md:36-38`, `tinycua_loop.md:67-84`, `node.md:216-220`.

#### [NEW] `src/tinycua/tests/integration/test_run_agent_traceability.py`

- **Description**: Assert one-shot script emits trace, final response, task tree, workspace files, and artifacts.
- **Rationale**: Prototype must be auditable from one prompt. Spec: `./spec.md:224`, `./spec.md:270`; source: `tinycua_loop.md:62-65`.

#### [NEW] `src/tinycua/tests/unit/test_runtime_invariant_task_decomposition.py`

- **Description**: Assert arbitrary analyzer subtasks are preserved exactly.
- **Rationale**: Runtime must not collapse or truncate model-owned roadmaps. Spec: `./spec.md:180`, `./spec.md:208-210`, `./spec.md:246-249`, `./spec.md:262`; source: `task_analyzer.md:23-31`, `models/task.md:10-28`, `tools/task.md:19-28`.

#### [NEW] `src/tinycua/tests/unit/test_runtime_invariant_tool_scopes.py`

- **Description**: Assert node tool policies match design and non-executor/non-response nodes have no arbitrary action tools.
- **Rationale**: Permission boundaries must be enforced by policy, not prompt obedience. Spec: `./spec.md:214`, `./spec.md:228`, `./spec.md:274`; source: `tools/task.md:5-18`, `information_digester.md:52-58`, `task_executor.md:31-43`, `response.md:31-58`.

#### [NEW] `src/tinycua/tests/unit/test_runtime_invariant_context_propagation.py`

- **Description**: Assert assistant/internal handoffs, segmented propagation, and dedupe.
- **Rationale**: Context isolation is a core trust invariant. Spec: `./spec.md:215-216`, `./spec.md:228-229`, `./spec.md:266`, `./spec.md:275`; source: `node.md:66-73`, `node.md:83-86`, `propagation.md:30-70`, `propagation.md:79-109`.

### Phase 2 — Remove Forced Behavior

#### [MODIFY] `src/tinycua/tinycua/tools/task_tools.py`

- **Description**: Remove any `_MAX_DECOMPOSE_SUBTASKS`, `maxItems`, slicing, task-list truncation, and prompt-specific rewrite/collapse logic.
- **Rationale**: TaskAnalyzer owns task tree mutations and task count. Spec: `./spec.md:208-210`, `./spec.md:246-249`; source: `task_analyzer.md:23-31`, `models/task.md:10-28`, `tools/task.md:19-28`.

#### [MODIFY] `src/tinycua/tinycua/loops/task_nodes.py`

- **Description**: Remove hardcoded vertical-slice/minimal-app/app-web-ui instructions or recovery text. Node prompts may state role, output contract, and tool scope only.
- **Rationale**: No prompt-category forcing. Spec: `./spec.md:29-42`, `./spec.md:206-210`, `./spec.md:246-249`; source: `node.md:25-27`, `task_analyzer.md:6-17`, `task_analyzer.md:23-31`.

#### [MODIFY] `src/tinycua/.env.example`

- **Description**: Remove prototype-forcing worker effort default such as `TINYCUA_WORKER_EFFORT=none` if it exists; defaults must follow config/design, not hidden shortcut behavior.
- **Rationale**: Effort controls assessor/analyzer passes and must not terminate/skew Worker. Spec: `./spec.md:186`, `./spec.md:297`; source: `analysis_effort.md:12-29`, `analysis_effort.md:30-53`, `analysis_effort.md:55-60`.

### Phase 3 — Enforce Route and Retry Contracts

#### [MODIFY] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Description**: Ensure the loop validates node output, route labels, tool scope, node input, and terminal response. Retry/correction stays same-node and generic.
- **Rationale**: Loop supervises contract validity only. Spec: `./spec.md:205-219`, `./spec.md:224-227`; source: `tinycua_loop.md:21-40`, `tinycua_loop.md:67-94`, `node.md:216-220`.

#### [MODIFY] route/queue helpers under `src/tinycua/tinycua/loops/`

- **Description**: Reject impossible transitions and keep `node.on_complete()` as queue-transition owner.
- **Rationale**: No hidden loop-side advancement or task-node skip to ResponseNode. Spec: `./spec.md:210`, `./spec.md:226`, `./spec.md:272`; source: `tinycua_loop.md:51-54`, `node_queue.md:44-47`, `task_analyzer.md:53-61`, `task_executor.md:44-52`.

### Phase 4 — Tool Scopes and Context Propagation

#### [MODIFY] tool policy/config modules under `src/tinycua/tinycua/`

- **Description**: Align resolved node tools with design docs; expose arbitrary write/execute tools only to TaskExecutor and ResponseNode.
- **Rationale**: Internal nodes must not rely on prompt obedience for safety. Spec: `./spec.md:214`, `./spec.md:228`, `./spec.md:274`; source: `tools/task.md:5-18`, `information_digester.md:13-18`, `information_digester.md:52-58`, `task_executor.md:31-43`, `response.md:31-58`.

#### [MODIFY] context/session propagation modules under `src/tinycua/tinycua/`

- **Description**: Persist internal handoffs/retries as assistant/internal records; propagate selected segmented output with dedupe, not wholesale prior context.
- **Rationale**: Prevent context bloat and user-history pollution. Spec: `./spec.md:215-216`, `./spec.md:228-229`, `./spec.md:266`, `./spec.md:275`; source: `node.md:66-73`, `node.md:83-86`, `propagation.md:30-70`, `propagation.md:79-109`, `propagation.md:116-135`.

### Phase 5 — Split Oversized Loop Code

#### [MODIFY/SPLIT] `src/tinycua/tinycua/loops/tinycua_loop.py`

- **Description**: Split only if the file is over 1000 LOC. Minimal modules should map to actual responsibilities: orchestration loop, route validation, retry/correction, trace collection, and SDK/tool execution adapter. Delete dead code instead of moving it.
- **Rationale**: `TinyCUALoop` must not become a policy dumping ground. Spec: `./spec.md:63-68`, `./spec.md:220-221`, `./spec.md:269`; source: `tinycua_loop.md:21-40`, `node.md:25-27`, `node_queue.md:25-47`, `propagation.md:30-70`.

### Phase 6 — One-Shot Script Traceability

#### [MODIFY] `src/tinycua/scripts/run_agent.py`

- **Description**: Keep script simple. It must run one prompt and print trace, final response, task tree, workspace file list, artifact list, and streaming node/tool lifecycle when `--stream` is used.
- **Rationale**: Prototype trust is inspectable behavior. Spec: `./spec.md:224`, `./spec.md:270`; source: `tinycua_loop.md:21-40`, `tinycua_loop.md:62-65`, `node_queue.md:85-101`.

### Protected Paths

#### [NO MODIFY] `src/tinycua/docs/design/**`

- **Description**: Must remain byte-for-byte untouched.
- **Rationale**: Source-of-truth tree. Spec: `./spec.md:16-18`, `./spec.md:49-57`, `./spec.md:264`.

#### [NO MODIFY] `src/tinycua-sdk/**`

- **Description**: Must remain untouched.
- **Rationale**: Runtime invariants wrap/adapt at TinyCUA layer only. Spec: `./spec.md:18-19`, `./spec.md:44-47`, `./spec.md:217`.

---

## Architecture Changes

| Component | Change Type | Description | References |
|-----------|-------------|-------------|------------|
| TinyCUALoop | Modify/Split | Keep orchestration/transport only; move cohesive helpers if file >1000 LOC. | Spec `./spec.md:205-221`; source `tinycua_loop.md:21-40`, `node.md:25-27` |
| NodeQueue/Route validation | Modify | Reject impossible transitions; keep `node.on_complete()` transition ownership. | Spec `./spec.md:210`, `./spec.md:226`; source `tinycua_loop.md:51-54`, `node_queue.md:44-47` |
| Task tools | Modify | Preserve all analyzer subtasks; remove caps/heuristics. | Spec `./spec.md:208-210`; source `task_analyzer.md:23-31`, `models/task.md:10-28` |
| Task node prompts | Modify | Remove app/web-ui/vertical-slice forcing. | Spec `./spec.md:29-42`; source `node.md:25-27`, `task_analyzer.md:6-17` |
| Tool policies | Modify | Enforce exact node scopes. | Spec `./spec.md:214`, `./spec.md:228`; source `tools/task.md:5-18` |
| Context propagation | Modify | Assistant/internal handoffs, segmented propagation, dedupe. | Spec `./spec.md:215-216`, `./spec.md:228-229`; source `propagation.md:30-109` |
| Trace script | Modify | Auditable one-shot run. | Spec `./spec.md:224`, `./spec.md:270`; source `tinycua_loop.md:62-65` |
| Tests | New | Route, recovery, tool-scope, context, decomposition, source-size guard, and traceability tests. | Spec `./spec.md:279-299` |
| Policy audit script | New | Standalone script for spec-guidance pattern checks; not pytest. | Spec `./spec.md:29-42`, `./spec.md:242-255` |
| SDK | No Modify | No `src/tinycua-sdk/**` changes. | Spec `./spec.md:18-19`, `./spec.md:44-47` |
| Source design docs | No Modify | No `src/tinycua/docs/design/**` changes. | Spec `./spec.md:16-18`, `./spec.md:49-57` |

## Data Model Changes

No required data model changes.

If retry/correction trace metadata is needed, it must be generic: node id, session id, attempt number, validation error, route label, tool call names. It must not encode prompt classes, app/web-ui categories, fixed task titles, or forced decomposition shapes. Spec: `./spec.md:193-197`, `./spec.md:218-219`; source: `tinycua_loop.md:67-84`.

## API Changes

No public API changes required.

`src/tinycua/scripts/run_agent.py` remains a script entry point. It may add trace flags if needed, but the default one-shot behavior should stay simple. Spec: `./spec.md:224`; source: `tinycua_loop.md:62-65`.

## Dependencies

### External Dependencies

None.

### Internal Dependencies

- [ ] Depends on immutable `src/tinycua/docs/design/**` references listed above.
- [ ] Depends on TinyCUA-SDK public behavior without modifying `src/tinycua-sdk/**`.
- [ ] Tests may add local scripted LLM/test doubles inside `src/tinycua/tests/**` only.

## Risks and Mitigations

| Risk | Impact | Mitigation | References |
|------|--------|------------|------------|
| Removing heuristics exposes LLM instability | High | Generic retry/correction only; no prompt-category behavior. | Spec `./spec.md:179`, `./spec.md:218-219`; source `tinycua_loop.md:67-84` |
| Route tests pass only happy path | High | Add malformed/missing-output tests for every internal node. | Spec `./spec.md:271-273`; source `node.md:216-220` |
| Unlimited task roadmaps are slow | Medium | Preserve tasks; batch later only without dropping tasks. | Spec `./spec.md:193-194`, `./spec.md:208`; source `models/task.md:10-28` |
| Tool scope drift | High | Negative tests per non-action node. | Spec `./spec.md:228`, `./spec.md:274`; source `tools/task.md:5-18` |
| Context duplication bloats prompts | High | Test segmented propagation and dedupe by origin id. | Spec `./spec.md:229`, `./spec.md:275`; source `propagation.md:30-109` |
| Loop split just moves complexity | High | Delete dead code; only split responsibilities that map to source docs. | Spec `./spec.md:63-68`, `./spec.md:220-221`; source `tinycua_loop.md:21-40` |
| Protected docs/SDK touched accidentally | Critical | Run `git diff -- src/tinycua/docs/design` and `git diff -- src/tinycua-sdk` before commit. | Spec `./spec.md:16-19`, `./spec.md:44-57` |

---

*Generated from spec.md and design.md*
*Last updated: 2026-06-17*
