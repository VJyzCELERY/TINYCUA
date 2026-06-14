"""Cross-cutting concern verification for architecture paths.

Validates propagation, dedupe, tool scoping, retry, and output validation
as part of path execution. Each PathExecutor includes a
CrossCuttingCollector that hooks into the node execution lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NodeInvocationRecord:
    """Record of a single node invocation for cross-cutting analysis.

    Attributes:
        node_id: The node that was invoked.
        expected_tools: Tools the node should have access to.
        actual_tools_invoked: Tools actually invoked during execution.
        output_valid: Whether output validation passed.
        retry_count: Number of retries for this invocation.
        session_created: Whether a new session was created.
    """

    node_id: str
    expected_tools: list[str] = field(default_factory=list)
    actual_tools_invoked: list[str] = field(default_factory=list)
    output_valid: bool = True
    retry_count: int = 0
    session_created: bool = False


@dataclass
class CrossCuttingReport:
    """Aggregated cross-cutting concern report for a path.

    Attributes:
        propagation_events: Context propagation events observed.
        dedupe_events: Deduplication events observed.
        tool_scope_violations: Tools invoked that weren't in the policy.
        retry_events: Retry events observed.
        validation_events: Output validation events.
        node_records: Per-node invocation records.
    """

    propagation_events: list[dict[str, Any]] = field(default_factory=list)
    dedupe_events: list[dict[str, Any]] = field(default_factory=list)
    tool_scope_violations: list[dict[str, Any]] = field(default_factory=list)
    retry_events: list[dict[str, Any]] = field(default_factory=list)
    validation_events: list[dict[str, Any]] = field(default_factory=list)
    node_records: list[NodeInvocationRecord] = field(default_factory=list)


class CrossCuttingCollector:
    """Collects cross-cutting concern data during path execution.

    Hooks into node execution lifecycle to record tool invocations,
    context propagation, deduplication, retry behavior, and output
    validation outcomes.
    """

    def __init__(self) -> None:
        """Initialize the collector."""
        self._report = CrossCuttingReport()
        self._current_node: str | None = None
        self._current_record: NodeInvocationRecord | None = None

    @property
    def report(self) -> CrossCuttingReport:
        """Return the collected cross-cutting report."""
        return self._report

    def on_before_node(self, node_id: str, expected_tools: list[str]) -> None:
        """Record before-node execution event.

        Args:
            node_id: The node about to execute.
            expected_tools: Tools the node should have access to.
        """
        self._current_node = node_id
        self._current_record = NodeInvocationRecord(
            node_id=node_id,
            expected_tools=expected_tools,
        )

    def on_after_node(
        self,
        node_id: str,
        tools_invoked: list[str] | None = None,
        output_valid: bool = True,
        retry_count: int = 0,
    ) -> None:
        """Record after-node execution event.

        Args:
            node_id: The node that just executed.
            tools_invoked: Tools actually invoked during execution.
            output_valid: Whether output validation passed.
            retry_count: Number of retries that occurred.
        """
        record = self._current_record
        if record is not None and record.node_id == node_id:
            record.actual_tools_invoked = tools_invoked or []
            record.output_valid = output_valid
            record.retry_count = retry_count
            self._report.node_records.append(record)

            # Check tool scope violations
            if record.expected_tools:
                for tool in record.actual_tools_invoked:
                    if tool not in record.expected_tools:
                        self._report.tool_scope_violations.append(
                            {
                                "node_id": node_id,
                                "tool": tool,
                                "expected": record.expected_tools,
                            }
                        )

            # Record retry events
            if retry_count > 0:
                self._report.retry_events.append(
                    {
                        "node_id": node_id,
                        "retry_count": retry_count,
                    }
                )

            # Record validation events
            self._report.validation_events.append(
                {
                    "node_id": node_id,
                    "valid": output_valid,
                }
            )

        self._current_node = None
        self._current_record = None

    def on_propagation(
        self,
        source_node: str,
        target_node: str,
        context_type: str,
    ) -> None:
        """Record a context propagation event.

        Args:
            source_node: The node propagating context.
            target_node: The node receiving context.
            context_type: Type of context propagated.
        """
        self._report.propagation_events.append(
            {
                "source": source_node,
                "target": target_node,
                "context_type": context_type,
            }
        )

    def on_dedupe(
        self,
        node_id: str,
        duplicates_removed: int,
    ) -> None:
        """Record a deduplication event.

        Args:
            node_id: The node where deduplication occurred.
            duplicates_removed: Number of duplicates removed.
        """
        if duplicates_removed > 0:
            self._report.dedupe_events.append(
                {
                    "node_id": node_id,
                    "duplicates_removed": duplicates_removed,
                }
            )

    def validate(self) -> list[str]:
        """Validate collected cross-cutting data.

        Returns:
            List of validation error messages (empty if all valid).
        """
        errors: list[str] = []

        # Check for tool scope violations
        if self._report.tool_scope_violations:
            for violation in self._report.tool_scope_violations:
                errors.append(
                    f"Tool scope violation: node '{violation['node_id']}' "
                    f"invoked tool '{violation['tool']}' which is not in "
                    f"expected tools {violation['expected']}"
                )

        # Check that all nodes had output validation
        for record in self._report.node_records:
            if not record.output_valid:
                errors.append(f"Output validation failed for node '{record.node_id}'")

        return errors
