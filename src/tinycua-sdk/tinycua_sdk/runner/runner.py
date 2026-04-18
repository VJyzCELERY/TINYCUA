"""Runner for local agent execution."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Union

import httpx

from tinycua_sdk.clients import ResponsesClient
from tinycua_sdk.models import ResponseRequest, RunResult, TaskPlan, ToolCall, TodoItem
from tinycua_sdk.models.result import PlanRunResult
from tinycua_sdk.models.response import StreamEvent, StreamEventType
from tinycua_sdk.tools import Tool
from tinycua_sdk.agent import Agent

logger = logging.getLogger(__name__)

DEFAULT_BASE_URLS = {
    "lmstudio": "http://localhost:1234/v1",
    "ollama": "http://localhost:11434/v1",
    "openai": "https://api.openai.com/v1",
}

DEFAULT_MODELS = {
    "lmstudio": "qwen/qwen3.5-9b",
    "ollama": "llama3",
    "openai": "gpt-4o-mini",
}


class Runner:
    """Local agent runner with tool execution."""

    def __init__(self, agent, cancel_event=None):
        """Initialize the runner with an agent.

        Args:
            agent: Agent instance or AgentConfig
            cancel_event: asyncio.Event for cancelling execution

        """
        from tinycua_sdk.agent import Agent

        # Get config from agent if it's an Agent instance
        if isinstance(agent, Agent):
            self.config = agent.config
            self._cancel_event = cancel_event or agent.cancel_event
            self.sub_agents = agent.sub_agents
        else:
            self.config = agent
            self._cancel_event = cancel_event
            self.sub_agents = getattr(agent, "sub_agents", [])

        # Resolve base URL
        if self.config.base_url:
            self.base_url = self.config.base_url
        elif self.config.provider in DEFAULT_BASE_URLS:
            self.base_url = DEFAULT_BASE_URLS[self.config.provider]
        else:
            self.base_url = "https://api.openai.com/v1"

        # Model
        self.model = self.config.model or DEFAULT_MODELS.get(
            self.config.provider, "gpt-4o-mini"
        )
        self.api_key = self.config.api_key
        self.tools = self.config.tools
        self.system_prompt = self.config.system_prompt
        self.max_tool_calls = self.config.policy.max_tool_calls

        # Configurable thinking strip patterns (None = use default, False = disable)
        self.strip_thinking_patterns = getattr(self.config, "strip_thinking", None)

        # These can be overridden per-run
        self.trace = False
        self.verbose = False
        self.stream_sse = False

        self.client = ResponsesClient(base_url=self.base_url, api_key=self.api_key)
        self.messages: list[dict[str, Any]] = []

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Runner":
        """Create runner from config dict.

        Args:
            config: Configuration dictionary containing agent settings.

        Returns:
            Runner instance initialized from config.
        """
        return cls(Agent.from_config(config))

    def add_tool(self, tool: Tool) -> None:
        """Add a tool to the runner.

        Args:
            tool: Tool instance to add.
        """
        self.tools.append(tool)

    def clear_messages(self) -> None:
        """Clear message history.

        Removes all messages from the conversation history.
        """
        self.messages = []

    def _is_cancelled(self) -> bool:
        """Check if execution has been cancelled."""
        if self._cancel_event and self._cancel_event.is_set():
            return True
        return False

    async def run(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool | None = None,
    ) -> Union[str, RunResult]:
        """Execute agent with tool loop.

        Handles trace internally - returns RunResult if trace=True.

        Args:
            user_input: User message
            instructions: Optional system instructions
            trace: If True, return RunResult with trace

        Returns:
            RunResult if trace=True, string otherwise
        """
        use_trace = trace if trace is not None else self.trace

        self._register_sub_agent_tools()

        return await self._chat_direct(user_input, instructions, use_trace)

    async def chat(self, *args, **kwargs) -> Union[str, RunResult]:
        """Backward compatible alias for run()."""
        return await self.run(*args, **kwargs)

    async def run_sse(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream agent execution with SSE events.

        Yields StreamEvent objects for all operations.

        Args:
            user_input: User message
            instructions: Optional system instructions

        Yields:
            StreamEvent objects
        """
        try:
            self._register_sub_agent_tools()
            async for event in self.stream_with_tools(user_input, instructions):
                yield event
        finally:
            await self.close()

    async def chat_sse(self, *args, **kwargs) -> AsyncIterator[StreamEvent]:
        """Backward compatible alias for run_sse()."""
        async for event in self.run_sse(*args, **kwargs):
            yield event

    async def execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> Any:
        """Execute a single tool.

        Args:
            tool_name: Name of tool to execute
            tool_input: Arguments for tool

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
        """
        for tool in self.tools:
            if tool.name == tool_name:
                result = tool.invoke(**tool_input)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
        raise ValueError(f"Tool '{tool_name}' not found")

    async def call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Call the LLM directly.

        Useful for custom loops that need to call LLM for planning/analysis.

        Args:
            messages: List of message dicts
            tools: Optional tool configurations

        Returns:
            LLM response object
        """
        request = ResponseRequest(
            model=self.model,
            input=messages,
            tools=tools or [],
        )
        return await self.client.create(request)

    # =========================================================================
    # Helper methods for custom loops
    # =========================================================================

    def build_messages(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> list[dict[str, Any]]:
        """Build message list with system prompt and user input.

        Args:
            user_input: User message
            instructions: Optional custom instructions

        Returns:
            List of message dicts
        """
        system_content = self.system_prompt
        if instructions:
            system_content += f"\n\n{instructions}"

        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.messages)
        messages.append({"role": "user", "content": user_input})
        return messages

    def get_tool_configs(self) -> list[dict[str, Any]]:
        """Get tool configurations for LLM requests.

        Returns:
            List of tool config dicts
        """
        return self._get_tool_configs()

    def build_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ResponseRequest:
        """Build a ResponseRequest object.

        Args:
            messages: Message list
            tools: Optional tool configs

        Returns:
            ResponseRequest object
        """
        return ResponseRequest(
            model=self.model,
            input=messages,
            tools=tools or [],
        )

    def emit_loop_log(self, message: str, level: str = "info") -> None:
        """Emit a log message from a custom loop.

        This allows custom loops to send log messages back to the client
        through the SSE stream. Events are collected and yielded during streaming.

        Args:
            message: The log message
            level: Log level (info, warn, error, debug)
        """
        if not hasattr(self, "_loop_logs"):
            self._loop_logs = []
        self._loop_logs.append({"level": level, "message": message})

    def get_loop_logger(self):
        """Get a logger function for custom loops.

        Returns a callable that can be used to emit loop logs.

        Returns:
            A callable that emits loop log events
        """
        return self.emit_loop_log

    async def execute_tool_loop(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[Any]]:
        """Execute a list of tool calls and return updated messages + results.

        Args:
            tool_calls: List of tool call dicts from LLM response

        Returns:
            Tuple of (tool message dicts for history, tool result values)
        """
        import json

        tool_messages = []
        results = []

        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name")

            try:
                tool_input = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                tool_input = {}

            result = await self.execute_tool(tool_name, tool_input)
            results.append(result)

            tool_messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": func.get("arguments", "{}"),
                            },
                        }
                    ],
                }
            )
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": str(result),
                }
            )

        return tool_messages, results

    def strip_thinking(self, content: str) -> str:
        """Strip thinking tags from content.

        Args:
            content: Raw content from LLM

        Returns:
            Content with thinking removed
        """
        return self._strip_thinking(content)

    def _register_sub_agent_tools(self) -> None:
        """Register sub-agents as tools for delegation.

        Creates delegate tools for each sub-agent, allowing the LLM to
        delegate tasks to specialized sub-agents.
        """
        if not self.sub_agents:
            return

        verbose = self.verbose
        trace = self.trace

        for sub_agent in self.sub_agents:
            tool_name = f"delegate_to_{sub_agent.name}"
            if any(t.name == tool_name for t in self.tools):
                continue

            if verbose:
                logger.info(f"[Delegation] Registering tool: {tool_name}")

            agent = sub_agent

            def create_delegate_fn(agent, verbose, trace):
                async def delegate_fn(task: str, context: str = "") -> str:
                    """Delegate a task to a sub-agent.

                    Args:
                        task: Task description for the sub-agent.
                        context: Additional context to pass to the sub-agent.

                    Returns:
                        Result from the sub-agent execution.
                    """
                    if verbose:
                        logger.info(f"[Delegation] → Delegating to {agent.name}")
                        logger.info(f"[Delegation]   Task: {task[:100]}...")
                        logger.info(
                            f"[Delegation]   Context: "
                            f"{context[:100] if context else '(none)'}..."
                        )

                    try:
                        result = await agent.run(
                            task, instructions=context, verbose=verbose, trace=trace
                        )

                        if verbose:
                            logger.info(
                                f"[Delegation] ← {agent.name} completed "
                                f"({len(result)} chars)"
                            )

                        return result
                    except Exception as e:
                        if verbose:
                            logger.error(f"[Delegation] × {agent.name} failed: {e}")
                        raise

                return delegate_fn

            delegate_fn = create_delegate_fn(agent, verbose, trace)

            delegate_tool = Tool(
                name=tool_name,
                description=(
                    f"Delegate task to {agent.name}. Use when the task matches "
                    f"{agent.name}'s expertise."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task to delegate to the sub-agent",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context for the sub-agent",
                            "default": "",
                        },
                    },
                    "required": ["task"],
                },
                _fn=delegate_fn,
            )
            self.tools.append(delegate_tool)

    def _find_sub_agent_for_task(self, task: str):
        """Find a sub-agent that matches the task based on keywords.

        Searches through sub-agents' keywords to find the best match
        for handling the given task.

        Args:
            task: Task description to match against.

        Returns:
            Matching sub-agent or None if no match found.
        """
        task_lower = task.lower()
        for sub in self.sub_agents:
            sub_keywords = sub.keywords or [sub.name.lower()]
            if any(kw.lower() in task_lower for kw in sub_keywords):
                return sub
        return None

    async def _delegate_to_sub_agent(
        self, sub_agent, user_input: str, instructions: str | None = None
    ) -> str:
        """Delegate task to a sub-agent.

        Wraps the task in a context that tells the sub-agent it's being
        delegated from a parent agent.

        Args:
            sub_agent: The sub-agent to delegate to.
            user_input: Task description.
            instructions: Optional additional instructions.

        Returns:
            Result from sub-agent execution wrapped with delegation info.
        """
        context = f"""
