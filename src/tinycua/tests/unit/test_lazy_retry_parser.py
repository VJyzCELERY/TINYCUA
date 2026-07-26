"""Unit tests for the lazy-retry markdown parser (FR-087..FR-093).

The parser extracts section fields from the markdown synthesis response. v1
templates cover four nodes: result_reviewer, task_executor, query_analyst,
worker. The parser MUST return None on missing sections, malformed enums, or
unparseable output so the caller falls back to standard recovery.

These tests are written BEFORE the implementation (TDD RED phase). The module
under test (`tinycua.loops.lazy_templates`) does not exist yet — these tests
are expected to fail on import until it is implemented.
"""

from __future__ import annotations

import pytest

# Import targets for the implementation. Module does not exist yet (RED).
from tinycua.loops.lazy_templates import (  # noqa: E402
    LAZY_TEMPLATES,
    parse_lazy_markdown,
)


class TestRegistry:
    """The v1 registry maps the four in-scope node IDs to a target tool."""

    def test_registry_has_four_v1_nodes(self):
        assert set(LAZY_TEMPLATES.keys()) == {
            "result_reviewer",
            "task_executor",
            "query_analyst",
            "worker",
        }

    @pytest.mark.parametrize(
        ("node_id", "expected_tool"),
        [
            ("result_reviewer", "task_review_decision"),
            ("task_executor", "task_result_update"),
            ("query_analyst", "select_query_route"),
            ("worker", "select_worker_route"),
        ],
    )
    def test_registry_maps_node_to_state_tool(self, node_id, expected_tool):
        target_tool, _template = LAZY_TEMPLATES[node_id]
        assert target_tool == expected_tool


class TestResultReviewerTemplate:
    """Parse valid/missing/malformed markdown for the reviewer template."""

    def test_valid_markdown_yields_decision_summary_and_task_id(self):
        md = (
            "# Review Assessment : approved\n"
            "# Review Summary\n"
            "The executor's evidence verifies the task.\n"
            "# Task ID\n"
            "abc-123\n"
        )
        parsed = parse_lazy_markdown("result_reviewer", md)
        assert parsed is not None
        assert parsed["decision"] == "approved"
        assert "verifies" in parsed["rationale"]
        assert parsed["task_id"] == "abc-123"

    @pytest.mark.parametrize(
        "decision",
        [
            "approved",
            "needs_revision",
            "replan",
            "postpone_siblings",
            "postpone_final",
            "compromise",
        ],
    )
    def test_model_facing_decisions_are_accepted(self, decision):
        md = (
            f"# Review Assessment : {decision}\n"
            "# Review Summary\n"
            "summary text\n"
            "# Task ID\n"
            "t-1\n"
        )
        parsed = parse_lazy_markdown("result_reviewer", md)
        assert parsed is not None
        assert parsed["decision"] == decision

    def test_legacy_rejected_is_not_model_facing(self):
        md = (
            "# Review Assessment : rejected\n"
            "# Review Summary\nlegacy\n"
            "# Task ID\nt-1\n"
        )

        assert parse_lazy_markdown("result_reviewer", md) is None

    def test_missing_section_returns_none(self):
        md = "# Review Assessment : approved\n"
        parsed = parse_lazy_markdown("result_reviewer", md)
        assert parsed is None

    def test_malformed_decision_enum_returns_none(self):
        md = (
            "# Review Assessment : maybe\n"
            "# Review Summary\n"
            "summary\n"
            "# Task ID\n"
            "t-1\n"
        )
        parsed = parse_lazy_markdown("result_reviewer", md)
        assert parsed is None

    def test_extra_text_outside_template_still_parses(self):
        """We extract sections only — preamble prose must not break parsing."""
        md = (
            "Here is my summary.\n\n"
            "# Review Assessment : needs_revision\n"
            "# Review Summary\n"
            "Failed to verify.\n"
            "# Task ID\n"
            "t-1\n"
        )
        parsed = parse_lazy_markdown("result_reviewer", md)
        assert parsed is not None
        assert parsed["decision"] == "needs_revision"

    def test_empty_summary_returns_none(self):
        md = (
            "# Review Assessment : approved\n"
            "# Review Summary\n"
            "\n"
            "# Task ID\n"
            "t-1\n"
        )
        parsed = parse_lazy_markdown("result_reviewer", md)
        assert parsed is None


