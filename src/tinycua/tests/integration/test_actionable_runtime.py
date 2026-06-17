"""Deterministic actionable runtime integration contracts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node import NodeExecutionError


class AppCreationScript:
    """Scripted model that uses real workspace tools to create an app."""

    def _task_id(self, messages, key: str = "active_task_id") -> str:
        """Extract a task id from task snapshots in prompt/tool messages."""
        text = "\n".join(str(message.get("content", "")) for message in messages)
        # Try raw dict format
        match = re.search(rf"'{key}': '([^']+)'", text) or re.search(
            rf'"{key}": "([^"]+)"',
            text,
        )
        if match:
            return match.group(1)
        # Try markdown format: Active: title (id=abc123)
        if key == "active_task_id":
            match = re.search(r'Active: .+ \(id=([^\)]+)\)', text)
            if match:
                return match.group(1)
        if key == "root_task_id":
            match = re.search(r'Root: .+ \(id=([^\)]+)\)', text)
            if match:
                return match.group(1)
        # Fallback
        match = re.search(r"'root_task_id': '([^']+)'", text) or re.search(
            r'"root_task_id": "([^"]+)"',
            text,
        )
        return match.group(1) if match else ""

    async def __call__(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002, C901
        tool_names = {tool.name for tool in tools}
        if "select_query_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "select_query_route",
                            "arguments": '{"route":"worker"}',
                        }
                    }
                ],
            }
        if "select_worker_route" in tool_names:
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
        if "digest_information" in tool_names:
            return {
                "content": '{"context_summary":"Create a tiny Python app"}',
                "tool_calls": [],
            }
        if "task_init" in tool_names:
            if any(
                message.get("role") == "tool"
                and "task_init" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "Initialized task tree.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_init",
                            "arguments": '{"title":"Create a tiny Python app"}',
                        }
                    }
                ],
            }
        if "task_decompose" in tool_names:
            task_id = self._task_id(messages, "root_task_id")
            if any(
                message.get("role") == "tool"
                and (
                    "task_decompose" in str(message.get("content", ""))
                    or "task_update" in str(message.get("content", ""))
                )
                for message in messages
            ):
                return {"content": "Task analysis recorded.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_decompose",
                            "arguments": (
                                '{"task_id":"'
                                + task_id
                                + '","subtasks":["Write app.py","Run app verification"]}'
                            ),
                        }
                    }
                ],
            }
        if "node_handoff" in tool_names:
            if any(
                message.get("role") == "tool"
                and "node_handoff" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "Assessment handed off.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "node_handoff",
                            "arguments": (
                                '{"target_node":"task_analyzer",'
                                '"instruction":"Analyze unfinished tasks for execution readiness.",'
                                '"payload":{"assessment":"ready for execution"}}'
                            ),
                        }
                    }
                ],
            }
        if "task_update" in tool_names:
            task_id = self._task_id(messages)
            if any(
                message.get("role") == "tool"
                and "task_update" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "Assessment recorded.", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_update",
                            "arguments": (
                                '{"task_id":"'
                                + task_id
                                + '","assessment":"ready for execution"}'
                            ),
                        }
                    }
                ],
            }
        if {"write_file", "run_shell"} <= tool_names:
            if any(
                message.get("role") == "tool"
                and "task_result_update" in str(message.get("content", ""))
                for message in messages
            ):
                return {
                    "content": "Created app.py and verified it runs.",
                    "tool_calls": [],
                }
            if any(
                message.get("role") == "tool"
                and "write_file" in str(message.get("content", ""))
                for message in messages
            ):
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_result_update",
                            "type": "function",
                            "function": {
                                "name": "task_result_update",
                                "arguments": '{"content":"Created app.py and verified it runs.","success":true}',
                            },
                        }
                    ],
                }
            return {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_write",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": '{"path":"app.py","content":"print(\\"hello app\\")\\n"}',
                        },
                    },
                    {
                        "id": "call_shell",
                        "type": "function",
                        "function": {
                            "name": "run_shell",
                            "arguments": '{"command":"python app.py","timeout":5}',
                        },
                    },
                ],
            }
        if "task_review_decision" in tool_names:
            if not any(
                message.get("role") == "tool"
                and (
                    "read_file" in str(message.get("content", ""))
                    or "list_files" in str(message.get("content", ""))
                )
                for message in messages
            ):
                return {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "list_files",
                                "arguments": "{}",
                            }
                        }
                    ],
                }
            if any(
                message.get("role") == "tool"
                and "task_review_decision" in str(message.get("content", ""))
                for message in messages
            ):
                return {"content": "approved", "tool_calls": []}
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_review_decision",
                            "arguments": '{"decision":"approved","rationale":"Tool evidence verifies the task."}',
                        }
                    }
                ],
            }
        return {"content": "final app creation summary", "tool_calls": []}


class PlannerOnlyScript:
    """Scripted model that routes correctly but emits planner/refusal prose."""

    planner_text = (
        "I cannot create files in a physical workspace or execute commands on your "
        "system. However, here is a complete project structure.\n\n"
        "## Project Structure\n```\nnote_scheduler_app/\n├── app.py\n├── templates/\n```"
    )

    async def __call__(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        tool_names = {tool.name for tool in tools}
        if "select_query_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "select_query_route",
                            "arguments": '{"route":"worker"}',
                        }
                    }
                ],
            }
        if "select_worker_route" in tool_names:
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
        return {"content": self.planner_text, "tool_calls": []}


class PromptEchoScript:
    """Scripted model that routes but echoes prompts for all worker nodes."""

    async def __call__(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        tool_names = {tool.name for tool in tools}
        if "select_query_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "select_query_route",
                            "arguments": '{"route":"worker"}',
                        }
                    }
                ],
            }
        if "select_worker_route" in tool_names:
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
        return {
            "content": "\n\n".join(
                str(message.get("content", ""))
                for message in messages
                if str(message.get("content", "")).strip()
            ),
            "tool_calls": [],
        }


class StreamingPromptEchoScript(PromptEchoScript):
    """Prompt echo script that emits streamed deltas like the notebook path."""

    def __call__(self, messages, tools, stream: bool = False):  # noqa: ANN001
        if not stream:
            return super().__call__(messages, tools, stream=stream)
        return self._stream(messages, tools)

    async def _stream(self, messages, tools):  # noqa: ANN001
        """Yield stream events for the scripted prompt echo response."""
        response = await super().__call__(messages, tools, stream=False)
        tool_calls = response.get("tool_calls", [])
        if tool_calls:
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                yield {
                    "type": "tool_call.ready",
                    "id": tool_call.get("id"),
                    "name": function.get("name", ""),
                    "arguments": function.get("arguments", "{}"),
                }
            return
        content = response.get("content", "")
        if content:
            yield {"type": "response.output_text.delta", "delta": content}
        yield {"type": "response.completed", "finish_reason": "completed"}


def _assert_worker_trace_uses_allowed_edges(trace: list[dict]) -> None:
    """Validate high-level worker lifecycle routing edges."""
    allowed_edges = {
        "query_analyst": {"digester", "response"},
        "digester": {"worker", "response"},
        "worker": {"task_create", "task_executor", "result_reviewer", "response"},
        "task_create": {"task_analyzer"},
        "task_analyzer": {"analysis_effort", "task_executor"},
        "analysis_effort": {"task_assessor", "task_executor"},
        "task_assessor": {"task_analyzer", "task_executor"},
        "task_executor": {"task_executor", "result_reviewer"},
        "result_reviewer": {
            "task_executor",
            "task_assessor",
            "result_aggregation",
            "response",
        },
        "result_aggregation": {"response"},
    }
    node_ids = [str(entry.get("node_id")) for entry in trace]
    for current, next_node in zip(node_ids, node_ids[1:], strict=False):
        if current == next_node:
            continue
        allowed = allowed_edges.get(current)
        assert allowed is not None, f"unexpected node in trace: {current}"
        assert next_node in allowed, f"illegal worker edge: {current} -> {next_node}"


async def test_worker_action_request_writes_file_and_runs_verification(
    tmp_path: Path,
) -> None:
    """Worker execution must perform real workspace actions via tools."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    agent._call_llm = AppCreationScript()  # type: ignore[method-assign]

    result = await agent.run("Create a tiny Python app and verify it runs.")

    app_file = tmp_path / "app.py"
    trace = agent.loop.get_execution_trace()
    task_snapshot = agent.loop.get_state_snapshot()["task_tree"]
    tasks = task_snapshot["tasks"]
    assert app_file.read_text() == 'print("hello app")\n'
    assert result.strip()
    assert any(
        item.get("name") == "run_shell"
        and item.get("output", {}).get("stdout") == "hello app\n"
        for entry in trace
        for item in entry.get("tool_results", [])
    )
    assert "task_tree_text" in agent.loop.get_state_snapshot()
    assert "Task [" in agent.loop.get_state_snapshot()["task_tree_text"]
    assert task_snapshot["root_task_id"] is not None
    assert task_snapshot["active_task_id"] is None
    assert tasks
    assert all(task["status"] == "completed" for task in tasks.values())
    _assert_worker_trace_uses_allowed_edges(trace)


