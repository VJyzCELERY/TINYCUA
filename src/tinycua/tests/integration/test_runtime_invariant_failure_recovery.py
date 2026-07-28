"""Weak/malformed node output self-recovers without route skipping.

Spec: ./specs/tinycua-runtime-invariants/spec.md:179, 187, 218-219, 227, 273
Source: src/tinycua/docs/design/loops/tinycua_loop.md:36-38, 67-84,
        src/tinycua/docs/design/loops/node.md:216-220

When an internal node emits one weak/malformed/missing-contract output, the
loop must retry/correct the SAME node so it can self-recover by calling the
required scoped tool. The run must still reach ResponseNode/terminal legally;
it must never skip to an unrelated node or ResponseNode to escape the failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent

# Reuse the proven scripted-LLM pattern from the route matrix tests. We import
# the script class to keep a single source of truth for worker-path responses.
from tests.integration.test_runtime_invariant_route_matrix import _RouteMatrixScript


def _make_agent(
    tmp_path: Path, *, bad_once_nodes: frozenset[str]
) -> tuple[Any, _RouteMatrixScript]:
    script = _RouteMatrixScript(route="worker", bad_once_nodes=bad_once_nodes)
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=True,
    )
    agent._call_llm = script  # type: ignore[method-assign]
    return agent, script


def _trace_node_ids(agent: Any) -> list[str]:
    return [entry["node_id"] for entry in agent.loop.get_execution_trace()]


# Internal nodes that own a task-state contract. Each must be able to emit
# one invalid/missing-tool-call output, then recover on retry.
_INTERNAL_CONTRACT_NODES = frozenset(
    {"task_create", "task_analyzer", "task_executor", "result_reviewer"}
)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_node", sorted(_INTERNAL_CONTRACT_NODES))
async def test_each_internal_node_bad_once_recovers_and_run_completes(
    tmp_path: Path, bad_node: str
) -> None:
    """Spec: ./spec.md:179, ./spec.md:187, ./spec.md:227, ./spec.md:273.

    Source: tinycua_loop.md:36-38, tinycua_loop.md:67-84, node.md:216-220.
    One bad emission from a contract node triggers same-node retry, then the
    node calls its required tool and the run completes legally.
    """
    agent, script = _make_agent(tmp_path, bad_once_nodes=frozenset({bad_node}))

    result = await agent.run("Build a multi-step plan")

    assert result.strip()
    node_ids = _trace_node_ids(agent)
    # The bad node was called at least twice (bad emission + recovery).
    assert script.calls_by_node.get(bad_node, 0) >= 2, (
        f"{bad_node} called {script.calls_by_node.get(bad_node, 0)} times, "
        f"expected >=2 (bad + recovery)"
    )
    # The run still terminates at response legally.
    assert node_ids[-1] == "response", f"did not terminate at response: {node_ids}"
    # No direct bad_node -> response skip (recovery path has intervening nodes).
    for i in range(len(node_ids) - 1):
        if node_ids[i] == bad_node and node_ids[i + 1] == "response":
            pytest.fail(f"loop skipped {bad_node} -> response directly: {node_ids}")


@pytest.mark.asyncio
async def test_bad_once_task_analyzer_does_not_skip_to_response(tmp_path: Path) -> None:
    """Spec: ./spec.md:195-196, ./spec.md:227, ./spec.md:272.

    Source: task_analyzer.md:53-61, tinycua_loop.md:67-84.
    Specifically prove TaskAnalyzer bad-once recovers via retry and does NOT
    use the forbidden vertical-slice recovery shortcut to reach response.
    """
    agent, script = _make_agent(tmp_path, bad_once_nodes=frozenset({"task_analyzer"}))

    await agent.run("Build a note taking app with web UI")
    node_ids = _trace_node_ids(agent)

    assert script.calls_by_node.get("task_analyzer", 0) >= 2
    assert node_ids[-1] == "response"
    # The forbidden recovery (analyzer miss -> fabricate vertical slice -> skip)
    # would show a direct task_analyzer -> response transition. Assert absent.
    for i in range(len(node_ids) - 1):
        assert not (node_ids[i] == "task_analyzer" and node_ids[i + 1] == "response"), (
            f"task_analyzer skipped to response: {node_ids}"
        )


@pytest.mark.asyncio
async def test_bad_forever_analyzer_recovers_without_illegal_route(
    tmp_path: Path,
) -> None:
    """Spec: ./spec.md:187, ./spec.md:218-219, ./spec.md:273.

    Source: tinycua_loop.md:36-38, tinycua_loop.md:86-94, node.md:216-220.
    An analyzer that never emits its required contract must exhaust retries,
    retain the root task, and continue through the executor rather than skip
    directly to response.
    """
    script = _RouteMatrixScript(
        route="worker",
        bad_once_nodes=frozenset(),
    )

    # Make task_analyzer bad-forever by reusing bad_once on every call: we
    # subclass to override _is_bad so the node never recovers.
    class _BadForeverScript(_RouteMatrixScript):
        def _is_bad(self, node: str) -> bool:  # noqa: D401
            return node == "task_analyzer"

    script = _BadForeverScript(route="worker")
    agent = create_tinycua_agent(
        session_config=SessionConfig(workspace_dir=tmp_path),
        enable_native_tools=True,
    )
    agent._call_llm = script  # type: ignore[method-assign]

    await agent.run("Build a plan")

    node_ids = _trace_node_ids(agent)
    assert "task_analyzer" in node_ids
    assert "task_executor" in node_ids
    assert not any(
        node_ids[index : index + 2] == ["task_analyzer", "response"]
        for index in range(len(node_ids) - 1)
    )
    root_id = agent.loop.root_session.task_store.root_task_id
    assert root_id is not None
    root = agent.loop.root_session.task_store.tasks[root_id]
    assert root.metadata["analyzer_recovery"]["recovery"] == "continue_execution"
