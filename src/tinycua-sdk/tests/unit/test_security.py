"""Tests for security module."""

import pytest
from tinycua_sdk.security.permissions import PermissionLevel, PermissionSystem
from tinycua_sdk.security.approval import ApprovalWorkflow, ApprovalRequest


class TestPermissionLevel:
    """Test PermissionLevel enum."""

    def test_permission_level_values(self):
        """Test PermissionLevel has correct values."""
        assert PermissionLevel.SAFE.value == "safe"
        assert PermissionLevel.WARNING.value == "warning"
        assert PermissionLevel.DANGEROUS.value == "dangerous"


class TestPermissionSystem:
    """Test PermissionSystem class."""

    def test_default_permissions_registered(self):
        """Test default permissions are registered."""
        ps = PermissionSystem()
        assert "calculator" in ps._permissions
        assert "shell_execute" in ps._permissions

    def test_safe_tool_allowed(self):
        """Test safe tools are allowed."""
        ps = PermissionSystem()
        assert ps.check_permission("calculator") is True

    def test_unknown_tool_defaults_to_allow(self):
        """Test unknown tools default to allow."""
        ps = PermissionSystem()
        assert ps.check_permission("unknown_tool") is True

    def test_dangerous_tool_not_allowed_without_approval(self):
        """Test dangerous tools require approval."""
        ps = PermissionSystem()
        assert ps.check_permission("shell_execute") is False

    def test_requires_approval_for_dangerous_tools(self):
        """Test dangerous tools require approval."""
        ps = PermissionSystem()
        assert ps.requires_approval("shell_execute") is True
        assert ps.requires_approval("calculator") is False


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