async def test_planner_only_worker_run_fails_without_workspace_artifacts(
    tmp_path: Path,
) -> None:
    """Planner prose must not be converted into hardcoded workspace artifacts."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    agent._call_llm = PlannerOnlyScript()  # type: ignore[method-assign]

    with pytest.raises(NodeExecutionError, match="task_create failed runtime validation"):
        await agent.run(
            "Please create a small note taking app with a scheduler in the workspace."
        )

    snapshot = agent.loop.get_state_snapshot()
    task_tree_text = snapshot["task_tree_text"]
    trace = agent.loop.get_execution_trace()

    assert not (tmp_path / "backend.py").exists()
    assert not (tmp_path / "scheduler.py").exists()
    assert not (tmp_path / "webapp" / "index.html").exists()
    assert "note_scheduler_app/" not in task_tree_text
    assert "├── app.py" not in task_tree_text
    failed_node = next(
        entry
        for entry in trace
        if entry.get("node_id") == "task_create" and entry.get("validation_errors")
    )
    assert failed_node["node_id"] == "task_create"
    assert "task_init" in failed_node["resolved_tool_names"]


async def test_prompt_echo_worker_run_keeps_clean_trace_without_artifacts(
    tmp_path: Path,
) -> None:
    """Prompt echo models must not pollute state or synthesize artifacts."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    agent._call_llm = PromptEchoScript()  # type: ignore[method-assign]

    with pytest.raises(NodeExecutionError, match="task_create failed runtime validation"):
        await agent.run(
            "Please create a small note taking app with a scheduler. Use Python for "
            "the backend and make the frontend a webapp. Create the project files in "
            "the workspace and run a simple verification command if possible."
        )

    snapshot = agent.loop.get_state_snapshot()
    task_tree_text = snapshot["task_tree_text"]
    transcript = agent.loop.get_transcript_text()
    trace = agent.loop.get_execution_trace()

    assert not (tmp_path / "backend.py").exists()
    assert not (tmp_path / "scheduler.py").exists()
    assert not (tmp_path / "webapp" / "index.html").exists()
    assert "Based on the external user request above" not in transcript
    assert "Based on the external user request above" not in task_tree_text
    assert "Context Enhanced Query:" not in task_tree_text
    failed_node = next(
        entry
        for entry in trace
        if entry.get("node_id") == "task_create" and entry.get("validation_errors")
    )
    assert failed_node["node_id"] == "task_create"
    assert "task_init" in failed_node["resolved_tool_names"]


