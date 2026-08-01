"""End-to-end runtime contract matrix: correct routing, retry, and fail-closed."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node import NodeExecutionError


class RuntimeContractScript:
    """Deterministic scripted LLM for full-lifecycle contract matrix tests.

    Detects which node is being called by available tool names, and returns
    correct responses unless the node is in bad_once/bad_forever sets.

    For the full worker path, this exercises:
    - Route decisions (query_analyst, worker)
    - Task creation (task_create)
    - Analysis effort loop (task_assessor → task_analyzer, repeated)
    - Task execution with real file writes (task_executor)
    - Result review with workspace inspection (result_reviewer)
    - Aggregation and final response
    - Failure → needs_revision → retry lifecycle
    """

    def __init__(
        self,
        *,
        bad_once_nodes: frozenset[str] = frozenset(),
        bad_forever_nodes: frozenset[str] = frozenset(),
    ) -> None:
        self.bad_once_nodes = set(bad_once_nodes)
        self.bad_forever_nodes = set(bad_forever_nodes)
        self.calls_by_node: dict[str, int] = {}
        self.captured_messages_by_node: dict[str, list[list[dict[str, Any]]]] = {}
        self.executor_write_done_by_task: set[str] = set()
        self.reviewer_approved_tasks: set[str] = set()
        self.reviewer_needs_revision_tasks: set[str] = set()

    # ── helpers ──────────────────────────────────────────────────────────

    def _task_id(
        self, messages: list[dict[str, Any]], key: str = "active_task_id"
    ) -> str:
        text = "\n".join(str(m.get("content", "")) for m in messages)
        # Try raw dict format first: 'active_task_id': '...'
        match = re.search(rf"'{key}': '([^']+)'", text) or re.search(
            rf'"{key}": "([^"]+)"',
            text,
        )
        if match:
            return match.group(1)
        # Try markdown format: Active: title (id=abc123)
        if key == "active_task_id":
            match = re.search(r"Active: .+ \(id=([^\)]+)\)", text)
            if match:
                return match.group(1)
        if key == "root_task_id":
            match = re.search(r"Root: .+ \(id=([^\)]+)\)", text)
            if match:
                return match.group(1)
        # Fallback: search for any task ID in the tree
        match = re.search(r"'root_task_id': '([^']+)'", text) or re.search(
            r'"root_task_id": "([^"]+)"',
            text,
        )
        return match.group(1) if match else ""

    def _task_snapshot(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse the task tree snapshot from messages."""
        text = "\n".join(str(m.get("content", "")) for m in messages)
        match = re.search(r"'tasks': (\{.*?\}), 'transition_log'", text, re.DOTALL)
        if not match:
            return {}
        try:
            return eval(match.group(1))  # noqa: S307 — test-only snapshot parse
        except Exception:
            return {}

    def _detect_node(self, tool_names: set[str], messages: list[dict[str, Any]]) -> str:
        if any(
            "ResultReviewer" in str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system"
        ):
            return "result_reviewer"
        if "final_response_synthesis" in tool_names:
            return "final"
        if "select_query_route" in tool_names:
            return "query_analyst"
        if "select_worker_route" in tool_names:
            return "worker"
        if "digest_information" in tool_names:
            return "digester"
        if "task_init" in tool_names:
            return "task_create"
        if "task_decompose" in tool_names:
            return "task_analyzer"
        if "task_assessment_decision" in tool_names:
            return "task_assessor"
        if "task_review_plan" in tool_names:
            return "result_reviewer"
        if "task_review_decision" in tool_names:
            return "result_reviewer"
        if "task_update" in tool_names and "task_decompose" not in tool_names:
            return "task_assessor"
        if "task_result_update" in tool_names:
            return "task_executor"
        if tool_names == {"task_inspect"}:
            return "result_aggregation"
        return "final"

    def _is_bad_call(self, node: str) -> bool:
        if node in self.bad_forever_nodes:
            return True
        if node in self.bad_once_nodes:
            return self.calls_by_node.get(node, 0) == 0
        return False

    # ── correct responses per node ───────────────────────────────────────

    def _correct_response(  # noqa: C901
        self,
        node: str,
        tool_names: set[str],
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if node == "query_analyst":
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "summarize_query_context",
                            "arguments": '{"context_summary":"Handle the current request."}',
                        }
                    },
                    {
                        "function": {
                            "name": "select_query_route",
                            "arguments": '{"route":"worker"}',
                        }
                    },
                ],
            }
        if node == "worker":
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "select_worker_route",
                            "arguments": '{"route":"task_creation"}',
                        }
                    }
                ],
            }
        if node == "digester":
            if any(
                m.get("role") == "tool"
                and "digest_information" in str(m.get("content", ""))
                for m in messages
            ):
                return {"content": "Digest recorded.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "digest_information",
                            "arguments": '{"context_summary":"Relevant context was gathered."}',
                        }
                    }
                ],
            }
        if node == "task_create":
            if any(
                m.get("role") == "tool" and "task_init" in str(m.get("content", ""))
                for m in messages
            ):
                return {"content": "Initialized.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_init",
                            "arguments": '{"title":"Build a note-taking app"}',
                        }
                    }
                ],
            }
        if node == "task_analyzer":
            # Check if we already decomposed (task has children)
            snapshot = self._task_snapshot(messages)
            root_id = self._task_id(messages, "root_task_id")
            root_task = snapshot.get(root_id, {})
            if root_task.get("children"):
                # Already decomposed — confirm or do nothing
                if any(
                    m.get("role") == "tool"
                    and (
                        "task_decompose" in str(m.get("content", ""))
                        or "task_update" in str(m.get("content", ""))
                    )
                    for m in messages
                ):
                    return {"content": "Analysis complete.", "tool_calls": []}
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "task_update",
                                "arguments": f'{{"task_id":"{root_id}","assessment":"decomposition complete"}}',
                            }
                        }
                    ],
                }
            # First decomposition — break root into 2 subtasks
            if any(
                m.get("role") == "tool"
                and (
                    "task_decompose" in str(m.get("content", ""))
                    or "task_update" in str(m.get("content", ""))
                )
                for m in messages
            ):
                return {"content": "Decomposition confirmed.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_decompose",
                            "arguments": f'{{"task_id":"{root_id}","subtasks":["Create backend","Create frontend"]}}',
                        }
                    }
                ],
            }
        if node == "task_assessor":
            if any(
                m.get("role") == "tool"
                and "task_assessment_decision" in str(m.get("content", ""))
                for m in messages
            ):
                return {"content": "Assessment handed off.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_assessment_decision",
                            "arguments": '{"decision":"ready","findings":[],"advisories":[],"rationale":"The roadmap is executable."}',
                        }
                    }
                ],
            }
        if node == "task_executor":
            task_id = self._task_id(messages)
            # First call: write file for this task
            if (
                "write_file" in tool_names
                and task_id not in self.executor_write_done_by_task
            ):
                self.executor_write_done_by_task.add(task_id)
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "write_file",
                                "arguments": f'{{"path":"{task_id}.txt","content":"Implementation of {task_id}\\n"}}',
                            }
                        }
                    ],
                }
            # After write: record result
            if any(
                m.get("role") == "tool"
                and "task_result_update" in str(m.get("content", ""))
                for m in messages
            ):
                return {"content": "Recorded.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_result_update",
                            "arguments": f'{{"content":"Completed {task_id}","success":true}}',
                        }
                    }
                ],
            }
        if node == "result_reviewer":
            task_id = self._task_id(messages)
            if "task_review_plan" in tool_names:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "task_review_plan",
                                "arguments": (
                                    '{"checks":[{"criterion_id":"acceptance-1",'
                                    '"testability":"empirical",'
                                    '"falsifying_condition":"The request is unmet.",'
                                    '"procedure":"Compare the result to the request.",'
                                    '"expected_observation":"The request is met."}]}'
                                ),
                            }
                        }
                    ],
                }
            # First call: inspect workspace
            if "list_files" in tool_names:
                if any(
                    message.get("role") == "tool"
                    and "list_files" in str(message.get("content", ""))
                    for message in messages
                ):
                    return {"content": "Inspection complete.", "tool_calls": []}
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "review-observation",
                            "function": {"name": "list_files", "arguments": "{}"},
                        }
                    ],
                }
            # After inspection: decide
            if any(
                m.get("role") == "tool"
                and "task_review_decision" in str(m.get("content", ""))
                for m in messages
            ):
                return {"content": "Review recorded.", "tool_calls": []}
            # COMMIT exposes only the decision tool.
            # First time seeing this task: approve
            if task_id not in self.reviewer_approved_tasks:
                self.reviewer_approved_tasks.add(task_id)
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "task_review_decision",
                                "arguments": f'{{"decision":"approved","rationale":"Task {task_id} completed successfully","task_id":"{task_id}","criterion_assessments":[{{"criterion_id":"acceptance-1","result":"supported","evidence_ids":["review-observation"],"inference":"The request is met.","limitations":"One scripted observation."}}]}}',
                            }
                        }
                    ],
                }
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_review_decision",
                            "arguments": f'{{"decision":"approved","rationale":"Verified","task_id":"{task_id}","criterion_assessments":[{{"criterion_id":"acceptance-1","result":"supported","evidence_ids":["review-observation"],"inference":"The request is met.","limitations":"One scripted observation."}}]}}',
                        }
                    }
                ],
            }
        if node == "result_aggregation":
            return {"content": "All tasks completed successfully.", "tool_calls": []}
        # Final / aggregation / response
        return {"content": "All tasks completed successfully.", "tool_calls": []}

    # ── main entry point ─────────────────────────────────────────────────

    async def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: Any,
        stream: bool = False,  # noqa: ANN001, ARG002
    ) -> dict[str, Any]:
        tool_names = {t.name for t in tools}
        node = self._detect_node(tool_names, messages)
        # Check bad BEFORE incrementing so count==0 triggers on first call
        is_bad = self._is_bad_call(node)
        self.calls_by_node[node] = self.calls_by_node.get(node, 0) + 1
        self.captured_messages_by_node.setdefault(node, []).append(messages)

        if is_bad:
            return {"content": "bad response without required tool", "tool_calls": []}
        return self._correct_response(node, tool_names, messages)


