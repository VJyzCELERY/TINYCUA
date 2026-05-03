"""Tests for security module."""

import pytest
from tinycua_sdk.security.approval import ApprovalWorkflow, ApprovalRequest


class TestApprovalWorkflow:
    """Test ApprovalWorkflow class."""

    def test_request_approval_creates_request(self):
        """Test requesting approval creates a request."""
        workflow = ApprovalWorkflow()
        request_id = workflow.request_approval("shell_execute", {"cmd": "ls"})
        assert request_id is not None
        assert workflow.get_status(request_id) == "pending"

    def test_approve_request(self):
        """Test approving a request."""
        workflow = ApprovalWorkflow()
        request_id = workflow.request_approval("shell_execute", {"cmd": "ls"})
        result = workflow.approve(request_id)
        assert result is True
        assert workflow.get_status(request_id) == "approved"

    def test_deny_request(self):
        """Test denying a request."""
        workflow = ApprovalWorkflow()
        request_id = workflow.request_approval("shell_execute", {"cmd": "ls"})
        result = workflow.deny(request_id)
        assert result is True
        assert workflow.get_status(request_id) == "denied"

    def test_approve_invalid_request_returns_false(self):
        """Test approving invalid request returns False."""
        workflow = ApprovalWorkflow()
        result = workflow.approve("invalid-id")
        assert result is False