async def test_streaming_prompt_echo_worker_run_keeps_notebook_state_clean(
    tmp_path: Path,
) -> None:
    """Streaming notebook path must be robust to prompt-echo model output."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    agent._call_llm = StreamingPromptEchoScript()  # type: ignore[method-assign]

    stream = await agent.run(
        "Please create a small note taking app with a scheduler. Use Python for "
        "the backend and make the frontend a webapp. Create the project files in "
        "the workspace and run a simple verification command if possible.",
        stream=True,
    )
    with pytest.raises(NodeExecutionError, match="task_create failed runtime validation"):
        async for _ in stream:
            pass

    snapshot = agent.loop.get_state_snapshot()
    task_tree_text = snapshot["task_tree_text"]
    transcript = agent.loop.get_transcript_text()
    trace = agent.loop.get_execution_trace()

    assert not (tmp_path / "backend.py").exists()
    assert not (tmp_path / "scheduler.py").exists()
    assert not (tmp_path / "webapp" / "index.html").exists()
    assert "Based on the external user request above" not in transcript
    assert "Based on the external user request above" not in task_tree_text
    assert "Context Enhanced Query:" not in task_tree_text
    failed_node = next(
        entry
        for entry in trace
        if entry.get("node_id") == "task_create" and entry.get("validation_errors")
    )
    assert failed_node["node_id"] == "task_create"
    assert "task_init" in failed_node["resolved_tool_names"]
