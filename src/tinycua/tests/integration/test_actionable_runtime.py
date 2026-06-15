"""Deterministic actionable runtime integration contracts."""

from __future__ import annotations

from pathlib import Path

from tinycua.config.session_config import SessionConfig
from tinycua.factory import create_tinycua_agent


class AppCreationScript:
    """Scripted model that uses real workspace tools to create an app."""

    async def __call__(self, messages, tools, stream: bool = False):  # noqa: ANN001, ARG002
        tool_names = {tool.name for tool in tools}
        if "select_query_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "select_query_route", "arguments": '{"route":"worker"}'}}
                ],
            }
        if "select_worker_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "select_worker_route", "arguments": '{"route":"task_creation"}'}}
                ],
            }
        if "digest_information" in tool_names:
            return {"content": '{"context_summary":"Create a tiny Python app"}', "tool_calls": []}
        if "task_init" in tool_names:
            return {"content": "Create a tiny Python app", "tool_calls": []}
        if "task_decompose" in tool_names:
            return {"content": "Write app.py\nRun app verification", "tool_calls": []}
        if {"write_file", "run_shell"} <= tool_names:
            if any(message.get("role") == "tool" for message in messages):
                return {"content": "Created app.py and verified it runs.", "tool_calls": []}
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
                    {"function": {"name": "select_query_route", "arguments": '{"route":"worker"}'}}
                ],
            }
        if "select_worker_route" in tool_names:
            return {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "select_worker_route", "arguments": '{"route":"task_creation"}'}}
                ],
            }
        return {"content": self.planner_text, "tool_calls": []}


async def test_worker_action_request_writes_file_and_runs_verification(tmp_path: Path) -> None:
    """Worker execution must perform real workspace actions via tools."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    agent._call_llm = AppCreationScript()  # type: ignore[method-assign]

    result = await agent.run("Create a tiny Python app and verify it runs.")

    app_file = tmp_path / "app.py"
    trace = agent.loop.get_execution_trace()
    task_snapshot = agent.loop.get_state_snapshot()["task_tree"]
    assert app_file.read_text() == 'print("hello app")\n'
    assert result.strip()
    assert any(
        item.get("name") == "run_shell" and item.get("output", {}).get("stdout") == "hello app\n"
        for entry in trace
        for item in entry.get("tool_results", [])
    )
    assert "task_tree_text" in agent.loop.get_state_snapshot()
    assert "Task [" in agent.loop.get_state_snapshot()["task_tree_text"]
    assert task_snapshot["root_task_id"] is not None


async def test_planner_only_worker_run_still_creates_workspace_artifacts(
    tmp_path: Path,
) -> None:
    """Notebook path should stay usable even when the model emits planner prose."""
    agent = create_tinycua_agent(session_config=SessionConfig(workspace_dir=tmp_path))
    agent.loop.max_iterations = 9
    agent._call_llm = PlannerOnlyScript()  # type: ignore[method-assign]

    await agent.run(
        "Please create a small note taking app with a scheduler in the workspace."
    )

    snapshot = agent.loop.get_state_snapshot()
    task_tree_text = snapshot["task_tree_text"]
    transcript = agent.loop.get_transcript_text()
    trace = agent.loop.get_execution_trace()

    assert (tmp_path / "backend.py").exists()
    assert (tmp_path / "scheduler.py").exists()
    assert (tmp_path / "webapp" / "index.html").exists()
    assert "note_scheduler_app/" not in task_tree_text
    assert "├── app.py" not in task_tree_text
    assert "I cannot create files" not in transcript
    task_executor = next(entry for entry in trace if entry["node_id"] == "task_executor")
    assert "write_file" in task_executor["resolved_tool_names"]
    assert any(
        item.get("name") == "write_file"
        for item in task_executor.get("tool_results", [])
    )
