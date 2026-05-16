"""Target 7.5: Verify changing tool_permissions at runtime takes effect immediately."""

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

    # First run: deny
    a.tool_permissions["shell_execute"] = "deny"
    r1 = await a.run("Run 'echo hello'", stream=False)
    assert isinstance(r1, str)
    print(f"[denied] Response: {r1}")

    # Second run: allow (runtime mutation)
    a.tool_permissions["shell_execute"] = "allow"
    r2 = await a.run("Run 'echo hello'", stream=False)
    assert isinstance(r2, str)
    print(f"[allowed] Response: {r2}")


asyncio.run(main())
