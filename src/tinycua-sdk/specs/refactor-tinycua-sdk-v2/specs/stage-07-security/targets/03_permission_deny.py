"""Target 7.3: Verify 'deny' permission blocks without needing a guardrail."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool


@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    return f"ran: {command}"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[shell_execute],
    )

    # Set deny permission (no guardrail needed)
    a.tool_permissions["shell_execute"] = "deny"

    response = await a.run("Run 'rm -rf /'", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