class TestTaskExecutorTemplate:
    """Parse valid/missing/malformed markdown for the executor template."""

    def test_valid_markdown_yields_status_summary_and_task_id(self):
        md = (
            "# Status : completed\n"
            "# Summary\n"
            "Implemented the feature and added tests.\n"
            "# Task ID\n"
            "t-2\n"
        )
        parsed = parse_lazy_markdown("task_executor", md)
        assert parsed is not None
        assert parsed["success"] is True
        assert "Implemented" in parsed["content"]
        assert parsed["task_id"] == "t-2"

    def test_failed_status_maps_to_success_false(self):
        md = (
            "# Status : failed\n"
            "# Summary\n"
            "Blocked by missing dependency.\n"
            "# Task ID\n"
            "t-3\n"
        )
        parsed = parse_lazy_markdown("task_executor", md)
        assert parsed is not None
        assert parsed["success"] is False

    def test_replan_status_returns_none(self):
        """v1 executor template maps completed→success=true, failed→false.
        'replan' is a reviewer concept, not an executor outcome — reject."""
        md = (
            "# Status : replan\n"
            "# Summary\n"
            "need to replan\n"
            "# Task ID\n"
            "t-3\n"
        )
        parsed = parse_lazy_markdown("task_executor", md)
        assert parsed is None

    def test_missing_summary_returns_none(self):
        md = (
            "# Status : completed\n"
            "# Task ID\n"
            "t-2\n"
        )
        parsed = parse_lazy_markdown("task_executor", md)
        assert parsed is None


class TestRouteTemplate:
    """Parse valid/missing/malformed markdown for query_analyst / worker."""

    def test_query_analyst_valid_route(self):
        md = (
            "# Route : worker\n"
            "# Rationale\n"
            "This needs task decomposition.\n"
        )
        parsed = parse_lazy_markdown("query_analyst", md)
        assert parsed is not None
        assert parsed["route"] == "worker"

    def test_worker_valid_route(self):
        md = (
            "# Route : proceed_execution\n"
            "# Rationale\n"
            "Tasks are ready to execute.\n"
        )
        parsed = parse_lazy_markdown("worker", md)
        assert parsed is not None
        assert parsed["route"] == "proceed_execution"

    def test_route_not_in_allowed_labels_returns_none(self):
        md = (
            "# Route : bogus_route\n"
            "# Rationale\n"
            "reason\n"
        )
        parsed = parse_lazy_markdown("query_analyst", md, allowed_labels={"worker", "passthrough"})
        assert parsed is None

    def test_route_validated_against_allowed_labels(self):
        md = (
            "# Route : passthrough\n"
            "# Rationale\n"
            "simple\n"
        )
        parsed = parse_lazy_markdown("query_analyst", md, allowed_labels={"worker", "passthrough"})
        assert parsed is not None
        assert parsed["route"] == "passthrough"

    def test_missing_rationale_returns_none(self):
        md = "# Route : worker\n"
        parsed = parse_lazy_markdown("query_analyst", md)
        assert parsed is None

    def test_missing_route_returns_none(self):
        md = "# Rationale\nreason\n"
        parsed = parse_lazy_markdown("query_analyst", md)
        assert parsed is None


class TestUnknownNodeReturnsNone:
    """Nodes without a v1 template (task_analyzer, task_create) return None."""

    def test_task_analyzer_returns_none(self):
        md = "# Status : completed\n"
        parsed = parse_lazy_markdown("task_analyzer", md)
        assert parsed is None

    def test_task_create_returns_none(self):
        md = "# Status : completed\n"
        parsed = parse_lazy_markdown("task_create", md)
        assert parsed is None

    def test_empty_markdown_returns_none(self):
        parsed = parse_lazy_markdown("result_reviewer", "")
        assert parsed is None

    def test_whitespace_markdown_returns_none(self):
        parsed = parse_lazy_markdown("result_reviewer", "   \n\n  ")
        assert parsed is None
