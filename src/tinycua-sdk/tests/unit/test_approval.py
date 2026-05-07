"""Tests for ApprovalWorkflow and DefaultApprovalWorkflow."""

import pytest
from tinycua_sdk.security.approval import (
    ApprovalWorkflow,
    DefaultApprovalWorkflow,
)


class TestApprovalWorkflowABC:
    """Test ApprovalWorkflow ABC."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            ApprovalWorkflow()


class TestDefaultApprovalWorkflow:
    """Test DefaultApprovalWorkflow."""

    @pytest.mark.asyncio
    async def test_request_approval_returns_approved(self):
        workflow = DefaultApprovalWorkflow()
        result = await workflow.request_approval(
            "any_tool", {"param": "value"}
        )
        assert result == {"approved": True}

    @pytest.mark.asyncio
    async def test_request_approval_always_approves(self):
        workflow = DefaultApprovalWorkflow()
        result1 = await workflow.request_approval("tool_a", {})
        result2 = await workflow.request_approval("tool_b", {"x": 1})
        assert result1 == {"approved": True}
        assert result2 == {"approved": True}
