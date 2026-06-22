"""Unit tests for reviewer as general sanity-checker (Milestone 8, FR-056)."""

from __future__ import annotations

from tinycua.config.node_config import create_node_config
from tinycua.loops.task_nodes import (
    TinyCUAResultReviewerNode,
    _RESULT_REVIEWER_CONTINUATION,
    _RESULT_REVIEWER_INSTRUCTION,
)
from tinycua.models.session import Session


class TestReviewerSanityCheckerInstruction:
    """FR-056: the reviewer instruction includes general sanity-checker responsibility."""

    def test_instruction_mentions_duplicate_content(self):
        lowered = _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "duplicate" in lowered or "repeated" in lowered

    def test_instruction_mentions_hallucination(self):
        lowered = _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "hallucin" in lowered or "fabricat" in lowered

    def test_instruction_mentions_structural_inconsistency(self):
        lowered = _RESULT_REVIEWER_INSTRUCTION.lower()
        assert "structural" in lowered or "inconsisten" in lowered

    def test_instruction_is_generic_not_artifact_specific(self):
        """The sanity-checker responsibility is generic across artifact types."""
        lowered = _RESULT_REVIEWER_INSTRUCTION.lower()
        # Should NOT hardcode "report structure" or "markdown sections" rules.
        assert "report structure" not in lowered
        assert "markdown sections" not in lowered


class TestReviewerSanityCheckerToolPrompt:
    """FR-056: build_tool_system_prompt adds dedup guidance when run_shell is available."""

    def test_dedup_guidance_when_run_shell_available(self):
        session = Session()
        node = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        node.session = session  # noqa: SLF001

        # Build a mock tool list that includes run_shell.
        class _FakeTool:
            def __init__(self, name: str) -> None:
                self.name = name

        tools = [_FakeTool("run_shell"), _FakeTool("read_file"), _FakeTool("task_review_decision")]
        prompt = node.build_tool_system_prompt(tools)
        lowered = prompt.lower()
        # FR-056: when run_shell is available, the prompt should suggest
        # using grep/wc/sort|uniq to detect duplicate content.
        assert "grep" in lowered or "uniq" in lowered or "wc" in lowered

    def test_no_dedup_guidance_when_run_shell_absent(self):
        session = Session()
        node = TinyCUAResultReviewerNode(
            node_id="result_reviewer",
            config=create_node_config("result_reviewer"),
        )
        node.session = session  # noqa: SLF001

        class _FakeTool:
            def __init__(self, name: str) -> None:
                self.name = name

        tools = [_FakeTool("read_file"), _FakeTool("task_review_decision")]
        prompt = node.build_tool_system_prompt(tools)
        # Without run_shell, the dedup guidance should not reference shell commands.
        # (It's fine to still mention duplicate detection conceptually, but
        # no grep/wc/sort|uniq guidance.)
        lowered = prompt.lower()
        assert "grep -c" not in lowered