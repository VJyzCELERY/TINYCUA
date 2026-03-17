"""Agent client for running agent loops."""

from typing import Any, Iterator

from tinycua_sdk.agent import Agent
from tinycua_sdk.clients.client import ResponsesClient
from tinycua_sdk.models.request import ResponseRequest
from tinycua_sdk.models.response import Response, StreamEvent
from tinycua_sdk.tools.decorators import Tool


class AgentClient:
    """Client for running agent interactions."""

    def __init__(self, client: ResponsesClient):
        """Initialize the AgentClient.

        Args:
            client: The ResponsesClient for making API requests.

        """
        self.client = client

    async def run(
        self,
        agent: Agent,
        user_input: str,
        session_id: str | None = None,
        server_orchestrated: bool = False,
    ) -> Response:
        """Run the agent with user input.

        Args:
            agent: The agent to run
            user_input: User message
            session_id: Session ID for server-orchestrated mode
            server_orchestrated: Whether to use server orchestration

        Returns:
            Response from the API

        """
        if session_id or server_orchestrated:
            return await self._run_server_orchestrated(agent, user_input, session_id)
        return await self._run_client_orchestrated(agent, user_input)

    async def _run_client_orchestrated(self, agent: Agent, user_input: str) -> Response:
        """Run agent locally (Mode A)."""
        messages = agent._build_context()
        messages.append({"role": "user", "content": user_input})

        request = ResponseRequest(
            model=agent.model,
            input=messages,
            tools=agent.tools,
            temperature=agent.policy.temperature,
        )

        response = await self.client.create(request)

        for _ in range(agent.policy.max_tool_calls):
            tool_calls = self._extract_tool_calls(response)
            if not tool_calls:
                break

            for tool_call in tool_calls:
                result = await self._execute_tool(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["call_id"],
                        "content": str(result),
                    }
                )

            request = ResponseRequest(
                model=agent.model,
                input=messages,
                tools=agent.tools,
                temperature=agent.policy.temperature,
            )
            response = await self.client.create(request)

        return response

    async def _run_server_orchestrated(
        self, agent: Agent, user_input: str, session_id: str | None = None
    ) -> Response:
        """Run agent via backend (Mode B)."""
        messages = agent._build_context()
        messages.append({"role": "user", "content": user_input})

        request = ResponseRequest(
            model=agent.model,
            input=messages,
            tools=agent.tools,
            temperature=agent.policy.temperature,
            session_id=session_id,
        )

        return await self.client.create(request)

    async def stream(
        self,
        agent: Agent,
        user_input: str,
        session_id: str | None = None,
    ) -> Iterator[StreamEvent]:
        """Stream agent response."""
        messages = agent._build_context()
        messages.append({"role": "user", "content": user_input})

        request = ResponseRequest(
            model=agent.model,
            input=messages,
            tools=agent.tools,
            temperature=agent.policy.temperature,
            session_id=session_id,
        )

        async for event in self.client.stream(request):
            yield event

    def _extract_tool_calls(self, response: Response) -> list[dict[str, Any]]:
        """Extract tool calls from response."""
        tool_calls = []
        for choice in response.choices:
            if "message" in choice:
                msg = choice["message"]
                if "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        tool_calls.append(
                            {
                                "call_id": tc.get("id", ""),
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": tc.get("function", {}).get(
                                    "arguments", ""
                                ),
                            }
                        )
        return tool_calls

    async def _execute_tool(self, tool_call: dict[str, Any]) -> Any:
        """Execute a tool call."""
        tool_name = tool_call["name"]
        import json

        args = json.loads(tool_call.get("arguments", "{}"))

        for tool in self._get_tool_by_name(tool_name):
            return tool.invoke(**args)

        raise ValueError(f"Tool {tool_name} not found")

    def _get_tool_by_name(self, name: str) -> list[Tool]:
        """Get tool by name."""
        return [t for t in self._registered_tools if t.name == name]

    def _set_tools(self, tools: list[Tool]) -> None:
        """Set available tools."""
        self._registered_tools = tools


__all__ = ["AgentClient"]