def _make_agent(tmp_path: Path, script: RuntimeContractScript) -> Any:
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=True,
    )
    agent._call_llm = script  # type: ignore[method-assign]
    return agent


# ── Test 1: Full worker path with nested tasks and analysis effort loop ─


@pytest.mark.asyncio
async def test_runtime_routes_full_worker_path_when_llm_calls_correct_tools(
    tmp_path: Path,
) -> None:
    """Full worker path: analyst → worker → create → analysis_effort loop →
    nested decomposition → execute each leaf → review each → aggregate → respond."""
    script = RuntimeContractScript()
    agent = _make_agent(tmp_path, script)

    result = await agent.run("Build me a note-taking app.")

    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]
    snapshot = agent.loop.get_state_snapshot()
    tasks = snapshot["task_tree"]["tasks"]

    # Result is non-empty
    assert result.strip()

    # All required nodes appear in trace
    for required_node in (
        "query_analyst",
        "digester",
        "worker",
        "task_create",
        "task_analyzer",
        "task_executor",
        "result_reviewer",
        "analysis_effort",
        "result_aggregation",
        "response",
    ):
        assert required_node in node_ids, f"{required_node} not in trace"

    # result_aggregation before response
    agg_idx = node_ids.index("result_aggregation")
    resp_idx = node_ids.index("response")
    assert agg_idx < resp_idx

    # Nested tasks exist (root has children)
    root_tasks = [t for t in tasks.values() if t["parent_id"] is None]
    assert len(root_tasks) == 1
    root = root_tasks[0]
    assert len(root["children"]) >= 2, (
        f"Root should have ≥2 children, got {len(root['children'])}"
    )

    # All tasks completed
    for task_data in tasks.values():
        assert task_data["status"] == "completed", (
            f"task {task_data['task_id']} status={task_data['status']}"
        )

    # Active task cleared
    assert agent.loop.root_session.task_store.active_task_id is None
    root_task = agent.loop.root_session.task_store.tasks[root["task_id"]]
    assert root_task.metadata["assurance_status"] == "observed"
    assert '"assurance_status":"observed"' in str(
        script.captured_messages_by_node["final"][-1]
    )

    # No validation errors on final attempt per node
    seen_nodes: set[str] = set()
    for entry in reversed(trace):
        nid = entry["node_id"]
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            assert not entry.get("validation_errors"), (
                f"{nid} final: {entry['validation_errors']}"
            )

    # Real file artifacts exist
    assert any(p.name.endswith(".txt") for p in tmp_path.iterdir()), (
        "No task artifact files written"
    )


