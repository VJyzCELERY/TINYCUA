"""Tests for ToolExecutor."""

import pytest

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.security.approval import ApprovalWorkflow


class MockApprovalWorkflow(ApprovalWorkflow):
    def __init__(self, return_value=None):
        self._return_value = return_value or {"approved": True}

    async def request_approval(self, tool_name, arguments):
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
