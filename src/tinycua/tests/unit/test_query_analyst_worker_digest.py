"""Tests for QueryAnalyst worker route with digestion."""

from unittest.mock import MagicMock

from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session


class TestQueryAnalystDigestSpawn:
    """Tests for QueryAnalyst digest spawn logic."""

    def test_route_worker_spawns_digester_before_worker(self) -> None:
        """_route_worker inserts InformationDigesterNode before WorkerNode."""
        queue = NodeQueue()
        query_analyst = TinyCUAQueryAnalystNode(
            node_id="qa",
            config=MagicMock(),
        )
        # We need a ResponseNode-like terminal
        from tinycua.loops.response_node import ResponseNode

        response = ResponseNode()
        queue.items = [query_analyst, response]

        session = Session()
        query_analyst.session = session
        query_analyst._queue = queue

        input_data = NodeInput(
            input_type="worker",
            messages=[{"role": "user", "content": "Create a plan for the migration"}],
        )

        query_analyst._route_worker(input_data)

        assert len(queue.items) == 4
        assert isinstance(queue.items[1], TinyCUAInformationDigesterNode)
        # items[2] is WorkerNode
        assert queue.items[2].node_id == "worker"

    def test_extract_user_query_returns_last_user_message(self) -> None:
        """_extract_user_query extracts the last user message."""
        query_analyst = TinyCUAQueryAnalystNode(
            node_id="qa",
            config=MagicMock(),
        )

        input_data = NodeInput(
            input_type="worker",
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "First query"},
                {"role": "assistant", "content": "response"},
                {"role": "user", "content": "Create a plan for the migration"},
            ],
        )

        result = query_analyst._extract_user_query(input_data)
        assert result == "Create a plan for the migration"

    def test_extract_user_query_returns_first_message_when_no_user_role(self) -> None:
        """_extract_user_query falls back to first message if no user role."""
        query_analyst = TinyCUAQueryAnalystNode(
            node_id="qa",
            config=MagicMock(),
        )

        input_data = NodeInput(
            input_type="worker",
            messages=[
                {"role": "system", "content": "system prompt"},
                {"role": "assistant", "content": "response"},
            ],
        )

        result = query_analyst._extract_user_query(input_data)
        assert result == "system prompt"

    def test_extract_user_query_returns_empty_for_empty_messages(self) -> None:
        """_extract_user_query returns empty string for no messages."""
        query_analyst = TinyCUAQueryAnalystNode(
            node_id="qa",
            config=MagicMock(),
        )

        input_data = NodeInput(
            input_type="worker",
            messages=[],
        )

        result = query_analyst._extract_user_query(input_data)
        assert result == ""

    def test_existing_digest_still_spawns_a_fresh_digester(self) -> None:
        """Each Worker entry must consolidate the current user turn again."""
        queue = NodeQueue()
        worker = MagicMock()
        worker.node_id = "w"
        worker.session = Session()
        digest = DigestedInformation(
            context_summary="Already digested", original_query="q"
        )
        worker.session.session_context.append(
            {
                "role": "assistant",
                "content": digest,
            }
        )

        from tinycua.loops.response_node import ResponseNode

        response = ResponseNode()
        queue.items = [worker, response]

        query_analyst = TinyCUAQueryAnalystNode(
            node_id="qa",
            config=MagicMock(),
        )
        query_analyst.session = worker.session
        query_analyst._queue = queue

        query_analyst._route_worker()

        assert [node.node_id for node in queue.items[:3]] == [
            "w",
            "digester",
            "worker",
        ]
