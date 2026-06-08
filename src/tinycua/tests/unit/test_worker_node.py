"""Unit tests for TinyCUAWorkerNode."""

from __future__ import annotations

from unittest.mock import MagicMock
from tinycua.config.node_config import NodeConfigBase
from tinycua.config.types import LLMResult
from tinycua.loops.worker import TinyCUAWorkerNode, WorkerRouteLabel
from tinycua.loops.node import DecisionResult
from tinycua.loops.node_queue import NodeQueue
from tinycua.models.session import Session
from tinycua.models.node_input import NodeInput


def _make_mock_node(node_id: str, *, is_terminal: bool = False) -> MagicMock:
    """Create a mock node with required attributes."""
    node = MagicMock()
    node.node_id = node_id
    node.is_terminal = is_terminal
    return node


class TestWorkerRouteLabel:
    """Tests for WorkerRouteLabel enum."""

    def test_task_creation_value(self) -> None:
        """WorkerRouteLabel.task_creation has correct value."""
        assert WorkerRouteLabel.task_creation.value == "task_creation"

    def test_task_recreation_value(self) -> None:
        """WorkerRouteLabel.task_recreation has correct value."""
        assert WorkerRouteLabel.task_recreation.value == "task_recreation"

    def test_task_reanalysis_value(self) -> None:
        """WorkerRouteLabel.task_reanalysis has correct value."""
        assert WorkerRouteLabel.task_reanalysis.value == "task_reanalysis"

    def test_passthrough_value(self) -> None:
        """WorkerRouteLabel.passthrough has correct value."""
        assert WorkerRouteLabel.passthrough.value == "passthrough"

    def test_proceed_execution_value(self) -> None:
        """WorkerRouteLabel.proceed_execution has correct value."""
        assert WorkerRouteLabel.proceed_execution.value == "proceed_execution"

    def test_enum_members(self) -> None:
        """WorkerRouteLabel has all expected members."""
        assert hasattr(WorkerRouteLabel, "task_creation")
        assert hasattr(WorkerRouteLabel, "task_recreation")
        assert hasattr(WorkerRouteLabel, "task_reanalysis")
        assert hasattr(WorkerRouteLabel, "passthrough")
        assert hasattr(WorkerRouteLabel, "proceed_execution")

    def test_enum_has_five_members(self) -> None:
        """WorkerRouteLabel has exactly five members."""
        assert len(WorkerRouteLabel) == 5


class TestWorkerNodeInit:
    """Tests for TinyCUAWorkerNode initialization."""

    def test_inherits_from_decision_node(self) -> None:
        """TinyCUAWorkerNode inherits from DecisionNode."""
        from tinycua.loops.node import DecisionNode

        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        assert isinstance(worker, DecisionNode)

    def test_classification_labels_include_task_creation(self) -> None:
        """WorkerNode classification labels include task_creation."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        assert "task_creation" in worker.classification_labels

    def test_classification_labels_include_all_five(self) -> None:
        """WorkerNode classification labels include all five route labels."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        assert "task_creation" in worker.classification_labels
        assert "task_recreation" in worker.classification_labels
        assert "task_reanalysis" in worker.classification_labels
        assert "passthrough" in worker.classification_labels
        assert "proceed_execution" in worker.classification_labels

    def test_route_map_registered(self) -> None:
        """WorkerNode has a route_map with task_creation handler."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        assert worker.route_map.has_route("task_creation")

    def test_route_map_has_all_five_routes(self) -> None:
        """WorkerNode has a route_map with all five route handlers."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        assert worker.route_map.has_route("task_creation")
        assert worker.route_map.has_route("task_recreation")
        assert worker.route_map.has_route("task_reanalysis")
        assert worker.route_map.has_route("passthrough")
        assert worker.route_map.has_route("proceed_execution")

    def test_default_node_id(self) -> None:
        """WorkerNode defaults to 'worker' node_id."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(config=config)
        assert worker.node_id == "worker"


class TestWorkerNodeDetectTaskExists:
    """Tests for TinyCUAWorkerNode._detect_task_exists."""

    def test_returns_false_when_no_task(self) -> None:
        """_detect_task_exists returns False when session.task is None."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = None
        worker.ensure_session(session)

        assert worker._detect_task_exists() is False

    def test_returns_true_when_task_exists(self) -> None:
        """_detect_task_exists returns True when session.task is set."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        assert worker._detect_task_exists() is True


class TestWorkerNodeDetectWorkerSpawnedNodes:
    """Tests for TinyCUAWorkerNode._detect_worker_spawned_nodes."""

    def test_finds_spawned_nodes(self) -> None:
        """_detect_worker_spawned_nodes finds nodes between worker and terminal."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        spawned = _make_mock_node("task_create")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, spawned, terminal]

        result = worker._detect_worker_spawned_nodes(queue)
        assert len(result) == 1
        assert result[0].node_id == "task_create"

    def test_returns_empty_when_no_spawned(self) -> None:
        """_detect_worker_spawned_nodes returns empty when no spawned nodes."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = worker._detect_worker_spawned_nodes(queue)
        assert result == []

    def test_stops_at_terminal(self) -> None:
        """_detect_worker_spawned_nodes stops scanning at terminal node."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        spawned = _make_mock_node("task_create")
        terminal = _make_mock_node("response", is_terminal=True)
        after_terminal = _make_mock_node("another_node")
        queue.items = [worker, spawned, terminal, after_terminal]

        result = worker._detect_worker_spawned_nodes(queue)
        assert len(result) == 1
        assert result[0].node_id == "task_create"


