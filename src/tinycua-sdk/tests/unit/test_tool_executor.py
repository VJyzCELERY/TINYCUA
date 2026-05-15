"""Tests for ToolExecutor."""

import pytest

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.security.approval import ApprovalWorkflow


class MockApprovalWorkflow(ApprovalWorkflow):
    def __init__(self, return_value=None):
        self._return_value = return_value or {"approved": True}
        self.calls = []

    async def request_approval(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return self._return_value


class TestToolExecutor:
    """Test ToolExecutor permission/approval/execution paths."""

    @pytest.mark.asyncio
    async def test_execute_allow_path(self):
        @tool
        def add(a: int, b: int) -> int:
            return a + b

        agent = Agent(llm_model=LanguageModel())
        result = await ToolExecutor.execute(add, {"a": 2, "b": 3}, agent)
        assert result == 5

    @pytest.mark.asyncio
    async def test_execute_deny_path(self):
        @tool
        def delete_file(path: str) -> str:
            return f"Deleted {path}"

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"delete_file": "deny"},
        )
        result = await ToolExecutor.execute(delete_file, {"path": "/etc/passwd"}, agent)
        assert isinstance(result, dict)
        assert "error" in result
        assert "denied" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_ask_approved_path(self):
        @tool
        def risky_op(param: str) -> str:
            return f"Executed {param}"

        mock_workflow = MockApprovalWorkflow(return_value={"approved": True})

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"risky_op": "ask"},
            approval_workflow=mock_workflow,
        )
        result = await ToolExecutor.execute(risky_op, {"param": "test"}, agent)
        assert result == "Executed test"

    @pytest.mark.asyncio
    async def test_execute_ask_denied_path(self):
        @tool
        def risky_op(param: str) -> str:
            return f"Executed {param}"

        mock_workflow = MockApprovalWorkflow(
            return_value={"approved": False, "reason": "Not allowed"}
        )

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"risky_op": "ask"},
            approval_workflow=mock_workflow,
        )
        result = await ToolExecutor.execute(risky_op, {"param": "test"}, agent)
        assert result == {"approved": False, "reason": "Not allowed"}

    @pytest.mark.asyncio
    async def test_execute_default_allow_when_no_permission_set(self):
        @tool
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        agent = Agent(llm_model=LanguageModel())
        result = await ToolExecutor.execute(greet, {"name": "World"}, agent)
        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_execute_ask_without_workflow_denies(self):
        @tool
        def simple_tool() -> str:
            return "done"

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"simple_tool": "ask"},
            approval_workflow=None,
        )
        result = await ToolExecutor.execute(simple_tool, {}, agent)
        assert isinstance(result, dict)
        assert "error" in result
        assert "approval_workflow" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_invalid_permission_fails_closed(self):
        """Invalid permission values are treated as deny (fail-closed)."""
        invoked = False

        @tool
        def my_tool() -> str:
            nonlocal invoked
            invoked = True
            return "done"

        agent = Agent(llm_model=LanguageModel())
        agent.tool_permissions["my_tool"] = "denny"
        result = await ToolExecutor.execute(my_tool, {}, agent)
        assert isinstance(result, dict)
        assert "error" in result
        assert invoked is False

    @pytest.mark.asyncio
    async def test_execute_multiple_workflows_all_approved(self):
        """All chained workflows approve and tool executes."""
        workflow1 = MockApprovalWorkflow(return_value={"approved": True})
        workflow2 = MockApprovalWorkflow(return_value={"approved": True})
        workflow3 = MockApprovalWorkflow(return_value={"approved": True})

        @tool
        def safe_tool() -> str:
            return "executed"

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"safe_tool": "ask"},
            approval_workflow=[workflow1, workflow2, workflow3],
        )
        result = await ToolExecutor.execute(safe_tool, {}, agent)
        assert result == "executed"
        assert len(workflow1.calls) == 1
        assert len(workflow2.calls) == 1
        assert len(workflow3.calls) == 1

    @pytest.mark.asyncio
    async def test_execute_chained_workflows_first_denial_wins(self):
        """Chained workflows stop at the first denial and do not invoke tool."""
        workflow1 = MockApprovalWorkflow(return_value={"approved": True})
        workflow2 = MockApprovalWorkflow(
            return_value={"approved": False, "reason": "Blocked by policy"}
        )
        workflow3 = MockApprovalWorkflow(return_value={"approved": True})
        invoked = False

        @tool
        def risky_tool() -> str:
            nonlocal invoked
            invoked = True
            return "executed"

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"risky_tool": "ask"},
            approval_workflow=[workflow1, workflow2, workflow3],
        )
        result = await ToolExecutor.execute(risky_tool, {}, agent)
        assert result == {"approved": False, "reason": "Blocked by policy"}
        assert invoked is False
        assert len(workflow1.calls) == 1
        assert len(workflow2.calls) == 1
        assert len(workflow3.calls) == 0

    @pytest.mark.asyncio
    async def test_execute_single_workflow_still_works_with_list_normalization(self):
        """A single workflow (non-list) still works with list normalization."""
        workflow = MockApprovalWorkflow(return_value={"approved": True})

        @tool
        def good_tool() -> str:
            return "ok"

        agent = Agent(
            llm_model=LanguageModel(),
            tool_permissions={"good_tool": "ask"},
            approval_workflow=workflow,
        )
        result = await ToolExecutor.execute(good_tool, {}, agent)
        assert result == "ok"
        assert len(workflow.calls) == 1
