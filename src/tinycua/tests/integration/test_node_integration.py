"""Integration tests for Node, ProcessNode, and DecisionNode."""

from __future__ import annotations


from tinycua.config.node_config import NodeConfigBase, NodeMessagePolicy, NodeRetryPolicy
from tinycua.config.types import LLMResult, ValidationResult
from tinycua.models.node_input import NodeInput, NodePayload
from tinycua.models.session import Session
from tests.mock_llm import MockLLM, MultiResponseMockLLM


class MinimalProcessNode:
    """Minimal ProcessNode subclass for testing."""

    INSTRUCTION = "You are a test process node."

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
    ) -> None:
        from tinycua.loops.node import ProcessNode

        self._impl = ProcessNode(
            node_id=node_id,
            config=config,
            instruction=self.INSTRUCTION,
        )

    def __call__(self, input: object) -> LLMResult:

        return self._impl(input)  # type: ignore[arg-type]

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        return self._impl.ensure_session(root_or_parent_session)

    @property
    def session(self) -> Session | None:
        return self._impl.session

    @session.setter
    def session(self, value: Session | None) -> None:
        self._impl.session = value

    @property
    def parent(self) -> object | None:
        return self._impl.parent

    @parent.setter
    def parent(self, value: object | None) -> None:
        self._impl.parent = value

    def build_messages(
        self, session: Session, input: object
    ) -> list[dict]:

        return self._impl.build_messages(session, input)  # type: ignore[arg-type]


class MinimalDecisionNode:
    """Minimal DecisionNode subclass for testing."""

    INSTRUCTION = "You are a test decision node."
    CLASSIFICATION_LABELS = ["passthrough", "worker"]

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
    ) -> None:
        from tinycua.loops.node import DecisionNode

        self._impl = DecisionNode(
            node_id=node_id,
            config=config,
            instruction=self.INSTRUCTION,
            classification_labels=self.CLASSIFICATION_LABELS,
        )

    def __call__(self, input: object) -> object:
        return self._impl(input)  # type: ignore[return-value]

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        return self._impl.ensure_session(root_or_parent_session)

    @property
    def session(self) -> Session | None:
        return self._impl.session

    @session.setter
    def session(self, value: Session | None) -> None:
        self._impl.session = value

    @property
    def parent(self) -> object | None:
        return self._impl.parent

    @parent.setter
    def parent(self, value: object | None) -> None:
        self._impl.parent = value


class RetryTestProcessNode:
    """ProcessNode that fails validation N times then succeeds."""

    INSTRUCTION = "You are a retry test node."

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
    ) -> None:
        from tinycua.loops.node import ProcessNode

        self._impl = ProcessNode(
            node_id=node_id,
            config=config,
            instruction=self.INSTRUCTION,
        )
        self.retry_count = 0

    def __call__(self, input: object) -> LLMResult:  # noqa: ARG002
        # Override validate_output to fail first N-1 times
        max_attempts = self._impl.config.retry_policy.max_attempts

        def patched_validate(response: LLMResult) -> ValidationResult:  # noqa: ARG005
            self.retry_count += 1
            result = ValidationResult()
            if self.retry_count < max_attempts:
                result.is_valid = False
                result.errors = [f"Simulated failure on attempt {self.retry_count}"]
            else:
                result.is_valid = True
                result.errors = []
            return result

        self._impl.validate_output = patched_validate  # type: ignore[method-assign]
        return self._impl(input)  # type: ignore[arg-type]

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        return self._impl.ensure_session(root_or_parent_session)


class LifecycleTestProcessNode:
    """ProcessNode that tracks lifecycle hook calls."""

    INSTRUCTION = "You are a lifecycle test node."

    def __init__(
        self,
        node_id: str,
        config: NodeConfigBase,
    ) -> None:
        from tinycua.loops.node import ProcessNode

        self._impl = ProcessNode(
            node_id=node_id,
            config=config,
            instruction=self.INSTRUCTION,
        )
        self.record_output_called = False
        self.propagate_called = False
        self.on_complete_called = False

    def __call__(self, input: object) -> LLMResult:
        original_record = self._impl.record_output
        original_propagate = self._impl.propagate

        def patched_record(response: LLMResult) -> None:
            self.record_output_called = True
            original_record(response)

        def patched_propagate() -> None:
            self.propagate_called = True
            original_propagate()

        def patched_on_complete(queue: object, response: LLMResult) -> None:  # noqa: ARG002
            self.on_complete_called = True

        self._impl.record_output = patched_record  # type: ignore[method-assign]
        self._impl.propagate = patched_propagate  # type: ignore[method-assign]
        self._impl.on_complete = patched_on_complete  # type: ignore[method-assign]
        return self._impl(input)  # type: ignore[arg-type]

    def ensure_session(self, root_or_parent_session: Session) -> Session:
        return self._impl.ensure_session(root_or_parent_session)


