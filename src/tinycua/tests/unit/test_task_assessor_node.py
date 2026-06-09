"""Unit tests for TinyCUATaskAssessorNode."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.task_assessor import TinyCUATaskAssessorNode
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


def _make_mock_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock()
    node.node_id = node_id
    node.is_terminal = is_terminal
    return node


class TestTaskAssessorNodeInit:
    """Tests for TinyCUATaskAssessorNode initialization."""

    def test_inherits_from_process_node(self) -> None:
        """TinyCUATaskAssessorNode inherits from ProcessNode."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(
            node_id="task_assessor", config=config,
        )
        assert isinstance(assessor, ProcessNode)

    def test_default_node_id(self) -> None:
        """TaskAssessorNode defaults to 'task_assessor' node_id."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(config=config)
        assert assessor.node_id == "task_assessor"

    def test_default_mode_is_effort_loop(self) -> None:
        """TaskAssessorNode defaults to 'effort_loop' mode."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(config=config)
        assert assessor.mode == "effort_loop"

    def test_custom_mode(self) -> None:
        """TaskAssessorNode can be created with custom mode."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(
            config=config, mode="reviewer_replan",
        )
        assert assessor.mode == "reviewer_replan"

    def test_selected_tasks_defaults_to_empty(self) -> None:
        """TaskAssessorNode selected_tasks defaults to empty list."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(config=config)
        assert assessor.selected_tasks == []


class TestTaskAssessorNodeEffortLoopMode:
    """Tests for TinyCUATaskAssessorNode in effort_loop mode."""

    def test_effort_loop_mode_evaluates_task_tree(self) -> None:
        """In effort_loop mode, TaskAssessor evaluates full task tree."""
        config = NodeConfigBase(llm_client=MagicMock())
        assessor = TinyCUATaskAssessorNode(
            config=config, mode="effort_loop",
        )
        session = Session()
        session.task = "Write a script"
        assessor.ensure_session(session)

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Evaluate tasks"}],
        )

        # Mock the LLM response to return task IDs
        mock_response = MagicMock()
        mock_response.content = '["task-1", "task-2"]'
        mock_response.role = "assistant"
        mock_response.tool_calls = []
        mock_response.metadata = {}

        with patch.object(assessor, "_call_llm", return_value=mock_response):
            assessor(input_data)
            assert assessor.selected_tasks == ["task-1", "task-2"]

    def test_effort_loop_mode_no_tasks_selected(self) -> None:
        """In effort_loop mode, TaskAssessor returns empty list when all tasks complete."""
        config = NodeConfigBase(llm_client=MagicMock())
        assessor = TinyCUATaskAssessorNode(
            config=config, mode="effort_loop",
        )
        session = Session()
        session.task = "Write a script"
        assessor.ensure_session(session)

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Evaluate tasks"}],
        )

        # Mock the LLM response to return empty list
        mock_response = MagicMock()
        mock_response.content = "[]"
        mock_response.role = "assistant"
        mock_response.tool_calls = []
        mock_response.metadata = {}

        with patch.object(assessor, "_call_llm", return_value=mock_response):
            assessor(input_data)
            assert assessor.selected_tasks == []

    def test_effort_loop_mode_selects_unfinished_tasks(self) -> None:
        """In effort_loop mode, TaskAssessor selects only unfinished tasks."""
        config = NodeConfigBase(llm_client=MagicMock())
        assessor = TinyCUATaskAssessorNode(
            config=config, mode="effort_loop",
        )
        session = Session()
        session.task = "Write a script with multiple parts"
        assessor.ensure_session(session)

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Evaluate tasks"}],
        )

        # Mock the LLM response to return specific task IDs
        mock_response = MagicMock()
        mock_response.content = '["task-3"]'
        mock_response.role = "assistant"
        mock_response.tool_calls = []
        mock_response.metadata = {}

        with patch.object(assessor, "_call_llm", return_value=mock_response):
            assessor(input_data)
            assert assessor.selected_tasks == ["task-3"]

    def test_effort_loop_mode_on_complete_advances_queue(self) -> None:
        """When tasks selected, on_complete advances queue (TaskAnalyzer follows)."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(
            config=config, mode="effort_loop",
        )
        assessor.selected_tasks = ["task-1"]

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [assessor, terminal]

        response = MagicMock()
        response.content = "Tasks selected"

        assessor.on_complete(queue, response)

        # Queue should have advanced (assessor removed)
        assert queue.items[0].node_id == "response"

    def test_effort_loop_mode_on_complete_no_tasks_advances(self) -> None:
        """When no tasks selected, on_complete advances queue (no TaskAnalyzer)."""
        config = NodeConfigBase()
        assessor = TinyCUATaskAssessorNode(
            config=config, mode="effort_loop",
        )
        assessor.selected_tasks = []

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [assessor, terminal]

        response = MagicMock()
        response.content = "No tasks selected"

        assessor.on_complete(queue, response)

        # Queue should have advanced (assessor removed)
        assert queue.items[0].node_id == "response"
