"""End-to-end integration tests for the full pipeline flow.

Tests the complete QueryAnalyst → InformationDigester → Worker → TaskCreate
pipeline with MockLLM responses, plus fallback path when digester fails.
"""

from __future__ import annotations

import json

import pytest

from tinycua.config.node_config import NodeConfigBase
from tinycua.loops.information_digester import TinyCUAInformationDigesterNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.loops.task_create import TinyCUATaskCreateNode
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.digested_information import DigestedInformation
from tinycua.models.node_input import NodeInput
from tinycua.models.session import Session

# Import shared fixtures from conftest
from .conftest import MockLLM  # noqa: F401 — re-export for clarity


# ---------------------------------------------------------------------------
# Helper to build a configured MockLLM for the full pipeline
# ---------------------------------------------------------------------------
def _make_pipeline_mock_llm() -> MockLLM:
    """Create a MockLLM with per-node responses for the full pipeline."""
    return MockLLM(
        node_responses={
            "qa": {
                "content": "This requires task planning. Classification: worker",
                "role": "assistant",
            },
            "digester": {
                "content": json.dumps({
                    "context_summary": "User wants a migration plan with clear phases",
                    "key_points": ["Break migration into phases", "Identify dependencies"],
                    "advisory_instructions": ["Consider rollback strategy"],
                    "constraints": ["Must complete within Q3"],
                    "known_gaps": ["No current inventory available"],
                }),
                "role": "assistant",
            },
            "worker": {
                "content": "Ready to create tasks. Classification: task_creation",
                "role": "assistant",
            },
            "task_create": {
                "content": "Task 1: Phase 1 migration\nTask 2: Phase 2 migration",
                "role": "assistant",
            },
        }
    )


