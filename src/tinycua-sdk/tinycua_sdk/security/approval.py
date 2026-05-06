"""Approval workflow for tool execution guardrails."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ApprovalWorkflow(ABC):
    """Abstract base for approval workflows."""

    @abstractmethod
    async def request_approval(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Request approval for a tool call."""


class DefaultApprovalWorkflow(ApprovalWorkflow):
    """Always-approve implementation."""

    async def request_approval(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Request approval — always returns approved."""
        return {"approved": True}
