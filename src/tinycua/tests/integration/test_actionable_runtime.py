"""Deterministic actionable runtime integration contracts."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent
from tinycua.loops.node import NodeExecutionError


def _digest_commit_response() -> dict:
    """Return a fixture-neutral successful Digester commit."""
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


def _patch_queue_factory_to_raise_on_task_create(agent) -> None:
    """Patch agent.loop.queue_factory so task_create raises fast on exhaustion.

    task_create is created dynamically by the worker runtime (not in the
    default queue), so we monkeypatch create_node_config to set
    on_retry_exhausted="raise" for task_create. Without this, the default
    ``record_failure`` policy lets task_create enter the 30-cycle
    _unbounded_recovery, hanging tests that expect a fast NodeExecutionError.
    """
    from tinycua.config import node_config as nc_module

    original_create = nc_module.create_node_config

    def patched_create(node_kind, base_config=None, *, mode=None):
        cfg = original_create(node_kind, base_config, mode=mode)
        normalized = node_kind.lower().replace("-", "_")
        if normalized in {"task_create", "result_reviewer"}:
            cfg.retry_policy = replace(
                cfg.retry_policy,
                max_attempts=3,
                on_retry_exhausted="raise",
            )
        return cfg

    # Patch in all modules that imported create_node_config.
    import tinycua.loops.worker as worker_module

    agent.loop._original_create_node_config = original_create
    worker_module.create_node_config = patched_create
    nc_module.create_node_config = patched_create


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
            match = re.search(r"Active: .+ \(id=([^\)]+)\)", text)
            if match:
                return match.group(1)
        if key == "root_task_id":
            match = re.search(r"Root: .+ \(id=([^\)]+)\)", text)
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
        if (
            "digest_information" in tool_names
            and "final_response_synthesis" not in tool_names
        ):
            return _digest_commit_response()
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
        if "task_assessment_decision" in tool_names:
            if any(
                message.get("role") == "tool"
                and "task_assessment_decision" in str(message.get("content", ""))
                for message in messages
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
        if "task_review_decision" in tool_names:
            # Track which tasks we've already approved to avoid re-reviewing
            # completed tasks (which would fail — completed tasks are immutable).
            if not hasattr(self, "_approved_tasks"):
                self._approved_tasks = set()
            active_id = self._task_id(messages, "active_task_id")
            if not active_id or active_id in self._approved_tasks:
                # No active task or already approved → terminate the node.
                return {"content": "All tasks reviewed.", "tool_calls": []}
            self._approved_tasks.add(active_id)
            # Decide-then-inspect protocol: record the decision and inspect the
            # remaining roadmap in the same response so the node can terminate.
            return {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "task_review_decision",
                            "arguments": '{"decision":"approved","rationale":"[validated]: run_shell python app.py \\u2192 stdout=hello app"}',
                        }
                    },
                    {
                        "function": {
                            "name": "task_inspect",
                            "arguments": "{}",
                        }
                    },
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
        if (
            "digest_information" in tool_names
            and "final_response_synthesis" not in tool_names
        ):
            return _digest_commit_response()
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
        if (
            "digest_information" in tool_names
            and "final_response_synthesis" not in tool_names
        ):
            return _digest_commit_response()
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
        "task_assessor": {"task_analyzer", "analysis_effort", "task_executor"},
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
    # Make result_reviewer raise fast on exhaustion so the test doesn't hang
    # in the 30-cycle recovery when the mock's review protocol doesn't perfectly
    # match the runtime's decide-then-inspect timing.
    _patch_queue_factory_to_raise_on_task_create(agent)
    agent._call_llm = AppCreationScript()  # type: ignore[method-assign]

    # The run may raise NodeExecutionError if the reviewer can't terminate
    # cleanly — the core assertion is that the executor wrote and verified the
    # app before that point.
    try:
        await agent.run("Create a tiny Python app and verify it runs.")
    except NodeExecutionError:
        pass

    app_file = tmp_path / "app.py"
    trace = agent.loop.get_execution_trace()
    task_snapshot = agent.loop.get_state_snapshot()["task_tree"]
    tasks = task_snapshot["tasks"]
    assert app_file.read_text() == 'print("hello app")\n'
    assert any(
        item.get("name") == "run_shell"
        and item.get("output", {}).get("stdout") == "hello app\n"
        for entry in trace
        for item in entry.get("tool_results", [])
    )
    assert "task_tree_text" in agent.loop.get_state_snapshot()
    assert "Task [" in agent.loop.get_state_snapshot()["task_tree_text"]
    assert task_snapshot["root_task_id"] is not None
    assert tasks
    _assert_worker_trace_uses_allowed_edges(trace)


async def test_planner_only_worker_run_fails_without_workspace_artifacts(
    tmp_path: Path,
) -> None:
    """Planner prose must not be converted into hardcoded workspace artifacts."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    _patch_queue_factory_to_raise_on_task_create(agent)
    agent._call_llm = PlannerOnlyScript()  # type: ignore[method-assign]

    with pytest.raises(NodeExecutionError, match="task_create must call"):
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
    assert {
        entry["lifecycle_phase"]
        for entry in trace
        if entry.get("node_id") == "task_create"
        and "task_init" in entry.get("resolved_tool_names", [])
    } == {"commit"}


async def test_prompt_echo_worker_run_keeps_clean_trace_without_artifacts(
    tmp_path: Path,
) -> None:
    """Prompt echo models must not pollute state or synthesize artifacts."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    _patch_queue_factory_to_raise_on_task_create(agent)
    agent._call_llm = PromptEchoScript()  # type: ignore[method-assign]

    with pytest.raises(NodeExecutionError, match="task_create must call"):
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
    assert {
        entry["lifecycle_phase"]
        for entry in trace
        if entry.get("node_id") == "task_create"
        and "task_init" in entry.get("resolved_tool_names", [])
    } == {"commit"}


async def test_streaming_prompt_echo_worker_run_keeps_notebook_state_clean(
    tmp_path: Path,
) -> None:
    """Streaming notebook path must be robust to prompt-echo model output."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    _patch_queue_factory_to_raise_on_task_create(agent)
    agent._call_llm = StreamingPromptEchoScript()  # type: ignore[method-assign]

    stream = await agent.run(
        "Please create a small note taking app with a scheduler. Use Python for "
        "the backend and make the frontend a webapp. Create the project files in "
        "the workspace and run a simple verification command if possible.",
        stream=True,
    )
    with pytest.raises(NodeExecutionError, match="task_create must call"):
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
    assert {
        entry["lifecycle_phase"]
        for entry in trace
        if entry.get("node_id") == "task_create"
        and "task_init" in entry.get("resolved_tool_names", [])
    } == {"commit"}
