"""Approval workflow for dangerous operations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class ApprovalRequest:
    """Approval request for dangerous operation."""
    id: str
    tool_name: str
    arguments: dict
    requested_at: datetime
    status: str


class ApprovalWorkflow:
    """Approval workflow for dangerous operations.

    Manages approval requests for tools that require explicit
    authorization before execution.
    """

    def __init__(self):
        """Initialize approval workflow."""
        self._requests: dict[str, ApprovalRequest] = {}

    def request_approval(self, tool_name: str, arguments: dict) -> str:
        """Request approval for dangerous operation.

        Args:
            tool_name: Name of the tool requiring approval.
            arguments: Arguments that will be passed to the tool.

        Returns:
            Request ID for tracking the approval request.
        """
        request_id = str(uuid.uuid4())
        request = ApprovalRequest(
            id=request_id,
            tool_name=tool_name,
            arguments=arguments,
            requested_at=datetime.now(),
            status="pending",
        )
        self._requests[request_id] = request
        return request_id

    def approve(self, request_id: str) -> bool:
        """Approve a request.

        Args:
            request_id: ID of the request to approve.

        Returns:
            True if approval succeeded, False if request not found.
        """
        request = self._requests.get(request_id)
        if not request:
            return False
        request.status = "approved"
        return True

    def deny(self, request_id: str) -> bool:
        """Deny a request.

        Args:
            request_id: ID of the request to deny.

        Returns:
            True if denial succeeded, False if request not found.
        """
        request = self._requests.get(request_id)
        if not request:
            return False
        request.status = "denied"
        return True

    def get_status(self, request_id: str) -> Optional[str]:
        """Get request status.

        Args:
            request_id: ID of the request to check.

        Returns:
            Status string if found, None otherwise.
        """
        request = self._requests.get(request_id)
        return request.status if request else None

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get the full request object.

        Args:
            request_id: ID of the request to retrieve.

        Returns:
            ApprovalRequest if found, None otherwise.
        """
        return self._requests.get(request_id)

    def list_pending_requests(self) -> list[ApprovalRequest]:
        """List all pending approval requests.

        Returns:
            List of pending approval requests.
        """
        return [r for r in self._requests.values() if r.status == "pending"]