class TestWorkerNodeHasWorkerSpawnedNodes:
    """Tests for TinyCUAWorkerNode._has_worker_spawned_nodes."""

    def test_returns_true_when_spawned_nodes_exist(self) -> None:
        """_has_worker_spawned_nodes returns True when spawned nodes exist."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        spawned = _make_mock_node("task_create")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, spawned, terminal]

        assert worker._has_worker_spawned_nodes(queue) is True

    def test_returns_false_when_no_spawned_nodes(self) -> None:
        """_has_worker_spawned_nodes returns False when no spawned nodes."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        assert worker._has_worker_spawned_nodes(queue) is False


class TestWorkerNodeGetClassificationLabels:
    """Tests for TinyCUAWorkerNode._get_classification_labels."""

    def test_includes_passthrough_when_spawned_nodes_exist(self) -> None:
        """_get_classification_labels includes passthrough when spawned nodes exist."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        spawned = _make_mock_node("task_create")
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, spawned, terminal]

        labels = worker._get_classification_labels(queue)
        assert "passthrough" in labels
        assert "task_recreation" in labels
        assert "task_reanalysis" in labels
        assert "proceed_execution" in labels

    def test_excludes_passthrough_when_no_spawned_nodes(self) -> None:
        """_get_classification_labels excludes passthrough when no spawned nodes."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        labels = worker._get_classification_labels(queue)
        assert "passthrough" not in labels
        assert "task_recreation" in labels
        assert "task_reanalysis" in labels
        assert "proceed_execution" in labels


class TestWorkerNodeRouteTaskCreation:
    """Tests for TinyCUAWorkerNode._route_task_creation."""

    def test_spawns_task_create_node(self) -> None:
        """_route_task_creation spawns TaskCreateNode after current."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = None
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = DecisionResult(
            route_label="task_creation",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(
                content="task_creation", role="assistant",
            ),
        )

        worker._route_task_creation(queue, result)

        # Worker should still be at front
        assert queue.current is worker
        # TaskCreateNode should be spawned after worker
        node_ids = [n.node_id for n in queue.items]
        assert "task_create" in node_ids
        task_create_idx = node_ids.index("task_create")
        worker_idx = node_ids.index("worker")
        assert task_create_idx == worker_idx + 1


class TestWorkerNodeCall:
    """Tests for TinyCUAWorkerNode.__call__."""

    def test_returns_decision_result_with_task_creation(self) -> None:
        """WorkerNode returns DecisionResult with task_creation label when no task."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = None
        worker.ensure_session(session)

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Help me write a script"}],
        )

        result = worker(input_data)

        assert isinstance(result, DecisionResult)
        assert result.route_label == "task_creation"

    def test_no_llm_calls_for_task_creation(self) -> None:
        """WorkerNode makes no LLM calls for deterministic task_creation."""
        mock_llm = MagicMock()
        config = NodeConfigBase(llm_client=mock_llm)
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = None
        worker.ensure_session(session)

        input_data = NodeInput(
            input_type="continuation",
            messages=[{"role": "user", "content": "Help me write a script"}],
        )

        worker(input_data)

        mock_llm.assert_not_called()


class TestWorkerNodeOnComplete:
    """Tests for TinyCUAWorkerNode.on_complete."""

    def test_dispatches_to_route_map(self) -> None:
        """on_complete dispatches to the route_map handler."""
        config = NodeConfigBase()
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = None
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = DecisionResult(
            route_label="task_creation",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(
                content="task_creation", role="assistant",
            ),
        )

        worker.on_complete(queue, result)

        # TaskCreateNode should be spawned
        node_ids = [n.node_id for n in queue.items]
        assert "task_create" in node_ids


