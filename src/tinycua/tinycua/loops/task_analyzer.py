"""TinyCUATaskAnalyzerNode — ProcessNode for task analysis with mode-based tool filtering."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tinycua.loops.node import NodeExecutionError, ProcessNode

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

# Valid analysis modes — five modes from the target architecture
_VALID_MODES = frozenset({
    "initial_analysis",
    "recreation",
    "reanalysis",
    "effort_loop_decomposition",
    "local_replan",
})


class TinyCUATaskAnalyzerNode(ProcessNode):
    """ProcessNode for task analysis with mode-based tool filtering.

    Supports five analysis modes:
    - ``initial_analysis``: Excludes TaskInit/TaskCreate tools (post-task-creation).
    - ``recreation``: Includes TaskInit/TaskCreate tools for full task recreation.
    - ``reanalysis``: Excludes TaskInit/TaskCreate tools, reanalyzes existing task.
    - ``effort_loop_decomposition``: Excludes TaskInit/TaskCreate, used by
      AnalysisEffortNode during effort-loop passes.
    - ``local_replan``: Excludes TaskInit/TaskCreate, for local replanning.

    Attributes:
        node_id: Always "task_analyzer" by default.
        mode: The analysis mode.
        tool_scope: Filtered list of tool names based on mode.
    """

    def __init__(
        self,
        node_id: str = "task_analyzer",
        config: NodeConfigBase | None = None,
        mode: str = "initial_analysis",
    ) -> None:
        """Initialize TaskAnalyzerNode.

        Args:
            node_id: Unique identifier for this node.
            config: Node configuration. Uses default if None.
            mode: Analysis mode. One of: initial_analysis, recreation, reanalysis,
                effort_loop_decomposition, local_replan.
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

        Only ``recreation`` mode includes TaskInit/TaskCreate tools.
        All other modes exclude them.

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
        if mode == "recreation":
            # Recreation mode — include all task tools including creation tools
            return list(_DEFAULT_ANALYSIS_TOOLS) + list(_TASK_CREATION_TOOLS)
        # All other modes — exclude task creation tools
        return [
            tool
            for tool in _DEFAULT_ANALYSIS_TOOLS
            if tool not in _TASK_CREATION_TOOLS
        ]

    def _validate_task_tree_non_none(self) -> None:
        """Validate that session.task is not None after LLM call completion.

        Raises:
            NodeExecutionError: If session.task is None (contract violation).
        """
        if self.session is not None and self.session.task is None:
            msg = (
                f"Node {self.node_id}: task tree is None after completion — "
                "the LLM call did not produce a valid task tree"
            )
            raise NodeExecutionError(msg)

    def __call__(self, input: NodeInputLike) -> LLMResult:
        """Execute task analysis.

        Args:
            input: The node input containing task context.

        Returns:
            The LLM response with task analysis.

        Raises:
            NodeExecutionError: If task tree is None after completion.
        """
        result = super().__call__(input)
        self._validate_task_tree_non_none()
        logger.info(
            "node=%s mode=%s analysis_complete content_len=%d",
            self.node_id,
            self.mode,
            len(result.content),
        )
        return result