# ---------------------------------------------------------------------------
# TestFullPipelineIntegration — broken into focused tests
# ---------------------------------------------------------------------------
class TestFullPipelineIntegration:
    """End-to-end test: QueryAnalyst → InformationDigester → Worker → TaskCreate."""

    def test_digester_calls_llm_and_records_response(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Digester executes ProcessNode lifecycle: build → LLM → record."""
        mock_llm = _make_pipeline_mock_llm()

        digester = TinyCUAInformationDigesterNode(node_id="digester", config=config)
        digester.config.llm_client = mock_llm
        digester.ensure_session(root_session)

        digester(NodeInput(
            input_type="worker",
            messages=[{"role": "user", "content": "Create a migration plan"}],
        ))

        # ProcessNode records LLM response in session_context
        assert len(digester.session.session_context) == 1
        recorded = digester.session.session_context[0]
        assert recorded.role == "assistant"
        # Content is the raw JSON string from the LLM
        parsed = json.loads(recorded.content)
        assert "context_summary" in parsed
        assert "key_points" in parsed

    def test_digester_propagate_stores_digest(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """When _current_digest is set, propagate() stores it in session_context."""
        digester = TinyCUAInformationDigesterNode(node_id="digester", config=config)
        digester.ensure_session(root_session)

        digest = DigestedInformation(
            context_summary="User wants a migration plan with clear phases",
            original_query="Create a migration plan",
            key_points=["Break migration into phases", "Identify dependencies"],
        )
        digester._current_digest = digest
        digester.propagate()

        assert len(digester.session.session_context) == 1
        assert isinstance(
            digester.session.session_context[0].content, DigestedInformation
        )
        assert digester.session.session_context[0].content is digest

    def test_worker_retrieves_digested_information(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Worker retrieves DigestedInformation from session_context."""
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        worker.ensure_session(root_session)

        # Simulate propagation: digest placed in worker's session_context
        digest = DigestedInformation(
            context_summary="User wants a migration plan with clear phases",
            original_query="Create a migration plan",
            key_points=["Break migration into phases", "Identify dependencies"],
        )
        worker.session.session_context.append({
            "role": "assistant",
            "content": digest,
        })

        retrieved = worker._get_digested_input()
        assert retrieved is not None
        assert isinstance(retrieved, DigestedInformation)
        assert retrieved.original_query == "Create a migration plan"
        assert retrieved.has_useful_context is True

    def test_worker_propagates_digest_downstream(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Worker propagate() stores digest in session_context."""
        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        worker.ensure_session(root_session)

        digest = DigestedInformation(
            context_summary="test context",
            original_query="test query",
            key_points=["point1"],
        )
        worker._current_digest = digest
        worker.propagate()

        assert any(
            isinstance(entry.content, DigestedInformation)
            for entry in worker.session.session_context
        )

    def test_task_create_extracts_digest_context(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """TaskCreateNode extracts digest context from session."""
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        task_create.ensure_session(root_session)

        digest = DigestedInformation(
            context_summary="User wants a migration plan with clear phases",
            original_query="Create a migration plan",
            key_points=["Break migration into phases", "Identify dependencies"],
        )
        task_create.session.session_context.append({
            "role": "assistant",
            "content": digest,
        })

        digest_ctx = task_create._extract_digest_context(task_create.session)
        assert digest_ctx is not None
        assert "migration plan" in digest_ctx.lower()
        assert "Key Points" in digest_ctx
        assert "Original Query" in digest_ctx

    def test_full_pipeline_end_to_end(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Full pipeline: QA spawns digester+worker, digest flows through all nodes."""
        mock_llm = _make_pipeline_mock_llm()

        # Step 1: Queue wiring — QA spawns digester + worker
        queue = NodeQueue()
        response_node = ResponseNode()
        query_analyst = TinyCUAQueryAnalystNode(node_id="qa", config=config)
        queue.items = [query_analyst, response_node]

        query_analyst.session = Session()
        query_analyst._queue = queue

        input_data = NodeInput(
            input_type="worker",
            messages=[{"role": "user", "content": "Create a migration plan"}],
        )
        query_analyst._route_worker(input_data)

        assert len(queue.items) == 4
        assert isinstance(queue.items[1], TinyCUAInformationDigesterNode)
        assert isinstance(queue.items[2], TinyCUAWorkerNode)
        assert queue.items[3].node_id == "response"

        # Step 2: Execute digester — ProcessNode records LLM response
        digester = queue.items[1]
        digester.config = config
        digester.config.llm_client = mock_llm
        digester.ensure_session(root_session)

        digester(NodeInput(
            input_type="worker",
            messages=[{"role": "user", "content": "Create a migration plan"}],
        ))
        # LLM response was recorded in session_context
        assert len(digester.session.session_context) == 1

        # Simulate orchestrator parsing: extract digest from recorded response
        recorded_content = digester.session.session_context[0].content
        parsed = json.loads(recorded_content)
        digest = DigestedInformation(
            context_summary=parsed["context_summary"],
            original_query="Create a migration plan",
            key_points=parsed["key_points"],
            advisory_instructions=parsed.get("advisory_instructions", []),
            constraints=parsed.get("constraints", []),
            known_gaps=parsed.get("known_gaps", []),
        )
        digester._current_digest = digest
        digester.propagate()

        # Step 3: Worker retrieves digest from propagated session_context
        worker = queue.items[2]
        worker.config = config
        worker.config.llm_client = mock_llm
        worker.ensure_session(root_session)

        # Simulate propagation chain: digest flows from digester → worker
        for entry in digester.session.session_context:
            worker.session.session_context.append(entry)

        retrieved = worker._get_digested_input()
        assert retrieved is not None
        assert retrieved.original_query == "Create a migration plan"

        # Step 4: Worker propagates
        worker._current_digest = retrieved
        worker.propagate()

        # Step 5: TaskCreate receives digest
        task_create = TinyCUATaskCreateNode(node_id="task_create", config=config)
        task_create.config.llm_client = mock_llm
        task_create.ensure_session(root_session)

        for entry in worker.session.session_context:
            task_create.session.session_context.append(entry)

        digest_ctx = task_create._extract_digest_context(task_create.session)
        assert digest_ctx is not None
        assert "migration plan" in digest_ctx.lower()


# ---------------------------------------------------------------------------
# TestFallbackPath — focused on digester failure scenarios
# ---------------------------------------------------------------------------
class TestFallbackPath:
    """Integration tests for digester fallback behavior."""

    def test_fallback_digest_preserves_original_query(self) -> None:
        """DigestedInformation.fallback() preserves the original query."""
        query = "Create a migration plan"
        fallback = DigestedInformation.fallback(query)

        assert fallback.original_query == query
        assert "migration plan" in fallback.context_summary.lower()
        assert fallback.has_useful_context is False

    def test_worker_receives_fallback_when_digester_fails(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Worker retrieves fallback digest when digester fails."""
        original_query = "Create a migration plan"
        fallback_digest = DigestedInformation.fallback(original_query)

        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        worker.ensure_session(root_session)

        worker.session.session_context.append({
            "role": "assistant",
            "content": fallback_digest,
        })

        retrieved = worker._get_digested_input()
        assert retrieved is not None
        assert isinstance(retrieved, DigestedInformation)
        assert retrieved.original_query == original_query
        assert "No useful extra information" in retrieved.context_summary

    def test_worker_proceeds_with_fallback_digest(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Worker can propagate fallback digest downstream."""
        fallback = DigestedInformation.fallback("any query")

        worker = TinyCUAWorkerNode(node_id="worker", config=config)
        worker.ensure_session(root_session)
        worker._current_digest = fallback
        worker.propagate()

        assert any(
            isinstance(entry.content, DigestedInformation)
            for entry in worker.session.session_context
        )

    @pytest.mark.parametrize(
        "query",
        [
            "Analyze the database schema and suggest improvements",
            "Help me debug this failing test",
            "Write a migration script for the users table",
        ],
        ids=["db-analysis", "debug-test", "migration-script"],
    )
    def test_fallback_preserves_various_queries(self, query: str) -> None:
        """Fallback preserves the original query for various inputs."""
        fallback = DigestedInformation.fallback(query)
        assert fallback.original_query == query
        assert query in fallback.context_summary
        assert fallback.has_useful_context is False


# ---------------------------------------------------------------------------
# TestPipelineQueueWiring — queue ordering and spawn behavior
# ---------------------------------------------------------------------------
class TestPipelineQueueWiring:
    """Verify spawn_after_current correctly inserts nodes in queue order."""

    def test_route_worker_spawns_digester_and_worker(self) -> None:
        """_route_worker inserts digester + worker after QA in the queue."""
        queue = NodeQueue()
        response_node = ResponseNode()
        qa = TinyCUAQueryAnalystNode(node_id="qa", config=NodeConfigBase())
        queue.items = [qa, response_node]

        qa.session = Session()
        qa._queue = queue

        input_data = NodeInput(
            input_type="worker",
            messages=[{"role": "user", "content": "test query"}],
        )
        qa._route_worker(input_data)

        node_ids = [n.node_id for n in queue.items]
        assert node_ids == ["qa", "digester", "worker", "response"]


# ---------------------------------------------------------------------------
# TestSessionContextFlow — session sharing and context accumulation
# ---------------------------------------------------------------------------
class TestSessionContextFlow:
    """Verify session_context is correctly shared and accumulated across nodes."""

    def test_digest_flows_through_root_session(
        self,
        config: NodeConfigBase,
        root_session: Session,
    ) -> None:
        """Digest propagates through root_session to downstream nodes."""
        # Digester produces and propagates digest
        digester = TinyCUAInformationDigesterNode(node_id="d", config=config)
        digester.ensure_session(root_session)
        digest = DigestedInformation(
            context_summary="Test context",
            original_query="test",
            key_points=["point1"],
        )
        digester._current_digest = digest
        digester.propagate()

        # Worker receives digest (shares root_session)
        worker = TinyCUAWorkerNode(node_id="w", config=config)
        worker.ensure_session(root_session)

        # Copy digester entries (snapshot first to avoid mutating while iterating)
        digester_entries = list(digester.session.session_context)
        for entry in digester_entries:
            worker.session.session_context.append(entry)

        retrieved = worker._get_digested_input()
        assert retrieved is not None
        assert retrieved.context_summary == "Test context"

        # Worker propagates downstream
        worker._current_digest = retrieved
        worker.propagate()

        # Downstream node sees accumulated context
        # Use a separate session for downstream to avoid shared-list infinite loop
        downstream = TinyCUATaskCreateNode(node_id="tc", config=config)
        downstream_session = Session()
        downstream.ensure_session(downstream_session)

        # Copy accumulated entries from worker's session
        worker_entries = list(worker.session.session_context)
        for entry in worker_entries:
            downstream.session.session_context.append(entry)

        ctx = downstream._extract_digest_context(downstream.session)
        assert ctx is not None
        assert "Test context" in ctx

    def test_digest_context_is_not_shared_between_independent_nodes(
        self,
        config: NodeConfigBase,
    ) -> None:
        """Independent nodes with separate sessions do not share context."""
        session_a = Session()
        session_b = Session()

        worker_a = TinyCUAWorkerNode(node_id="w1", config=config)
        worker_a.ensure_session(session_a)

        worker_b = TinyCUAWorkerNode(node_id="w2", config=config)
        worker_b.ensure_session(session_b)

        digest = DigestedInformation(
            context_summary="Only for A",
            original_query="query A",
        )
        worker_a.session.session_context.append({
            "role": "assistant",
            "content": digest,
        })

        # B should not see A's digest
        assert worker_b._get_digested_input() is None


# ---------------------------------------------------------------------------
# TestDigestInformationFallback — fallback properties
# ---------------------------------------------------------------------------
class TestDigestInformationFallback:
    """Unit tests for DigestedInformation fallback behavior."""

    def test_fallback_has_no_useful_context(self) -> None:
        """Fallback digest has_useful_context is False."""
        fallback = DigestedInformation.fallback("any query")
        assert fallback.has_useful_context is False
        assert fallback.key_points == []
        assert fallback.advisory_instructions == []
        assert fallback.constraints == []

    def test_digest_with_key_points_has_useful_context(self) -> None:
        """Digest with key_points has_useful_context is True."""
        digest = DigestedInformation(
            context_summary="summary",
            original_query="q",
            key_points=["important"],
        )
        assert digest.has_useful_context is True

    def test_digest_with_advisory_has_useful_context(self) -> None:
        """Digest with advisory_instructions has_useful_context is True."""
        digest = DigestedInformation(
            context_summary="summary",
            original_query="q",
            advisory_instructions=["be careful"],
        )
        assert digest.has_useful_context is True

    def test_digest_with_constraints_has_useful_context(self) -> None:
        """Digest with constraints has_useful_context is True."""
        digest = DigestedInformation(
            context_summary="summary",
            original_query="q",
            constraints=["deadline is Friday"],
        )
        assert digest.has_useful_context is True

    def test_empty_digest_has_no_useful_context(self) -> None:
        """Empty digest has_useful_context is False."""
        digest = DigestedInformation()
        assert digest.has_useful_context is False
