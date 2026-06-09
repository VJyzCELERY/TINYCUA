"""TinyCUATaskAnalyzerNode — ProcessNode for task analysis with mode-based tool filtering."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tinycua.loops.node import ProcessNode

if TYPE_CHECKING:
    from tinycua.config.node_config import NodeConfigBase
    from tinycua.config.types import LLMResult
    from tinycua.models.node_input import NodeInputLike

logger = logging.getLogger(__name__)

# Tools excluded from initial_analysis mode
_TASK_CREATION_TOOLS = frozenset({"TaskInit", "TaskCreate"})

# Standard analysis tools
_DEFAULT_ANALYSIS_TOOLS: list[str] = [
    "TaskUpdate",
    "TaskComplete",
    "TaskDecompose",
]

# Valid analysis modes
_VALID_MODES = frozenset({"analysis", "initial_analysis", "effort_loop_decomposition"})


class TinyCUATaskAnalyzerNode(ProcessNode):
    """ProcessNode for task analysis with mode-based tool filtering.

    Supports three modes:
    - ``initial_analysis``: Excludes TaskInit/TaskCreate tools (post-task-creation).
    - ``analysis``: Standard analysis mode with all analysis tools.
    - ``effort_loop_decomposition``: Excludes TaskInit/TaskCreate tools, used
      by AnalysisEffortNode during effort-loop passes.

    Attributes:
        node_id: Always "task_analyzer" by default.
        mode: The analysis mode.
        tool_scope: Filtered list of tool names based on mode.
    """

    def __init__(
        self,
        node_id: str = "task_analyzer",
        config: NodeConfigBase | None = None,
        mode: str = "analysis",
    ) -> None:
        """Initialize TaskAnalyzerNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            mode: Analysis mode. "initial_analysis" excludes TaskInit/TaskCreate.
        """
        super().__init__(
            node_id=node_id,
            config=config,  # type: ignore[arg-type]
            instruction=(
                "You are a task analyzer. Analyze the current task state and "
                "determine what actions are needed. Provide clear, structured "
                "analysis of the task and recommended next steps."
            ),
        )
        self.mode = mode
        self.tool_scope = self._resolve_tool_scope(mode)

    def _resolve_tool_scope(self, mode: str) -> list[str]:
        """Resolve tool scope based on analysis mode.

        Args:
            mode: The analysis mode.

        Returns:
            List of tool names available in this mode.

        Raises:
            ValueError: If mode is not a recognized analysis mode.
        """
        if mode not in _VALID_MODES:
            raise ValueError(
                f"Unknown analysis mode: {mode!r}. "
                f"Valid modes: {sorted(_VALID_MODES)}"
            )
        if mode in ("initial_analysis", "effort_loop_decomposition"):
            # Exclude task creation tools — task already exists or is being
            # decomposed by effort-loop passes
            return [
                tool
                for tool in _DEFAULT_ANALYSIS_TOOLS
                if tool not in _TASK_CREATION_TOOLS
            ]
        # Standard analysis mode — all analysis tools
        return list(_DEFAULT_ANALYSIS_TOOLS)

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute task analysis.

        Args:
            input: The node input containing task context.

        Returns:
            The LLM response with task analysis.
        """
        result = super().__call__(input)
        logger.info(
            "node=%s mode=%s analysis_complete content_len=%d",
            self.node_id,
            self.mode,
            len(result.content),
        )
        return result
