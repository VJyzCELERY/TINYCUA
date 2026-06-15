"""Concrete worker-mode task nodes."""

from __future__ import annotations

from tinycua.loops.node import ProcessNode


class TinyCUATaskAnalyzerNode(ProcessNode):
    """Analyze or refine task structure."""


class TinyCUATaskAssessorNode(ProcessNode):
    """Assess task readiness and progress."""


class TinyCUATaskExecutorNode(ProcessNode):
    """Execute or dispatch task work."""


class TinyCUAResultReviewerNode(ProcessNode):
    """Review task execution results."""


class TinyCUAResultAggregationNode(ProcessNode):
    """Aggregate task results into worker output."""


class TinyCUAAnalysisEffortNode(ProcessNode):
    """Determine analysis effort for worker-mode planning."""