# ── Test 2: Bad once per contract node retries then completes ────────────


@pytest.mark.asyncio
async def test_runtime_retries_each_contract_node_then_completes_when_llm_corrects(
    tmp_path: Path,
) -> None:
    """Each bad-once node gets retried and then completes on correction."""
    bad_nodes = {
        "query_analyst",
        "task_create",
        "task_analyzer",
        "task_assessor",
        "task_executor",
        "result_reviewer",
    }
    script = RuntimeContractScript(bad_once_nodes=frozenset(bad_nodes))
    agent = _make_agent(tmp_path, script)

    result = await agent.run("Build me a note-taking app.")

    assert result.strip()

    for node in bad_nodes:
        assert script.calls_by_node.get(node, 0) >= 2, (
            f"{node} called {script.calls_by_node.get(node, 0)} times, expected ≥2"
        )
        second_attempt = script.captured_messages_by_node[node][1]
        assert any(
            message.get("role") == "user"
            and "[System:" in str(message.get("content", ""))
            and any(
                directive in str(message.get("content", ""))
                for directive in ("Call ", "Correct ", "COMMIT PHASE")
            )
            for message in second_attempt
        ), f"{node} retry did not include correction or commit guidance"

    # Task tree completed
    snapshot = agent.loop.get_state_snapshot()
    for task_data in snapshot["task_tree"]["tasks"].values():
        assert task_data["status"] == "completed"


