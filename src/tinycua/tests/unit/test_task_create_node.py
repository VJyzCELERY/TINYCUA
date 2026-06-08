"""Unit tests for TinyCUATaskCreateNode."""

from __future__ import annotations

from unittest.mock import MagicMock
from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.node import ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


class TestTaskCreateNodeInit:
    """Tests for TinyCUATaskCreateNode initialization."""

    def test_inherits_from_process_node(self) -> None:
        """TinyCUATaskCreateNode inherits from ProcessNode."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        assert isinstance(task_create, ProcessNode)

    def test_tool_scope_has_task_init_and_task_create(self) -> None:
        """TaskCreateNode has TaskInit and TaskCreate in tool_scope."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        assert "TaskInit" in task_create.tool_scope
        assert "TaskCreate" in task_create.tool_scope

    def test_default_node_id(self) -> None:
        """TaskCreateNode defaults to 'task_create' node_id."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(config=config)
        assert task_create.node_id == "task_create"

    def test_instruction_mentions_task_creation(self) -> None:
        """TaskCreateNode instruction mentions task creation."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        instruction = task_create.build_instruction()
        assert "task" in instruction.lower()


class TestTaskCreateNodeCall:
    """Tests for TinyCUATaskCreateNode.__call__."""

    def test_creates_task_in_session(self) -> None:
        """TaskCreateNode creates root task in session."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        session = Session()
        session.task = None
        task_create.ensure_session(session)

        # Mock LLM to return a successful response
        mock_llm = MagicMock()
        mock_llm.return_value = {
            "content": "Task created: Write a script",
            "role": "assistant",
            "tool_calls": [],
        }
        config.llm_client = mock_llm

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Help me write a script"}],
        )
        result = task_create(input_data)

        # Assert
        assert session.task is not None
        assert isinstance(result, LLMResult)


class TestTaskCreateNodeOnComplete:
    """Tests for TinyCUATaskCreateNode.on_complete."""

    def test_advances_queue(self) -> None:
        """TaskCreateNode.on_complete advances queue past current."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        session = Session()
        task_create.ensure_session(session)

        queue = NodeQueue()
        task_analyzer = MagicMock()
        task_analyzer.node_id = "task_analyzer"
        queue.items = [task_create, task_analyzer]

        result = LLMResult(
            content="Task created",
            role="assistant",
        )

        task_create.on_complete(queue, result)

        assert queue.current.node_id == "task_analyzer"

    def test_on_complete_stores_task_in_session(self) -> None:
        """TaskCreateNode.on_complete stores task content in session.task."""
        config = NodeConfigBase()
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        session = Session()
        task_create.ensure_session(session)

        queue = NodeQueue()
        task_analyzer = MagicMock()
        task_analyzer.node_id = "task_analyzer"
        queue.items = [task_create, task_analyzer]

        # Mock LLM to return a successful response
        mock_llm = MagicMock()
        mock_llm.return_value = {
            "content": "Task created: Write a script",
            "role": "assistant",
            "tool_calls": [],
        }
        config.llm_client = mock_llm

        # Call __call__ first to create the task
        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Help me write a script"}],
        )
        result = task_create(input_data)

        # Then call on_complete to advance queue
        task_create.on_complete(queue, result)

        # Session should have task content stored
        assert session.task is not None
