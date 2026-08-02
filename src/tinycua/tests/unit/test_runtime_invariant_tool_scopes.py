"""Tool scopes match design docs (runtime invariant).

Spec: ./specs/tinycua-runtime-invariants/spec.md:183, 188, 213-214, 228, 274
Source: src/tinycua/docs/design/tools/task.md:5-18,
        src/tinycua/docs/design/loops/information_digester.md:13-18, 52-58,
        src/tinycua/docs/design/loops/task_executor.md:31-43,
        src/tinycua/docs/design/loops/response.md:31-58

Only TaskExecutor and ResponseNode may receive arbitrary workspace/action
tools. Structured nodes may receive write_file and str_replace solely for
runtime-bound managed drafts; all other paths are rejected. These assertions
fail if an unrestricted tool leaks into a non-action node.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tinycua.config.tool_scopes import (
    information_digester_tool_scope,
    query_analyst_tool_scope,
    result_aggregation_tool_scope,
    result_reviewer_tool_scope,
    task_analyzer_tool_scope,
    task_assessor_tool_scope,
    task_create_tool_scope,
    task_executor_tool_scope,
    worker_tool_scope,
)
from tinycua.config.node_config import NodeToolPolicy

# Response scope needs a tiny shim because the default allow_digest path
# depends on session config; import lazily to keep the test hermetic.
from tinycua.config.tool_scopes import response_tool_scope

# Unrestricted write/execute tools — only TaskExecutor and ResponseNode may have
# these. write_file and str_replace are excluded because draft-owning nodes can
# use them only after json_draft_create binds their path. run_shell is NOT in this set: it is the gated exploratory shell
# (hardline blocks unrecoverable commands like rm -rf /; recoverable destructive
# commands warn but execute). Reviewer/analyzer/digester/assessor use it for
# verification (test -f, grep, pytest, git diff) — the gate is the safety net,
# not tool selection.
_ARBITRARY_ACTION_AGENT_TOOLS = frozenset({"append_file", "run_python"})

# (node_id, scope_factory) pairs for every internal node that is NOT
# TaskExecutor or ResponseNode. These must never resolve arbitrary action tools.
_NON_ACTION_NODES: list[tuple[str, Callable[[], NodeToolPolicy]]] = [
    ("query_analyst", query_analyst_tool_scope),
    ("information_digester", information_digester_tool_scope),
    ("worker", worker_tool_scope),
    ("task_create", task_create_tool_scope),
    ("task_analyzer_creation", lambda: task_analyzer_tool_scope("task_creation")),
    ("task_analyzer_recreation", lambda: task_analyzer_tool_scope("task_recreation")),
    ("task_analyzer_reanalysis", lambda: task_analyzer_tool_scope("task_reanalysis")),
    ("task_assessor", task_assessor_tool_scope),
    ("result_reviewer", result_reviewer_tool_scope),
    ("result_aggregation", result_aggregation_tool_scope),
]


def _resolved_tool_names(policy: NodeToolPolicy) -> set[str]:
    """Return the full set of tool names a policy exposes to the LLM.

    Node tools are always exposed. Agent tools are only exposed when
    include_agent_tools != "none"; for "selected" only allowlisted names
    appear, for "all" every agent tool would appear (not asserted here
    because agent tools are runtime-injected).
    """
    names = {t.name for t in policy.node_tools}
    if policy.include_agent_tools == "selected":
        names.update(policy.allowed_agent_tool_names)
    return names


def test_information_digester_has_only_digest_and_managed_draft_tools() -> None:
    """Spec: ./spec.md:188, ./spec.md:228, ./spec.md:274.

    Source: information_digester.md:13-18, information_digester.md:52-58.
    InformationDigester must not receive task tools or unrestricted action tools.
    """
    names = _resolved_tool_names(information_digester_tool_scope())

    assert "enhanced_context_retrieval" in names
    assert "digest_information" in names
    # Forbidden task tools
    assert "task_init" not in names
    assert "task_create" not in names
    assert "task_decompose" not in names
    assert "task_result_update" not in names
    assert "task_review_decision" not in names
    # write_file and str_replace are runtime-bound to one managed draft. The
    # orientation-only Digester does not receive arbitrary shell execution.
    assert "write_file" in names
    assert "str_replace" in names
    assert "append_file" not in names
    assert "run_python" not in names
    assert "run_shell" not in names


@pytest.mark.parametrize(
    "node_id, factory",
    _NON_ACTION_NODES,
    ids=[nid for nid, _ in _NON_ACTION_NODES],
)
def test_non_action_nodes_have_no_arbitrary_write_execute_tools(
    node_id: str, factory: Callable[[], NodeToolPolicy]
) -> None:
    """Spec: ./spec.md:183, ./spec.md:213-214, ./spec.md:228, ./spec.md:274.

    Source: task_executor.md:31-43, response.md:31-58, tools/task.md:5-18.
    Every node except TaskExecutor and ResponseNode must be free of
    unrestricted write/execute tools.
    """
    names = _resolved_tool_names(factory())
    leaked = _ARBITRARY_ACTION_AGENT_TOOLS & names
    assert not leaked, f"{node_id} leaks arbitrary action tools: {leaked}"


def test_task_executor_has_arbitrary_action_tools() -> None:
    """Spec: ./spec.md:214, ./spec.md:228, ./spec.md:274.

    Source: task_executor.md:31-43.
    TaskExecutor is one of the two nodes allowed arbitrary action tools.
    """
    names = _resolved_tool_names(task_executor_tool_scope())
    assert _ARBITRARY_ACTION_AGENT_TOOLS <= names


def test_response_node_has_arbitrary_action_tools() -> None:
    """Spec: ./spec.md:214, ./spec.md:228, ./spec.md:274.

    Source: response.md:31-58.
    ResponseNode is the other node allowed arbitrary action tools.
    """
    names = _resolved_tool_names(response_tool_scope())
    assert _ARBITRARY_ACTION_AGENT_TOOLS <= names


def test_task_analyzer_has_no_execution_or_action_tools_in_any_mode() -> None:
    """Spec: ./spec.md:183, ./spec.md:213-214, ./spec.md:274.

    Source: task_analyzer.md:33-42, tools/task.md:5-18.
    TaskAnalyzer mutates the task tree via structural tools only.
    """
    for mode in ("task_creation", "task_recreation", "task_reanalysis"):
        names = _resolved_tool_names(task_analyzer_tool_scope(mode))
        assert "task_result_update" not in names, f"{mode}: executor tool leaked"
        assert "task_review_decision" not in names, f"{mode}: reviewer tool leaked"
        assert not (_ARBITRARY_ACTION_AGENT_TOOLS & names), (
            f"{mode}: action tools leaked: {_ARBITRARY_ACTION_AGENT_TOOLS & names}"
        )


def test_result_reviewer_has_only_managed_draft_writes() -> None:
    """Spec: ./spec.md:183, ./spec.md:213-214, ./spec.md:274.

    Source: result_reviewer.md:6-18, response.md:31-58.
    ResultReviewer may inspect artifacts and edit only a managed draft.
    """
    names = _resolved_tool_names(result_reviewer_tool_scope())
    assert "task_review_decision" in names
    assert "read_file" in names
    assert "list_files" in names
    # run_shell IS in the reviewer scope — it is the gated exploratory shell
    # (hardline blocks unrecoverable; recoverable-destructive warns). The
    # reviewer verifies via exit_code/exit_code_meaning.
    assert "run_shell" in names
    assert "write_file" in names
    assert "str_replace" in names
    assert "append_file" not in names
    assert "run_python" not in names
