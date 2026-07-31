"""Session-memory JSON draft contracts."""

from __future__ import annotations

from unittest.mock import MagicMock

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.tinycua_loop import TinyCUALoop
from tinycua.tools.json_drafts import (
    JsonDraftCommitTool,
    JsonDraftCreateTool,
    JsonDraftReplaceTool,
)


def _bind(tool, drafts: dict[str, dict]) -> None:  # noqa: ANN001
    tool.bind_json_drafts(drafts, "session", "reviewer", 3, {"task_review_decision"})


def test_json_draft_replaces_one_exact_occurrence() -> None:
    """A correction changes only one exact draft fragment."""
    drafts: dict[str, dict] = {}
    create = JsonDraftCreateTool()
    replace = JsonDraftReplaceTool()
    _bind(create, drafts)
    _bind(replace, drafts)
    created = create("task_review_decision", '{"decision":"approved"}')

    updated = replace(created["draft_id"], 0, '"approved"', '"needs_revision"')

    assert updated["revision"] == 1
    assert drafts[created["draft_id"]]["content"] == '{"decision":"needs_revision"}'


def test_json_draft_commit_retains_invalid_json_for_repair() -> None:
    """Invalid JSON reports its position without deleting the draft."""
    drafts: dict[str, dict] = {}
    create = JsonDraftCreateTool()
    commit = JsonDraftCommitTool()
    _bind(create, drafts)
    _bind(commit, drafts)
    created = create("task_review_decision", '{"decision":')

    result = commit(created["draft_id"], 0)

    assert result["success"] is False
    assert "invalid_json line=" in result["error"]
    assert created["draft_id"] in drafts


async def test_json_draft_commit_executes_and_consumes_its_target() -> None:
    """A successful draft commit uses the canonical target mutation once."""
    loop = TinyCUALoop()
    node = TinyCUATaskCreateNode("task_create", create_node_config("task_create"))
    _messages, tools = loop._prepare_node(node, [], None)
    agent = MagicMock()
    agent.tool_permissions = {}
    agent.approval_workflow = None
    create = next(tool for tool in tools if tool.name == "json_draft_create")
    created = create("task_init", '{"title":"Draft task","description":"From draft"}')

    results = await loop._execute_tool_calls(
        agent,
        [
            {
                "id": "commit-1",
                "type": "function",
                "function": {
                    "name": "json_draft_commit",
                    "arguments": (
                        f'{{"draft_id":"{created["draft_id"]}","expected_revision":0}}'
                    ),
                },
            }
        ],
        tools,
        node,
    )

    assert results[0]["name"] == "task_init"
    assert loop.root_session.task_store.root_task_id is not None
    assert created["draft_id"] not in loop.root_session.json_drafts