Parent Task: {user_input}
Parent Instructions: {instructions or "None"}

You are now handling this task. Complete it and return results.
"""
        result = await sub_agent.run(user_input, instructions=context)
        return f"[Delegated to {sub_agent.name}]\n{result}"

    def _get_tool_configs(self) -> list[dict[str, Any]]:
        """Get tool configurations in OpenAI function format.

        Returns:
            List of tool configurations for API requests.
        """
        configs = []
        for tool in self.tools:
            config = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            if self.verbose:
                logger.debug(f"[Tool Config] {config}")
            configs.append(config)
        return configs

    DEFAULT_THINKING_PATTERNS = [
        r"<think>.*?</think>",
        r"<think>.*?</think>\s*",
        r"<thinking>.*?</thinking>",
        r"<think>[\s\S]*?</think>",
    ]

    def _strip_thinking(self, content: str) -> str:
        """Strip thinking tags from content based on configured patterns.

        Removes LLM thinking/output reasoning tags from the response
        to return clean content.

        Args:
            content: Raw content that may contain thinking tags.

        Returns:
            Content with thinking tags removed.
        """
        import re

        if self.strip_thinking_patterns is False:
            return content

        patterns = self.strip_thinking_patterns or self.DEFAULT_THINKING_PATTERNS

        for pattern in patterns:
            content = re.sub(pattern, "", content, flags=re.DOTALL)

        return content.strip()

    async def _chat_direct(
        self, user_input: str, instructions: str | None = None, trace: bool = False
    ) -> Union[str, RunResult]:
        """Direct chat without planning.

        Sends a user message directly to the LLM with tool execution,
        without using the planning phase.

        Args:
            user_input: User message to send.
            instructions: Optional system instructions.
            trace: If True, return RunResult with trace data.

        Returns:
            Assistant response string, or RunResult if trace=True.
        """
        system_content = self.system_prompt
        if instructions:
            system_content += f"\n\n{instructions}"

        self.messages.append({"role": "user", "content": user_input})

        trace_data: list[dict[str, Any]] = []
        tool_call_records: list[ToolCall] = []

        for _ in range(self.max_tool_calls):
            request_messages = [{"role": "system", "content": system_content}]
            request_messages.extend(self.messages)

            tool_configs = self._get_tool_configs()

            request = ResponseRequest(
                model=self.model,
                input=request_messages,
                tools=tool_configs,
            )

            if self.verbose:
                logger.debug(f"[Request] {request.model_dump_json()}")

            response = await self.client.create(request)

            if self.verbose:
                logger.debug(f"[Response] {response.model_dump_json()}")

            choice = response.choices[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            content = self._strip_thinking(content)

            usage_data = response.usage.model_dump() if response.usage else {}

            trace_data.append(
                {
                    "request": request.model_dump(),
                    "response": response.model_dump(),
                    "usage": usage_data,
                }
            )

            assistant_message = str(content) if content else ""
            tool_calls_found = False

            if tool_calls:
                tool_call_msg = {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {
                                "name": tc.get("function", {}).get("name"),
                                "arguments": tc.get("function", {}).get(
                                    "arguments", "{}"
                                ),
                            },
                        }
                        for tc in tool_calls
                    ],
                }
                self.messages.append(tool_call_msg)

                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name")

                    try:
                        tool_input = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_input = {}

                    result = await self._execute_tool_async(tool_name, tool_input)

                    tool_call_records.append(
                        ToolCall(
                            id=tc.get("id", ""),
                            name=tool_name,
                            arguments=tool_input,
                            result=result,
                        )
                    )

                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "content": str(result),
                        }
                    )

                    if self.verbose:
                        logger.debug(
                            f"[Tool Call] {tool_name}({tool_input}) -> {result}"
                        )
                    print(f"[Tool] {tool_name} -> {result}")
                    tool_calls_found = True

            if not tool_calls_found:
                self.messages.append(
                    {"role": "assistant", "content": assistant_message}
                )

                if trace:
                    return RunResult(
                        response=assistant_message,
                        tool_calls=tool_call_records,
                        usage=usage_data,
                        trace=trace_data,
                        finish_reason=choice.get("finish_reason"),
                    )
                return assistant_message

        if trace:
            return RunResult(
                response=assistant_message,
                tool_calls=tool_call_records,
                usage=usage_data,
                trace=trace_data,
                finish_reason="max_calls",
            )
        return assistant_message

    async def _chat_with_plan(
        self, user_input: str, instructions: str | None = None, trace: bool = False
    ) -> Union[str, RunResult]:
        """Chat with plan mode.

        Uses the planning phase to decompose the task into subtasks,
        executes each subtask, then aggregates the results.

        Args:
            user_input: User message to send.
            instructions: Optional system instructions.
            trace: If True, return PlanRunResult with trace data.

        Returns:
            Assistant response string, or PlanRunResult if trace=True.
        """
        self.messages.append({"role": "user", "content": user_input})

        plan = await self.analyze(user_input, instructions)
        print(f"[Plan] {len(plan.todo)} subtasks identified")

        todo_items = await self.execute_todo(plan)

        final_response = await self.aggregate(todo_items)

        self.messages.append({"role": "assistant", "content": final_response})

        if trace:
            return PlanRunResult(
                response=final_response,
                plan={
                    "main_task": plan.main_task,
                    "todo": [
                        {
                            "id": t.id,
                            "description": t.description,
                            "status": t.status,
                            "result": t.result,
                        }
                        for t in plan.todo
                    ],
                },
                todo_items=[
                    {
                        "id": t.id,
                        "description": t.description,
                        "status": t.status,
                        "result": t.result,
                    }
                    for t in todo_items
                ],
            )
        return final_response

    async def analyze(self, task: str, instructions: str | None = None) -> TaskPlan:
        """Analyze task and create a todo list using the LLM.

        Sends the task to the LLM with the planning prompt to decompose
        the task into smaller todo items with tool calls.

        Args:
            task: The task to analyze.
            instructions: Optional additional instructions for the planner.

        Returns:
            TaskPlan containing main task and list of TodoItems.

        Raises:
            json.JSONDecodeError: If response is not valid JSON.
        """
        prompt = self.planning_prompt
        if instructions:
            prompt += f"\n\n{instructions}"

        tool_configs = self._get_tool_configs()

        request = ResponseRequest(
            model=self.model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": task},
            ],
            tools=tool_configs,
        )

        response = await self.client.create(request)
        content = response.choices[0].get("message", {}).get("content", "")

        if self.verbose:
            logger.debug(f"[Analyze] Response: {content}")

        try:
            data = json.loads(content)
            todo = [
                TodoItem(
                    id=item.get("id", str(i)),
                    description=item.get("description", ""),
                    tool_name=item.get("tool_name"),
                    tool_args=item.get("tool_args", {}),
                )
                for i, item in enumerate(data.get("todo", []))
            ]
            return TaskPlan(main_task=data.get("main_task", task), todo=todo)
        except json.JSONDecodeError:
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    todo = [
                        TodoItem(
                            id=item.get("id", str(i)),
                            description=item.get("description", ""),
                            tool_name=item.get("tool_name"),
                            tool_args=item.get("tool_args", {}),
                        )
                        for i, item in enumerate(data.get("todo", []))
                    ]
                    return TaskPlan(main_task=data.get("main_task", task), todo=todo)
                except json.JSONDecodeError:
                    pass
            return TaskPlan(
                main_task=task,
                todo=[TodoItem(id="1", description=task, tool_name=None)],
            )

    async def execute_todo(self, plan: TaskPlan) -> list[TodoItem]:
        """Execute each todo item sequentially.

        Runs through each TodoItem in the plan, executing the associated
        tool and updating the item status and result.

        Args:
            plan: TaskPlan containing todo items to execute.

        Returns:
            List of TodoItems with updated status and results.
        """
        for todo in plan.todo:
            if todo.tool_name:
                print(f"[Todo] {todo.id}: {todo.description} ({todo.tool_name})")
                todo.status = "in_progress"
                result = self._execute_tool(todo.tool_name, todo.tool_args)
                todo.result = result
                todo.status = "completed"
                print(f"[Done] {todo.id} -> {result}")
            else:
                print(f"[Todo] {todo.id}: {todo.description} (direct)")
                todo.status = "in_progress"
                request = ResponseRequest(
                    model=self.model,
                    input=[{"role": "user", "content": todo.description}],
                )
                response = await self.client.create(request)
                result = response.choices[0].get("message", {}).get("content", "")
                todo.result = result
                todo.status = "completed"
                print(f"[Done] {todo.id} -> {result[:100]}...")
        return plan.todo

    async def aggregate(self, todo_items: list[TodoItem]) -> str:
        """Aggregate todo results into a final response.

        Combines completed todo items into a formatted response that
        summarizes all the results.

        Args:
            todo_items: List of TodoItems to aggregate.

        Returns:
            Formatted string with aggregated results.
        """
        results = [
            f"- {item.description}: {item.result}"
            for item in todo_items
            if item.status == "completed"
        ]
        results_text = "\n".join(results) if results else "No results"

        request = ResponseRequest(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": "Summarize the following results into a clear response:",
                },
                {"role": "user", "content": results_text},
            ],
        )

        response = await self.client.create(request)
        return response.choices[0].get("message", {}).get("content", "No response")

    async def stream(
        self, user_input: str, instructions: str | None = None
    ) -> AsyncIterator[str]:
        """Stream responses token by token.

        Args:
            user_input: User message
            instructions: Optional custom instructions

        Yields:
            Response tokens

        """
        system_content = self.system_prompt
        if instructions:
            system_content += f"\n\n{instructions}"

        self.messages.append({"role": "user", "content": user_input})

        # Build request messages with system prompt
        request_messages = [{"role": "system", "content": system_content}]
        request_messages.extend(self.messages)

        request = ResponseRequest(
            model=self.model,
            input=request_messages,
            tools=self._get_tool_configs(),
        )

        async for event in self.client.stream(request):
            if self._is_cancelled():
                return

            if event.data.get("choices"):
                delta = event.data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content

    async def stream_with_tools(
        self, user_input: str, instructions: str | None = None
    ) -> AsyncIterator[StreamEvent]:
        """Stream responses with tool execution.

        Args:
            user_input: User message
            instructions: Optional custom instructions

        Yields:
            StreamEvent objects with type and data

        """
        import inspect

        self._register_sub_agent_tools()

        system_content = self.system_prompt
        if instructions:
            system_content += f"\n\n{instructions}"

        self.messages.append({"role": "user", "content": user_input})

        request_messages = [{"role": "system", "content": system_content}]
        request_messages.extend(self.messages)

        request = ResponseRequest(
            model=self.model,
            input=request_messages,
            tools=self._get_tool_configs(),
        )

        if self.stream_sse:
            yield StreamEvent(
                type=StreamEventType.LLM_REQUEST,
                data={"model": self.model, "messages": request_messages},
            )
            for log_entry in getattr(self, "_loop_logs", []):
                yield StreamEvent(
                    type=StreamEventType.LOOP_LOG,
                    data=log_entry,
                )

        (
            tool_calls_buffer,
            assistant_content,
            finish_reason,
        ) = await self._collect_tool_calls(request)

        if not tool_calls_buffer:
            if assistant_content:
                yield StreamEvent(
                    type=StreamEventType.CONTENT,
                    data={"content": assistant_content},
                )
            yield StreamEvent(
                type=StreamEventType.DONE, data={"finish_reason": finish_reason}
            )
            return

        yield StreamEvent(
            type=StreamEventType.TOOL_CALL_START,
            data={"tool_calls": tool_calls_buffer},
        )

        yield StreamEvent(
            type=StreamEventType.TOOL_CALL_END,
            data={"tool_calls": tool_calls_buffer},
        )

        self.messages.append({"role": "assistant", "content": assistant_content})

        tool_results = []
        for tc in tool_calls_buffer:
            async for event in self._stream_tool_execution(tc, inspect):
                yield event
                if event.type == StreamEventType.TOOL_RESULT_END:
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "content": event.data.get("result", ""),
                        }
                    )

        continuation_request = ResponseRequest(
            model=self.model,
            input=request_messages
            + [{"role": "assistant", "content": assistant_content}]
            + tool_results,
        )

        async for event in self.client.stream(continuation_request):
            if self._is_cancelled():
                yield StreamEvent(
                    type=StreamEventType.DONE, data={"finish_reason": "cancelled"}
                )
                return

            if event.data.get("choices"):
                delta = event.data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield StreamEvent(
                        type=StreamEventType.CONTENT,
                        data={"content": content},
                    )

        yield StreamEvent(
            type=StreamEventType.DONE, data={"finish_reason": finish_reason}
        )

    async def _collect_tool_calls(
        self, request: ResponseRequest
    ) -> tuple[list[dict[str, Any]], str, str]:
        """Collect tool calls from first LLM response.

        Streams the LLM response and collects any tool calls made by the model.

        Args:
            request: The ResponseRequest to send to the LLM.

        Returns:
            Tuple of (tool_calls_buffer, assistant_content, finish_reason).
        """
        tool_calls_buffer: list[dict[str, Any]] = []
        current_tool_call: dict[str, Any] | None = None
        assistant_content = ""
        finish_reason = ""

        async for event in self.client.stream(request):
            if event.data.get("choices"):
                delta = event.data["choices"][0].get("delta", {})
                content = delta.get("content", "")
                tool_calls = delta.get("tool_calls", [])
                finish_reason = event.data["choices"][0].get("finish_reason", "")

                if content:
                    assistant_content += content

                for tc in tool_calls:
                    current_tool_call = self._update_tool_call_buffer(
                        tc, current_tool_call, tool_calls_buffer
                    )

        if current_tool_call and current_tool_call.get("name"):
            tool_calls_buffer.append(current_tool_call)

        return tool_calls_buffer, assistant_content, finish_reason

    def _update_tool_call_buffer(
        self,
        tc: dict[str, Any],
        current_tool_call: dict[str, Any] | None,
        tool_calls_buffer: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Update tool call buffer with new delta.

        Processes incoming tool call deltas from the LLM streaming response,
        handling both new tool calls and continuations of existing ones.

        Args:
            tc: Tool call delta from LLM.
            current_tool_call: Currently building tool call (if any).
            tool_calls_buffer: List to append completed tool calls to.

        Returns:
            Updated current_tool_call.
        """
        func = tc.get("function", {})
        tc_id = tc.get("id", "")
        func_name = func.get("name", "")
        func_args = func.get("arguments", "")

        is_new_call = func_name and (
            not current_tool_call or current_tool_call.get("id") != tc_id
        )
        is_continuation = (
            bool(func_args) and current_tool_call and current_tool_call.get("name")
        )

        if is_new_call:
            if current_tool_call and current_tool_call.get("name"):
                tool_calls_buffer.append(current_tool_call)
            current_tool_call = {
                "id": tc_id,
                "name": func_name,
                "arguments": func_args,
            }
        elif is_continuation and current_tool_call:
            current_tool_call["arguments"] += func_args
        elif func_name and not current_tool_call:
            current_tool_call = {
                "id": tc_id,
                "name": func_name,
                "arguments": func_args,
            }

        return current_tool_call

    async def _stream_tool_execution(
        self, tc: dict[str, Any], inspect_module: Any
    ) -> AsyncIterator[StreamEvent]:
        """Stream tool execution results.

        Executes a tool and yields SSE events for the streaming response.

        Args:
            tc: Tool call dictionary with name, id, and arguments.
            inspect_module: The inspect module for checking async generators.

        Yields:
            StreamEvent objects for tool execution progress.
        """
        tool_name = tc.get("name", "")
        tool_call_id = tc.get("id", "")
        try:
            tool_input = json.loads(tc.get("arguments", "{}"))
        except json.JSONDecodeError:
            tool_input = {}

        is_delegation = tool_name.startswith("delegate_to_")
        delegate_target = (
            tool_name.replace("delegate_to_", "") if is_delegation else None
        )
        if is_delegation and self.stream_sse:
            yield StreamEvent(
                type=StreamEventType.DELEGATION_START,
                data={
                    "tool_call_id": tool_call_id,
                    "agent": delegate_target,
                    "task": tool_input.get("task", ""),
                    "context": tool_input.get("context", ""),
                },
            )

        yield StreamEvent(
            type=StreamEventType.TOOL_RESULT_START,
            data={"tool_call_id": tc.get("id"), "tool_name": tool_name},
        )

        result = self._execute_tool_streaming(tool_name, tool_input)
        result_str = str(result)

        if inspect_module.isasyncgen(result):
            async for chunk in result:
                yield StreamEvent(
                    type=StreamEventType.TOOL_RESULT_CHUNK,
                    data={
                        "tool_call_id": tc.get("id"),
                        "tool_name": tool_name,
                        "content": chunk,
                    },
                )
                result_str = str(result)
        else:
            chunk_size = 10
            for i in range(0, len(result_str), chunk_size):
                yield StreamEvent(
                    type=StreamEventType.TOOL_RESULT_CHUNK,
                    data={
                        "tool_call_id": tc.get("id"),
                        "tool_name": tool_name,
                        "content": result_str[i : i + chunk_size],
                    },
                )

        yield StreamEvent(
            type=StreamEventType.TOOL_RESULT_END,
            data={
                "tool_call_id": tc.get("id"),
                "tool_name": tool_name,
                "result": result_str,
            },
        )

        if is_delegation and self.stream_sse:
            yield StreamEvent(
                type=StreamEventType.DELEGATION_END,
                data={
                    "tool_call_id": tool_call_id,
                    "agent": delegate_target,
                    "result_length": len(result_str),
                },
            )

    def _execute_tool_streaming(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> Union[Any, AsyncIterator[str]]:
        """Execute a tool and return result or async iterator for streaming.

        Finds and invokes the tool by name. If the result is a coroutine,
        converts it to an async generator that yields chunks.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Arguments to pass to the tool.

        Returns:
            Tool result, or async iterator for streaming results.
        """
        for tool in self.tools:
            if tool.name == tool_name:
                result = tool.invoke(**tool_input)
                if asyncio.iscoroutine(result):
                    # Convert coroutine to async generator that yields chunks
                    async def async_result_to_chunks():
                        resolved = await result
                        result_str = str(resolved)
                        chunk_size = 10
                        for i in range(0, len(result_str), chunk_size):
                            yield result_str[i : i + chunk_size]

                    return async_result_to_chunks()
                return result
        return {"error": f"Tool {tool_name} not found"}

    def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """Execute a tool by name.

        Finds and invokes the tool by name.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Arguments to pass to the tool.

        Returns:
            Tool result, or error dict if tool not found.
        """
        for tool in self.tools:
            if tool.name == tool_name:
                return tool.invoke(**tool_input)
        return {"error": f"Tool {tool_name} not found"}

    async def _execute_tool_async(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> Any:
        """Execute a tool by name (async-aware).

        Finds and invokes the tool by name, awaiting if result is coroutine.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Arguments to pass to the tool.

        Returns:
            Tool result, or error dict if tool not found.
        """
        for tool in self.tools:
            if tool.name == tool_name:
                result = tool.invoke(**tool_input)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
        return {"error": f"Tool {tool_name} not found"}

    async def close(self) -> None:
        """Close the runner.

        Closes the HTTP client and releases resources.
        """
        await self.client.close()

    def __enter__(self) -> "Runner":
        """Enter the runtime context.

        Returns:
            The Runner instance.

        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the runtime context and close the runner.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.

        """
        asyncio.get_event_loop().run_until_complete(self.close())


@dataclass
class RunnerOptions:
    """Options for runner execution."""

    model: str
    temperature: float = 1.0
    max_tokens: int | None = None
    stream: bool = True


class RemoteRunner(ABC):
    """Abstract base class for remote runners.

    Subclasses must implement execute() and health_check() methods.
    """

    def __init__(self, base_url: str, api_key: str | None = None):
        """Initialize the remote runner.

        Args:
            base_url: Base URL of the runner service
            api_key: Optional API key for authentication

        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    async def execute(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: RunnerOptions,
    ) -> AsyncIterator[str]:
        """Execute agent task on remote runner.

        Args:
            messages: Conversation messages
            tools: Tool definitions
            options: Runner options

        Yields:
            Stream events from the runner

        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the runner is healthy.

        Returns:
            True if runner is healthy, False otherwise

        """
        pass


class HTTPRunner(RemoteRunner):
    """HTTP-based remote runner.

    Executes agent tasks via HTTP API.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
    ):
        """Initialize HTTP runner.

        Args:
            base_url: Base URL of the runner service
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds

        """
        super().__init__(base_url, api_key)
        self.timeout = timeout

    def _get_headers(self) -> dict[str, str]:
        """Get request headers.

        Returns:
            Headers dict with authentication

        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def execute(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        options: RunnerOptions,
    ) -> AsyncIterator[str]:
        """Execute agent task via HTTP.

        Args:
            messages: Conversation messages
            tools: Tool definitions
            options: Runner options

        Yields:
            Stream events from the runner

        """
        payload = {
            "messages": messages,
            "tools": tools,
            "model": options.model,
            "temperature": options.temperature,
            "stream": options.stream,
        }
        if options.max_tokens:
            payload["max_tokens"] = options.max_tokens

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/execute",
                    json=payload,
                    headers=self._get_headers(),
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            yield line[6:]
                        elif line:
                            yield line
        except httpx.ConnectError:
            raise ConnectionError(f"Cannot connect to runner at {self.base_url}")
        except httpx.TimeoutException:
            raise TimeoutError("Request to runner timed out")

    async def health_check(self) -> bool:
        """Check if runner is healthy.

        Returns:
            True if runner is healthy, False otherwise

        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except Exception:
            return False


__all__ = [
    "Runner",
    "RemoteRunner",
    "HTTPRunner",
    "RunnerOptions",
]