# ── Integration Tests ────────────────────────────────────────────────────


def test_process_node_with_string_input() -> None:
    """ProcessNode subclass can be called with string input and returns a response."""
    mock_llm = MockLLM(response="processed result")
    config = NodeConfigBase(llm_client=mock_llm)
    node = MinimalProcessNode(node_id="test-process", config=config)
    session = Session()
    node.ensure_session(session)

    result = node("Hello, process this input")

    assert result is not None
    assert hasattr(result, "content")
    assert node.session is not None


def test_decision_node_with_node_input() -> None:
    """DecisionNode subclass can classify input and return a route label."""
    mock_llm = MultiResponseMockLLM(["analysis result", "worker"])
    config = NodeConfigBase(llm_client=mock_llm)
    node = MinimalDecisionNode(node_id="test-decision", config=config)
    session = Session()
    node.ensure_session(session)

    result = node(
        NodeInput(
            input_type="analysis",
            messages=[{"role": "user", "content": "Classify this"}],
        )
    )

    assert result is not None
    assert hasattr(result, "route_label")
    assert result.route_label in ["passthrough", "worker"]


def test_process_node_with_node_payload() -> None:
    """ProcessNode subclass can be called with a NodePayload input."""
    mock_llm = MockLLM(response="payload processed")
    config = NodeConfigBase(llm_client=mock_llm)
    node = MinimalProcessNode(node_id="test-payload", config=config)
    session = Session()
    node.ensure_session(session)
    payload = NodePayload(payload_type="test", content={"key": "value"})

    result = node(payload)

    assert result is not None
    assert hasattr(result, "content")


def test_session_attachment_with_root_session() -> None:
    """ensure_session creates a session from root session."""
    mock_llm = MockLLM()
    config = NodeConfigBase(llm_client=mock_llm)
    node = MinimalProcessNode(node_id="test-session", config=config)
    root_session = Session()

    session = node.ensure_session(root_session)

    assert session is not None
    assert node.session is session


def test_session_attachment_with_parent_node() -> None:
    """ensure_session adopts session from parent node."""
    mock_llm = MockLLM()
    config = NodeConfigBase(llm_client=mock_llm)
    parent = MinimalProcessNode(node_id="parent", config=config)
    child = MinimalProcessNode(node_id="child", config=config)
    child.parent = parent  # type: ignore[assignment]
    root_session = Session()
    parent.ensure_session(root_session)

    session = child.ensure_session(root_session)

    assert session is parent.session


def test_message_building_with_session_context() -> None:
    """build_messages includes session context when enabled."""
    mock_llm = MockLLM()
    config = NodeConfigBase(
        llm_client=mock_llm,
        message_policy=NodeMessagePolicy(include_session_context=True),
    )
    node = MinimalProcessNode(node_id="test-messages", config=config)
    session = Session()
    session.session_context = [{"role": "assistant", "content": "Previous context"}]
    node.ensure_session(session)

    messages = node.build_messages(session, "New input")

    assert len(messages) > 0
    # Session context appears in continuation messages (assistant-role)
    continuation_msgs = [m for m in messages if m["role"] == "assistant"]
    assert any("Previous context" in m["content"] for m in continuation_msgs)


def test_retry_on_validation_failure() -> None:
    """Node retries when validation fails."""
    mock_llm = MockLLM(response="retry result")
    config = NodeConfigBase(
        llm_client=mock_llm,
        retry_policy=NodeRetryPolicy(max_attempts=3),
    )
    node = RetryTestProcessNode(node_id="test-retry", config=config)
    session = Session()
    node.ensure_session(session)

    result = node("Trigger retry")

    assert result is not None
    assert node.retry_count == 3


def test_lifecycle_hooks_fire() -> None:
    """record_output, propagate, and on_complete are called."""
    mock_llm = MockLLM(response="lifecycle result")
    config = NodeConfigBase(llm_client=mock_llm)
    node = LifecycleTestProcessNode(node_id="test-lifecycle", config=config)
    session = Session()
    node.ensure_session(session)

    node("Test input")

    assert node.record_output_called
    assert node.propagate_called
    assert node.on_complete_called
