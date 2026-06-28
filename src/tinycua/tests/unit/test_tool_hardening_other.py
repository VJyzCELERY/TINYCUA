"""Unit tests for Milestone 6 Stream D — tool hardening (other tools)."""

from __future__ import annotations


from tinycua.agent.tools.native.tool_result import ToolResult
from tinycua.tools.task_tools import TaskReviewDecisionTool, TaskStateStore
from tinycua.tools.todo_tools import TodoWriteTool


class TestReviewDecisionRequired:
    """TaskReviewDecisionTool must not default to approve."""

    def test_no_decision_returns_error(self):
        tool = TaskReviewDecisionTool()
        tool.bind_task_store(TaskStateStore())
        result = tool()
        assert result["success"] is False
        assert "required" in result["error"].lower()


class TestTodoRealOps:
    """todo_tools supports update-in-place and delete."""

    def test_todo_append(self):
        tool = TodoWriteTool()
        tool.bind_todo_store([])
        result = tool(descriptions=["task A", "task B"])
        assert len(result) == 2
        assert result[0]["description"] == "task A"
        assert result[0]["status"] == "pending"

    def test_todo_mark_done(self):
        tool = TodoWriteTool()
        store = []
        tool.bind_todo_store(store)
        tool(descriptions=["task A"])
        result = tool(done_index=0)
        assert result[0]["status"] == "done"
        assert result[0]["done"] is True

    def test_todo_update_in_place(self):
        tool = TodoWriteTool()
        store = []
        tool.bind_todo_store(store)
        tool(descriptions=["old description"])
        result = tool(update_index=0, update_description="new description")
        assert result[0]["description"] == "new description"

    def test_todo_update_status(self):
        tool = TodoWriteTool()
        store = []
        tool.bind_todo_store(store)
        tool(descriptions=["task A"])
        result = tool(update_index=0, update_status="in_progress")
        assert result[0]["status"] == "in_progress"
        assert result[0]["done"] is False

    def test_todo_delete(self):
        tool = TodoWriteTool()
        store = []
        tool.bind_todo_store(store)
        tool(descriptions=["task A", "task B"])
        result = tool(delete_index=0)
        assert len(result) == 1
        assert result[0]["description"] == "task B"

    def test_todo_update_out_of_range_no_crash(self):
        tool = TodoWriteTool()
        store = []
        tool.bind_todo_store(store)
        tool(descriptions=["task A"])
        # Should not crash — just no-op
        result = tool(update_index=99, update_description="x")
        assert result[0]["description"] == "task A"


class TestToolResultEnvelope:
    """ToolResult dataclass has the correct shape."""

    def test_success_result(self):
        r = ToolResult(success=True, output="hello")
        assert r.success is True
        assert r.output == "hello"
        assert r.error is None
        assert r.metadata == {}

    def test_error_result(self):
        r = ToolResult(success=False, error="not found")
        assert r.success is False
        assert r.output is None
        assert r.error == "not found"

    def test_to_dict(self):
        r = ToolResult(success=True, output="x", metadata={"url": "http://example.com"})
        d = r.to_dict()
        assert d["success"] is True
        assert d["output"] == "x"
        assert d["metadata"]["url"] == "http://example.com"


class TestPythonExecTimeoutRejection:
    """python_exec rejects oversized timeouts with a clear error."""

    def test_reject_oversized_timeout(self):
        from tinycua.agent.tools.native.python_exec import run_python

        result = run_python("print('hello')", timeout=60)
        assert result["error"] is not None
        assert "exceeds maximum" in result["error"]
        assert result["exit_code"] == -1

    def test_accept_valid_timeout(self):
        from tinycua.agent.tools.native.python_exec import run_python

        result = run_python("print('hello')", timeout=10)
        # Should execute (not rejected)
        assert result["error"] is None
        assert "hello" in result["stdout"]
