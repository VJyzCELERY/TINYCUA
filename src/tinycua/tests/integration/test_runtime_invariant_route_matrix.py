"""Route matrix: legal passthrough/worker paths and impossible-route rejection.

Spec: ./specs/tinycua-runtime-invariants/spec.md:184-186, 195-196, 224-227, 271-272
Source: src/tinycua/docs/design/loops/query_analyst.md:57-65, 83-101,
        src/tinycua/docs/design/loops/worker.md:75-89,
        src/tinycua/docs/design/loops/task_analyzer.md:53-61,
        src/tinycua/docs/design/loops/task_executor.md:44-52,
        src/tinycua/docs/design/loops/result_reviewer.md:56-91,
        src/tinycua/docs/design/loops/response.md:60-90

Every ``Agent.run`` must terminate at ResponseNode or an explicit terminal
node and follow only source-of-truth queue shapes. Impossible routes
(TaskAnalyzer/TaskCreate/TaskExecutor directly to ResponseNode) must be
rejected, never silently accepted.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node import NodeExecutionError
from tinycua.models.session_context_entry import entry_content
from tinycua.models.task import TaskStatus


class _RouteMatrixScript:
    """Deterministic scripted LLM for route-matrix invariant tests.

    Detects which node is being called by available tool names and returns
    route-appropriate responses. ``bad_once_nodes`` makes a node emit one
    invalid response (no required tool call) before its correct response.
    ``force_route`` overrides the analyzer/executor/reviewer to attempt an
    illegal direct-to-response skip so the impossible-route test can prove
    the loop rejects it.
    """

    def __init__(
        self,
        *,
        route: str = "passthrough",
        worker_route: str = "task_creation",
        bad_once_nodes: frozenset[str] = frozenset(),
        force_route: str | None = None,
    ) -> None:
        self.route = route
        self.worker_route = worker_route
        self.bad_once_nodes = set(bad_once_nodes)
        self.force_route = force_route
        self.calls_by_node: dict[str, int] = {}
        self._bad_emitted: set[str] = set()

    def _detect_node(self, tool_names: set[str]) -> str:
        if "final_response_synthesis" in tool_names:
            return "response"
        if "select_query_route" in tool_names:
            return "query_analyst"
        if "select_worker_route" in tool_names:
            return "worker"
        if "digest_information" in tool_names:
            return "digester"
        if "task_init" in tool_names and "task_decompose" not in tool_names:
            return "task_create"
        if "task_decompose" in tool_names:
            return "task_analyzer"
        if "task_assessment_decision" in tool_names:
            return "task_assessor"
        if "task_review_plan" in tool_names:
            return "result_reviewer"
        if "task_review_decision" in tool_names:
            return "result_reviewer"
        if "task_update" in tool_names:
            return "result_reviewer"
        if "task_inspect" in tool_names and tool_names & {
            "read_file",
            "run_shell",
            "list_files",
        }:
            return "result_reviewer"
        if "write_file" in tool_names:
            return "task_executor"
        if "task_result_update" in tool_names:
            return "task_executor"
        if tool_names == {"task_inspect"}:
            return "result_aggregation"
        return "response"

    def _is_bad(self, node: str) -> bool:
        if node in self.bad_once_nodes:
            return node not in self._bad_emitted
        return False

    def _task_id(self, messages: list[dict[str, Any]]) -> str:
        """Resolve the active or root task id from rendered node context.

        The loop renders task-tree context into messages as markdown
        (``Root: title (id=abc123)`` / ``Active: title (id=abc123)``) and as
        raw snapshot dicts (``'root_task_id': '...'``). We try both.
        """
        text = "\n".join(str(m.get("content", "")) for m in messages)
        # Markdown: Active: title (id=abc123)
        match = re.search(r"Active: .+ \(id=([^\)]+)\)", text)
        if match:
            return match.group(1)
        # Markdown: Root: title (id=abc123)
        match = re.search(r"Root: .+ \(id=([^\)]+)\)", text)
        if match:
            return match.group(1)
        # Raw snapshot dict: 'root_task_id': '...'
        match = re.search(r"'root_task_id': '([^']+)'", text) or re.search(
            r'"root_task_id": "([^"]+)"',
            text,
        )
        if match:
            return match.group(1)
        # Raw snapshot dict: 'active_task_id': '...'
        match = re.search(r"'active_task_id': '([^']+)'", text) or re.search(
            r'"active_task_id": "([^"]+)"',
            text,
        )
        return match.group(1) if match else ""

    async def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: Any,
        stream: bool = False,  # noqa: ANN001, ARG002
    ) -> dict[str, Any]:
        tool_names = {t.name for t in tools}
        node = self._detect_node(tool_names)
        is_bad = self._is_bad(node) and not (
            (node == "task_executor" and "task_result_update" not in tool_names)
            or (node == "result_reviewer" and "task_review_decision" not in tool_names)
        )
        if is_bad:
            self._bad_emitted.add(node)
        self.calls_by_node[node] = self.calls_by_node.get(node, 0) + 1

        if is_bad:
            return {"content": "bad response without required tool", "tool_calls": []}
        return self._response(node, tool_names, messages)

    def _response(  # noqa: C901
        self, node: str, tool_names: set[str], messages: list[dict[str, Any]]
    ) -> dict[str, Any]:
        # Forced illegal route: the target task node tries to jump straight
        # to response. We only force on the TARGET node, and only after the
        # prerequisite nodes (task_create -> task_analyzer) have built the
        # task tree, so the forced node actually runs. task_create must
        # always run its real tool so the tree exists.
        if self.force_route and node == self.force_route:
            return {
                "content": f"Forcing illegal {node} -> response skip.",
                "tool_calls": [],
                "metadata": {"forced_route": "response"},
            }

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
                            "arguments": f'{{"route":"{self.route}"}}',
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
                            "arguments": f'{{"route":"{self.worker_route}"}}',
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
                            "arguments": (
                                '{"title":"Build a note-taking app",'
                                '"acceptance_clauses":["Build a note-taking app"]}'
                            ),
                        }
                    }
                ],
            }
        if node == "task_analyzer":
            root_id = self._task_id(messages)
            if any(
                m.get("role") == "tool"
                and ("task_decompose" in str(m.get("content", "")))
                for m in messages
            ):
                return {"content": "Analysis complete.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_decompose",
                            "arguments": (
                                f'{{"task_id":"{root_id}","subtasks":['
                                '"Create backend","Create frontend"]}'
                            ),
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
                            "arguments": (
                                '{"decision":"ready","findings":[],"advisories":[],'
                                '"rationale":"The roadmap is executable."}'
                            ),
                        }
                    }
                ],
            }
        if node == "task_executor":
            task_id = self._task_id(messages) or "active"
            if "write_file" in tool_names:
                if any(
                    m.get("role") == "tool"
                    and "write_file" in str(m.get("content", ""))
                    for m in messages
                ):
                    return {"content": "Action complete.", "tool_calls": []}
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "write_file",
                                "arguments": (
                                    f'{{"path":"{task_id}.txt",'
                                    f'"content":"Completed {task_id}\\n"}}'
                                ),
                            }
                        }
                    ],
                }
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
                            "arguments": (
                                f'{{"content":"Completed {task_id}","success":true}}'
                            ),
                        }
                    }
                ],
            }
        if node == "result_reviewer":
            if "task_review_plan" in tool_names:
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "task_review_plan",
                                "arguments": (
                                    '{"checks":[{"criterion_id":"acceptance-1",'
                                    '"testability":"judgment",'
                                    '"falsifying_condition":"The request is unmet.",'
                                    '"procedure":"Compare the result to the request.",'
                                    '"expected_observation":"The request is met."}]}'
                                ),
                            }
                        }
                    ],
                }
            if "task_review_decision" not in tool_names:
                if any(
                    m.get("role") == "tool"
                    and "task_inspect" in str(m.get("content", ""))
                    for m in messages
                ):
                    return {"content": "Inspection complete.", "tool_calls": []}
                return {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "task_inspect", "arguments": "{}"}}
                    ],
                }
            if any(
                m.get("role") == "tool"
                and "task_review_decision" in str(m.get("content", ""))
                for m in messages
            ):
                return {"content": "Review recorded.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_review_decision",
                            "arguments": (
                                '{"decision":"approved",'
                                '"rationale":"The scripted result is acceptable.",'
                                '"criterion_assessments":[{'
                                '"criterion_id":"acceptance-1",'
                                '"result":"judgment_only","evidence_ids":[],'
                                '"inference":"The request is met.",'
                                '"limitations":"Scripted judgment only."}]}'
                            ),
                        }
                    },
                ],
            }
        if node == "result_aggregation":
            return {"content": "All tasks completed successfully.", "tool_calls": []}
        # response / final
        return {"content": "Final response to the user.", "tool_calls": []}


def _make_agent(tmp_path: Path, *, route: str = "passthrough", **kwargs: Any) -> Any:
    script = _RouteMatrixScript(route=route, **kwargs)
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=True,
    )
    agent._call_llm = script  # type: ignore[method-assign]
    return agent, script


def _trace_node_ids(agent: Any) -> list[str]:
    return [entry["node_id"] for entry in agent.loop.get_execution_trace()]


def _has_direct_transition(node_ids: list[str], src: str, dst: str) -> bool:
    """Return True if ``dst`` immediately follows ``src`` anywhere in trace.

    A direct transition is the route-skip signature: the forced node
    completed and the very next trace entry is the response node, with no
    intervening legal node (reviewer/aggregation) between them.
    """
    for i in range(len(node_ids) - 1):
        if node_ids[i] == src and node_ids[i + 1] == dst:
            return True
    return False


# ── Legal routes ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_one_shot_passthrough_route_is_query_analyst_then_response(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:185, ./spec.md:224-226 (acceptance scenario 7).

    Source: query_analyst.md:57-65, query_analyst.md:83-93, response.md:60-90,
            route_map.md:55-93.

    Passthrough is a forwarding decision: it sends user input to the next
    node in the queue. This test is scoped to ONE-SHOT prompting, where the
    default queue is [QueryAnalyst, ResponseNode], so passthrough legally
    forwards to ResponseNode. (In a continuation queue such as
    [QueryAnalyst, TaskExecutor, ResponseNode] a passthrough decision would
    forward to TaskExecutor — that is also legal, but is NOT what this
    one-shot test asserts.)
    """
    agent, _ = _make_agent(tmp_path, route="passthrough")

    result = await agent.run("hello")

    assert result.strip()
    node_ids = _trace_node_ids(agent)
    assert node_ids[0] == "query_analyst"
    assert node_ids[-1] == "response"
    # In one-shot the default queue has only QueryAnalyst and ResponseNode,
    # so no worker-path nodes may appear.
    for forbidden in ("digester", "worker", "task_create", "task_executor"):
        assert forbidden not in node_ids, (
            f"{forbidden} appeared in one-shot passthrough route: {node_ids}"
        )


