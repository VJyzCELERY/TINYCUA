"""Path execution engine for the verification gate.

Instantiates actual TinyCUA nodes and runs them through a manual execution
loop. This bypasses TinyCUALoop because the loop's _execute_node makes a
single agent._call_llm() call, but DecisionNode.__call__ needs to make
two calls (analysis + classification) via self.config.llm_client.

The executor wires the agent's async _call_llm to each node's config.llm_client
so nodes can make their own LLM calls during __call__.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from tinycua.config.node_config import NodeConfigBase
from tinycua.config.tool_scopes import (
    query_analyst_tool_scope,
    response_tool_scope,
)
from tinycua.loops.node import DecisionResult, Node
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import ResponseNode
from tinycua.models.node_input import NodeInputLike
from tinycua.models.session import Session
from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.llm_model import LanguageModel

from tests.verification.config import GateConfig
from tests.verification.cross_cutting import CrossCuttingCollector
from tests.verification.paths import ArchitecturePath
from tests.verification.reporter import PathResult

logger = logging.getLogger(__name__)

_DEFAULT_QUERY = (
    "Please help me with a simple task: list the first 5 prime numbers "
    "and explain what a prime number is."
)

_TASK_ASSESSOR_INSTRUCTION = (
    "You are a task assessor. Evaluate the current task state and determine "
    "if tasks need decomposition, reanalysis, or can proceed as-is."
)

_TASK_ANALYZER_INSTRUCTION = (
    "You are a task analyzer. Analyze tasks and decompose them into "
    "sub-tasks when needed."
)

_TASK_EXECUTOR_INSTRUCTION = (
    "You are a task executor. Execute the current task by producing "
    "the requested output."
)

_RESULT_REVIEWER_INSTRUCTION = (
    "You are a result reviewer. Review task execution results and "
    "determine if they are acceptable, need retry, require replanning, "
    "or have reached the failure threshold."
)


class _SyncLLMClient:
    """Synchronous LLM client wrapper that delegates to an async agent.

    Bridges the gap between Node._call_llm (sync) and Agent._call_llm (async).
    Records LLM interactions for debugging failed paths.
    """

    def __init__(self, agent: Agent) -> None:
        self._agent = agent
        self._loop: asyncio.AbstractEventLoop | None = None
        self.interactions: list[dict[str, Any]] = []

    def __call__(
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> dict[str, Any]:
        """Synchronous call that wraps the agent's async _call_llm.

        Records the messages sent and response received for debugging.

        Args:
            messages: The message list for the LLM call.
            **kwargs: Additional keyword arguments (ignored).

        Returns:
            Dict response from the LLM.
        """
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()

        async def _call() -> dict[str, Any]:
            return await self._agent._call_llm(messages, None)

        try:
            response = self._loop.run_until_complete(_call())
        except RuntimeError:
            # Event loop already running — create a new one
            self._loop = asyncio.new_event_loop()
            response = self._loop.run_until_complete(_call())

        self.interactions.append(
            {
                "messages": [
                    {"role": m.get("role", ""), "content": m.get("content", "")}
                    for m in messages
                ],
                "response": response,
            }
        )
        return response


def _create_digester(node_id: str, config: NodeConfigBase) -> Any:
    """Create an InformationDigesterNode."""
    from tinycua.loops.information_digester import TinyCUAInformationDigesterNode

    return TinyCUAInformationDigesterNode(node_id=node_id, config=config)


class PathExecutor:
    """Executes a single architecture path using actual TinyCUA nodes.

    Manually orchestrates node execution, calling each node's __call__
    method and handling queue mutations via on_complete.
    """

    def __init__(self, gate_config: GateConfig) -> None:
        """Initialize with GateConfig.

        Args:
            gate_config: Verification gate configuration.
        """
        self._gate_config = gate_config
        self._cross_cutting = CrossCuttingCollector()

    @property
    def cross_cutting(self) -> CrossCuttingCollector:
        """Return the cross-cutting concern collector."""
        return self._cross_cutting

    def execute(
        self,
        path: ArchitecturePath,
        query: str = _DEFAULT_QUERY,
    ) -> PathResult:
        """Execute a single architecture path.

        Args:
            path: The architecture path to execute.
            query: The user query to send.

        Returns:
            PathResult with execution details.
        """
        start_time = time.monotonic()
        timeout = path.timeout_seconds or self._gate_config.default_timeout_seconds

        session = Session()

        llm_model = LanguageModel(
            provider=self._gate_config.provider,
            model_name=self._gate_config.model_name,
            base_url=self._gate_config.base_url,
            api_key=self._gate_config.api_key,
            temperature=0.7,
        )

        agent = Agent(llm_model=llm_model)
        llm_client = _SyncLLMClient(agent)

        # Build initial queue with QueryAnalyst and terminal ResponseNode
        qa = TinyCUAQueryAnalystNode(
            node_id="query_analyst",
            config=NodeConfigBase(
                tool_policy=query_analyst_tool_scope(),
                llm_client=llm_client,
            ),
            classification_labels=["worker", "uncertain", "passthrough"],
        )

        terminal = ResponseNode(
            node_id="response",
            config=NodeConfigBase(
                tool_policy=response_tool_scope(allow_digest=False),
                llm_client=llm_client,
            ),
        )

        queue = NodeQueue()
        queue.items = [qa, terminal]

        # Run setup_fn if provided
        if path.setup_fn is not None:
            path.setup_fn(queue, session, self._gate_config)

        # Inject worker classification if specified
        if path.worker_classification is not None:
            from tinycua.models.session_context_entry import SessionContextEntry

            session.session_context.append(
                SessionContextEntry(
                    content=f"Worker classification: {path.worker_classification}",
                    segment="output",
                )
            )

        # Execute with timeout
        try:
            self._run_execution_loop(
                queue, session, agent, llm_client, query, timeout, path.name
            )
        except TimeoutError:
            elapsed = time.monotonic() - start_time
            return PathResult(
                path_name=path.name,
                status="timeout",
                duration_seconds=elapsed,
                error=f"Path exceeded timeout of {timeout}s",
            )
        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("Path '%s' raised exception: %s", path.name, e)
            import traceback

            return PathResult(
                path_name=path.name,
                status="error",
                duration_seconds=elapsed,
                error=str(e),
                error_traceback=traceback.format_exc(),
            )

        elapsed = time.monotonic() - start_time

        path_result = PathResult(
            path_name=path.name,
            status="pass",
            duration_seconds=elapsed,
            llm_interactions=llm_client.interactions,
            node_outputs=self._capture_node_outputs(queue),
            session_state=self._capture_session_state(session),
        )

        if path.validation_fn is not None:
            path.validation_fn(path_result)

        self._validate_outcome(path, path_result, session)

        cross_cutting_errors = self._cross_cutting.validate()
        if cross_cutting_errors and path_result.status == "pass":
            path_result.status = "fail"
            path_result.error = "Cross-cutting concerns failed: " + "; ".join(
                cross_cutting_errors
            )

        return path_result

    def _run_execution_loop(
        self,
        queue: NodeQueue,
        session: Session,
        agent: Agent,
        llm_client: _SyncLLMClient,
        query: str,
        timeout: float,
        path_name: str,
    ) -> str:
        """Run the node execution loop manually.

        Iterates through the queue, calling each node's __call__ method
        and handling queue mutations via on_complete.

        Args:
            queue: The node queue to execute.
            session: The root session.
            agent: The agent with LLM configuration.
            llm_client: Synchronous LLM client wrapper.
            query: The user query.
            timeout: Timeout in seconds.
            path_name: Name of the path (for logging).

        Returns:
            The final response content.

        Raises:
            TimeoutError: If execution exceeds the timeout.
        """
        import threading

        def _timeout_handler() -> None:
            raise TimeoutError(f"Path '{path_name}' exceeded timeout of {timeout}s")

        _timer = threading.Timer(float(timeout), _timeout_handler)
        _timer.start()

        try:
            last_content = ""
            input_data: NodeInputLike = [{"role": "user", "content": query}]

            while not queue.is_empty():
                node = queue.current
                if node is None:
                    break

                # Wire queue on QueryAnalystNode
                if isinstance(node, TinyCUAQueryAnalystNode):
                    node._queue = queue

                # Ensure node has a session
                node.ensure_session(session)

                # Set input for the node
                if input_data is not None:
                    queue.set_input(node, input_data)

                # Get the node's input
                node_input = queue.input_for_current()

                # Record before-node hook for cross-cutting concerns
                self._cross_cutting.on_before_node(node.node_id, [])

                # Track interactions before node call to capture tool invocations
                interactions_before = len(llm_client.interactions)

                # Call the node's __call__ method
                response = node(node_input)

                # Capture tool invocations from LLM interactions after node call
                tools_invoked = self._extract_tool_invocations(
                    llm_client.interactions[interactions_before:]
                )

                # Validate output — terminal nodes must produce content
                output_valid = self._validate_node_output(node, response)

                # Record after-node hook for cross-cutting concerns
                self._cross_cutting.on_after_node(
                    node.node_id,
                    tools_invoked=tools_invoked,
                    output_valid=output_valid,
                    retry_count=0,
                )

                # Extract content
                if isinstance(response, DecisionResult):
                    content = response.route_label
                elif hasattr(response, "content"):
                    content = response.content
                else:
                    content = str(response)

                last_content = content

                # Record output into root session chat_history
                if content:
                    from tinycua.models.chat_record import ChatRecord

                    session.chat_history.append(
                        ChatRecord(
                            role="assistant",
                            content=content,
                            source_node_id=node.node_id,
                            source_session_id=getattr(node.session, "session_id", ""),
                        )
                    )

                # Fire on_complete for queue mutations
                node.on_complete(queue, response)

                # Check if terminal
                if node.is_terminal:
                    break

                # Record context propagation event
                if len(queue.items) > 1:
                    next_node = queue.items[1]
                    self._cross_cutting.on_propagation(
                        source_node=node.node_id,
                        target_node=next_node.node_id,
                        context_type="session_context",
                    )

                # Advance queue (propagate + forward output)
                queue.advance()

                # Wire on_dedupe: compute duplicates removed during forwarding.
                if not queue.is_empty() and queue.current is not None:
                    duplicates_removed = self._check_dedupe(node, queue.current)
                    if duplicates_removed > 0:
                        self._cross_cutting.on_dedupe(node.node_id, duplicates_removed)

                # Get input for next node from the advanced queue
                if not queue.is_empty() and queue.current is not None:
                    # The next node's input was set by advance() or on_complete
                    input_data = queue.input_for_current()
                else:
                    input_data = None

            return last_content
        finally:
            _timer.cancel()

    def _capture_node_outputs(
        self,
        queue: NodeQueue,
    ) -> dict[str, Any]:
        """Capture outputs from all executed nodes."""
        outputs: dict[str, Any] = {}
        for node in queue.items:
            if node.session is not None:
                outputs[node.node_id] = {
                    "chat_history_length": len(node.session.chat_history),
                    "session_context_length": len(node.session.session_context),
                }
        return outputs

    def _capture_session_state(
        self,
        session: Session,
    ) -> dict[str, Any]:
        """Capture the final session state."""
        return {
            "session_id": session.session_id,
            "chat_history_length": len(session.chat_history),
            "session_context_length": len(session.session_context),
            "input_context_length": len(session.input_context),
        }

    def _extract_tool_invocations(
        self,
        interactions: list[dict[str, Any]],
    ) -> list[str]:
        """Extract tool names from LLM interactions.

        Inspects the response from each interaction for tool_calls,
        which indicate tools that were actually invoked during node execution.

        Args:
            interactions: List of LLM interaction records.

        Returns:
            List of unique tool names invoked.
        """
        tools_invoked: list[str] = []
        seen: set[str] = set()

        for interaction in interactions:
            response = interaction.get("response", {})
            tool_calls = response.get("tool_calls") or []
            for tool_call in tool_calls:
                # tool_calls can be in OpenAI format: {"function": {"name": "..."}}
                if isinstance(tool_call, dict):
                    func = tool_call.get("function", {})
                    if isinstance(func, dict):
                        tool_name = func.get("name", "")
                        if tool_name and tool_name not in seen:
                            tools_invoked.append(tool_name)
                            seen.add(tool_name)

        return tools_invoked

    def _check_dedupe(self, source_node: Node, next_node: Node) -> int:
        """Count duplicate context records removed during forwarding."""
        if next_node.session is None or source_node.session is None:
            return 0
        from tinycua.loops.propagation import forward_output_to_next, dedupe_records

        forwarded = forward_output_to_next(source_node.session)
        if not forwarded:
            return 0
        unique = dedupe_records(forwarded, next_node.session.session_context)
        return len(forwarded) - len(unique)

    def _validate_node_output(self, node: Any, response: Any) -> bool:
        """Validate that a node produced valid output.

        Terminal nodes must produce non-empty content. Non-terminal nodes
        are always considered valid (empty output is acceptable for
        intermediate nodes that just propagate context).

        Args:
            node: The node that was executed.
            response: The node's response.

        Returns:
            True if output is valid, False otherwise.
        """
        if not node.is_terminal:
            return True

        if isinstance(response, DecisionResult):
            content = response.route_label
        elif hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)

        return bool(content and content.strip())

    def _validate_outcome(
        self,
        path: ArchitecturePath,
        result: PathResult,
        session: Session,
    ) -> None:
        """Validate that the path outcome matches expectations."""
        if path.expected_outcome == "success":
            if result.status == "pass" and len(session.chat_history) == 0:
                result.status = "fail"
                result.error = "Expected successful response but chat_history is empty"
        elif path.expected_outcome == "hitl":
            # HITL: agent stays active, no terminal response node should execute.
            # If the path completed with a terminal response, it failed to
            # maintain human-in-the-loop behavior.
            if result.status == "pass" and "response" in path.node_sequence:
                result.status = "fail"
                result.error = (
                    "Expected HITL (agent stays active) but got terminal response"
                )
        elif path.expected_outcome == "failure":
            # Failure: path should not produce a successful response.
            if result.status == "pass":
                result.status = "fail"
                result.error = "Expected failure but path completed successfully"