class TestWorkerNodeRouteTaskRecreation:
    """Tests for TinyCUAWorkerNode._route_task_recreation."""

    def test_clears_spawned_nodes_and_spawns_task_analyzer(self) -> None:
        """_route_task_recreation clears worker-spawned nodes and spawns TaskAnalyzerNode."""
        config = NodeConfigBase(llm_client=MagicMock())
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]
        spawned = _make_mock_node("old_spawned")
        queue.spawn_after_current([spawned])

        result = DecisionResult(
            route_label="task_recreation",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(content="task_recreation", role="assistant"),
        )

        worker._route_task_recreation(queue, result)

        # Old spawned node should be cleared
        node_ids = [n.node_id for n in queue.items]
        assert "old_spawned" not in node_ids
        # TaskAnalyzerNode should be spawned with mode="analysis"
        assert "task_analyzer" in node_ids
        task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
        assert task_analyzer.mode == "analysis"

    def test_ensures_terminal_response_path(self) -> None:
        """_route_task_recreation ensures terminal response path exists."""
        config = NodeConfigBase(llm_client=MagicMock())
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = DecisionResult(
            route_label="task_recreation",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(content="task_recreation", role="assistant"),
        )

        worker._route_task_recreation(queue, result)

        # Terminal node should exist
        assert queue.items[-1].is_terminal


class TestWorkerNodeRouteTaskReanalysis:
    """Tests for TinyCUAWorkerNode._route_task_reanalysis."""

    def test_clears_spawned_nodes_and_spawns_task_analyzer(self) -> None:
        """_route_task_reanalysis clears worker-spawned nodes and spawns TaskAnalyzerNode."""
        config = NodeConfigBase(llm_client=MagicMock())
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]
        spawned = _make_mock_node("old_spawned")
        queue.spawn_after_current([spawned])

        result = DecisionResult(
            route_label="task_reanalysis",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(content="task_reanalysis", role="assistant"),
        )

        worker._route_task_reanalysis(queue, result)

        # TaskAnalyzerNode should be spawned with mode="initial_analysis"
        task_analyzer = [n for n in queue.items if n.node_id == "task_analyzer"][0]
        assert task_analyzer.mode == "initial_analysis"

    def test_ensures_terminal_response_path(self) -> None:
        """_route_task_reanalysis ensures terminal response path exists."""
        config = NodeConfigBase(llm_client=MagicMock())
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = DecisionResult(
            route_label="task_reanalysis",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(content="task_reanalysis", role="assistant"),
        )

        worker._route_task_reanalysis(queue, result)

        # Terminal node should exist
        assert queue.items[-1].is_terminal


class TestWorkerNodeRoutePassthrough:
    """Tests for TinyCUAWorkerNode._route_passthrough."""

    def test_advances_queue_and_forwards_input(self) -> None:
        """_route_passthrough advances queue and forwards input to next node."""
        config = NodeConfigBase(llm_client=MagicMock())
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]
        spawned = _make_mock_node("next_node")
        queue.spawn_after_current([spawned])

        result = DecisionResult(
            route_label="passthrough",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(content="passthrough", role="assistant"),
        )

        worker._last_input = NodeInput(input_type="continuation", messages=[])
        worker._route_passthrough(queue, result)

        # Worker should be removed, next_node should be current
        assert queue.items[0].node_id == "next_node"
        # Input should be forwarded
        assert queue._inputs.get("next_node") is not None


class TestWorkerNodeRouteProceedExecution:
    """Tests for TinyCUAWorkerNode._route_proceed_execution."""

    def test_ensures_terminal_response_path(self) -> None:
        """_route_proceed_execution ensures terminal response path exists."""
        config = NodeConfigBase(llm_client=MagicMock())
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        session = Session()
        session.task = "Write a script"
        worker.ensure_session(session)

        queue = NodeQueue()
        terminal = _make_mock_node("response", is_terminal=True)
        queue.items = [worker, terminal]

        result = DecisionResult(
            route_label="proceed_execution",
            analysis_response=LLMResult(content="analysis", role="assistant"),
            classification_response=LLMResult(content="proceed_execution", role="assistant"),
        )

        worker._route_proceed_execution(queue, result)

        # Terminal node should exist
        assert queue.items[-1].is_terminal
