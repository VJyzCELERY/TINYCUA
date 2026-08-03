"""Managed file-backed JSON draft contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tinycua.config.node_config import create_node_config
from tinycua.config.session_config import SessionConfig
from tinycua.config.types import Tool
from tinycua.loops.node_contract import LifecyclePhase
from tinycua.loops.task_nodes import TinyCUAResultReviewerNode, TinyCUATaskAssessorNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.models.session import Session
from tinycua.models.task import TaskResult
from tinycua.tools.json_drafts import JsonDraftCommitTool, JsonDraftCreateTool
from tinycua_sdk import Agent, LanguageModel
from tinycua.agent.tools.native.files import str_replace, write_file


class _WriteTool(Tool):
    def __init__(self) -> None:
        super().__init__(name="write_file")
        self.paths: list[str] = []

    def __call__(self, path: str) -> dict[str, str | bool]:
        self.paths.append(path)
        return {"success": True, "path": path}


def _bind(tool, drafts: dict[str, dict], workspace: Path) -> None:  # noqa: ANN001
    tool.bind_json_drafts(
        drafts,
        "session-1",
        "task_assessor",
        3,
        {"task_assessment_decision"},
        workspace,
    )


def test_json_draft_create_makes_one_managed_file(tmp_path: Path) -> None:
    """The runtime selects and creates the only draft path."""
    drafts: dict[str, dict] = {}
    create = JsonDraftCreateTool()
    _bind(create, drafts, tmp_path)

    created = create("task_assessment_decision")

    path = tmp_path / created["path"]
    assert path.read_text(encoding="utf-8") == "{}\n"
    assert created["draft_id"] in drafts
    assert path.is_relative_to(tmp_path / ".tinycua" / "session-1" / "tmp")


def test_json_draft_commit_retains_invalid_file_for_repair(tmp_path: Path) -> None:
    """Parse failure retains the managed file and reports its JSON location."""
    drafts: dict[str, dict] = {}
    create = JsonDraftCreateTool()
    commit = JsonDraftCommitTool()
    _bind(create, drafts, tmp_path)
    _bind(commit, drafts, tmp_path)
    created = create("task_assessment_decision")
    path = tmp_path / created["path"]
    path.write_text('{"decision":', encoding="utf-8")

    result = commit(created["draft_id"])

    assert result["success"] is False
    assert "invalid_json line=" in result["error"]
    assert path.exists()


def test_json_draft_commit_reads_the_file_not_tool_call_content(tmp_path: Path) -> None:
    """The managed file is the sole source for canonical target arguments."""
    drafts: dict[str, dict] = {}
    create = JsonDraftCreateTool()
    commit = JsonDraftCommitTool()
    _bind(create, drafts, tmp_path)
    _bind(commit, drafts, tmp_path)
    created = create("task_assessment_decision")
    path = tmp_path / created["path"]
    path.write_text(json.dumps({"decision": "ready"}), encoding="utf-8")

    result = commit(created["draft_id"])

    assert result["arguments"] == {"decision": "ready"}


def test_json_draft_create_allows_one_active_draft(tmp_path: Path) -> None:
    """A node execution cannot commit a different draft by selecting another file."""
    drafts: dict[str, dict] = {}
    create = JsonDraftCreateTool()
    _bind(create, drafts, tmp_path)

    create("task_assessment_decision")

    assert create("task_assessment_decision") == {
        "success": False,
        "error": "active_draft_exists",
    }


@pytest.mark.asyncio
async def test_managed_draft_replaces_model_file_path(tmp_path: Path) -> None:
    """Normal file tools receive the runtime-selected managed draft path."""
    config = SessionConfig(workspace_dir=tmp_path)
    loop = TinyCUALoop(
        root_session=Session(session_config=config), session_config=config
    )
    node = TinyCUATaskAssessorNode("task_assessor", create_node_config("task_assessor"))
    write_tool = _WriteTool()
    _messages, tools = loop._prepare_node(node, [write_tool])
    agent = Agent(llm_model=LanguageModel())

    blocked = await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "write_file", "arguments": {"path": "wrong.json"}}}],
        tools,
        node,
    )
    created = await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "json_draft_create",
                    "arguments": {"target_tool": "task_assessment_decision"},
                }
            }
        ],
        tools,
        node,
    )
    await loop._execute_tool_calls(
        agent,
        [{"function": {"name": "write_file", "arguments": {"path": "wrong.json"}}}],
        tools,
        node,
    )

    assert blocked[0]["error"] == "managed_draft_required"
    assert write_tool.paths == [created[0]["output"]["path"]]


@pytest.mark.asyncio
async def test_reviewer_exposes_managed_editors_only_after_draft(
    tmp_path: Path,
) -> None:
    """Reviewer draft aliases omit paths and commit their JSON as a decision."""
    config = SessionConfig(workspace_dir=tmp_path)
    loop = TinyCUALoop(
        root_session=Session(session_config=config), session_config=config
    )
    node = TinyCUAResultReviewerNode(
        "result_reviewer", create_node_config("result_reviewer")
    )
    task = loop.root_session.task_store.create_task("Review completed work")
    loop.root_session.task_store.record_result(task.task_id, TaskResult(content="done"))
    node.progress.lifecycle_phase = LifecyclePhase.PLAN
    _messages, resolved_tools = loop._prepare_node(node, [write_file, str_replace])
    agent = Agent(llm_model=LanguageModel())

    plan_tools = loop._phase_tools(node, resolved_tools, LifecyclePhase.PLAN)
    assert {tool.name for tool in plan_tools} == {
        "json_draft_create",
        "task_review_plan",
    }
    plan_create = next(tool for tool in plan_tools if tool.name == "json_draft_create")
    assert plan_create.parameters["properties"]["target_tool"]["enum"] == [
        "task_review_plan"
    ]

    node.progress.lifecycle_phase = LifecyclePhase.ACTION
    action_tools = loop._phase_tools(node, resolved_tools, LifecyclePhase.ACTION)
    assert "write_file" not in {tool.name for tool in action_tools}
    assert "str_replace" not in {tool.name for tool in action_tools}
    assert not any(tool.name.startswith("json_draft_") for tool in action_tools)

    node.progress.lifecycle_phase = LifecyclePhase.COMMIT
    before_draft = loop._phase_tools(node, resolved_tools, LifecyclePhase.COMMIT)
    assert {tool.name for tool in before_draft} == {
        "json_draft_create",
        "task_review_decision",
    }
    commit_create = next(
        tool for tool in before_draft if tool.name == "json_draft_create"
    )
    assert commit_create.parameters["properties"]["target_tool"]["enum"] == [
        "task_review_decision"
    ]

    created = await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "json_draft_create",
                    "arguments": {"target_tool": "task_review_decision"},
                }
            }
        ],
        before_draft,
        node,
    )
    after_draft = loop._phase_tools(node, resolved_tools, LifecyclePhase.COMMIT)
    tools = {tool.name: tool for tool in after_draft}

    assert set(tools) == {
        "json_draft_commit",
        "json_draft_replace",
        "json_draft_write",
        "task_review_decision",
    }
    assert "path" not in tools["json_draft_write"].parameters["properties"]
    assert "path" not in tools["json_draft_replace"].parameters["properties"]
    assert "managed JSON draft" in tools["json_draft_write"].description
    assert write_file.name == "write_file"
    assert str_replace.name == "str_replace"

    await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "json_draft_write",
                    "arguments": {
                        "content": json.dumps(
                            {
                                "decision": "approved",
                                "rationale": "Verified.",
                                "review_summary": "Verified.",
                            }
                        )
                    },
                }
            }
        ],
        after_draft,
        node,
    )
    committed = await loop._execute_tool_calls(
        agent,
        [
            {
                "function": {
                    "name": "json_draft_commit",
                    "arguments": {"draft_id": created[0]["output"]["draft_id"]},
                }
            }
        ],
        after_draft,
        node,
    )

    assert committed[0]["name"] == "task_review_decision"
    assert committed[0]["output"]["success"] is True
    assert committed[0]["output"]["staged"] is True
