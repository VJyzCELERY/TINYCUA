"""TinyCUA execution loop extending SDK BaseLoop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from tinycua_sdk.agent.loop import BaseLoop

from tinycua.config.system_prompt import SystemPromptBuilder
from tinycua.config.types import LLMResult
from tinycua.loops.node import DecisionNode, DecisionResult, ProcessNode
from tinycua.loops.node_queue import NodeQueue
from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode
from tinycua.loops.response_node import TinyCUAResponseNode
from tinycua.loops.result_aggregation import TinyCUAResultAggregationNode
from tinycua.loops.worker import TinyCUAWorkerNode
from tinycua.models.classification import MandatoryPassthrough
from tinycua.models.node_input import NodeInput
from tinycua.models.reviewer_decision import ReviewerRetryState
from tinycua.models.session import Session
from tinycua.models.task import ReviewerDecision, Task, TaskResult

from tinycua.config.session_config import SessionConfig

if TYPE_CHECKING:
    from tinycua.loops.node import Node
    from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode
    from tinycua_sdk.agent.agent import Agent
    from tinycua_sdk.tools.decorators import Tool

logger = logging.getLogger(__name__)


class TinyCUALoop(BaseLoop):
    """Execution loop for TinyCUA agents.

    Extends the SDK BaseLoop with node-based execution, session management,
    chat history recording, message merging, tool scoping, and streaming.
    """

    def __init__(
        self,
        root_session: Session | None = None,
        queue: NodeQueue | None = None,
        session_config: SessionConfig | None = None,
        max_iterations: int = 50,
        default_terminal_node: Node | None = None,
    ) -> None:
        """Initialize TinyCUALoop.

        Args:
            root_session: The root session for this loop. Created if not provided.
            queue: Node queue for execution. Created if not provided.
            session_config: Session configuration to apply.
                **Important**: If ``session_config.llm_client`` is None (the default),
                custom ``ProcessNode.__call__`` logic (e.g., TaskExecutor's ReAct loop
                and ResultReviewer's decision parsing) is **bypassed** — the loop falls
                back to ``agent._call_llm()`` instead. Set
                ``SessionConfig(llm_client=<client>)`` to enable custom node behavior.
                See design.md Decision #7 for details.
            max_iterations: Maximum loop iterations before forced stop.
            default_terminal_node: Default terminal node for ensure_terminal() bootstrap.
        """
        super().__init__(max_iterations=max_iterations)
        self.root_session = root_session or Session()
        self.session_config = (
            session_config if session_config is not None else SessionConfig()
        )
        self.default_terminal_node = default_terminal_node
        self.root_task: Task | None = None
        self._active_task_id: str | None = None
        self._reviewer_retry_state: ReviewerRetryState = ReviewerRetryState()
        self._pending_mandatory_passthrough: MandatoryPassthrough | None = None

        if self.session_config.llm_client is None:
            logger.warning(
                "TinyCUALoop created without llm_client in session_config — "
                "ProcessNode custom logic (ReAct loops, decision parsing) will "
                "be bypassed. Set SessionConfig(llm_client=<client>) to enable "
                "custom node behavior. See design.md Decision #7."
            )

        if queue is not None:
            self.queue = queue
        else:
            query_analyst = TinyCUAQueryAnalystNode()
            response_node = TinyCUAResponseNode()
            self.queue = NodeQueue(items=[query_analyst, response_node])

    async def run(
        self,
        agent: Agent,
        messages: list[dict[str, Any]],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        """Execute the loop with node-based execution.

        Merges SDK messages into root_session.input_context, then
        iterates through the node queue executing each node via
        agent._call_llm().

        Args:
            agent: The agent executing.
            messages: List of message dicts.
            tools: Available tools.
            override_instructions: Optional instructions override.
            stream: When True, returns an async iterator of stream events.

        Returns:
            Final response string when stream=False, or an async iterator
            of event dicts when streaming.
        """
        # Merge SDK messages into root session input context (FR-005)
        # Note: User messages are NOT recorded in chat_history here because
        # they are already stored in input_context and passed to nodes via
        # _build_node_messages(). Recording them in chat_history as well would
        # cause duplication when include_chat_history=True.
        self.root_session.input_context = list(messages)

        # Ensure terminal safety at queue bootstrap
        if self.default_terminal_node is not None:
            self.queue.ensure_terminal(self.default_terminal_node)

        if stream:
            return self._run_stream(agent, tools, override_instructions)

        return await self._run_sync(agent, tools, override_instructions)

    async def _run_sync(
        self,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> str:
        """Run in non-streaming mode: iterate through node queue.

        For each node, builds messages, calls agent._call_llm(),
        records chat_history and session_context, and advances the queue.

        Args:
            agent: The agent executing.
            tools: Available tools.
            override_instructions: Optional instructions override.

        Returns:
            The final response content string.
        """
        # If a mandatory passthrough is pending, ensure QueryAnalyst is at front
        # so the passthrough injection in _execute_decision_node is reachable.
        if self._pending_mandatory_passthrough is not None:
            self._ensure_query_analyst_at_front()

        last_content = ""
        iterations = 0

        while not self.queue.is_empty():
            if iterations >= self.max_iterations:
                logger.warning(
                    "max_iterations=%d reached, breaking loop",
                    self.max_iterations,
                )
                break

            node = self.queue.current
            if node is None:
                break

            content, should_advance = await self._execute_node(
                node,
                agent,
                tools,
                override_instructions,
            )
            last_content = content
            iterations += 1

            # Stop at terminal nodes — do not advance past them
            if node.is_terminal:
                break

            # Advance queue unless node requested to stay active
            # (e.g., "uncertain" classification keeps QueryAnalyst active)
            if should_advance:
                self.queue.advance()

        return last_content

    def _prepare_node(
        self,
        node: Node,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[Tool]]:
        """Prepare a node for execution: attach session, build messages, resolve tools.

        Args:
            node: The node to prepare.
            tools: Available tools from the agent.
            override_instructions: Optional instructions override.

        Returns:
            Tuple of (messages, resolved_tools) ready for LLM call.
        """
        node.ensure_session(self.root_session)
        messages = self._build_node_messages(node, override_instructions)
        resolved_tools = node.config.tool_policy.resolve_tools(tools)
        return messages, resolved_tools

    def _build_node_input(self, node: Node) -> NodeInput:
        """Build a NodeInput from the root session's input context.

        Constructs a NodeInput envelope so node.__call__() receives
        structured input with metadata (e.g., active_task).

        Args:
            node: The node that will receive the input.

        Returns:
            NodeInput constructed from the root session input context.
        """
        messages: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        if self.root_session.input_context:
            for msg in self.root_session.input_context:
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )
                if "metadata" in msg:
                    metadata.update(msg["metadata"])
        # Inject active task so TaskExecutor/ResultReviewer can access it
        active_task = self.get_active_task()
        if active_task is not None:
            metadata["active_task"] = active_task
        return NodeInput(
            input_type="continuation", messages=messages, metadata=metadata
        )

    def _record_node_output(
        self,
        node: Node,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        """Record node output in chat_history and session_context.

        Args:
            node: The node that produced output.
            content: The response content string.
            tool_calls: Optional list of tool call dicts.
        """
        if content:
            self.root_session.chat_history.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

        llm_result = LLMResult(
            content=content,
            role="assistant",
            tool_calls=tool_calls or [],
        )
        node.record_output(llm_result)

    async def _run_stream(
        self,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run in streaming mode: iterate through node queue, yield events.

        For each node, builds messages, calls agent._call_llm(stream=True),
        yields stream events, records chat_history and session_context.

        Args:
            agent: The agent executing.
            tools: Available tools.
            override_instructions: Optional instructions override.

        Yields:
            Stream event dicts from the LLM.
        """
        # If a mandatory passthrough is pending, ensure QueryAnalyst is at front
        # so the passthrough injection in _execute_decision_node is reachable.
        if self._pending_mandatory_passthrough is not None:
            self._ensure_query_analyst_at_front()

        iterations = 0

        while not self.queue.is_empty():
            if iterations >= self.max_iterations:
                logger.warning(
                    "max_iterations=%d reached, breaking stream loop",
                    self.max_iterations,
                )
                break

            node = self.queue.current
            if node is None:
                break

            # DecisionNode subclasses: two-step classification via agent._call_llm()
            # Note: streaming not supported for two-step classification;
            # fall back to sync-like flow using agent._call_llm() without stream.
            if isinstance(node, DecisionNode):
                content, should_advance, _decision = await self._execute_decision_node(
                    node,
                    agent,
                    tools,
                    override_instructions,
                )
                iterations += 1
                if node.is_terminal:
                    break
                if should_advance:
                    self.queue.advance()
                continue

            messages, resolved_tools = self._prepare_node(
                node,
                tools,
                override_instructions,
            )

            # Stream from agent._call_llm() and yield events
            content_parts: list[str] = []
            collected_tool_calls: list[dict[str, Any]] = []
            async for event in agent._call_llm(messages, resolved_tools, stream=True):  # type: ignore[arg-type]
                if event.get("type") == "response.output_text.delta":
                    content_parts.append(event.get("delta", ""))
                if event.get("type") == "response.tool_call":
                    collected_tool_calls.append(event)
                yield event

            combined = "".join(content_parts)
            self._record_node_output(node, combined, collected_tool_calls)
            iterations += 1

            # Stop at terminal nodes — do not advance past them
            if node.is_terminal:
                break

            # Advance queue (calls propagate on current node)
            self.queue.advance()

    async def _execute_decision_node(
        self,
        node: DecisionNode,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> tuple[str, bool, DecisionResult]:
        """Execute a DecisionNode with two-step analysis + classification.

        Performs the analysis call → classification call → route dispatch flow
        using agent._call_llm(), with retry logic for invalid labels.

        For QueryAnalyst nodes, checks mandatory_passthrough first (FR-005/FR-006).

        Args:
            node: The DecisionNode to execute.
            agent: The agent executing.
            tools: Available tools from the agent.
            override_instructions: Optional instructions override.

        Returns:
            Tuple of (content, should_advance, decision_result).
        """
        node.ensure_session(self.root_session)

        # Provide queue reference and adjust labels dynamically (WorkerNode)
        if isinstance(node, TinyCUAWorkerNode):
            node._queue = self.queue
            node._loop = self
            node.classification_labels = node._get_classification_labels(self.queue)

        # Precheck: mandatory_passthrough for QueryAnalyst (FR-005/FR-006)
        if isinstance(node, TinyCUAQueryAnalystNode):
            input_data = self._build_query_analyst_input()
            had_pending = self._pending_mandatory_passthrough is not None
            # Inject pending mandatory passthrough into metadata if present
            if self._pending_mandatory_passthrough is not None:
                input_data.metadata["mandatory_passthrough"] = self._pending_mandatory_passthrough
            mandatory = node.check_mandatory_passthrough(input_data)
            if mandatory is not None:
                logger.info(
                    "node=%s mandatory_passthrough detected in loop, bypassing LLM",
                    node.node_id,
                )
                from tinycua.models.classification import PASSTHROUGH

                passthrough_content = (
                    f"[Passthrough] target={mandatory.target_node_id} "
                    f"reason={mandatory.reason}"
                )
                self._record_node_output(node, passthrough_content)
                decision = DecisionResult(
                    route_label=PASSTHROUGH,
                    analysis_response=LLMResult(content="", role="assistant"),
                    classification_response=LLMResult(
                        content=PASSTHROUGH, role="assistant"
                    ),
                )
                node.on_complete(self.queue, decision)
                # Clear passthrough after successful forward
                self._clear_mandatory_passthrough()
                return passthrough_content, True, decision

            # If a pending passthrough was injected but check_mandatory_passthrough
            # returned None (stale/expired), clear it so the loop doesn't keep
            # attempting to restart on subsequent runs.
            if had_pending:
                logger.info(
                    "node=%s stale pending mandatory_passthrough detected and cleared",
                    node.node_id,
                )
                self._clear_mandatory_passthrough()

        messages, resolved_tools = self._prepare_node(
            node,
            tools,
            override_instructions,
        )

        async def _analyze(msgs: list[dict[str, str]]) -> LLMResult:
            raw = await agent._call_llm(msgs, resolved_tools)  # type: ignore[arg-type]
            return LLMResult(content=raw.get("content") or "", role="assistant")

        async def _classify(
            msgs: list[dict[str, str]],
            analysis: LLMResult,
        ) -> LLMResult:
            classification_messages = list(msgs)
            classification_messages.append(
                {"role": "assistant", "content": analysis.content}
            )
            labels_str = ", ".join(node.classification_labels)
            classification_messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Classify your analysis into one of these categories: "
                        f"{labels_str}. Respond with only the category label."
                    ),
                }
            )
            raw = await agent._call_llm(  # type: ignore[arg-type]
                classification_messages,
                resolved_tools,
            )
            return LLMResult(
                content=raw.get("content") or "",
                role="assistant",
            )

        decision = await node._execute_with_retry(  # type: ignore[misc]
            messages,
            analyze=_analyze,
            classify=_classify,
        )

        content = (
            f"[Analysis] {decision.analysis_response.content}\n"
            f"[Classification] {decision.route_label}"
        )
        self._record_node_output(node, content)
        node.on_complete(self.queue, decision)

        should_advance = decision.route_label != "uncertain"
        return content, should_advance, decision

    async def _execute_node(
        self,
        node: Node,
        agent: Agent,
        tools: list[Tool],
        override_instructions: str | None = None,
    ) -> tuple[str, bool]:
        """Execute a single node and return (content, should_advance).

        For DecisionNode subclasses (including QueryAnalyst), performs the
        two-step analysis + classification flow using agent._call_llm(),
        then dispatches routes via node.on_complete() (FR-008, FR-010-015).

        For other nodes, builds messages and calls agent._call_llm() directly.

        The should_advance flag indicates whether the queue should advance
        after this node completes. For "uncertain" classification, the
        QueryAnalyst remains active and the queue should NOT advance.

        Args:
            node: The node to execute.
            agent: The agent executing.
            tools: Available tools from the agent.
            override_instructions: Optional instructions override.

        Returns:
            Tuple of (response content string, should_advance flag).
        """
        # DecisionNode subclasses: two-step analysis + classification + route dispatch
        if isinstance(node, DecisionNode):
            content, should_advance, _decision = await self._execute_decision_node(
                node,
                agent,
                tools,
                override_instructions,
            )
            return content, should_advance

        # Non-decision nodes: delegate to node.__call__() so custom logic
        # (ReAct loops, decision parsing, active_task extraction) runs.
        # Terminal nodes: TinyCUAResponseNode uses __call__ for three-phase
        # execution (context sufficiency → digester/tools → synthesis);
        # other terminals use the default LLM call path.
        if node.is_terminal:
            if isinstance(node, TinyCUAResponseNode):
                # Check if the node has its own LLM client for three-phase
                # execution. If not, fall back to agent._call_llm().
                effective_llm_client = getattr(node.config, "llm_client", None) or getattr(
                    self.session_config, "llm_client", None
                )
                if effective_llm_client is not None:
                    # Inject client and delegate to __call__ for three-phase
                    original_client = getattr(node.config, "llm_client", None)
                    if original_client is None and hasattr(node.config, "llm_client"):
                        node.config.llm_client = effective_llm_client
                    try:
                        node.ensure_session(self.root_session)
                        input_data = self._build_node_input(node)
                        result = await asyncio.to_thread(node, input_data)
                        if isinstance(result, LLMResult):
                            llm_result = result
                        else:
                            llm_result = LLMResult(content=str(result), role="assistant")
                    finally:
                        if original_client is None and hasattr(node.config, "llm_client"):
                            node.config.llm_client = None
                else:
                    # No LLM client — use the default terminal path via
                    # agent._call_llm() so tests and fallback scenarios work.
                    messages, resolved_tools = self._prepare_node(
                        node,
                        tools,
                        override_instructions,
                    )
                    response = await agent._call_llm(messages, resolved_tools)  # type: ignore[arg-type]
                    llm_result = LLMResult(
                        content=response.get("content") or "",
                        role=response.get("role", "assistant"),
                        tool_calls=response.get("tool_calls", []),
                        metadata=response.get("metadata", {}),
                    )
                content = llm_result.content or ""
            else:
                # Default terminal path for non-ResponseNode terminals
                messages, resolved_tools = self._prepare_node(
                    node,
                    tools,
                    override_instructions,
                )
                response = await agent._call_llm(messages, resolved_tools)  # type: ignore[arg-type]
                content = response.get("content") or ""
                llm_result = LLMResult(
                    content=content,
                    role=response.get("role", "assistant"),
                    tool_calls=response.get("tool_calls", []),
                    metadata=response.get("metadata", {}),
                )
        else:
            node.ensure_session(self.root_session)
            # Delegate to node.__call__() if the node has its own LLM client,
            # so custom logic (ReAct loops, decision parsing) runs.
            # Fall back to agent._call_llm() for nodes without a configured
            # client (e.g. test stubs, nodes relying on agent transport).
            # Check node.config.llm_client first, then fall back to
            # session_config.llm_client (the default production path when
            # SessionConfig has an llm_client set — see design.md Decision #7).
            effective_llm_client = getattr(node.config, "llm_client", None) or getattr(
                self.session_config, "llm_client", None
            )
            if effective_llm_client is not None:
                # Temporarily inject the effective client so node.__call__ can use it
                original_client = getattr(node.config, "llm_client", None)
                if original_client is None and hasattr(node.config, "llm_client"):
                    node.config.llm_client = effective_llm_client
                try:
                    input_data = self._build_node_input(node)
                    result = await asyncio.to_thread(node, input_data)
                    # Node __call__ may return LLMResult or plain str (test stubs)
                    if isinstance(result, LLMResult):
                        llm_result = result
                    else:
                        llm_result = LLMResult(content=str(result), role="assistant")
                finally:
                    # Restore original client state if we injected one
                    if original_client is None and hasattr(node.config, "llm_client"):
                        node.config.llm_client = None
            else:
                if (
                    hasattr(node, "__call__")
                    and type(node).__call__ is not ProcessNode.__call__
                ):
                    logger.error(
                        "Fallback path: node %s overrides ProcessNode.__call__ "
                        "but neither node.config.llm_client nor "
                        "session_config.llm_client is set — custom logic "
                        "(ReAct loops, decision parsing) will be bypassed. "
                        "To fix: set SessionConfig.llm_client or "
                        "node.config.llm_client.",
                        node.node_id,
                    )
                messages, resolved_tools = self._prepare_node(
                    node,
                    tools,
                    override_instructions,
                )
                response = await agent._call_llm(messages, resolved_tools)  # type: ignore[arg-type]
                llm_result = LLMResult(
                    content=response.get("content") or "",
                    role=response.get("role", "assistant"),
                    tool_calls=response.get("tool_calls", []),
                    metadata=response.get("metadata", {}),
                )
            content = llm_result.content or ""

        self._record_node_output(node, content, llm_result.tool_calls)
        node.on_complete(self.queue, llm_result)

        return content, True

    def _build_query_analyst_input(self) -> NodeInput:
        """Build a NodeInput from the root session's input context for mandatory_passthrough checks.

        Converts the current input context messages into a NodeInput
        so QueryAnalyst can inspect metadata for mandatory_passthrough.

        Returns:
            NodeInput constructed from the root session input context.
        """
        messages: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {}
        if self.root_session.input_context:
            for msg in self.root_session.input_context:
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )
                if "metadata" in msg:
                    metadata.update(msg["metadata"])
        return NodeInput(
            input_type="continuation", messages=messages, metadata=metadata
        )

    def _build_node_messages(
        self,
        node: Node,
        override_instructions: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build messages for a node's LLM call.

        Assembles system instruction (with override support),
        session context, chat history, and node-specific instruction.

        Args:
            node: The node to build messages for.
            override_instructions: Optional instructions override.

        Returns:
            List of message dictionaries for the LLM call.
        """
        messages: list[dict[str, Any]] = []

        # Build system message via SystemPromptBuilder
        builder = SystemPromptBuilder()
        instruction = node.build_instruction(override_instructions)
        if instruction:
            builder.add_static(instruction)

        system_msg = builder.build()
        if system_msg["content"]:
            messages.append(system_msg)

        # Add session context if policy says so
        if (
            node.config.message_policy.include_session_context
            and self.root_session.session_context
        ):
            messages.extend(
                {
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in self.root_session.session_context
            )

        # Add chat history if policy says so
        if (
            node.config.message_policy.include_chat_history
            and self.root_session.chat_history
        ):
            messages.extend(
                {
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in self.root_session.chat_history
            )

        # Add input context (merged SDK messages) as continuation
        if self.root_session.input_context:
            messages.extend(
                {
                    "role": m["role"],
                    "content": m["content"],
                }
                for m in self.root_session.input_context
            )

        return messages

    def get_active_task(self) -> Task | None:
        """Find the active task via DFS pre-order traversal.

        Uses _active_task_id as a traversal hint when set.
        Uses active_child_id hints to resume from a specific child when available.
        Updates active_child_id lazily during traversal.

        Returns:
            The first unfinished task, or None if all tasks are complete.
        """
        if self.root_task is None:
            return None

        # If _active_task_id is set, try to find that task first
        if self._active_task_id is not None:
            task = self._find_task_by_id(self.root_task, self._active_task_id)
            if task is not None and task.status not in ("done", "failed"):
                return task
            # If task not found or already done, clear the hint and fall through
            self._active_task_id = None

        return self._dfs_find_active(self.root_task)

    def _dfs_find_active(self, task: Task) -> Task | None:
        """Internal DFS helper to find the first unfinished task.

        Algorithm (DFS pre-order, children-first):
        1. Search children first (prefer hint via active_child_id).
        2. For each child, recurse with _dfs_find_active.
        3. If any child returns a task, return it immediately.
        4. If no child returned a task (all children done or no children):
           a. If this task is unfinished (status in {pending, in_progress, blocked}),
              return this task.
           b. Otherwise, return None.

        Args:
            task: The subtree root to search.

        Returns:
            The first unfinished task in DFS pre-order, or None.
        """
        # 1. Search children first (with active_child_id hint)
        if task.children:
            # If there's an active_child_id hint, try that child first
            if task.active_child_id is not None:
                for child in task.children:
                    if child.task_id == task.active_child_id:
                        result = self._dfs_find_active(child)
                        if result is not None:
                            # Update the hint to point to the selected child
                            task.active_child_id = child.task_id
                            return result
                # Hint was invalid — fall through to standard DFS

            # Standard DFS: iterate children in order
            for child in task.children:
                result = self._dfs_find_active(child)
                if result is not None:
                    # Update hint to point to the first unfinished child
                    # (only write if changed to avoid unnecessary overwrites)
                    if task.active_child_id != child.task_id:
                        task.active_child_id = child.task_id
                    return result

        # 2. If no child returned an active task, check this task
        if task.status not in ("done", "failed"):
            return task

        # 3. Return None if all complete
        return None

    def set_active_task(self, task_id: str) -> None:
        """Explicitly set the active task by ID.

        Args:
            task_id: The task_id to set as active.

        Raises:
            ValueError: If task_id is not found in the task tree.
        """
        task = self._find_task_by_id(self.root_task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        self._active_task_id = task_id

    def _find_task_by_id(self, root: Task | None, task_id: str) -> Task | None:
        """Find a task by ID in the tree (DFS).

        Args:
            root: The subtree root to search.
            task_id: The task_id to find.

        Returns:
            The task if found, else None.
        """
        if root is None:
            return None
        if root.task_id == task_id:
            return root
        for child in root.children:
            found = self._find_task_by_id(child, task_id)
            if found is not None:
                return found
        return None

    def update_active_task_result(self, result: TaskResult) -> None:
        """Update the active task's result field.

        Args:
            result: The TaskResult to assign to the active task.

        Raises:
            ValueError: If no active task, or result.task_id doesn't match active task.
        """
        active = self.get_active_task()
        if active is None:
            raise ValueError("No active task to update")
        if result.task_id != active.task_id:
            raise ValueError(
                f"Result task_id '{result.task_id}' does not match "
                f"active task_id '{active.task_id}'"
            )
        active.result = result

    def _on_reviewer_accept(self, active_task: Task) -> bool:
        """Mark active task as done, reset retry counter, and check if root task is complete.

        Walks up the parent chain marking parent tasks as done when all their
        children complete. Resets the retry counter since the task was accepted.
        Does NOT recompute the next active task — callers should call
        get_active_task() after this method returns.

        Returns True if root task is done (should route to aggregation),
        False otherwise (caller should route to next active task via
        get_active_task()).

        Args:
            active_task: The task that was accepted.

        Returns:
            True if root task is done, False otherwise.
        """
        # Reset retry counter on accept
        self._reviewer_retry_state.reset()

        # Set reviewer_decision per design spec (step 1)
        if active_task.result is not None:
            active_task.result.reviewer_decision = ReviewerDecision(outcome="accept")

        # Mark this task as done
        active_task.status = "done"

        # Walk up parent chain
        self._walk_parent_chain_done(active_task)

        # Check if root is done
        return self._is_root_task_done()

    _MAX_PARENT_WALK_DEPTH = 100

    def _walk_parent_chain_done(self, task: Task, _depth: int = 0) -> None:
        """Walk up parent chain marking parents done when all children complete.

        Note: This is a best-effort parent walk. In a tree without parent pointers,
        we need to traverse from root each time. For simplicity, we check if all
        siblings of the task are done, then mark the parent done recursively.

        Args:
            task: The task that was just completed.
            _depth: Current recursion depth (used for cycle detection).
        """
        if _depth >= self._MAX_PARENT_WALK_DEPTH:
            logger.error("Parent walk exceeded max depth (%d); possible cycle", _depth)
            return

        # Find parent of this task by traversing from root
        parent = self._find_parent(self.root_task, task.task_id)
        if parent is None:
            return  # task is root or not found

        # Check if all children of parent are done
        all_done = all(child.status in ("done", "failed") for child in parent.children)
        if all_done:
            parent.status = "done"
            # Recurse up
            self._walk_parent_chain_done(parent, _depth + 1)

    def _find_parent(self, root: Task | None, child_id: str) -> Task | None:
        """Find the parent of a task by child_id.

        Args:
            root: The subtree root to search.
            child_id: The task_id of the child to find parent for.

        Returns:
            The parent task if found, else None.
        """
        if root is None:
            return None
        for child in root.children:
            if child.task_id == child_id:
                return root
            found = self._find_parent(child, child_id)
            if found is not None:
                return found
        return None

    def _on_reviewer_retry(self, active_task: Task) -> None:
        """Preserve active task on retry decision.

        Increments the retry counter and logs a warning if threshold is
        reached. Preserves the active task for re-execution.

        Args:
            active_task: The task that should be retried.
        """
        self._reviewer_retry_state.increment()
        if self._reviewer_retry_state.is_threshold_reached():
            logger.warning(
                "reviewer retry threshold reached: retry_count=%d threshold=%d",
                self._reviewer_retry_state.retry_count,
                self._reviewer_retry_state.threshold,
            )
        logger.info(
            "reviewer_retry task_id=%s retry_count=%d",
            active_task.task_id,
            self._reviewer_retry_state.retry_count,
        )

    def _on_reviewer_replan(self, active_task: Task) -> None:
        """Handle replan decision: log event, preserve active task.

        Queue mutation is owned by ResultReviewer.on_complete per the
        design doc (design.md:397-408):
        - clear_after_current()
        - spawn TaskAssessor + TaskAnalyzer + TaskExecutor
        - ensure_terminal(terminal_node)

        This handler only logs and preserves the active task (by doing nothing
        to it). See ResultReviewer.on_complete for the full dispatch.

        Args:
            active_task: The active task to preserve (NOT modified here).
        """
        logger.info(
            "reviewer_replan task_id=%s — queue mutation handled by ResultReviewer.on_complete",
            active_task.task_id,
        )

    def _install_mandatory_passthrough(self, mandatory: MandatoryPassthrough) -> None:
        """Store a MandatoryPassthrough directive on the loop, replacing any existing one.

        Args:
            mandatory: The MandatoryPassthrough directive to store.
        """
        if self._pending_mandatory_passthrough is not None:
            logger.info(
                "mandatory_passthrough replacing existing: old_target=%s new_target=%s",
                self._pending_mandatory_passthrough.target_node_id,
                mandatory.target_node_id,
            )
        self._pending_mandatory_passthrough = mandatory
        logger.info(
            "mandatory_passthrough installed: target_node_id=%s target_session_id=%s reason=%s",
            mandatory.target_node_id,
            mandatory.target_session_id,
            mandatory.reason,
        )

    def _clear_mandatory_passthrough(self) -> None:
        """Remove the pending mandatory passthrough directive."""
        self._pending_mandatory_passthrough = None

    def _find_result_reviewer(self) -> TinyCUAResultReviewerNode | None:
        """Find the active ResultReviewer node in the queue.

        Scans ``self.queue.items`` for ``TinyCUAResultReviewerNode``
        instances and returns the first match.

        Returns:
            The first ResultReviewer node found, or None if not found.
        """
        # Local import to avoid circular dependency
        from tinycua.loops.result_reviewer import TinyCUAResultReviewerNode

        for item in self.queue.items:
            if isinstance(item, TinyCUAResultReviewerNode):
                return item
        return None

    def _ensure_query_analyst_at_front(self) -> None:
        """Ensure QueryAnalyst is at the front of the queue.

        If QueryAnalyst is already at ``items[0]``, this is a no-op.
        If found elsewhere in the queue, moves it to front.
        If not found at all (already popped), creates a fresh
        ``TinyCUAQueryAnalystNode`` and prepends it.
        """
        # Local import to avoid circular dependency
        from tinycua.loops.query_analyst import TinyCUAQueryAnalystNode

        # If already at front, no-op
        if self.queue.items and isinstance(self.queue.items[0], TinyCUAQueryAnalystNode):
            return

        # Find QA elsewhere in queue and move to front
        for i, item in enumerate(self.queue.items):
            if isinstance(item, TinyCUAQueryAnalystNode):
                self.queue.items.pop(i)
                self.queue.items.insert(0, item)
                logger.info(
                    "mandatory_passthrough: moved QueryAnalyst to queue front (index=%d)",
                    i,
                )
                return

        # Not found — create fresh QA and prepend
        fresh_qa = TinyCUAQueryAnalystNode()
        self.queue.items.insert(0, fresh_qa)
        logger.info(
            "mandatory_passthrough: created fresh QueryAnalyst at queue front",
        )

    def _on_reviewer_open_question(self, active_task: Task | None) -> None:
        """Handle open_question decision by installing a MandatoryPassthrough.

        If ``active_task`` is None, logs a warning and returns without
        installing a passthrough. Otherwise, finds the active
        ResultReviewer in the queue and installs a MandatoryPassthrough
        targeting its node and session.

        Args:
            active_task: The active task that triggered the open_question,
                or None if no active task exists.
        """
        if active_task is None:
            logger.warning(
                "reviewer_open_question called with None active_task — "
                "no passthrough installed",
            )
            return

        reviewer = self._find_result_reviewer()
        if reviewer is not None and reviewer.session is not None:
            mandatory = MandatoryPassthrough(
                target_node_id=reviewer.node_id,
                target_session_id=reviewer.session.session_id,
                reason="open_question",
                allow_query_analyst_restart=True,
            )
            self._install_mandatory_passthrough(mandatory)
            logger.info(
                "reviewer_open_question task_id=%s — "
                "mandatory_passthrough installed targeting node=%s session=%s",
                active_task.task_id,
                reviewer.node_id,
                reviewer.session.session_id,
            )
        else:
            logger.warning(
                "reviewer_open_question task_id=%s — "
                "no ResultReviewer found in queue, skipping",
                active_task.task_id,
            )

    def _is_root_task_done(self) -> bool:
        """Check if root task and all children are complete.

        Returns:
            True if root task status is 'done' or 'failed' and all children
            are also 'done' or 'failed'.
        """
        if self.root_task is None:
            return False
        if self.root_task.status not in ("done", "failed"):
            return False
        # Check all children recursively
        return self._is_subtree_done(self.root_task)

    def _is_subtree_done(self, task: Task) -> bool:
        """Check if a task and all its descendants are complete.

        Args:
            task: The subtree root to check.

        Returns:
            True if task and all descendants are 'done' or 'failed'.
        """
        if task.status not in ("done", "failed"):
            return False
        for child in task.children:
            if not self._is_subtree_done(child):
                return False
        return True

    def _route_to_aggregation(self, queue: NodeQueue) -> None:
        """Route to aggregation: clear queue after current, spawn aggregation then response nodes, and ensure the queue ends with a terminal node.

        Called by ``ResultReviewer.on_complete`` when ``_on_reviewer_accept``
        returns ``True`` (root task is done).

        Args:
            queue: The node queue to mutate.
        """
        aggregation_node = TinyCUAResultAggregationNode(loop=self)
        response_node = TinyCUAResponseNode()
        queue.clear_after_current()
        queue.spawn_after_current([aggregation_node, response_node])
        queue.ensure_terminal(response_node)
        logger.info(
            "node=result_reviewer _route_to_aggregation — "
            "spawned result_aggregation + response nodes"
        )