@pytest.mark.asyncio
async def test_worker_route_reaches_executor_then_reviewer_before_response(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:186, ./spec.md:226.

    Source: worker.md:75-89, task_executor.md:44-52, result_reviewer.md:56-91,
            response.md:60-90.
    Worker route must include executor BEFORE reviewer and end at response.
    """
    agent, _ = _make_agent(tmp_path, route="worker")

    await agent.run("Create a multi-step implementation plan")
    node_ids = _trace_node_ids(agent)

    assert node_ids[0] == "query_analyst"
    assert "digester" in node_ids
    assert "worker" in node_ids
    assert "task_executor" in node_ids
    assert "result_reviewer" in node_ids
    assert node_ids.index("task_executor") < node_ids.index("result_reviewer"), (
        f"executor must precede reviewer: {node_ids}"
    )
    assert node_ids[-1] == "response"


@pytest.mark.asyncio
async def test_mock_llm_recreation_archives_terminal_tree_and_creates_a_new_root(
    tmp_path: Path,
) -> None:
    """A terminal tree is archived, then a mock-driven route builds a fresh one."""
    agent, _ = _make_agent(tmp_path, route="worker", worker_route="task_recreation")
    old_root = agent.loop.root_session.task_store.create_task("Completed old root")
    old_root.status = TaskStatus.COMPLETED

    await agent.run("Start a different objective")

    store = agent.loop.root_session.task_store
    assert store.root_task_id != old_root.task_id
    assert any(
        isinstance(entry_content(entry), dict)
        and entry_content(entry).get("archive_type") == "task_tree"
        and entry_content(entry)["task_tree"]["root_task_id"] == old_root.task_id
        for entry in agent.loop.root_session.session_context
    )
    assert "task_create" in _trace_node_ids(agent)


@pytest.mark.asyncio
async def test_every_run_terminates_at_response_or_terminal_node(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:184-186, ./spec.md:225, ./spec.md:271.

    Source: tinycua_loop.md:19-40, node_queue.md:85-101, response.md:60-90.
    The last trace entry must always be the response/terminal node.
    """
    agent, _ = _make_agent(tmp_path, route="worker")

    await agent.run("Plan and build something")
    node_ids = _trace_node_ids(agent)

    last = node_ids[-1]
    assert last == "response", f"run did not terminate at response: {last}"


# ── Impossible routes ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "force_node",
    ["task_analyzer", "task_create", "task_executor"],
)
async def test_impossible_task_route_to_response_is_rejected(
    tmp_path: Path, force_node: str
) -> None:
    """Spec: ./spec.md:195-196, ./spec.md:226, ./spec.md:272.

    Source: task_analyzer.md:53-61, task_executor.md:44-52,
            result_reviewer.md:56-91.
    A task node that tries to skip directly to ResponseNode must be rejected
    (via retry/correction or failure), never silently accepted.
    """
    agent, _script = _make_agent(tmp_path, route="worker", force_route=force_node)

    # The run either retries the node to recovery (good) or fails closed.
    # What must NOT happen: the run "succeeds" with the forced skip.
    try:
        await agent.run("force skip")
    except NodeExecutionError:
        # Fail-closed is an acceptable rejection of the impossible route.
        pass

    node_ids = _trace_node_ids(agent)
    # The forced node must appear (it was attempted)...
    assert force_node in node_ids, f"{force_node} never ran: {node_ids}"
    # ...but a direct force_node -> response skip must NEVER be accepted.
    # Either the loop retried the node to recovery (response appears only
    # after the legal intervening nodes) or it failed closed (no response).
    assert not _has_direct_transition(node_ids, force_node, "response"), (
        f"loop accepted illegal {force_node} -> response direct skip: {node_ids}"
    )