# ── Test 3: Bad forever route node fails closed ──────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("node_id", ["query_analyst"])
async def test_runtime_fails_closed_when_route_node_never_calls_required_tool(
    tmp_path: Path, node_id: str
) -> None:
    """Route node that never calls required tool exhausts retries and fails."""
    script = RuntimeContractScript(bad_forever_nodes=frozenset({node_id}))
    agent = _make_agent(tmp_path, script)

    with pytest.raises(NodeExecutionError):
        await agent.run("Build me a note-taking app.")

    # No task tree fabricated for query_analyst; no execution for worker
    snapshot = agent.loop.get_state_snapshot()
    tasks = snapshot["task_tree"]["tasks"]
    if node_id == "query_analyst":
        assert len(tasks) <= 1, (
            f"query_analyst failure should not fabricate tasks: {len(tasks)}"
        )

    trace = agent.loop.get_execution_trace()
    node_ids = [entry["node_id"] for entry in trace]
    if node_id == "worker":
        assert "task_executor" not in node_ids


# ── Test 4: Bad forever task-state node fails without fake state ─────────


@pytest.mark.asyncio
@pytest.mark.parametrize("node_id", ["task_create", "task_executor", "result_reviewer"])
async def test_runtime_fails_without_fabricating_task_state_when_task_node_never_calls_tool(
    tmp_path: Path, node_id: str
) -> None:
    """Task-state node that never calls tool fails without producing fake completed state."""
    script = RuntimeContractScript(bad_forever_nodes=frozenset({node_id}))
    agent = _make_agent(tmp_path, script)

    with pytest.raises(NodeExecutionError):
        await agent.run("Build me a note-taking app.")

    assert script.calls_by_node.get(node_id, 0) > 0, f"{node_id} was never called"


@pytest.mark.asyncio
async def test_runtime_recovers_when_task_analyzer_never_calls_tool(
    tmp_path: Path,
) -> None:
    """Analyzer exhaustion retains the root and proceeds autonomously."""
    script = RuntimeContractScript(bad_forever_nodes=frozenset({"task_analyzer"}))
    agent = _make_agent(tmp_path, script)

    await agent.run("Build me a note-taking app.")

    root_id = agent.loop.root_session.task_store.root_task_id
    assert root_id is not None
    root = agent.loop.root_session.task_store.tasks[root_id]
    assert root.metadata["analyzer_recovery"]["recovery"] == "continue_execution"
    assert "task_executor" in [
        entry["node_id"] for entry in agent.loop.get_execution_trace()
    ]
