"""Target 7.2: Verify LoggingGuardrail records but never blocks."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


@tool
def read_file(path: str) -> str:
    """Read a file."""
    return "file content"


class LoggingGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"[AUDIT] tool={tool_name} args={arguments}")
        return {"approved": True, "logged_at": "2024-01-15T10:00:00Z"}


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[read_file],
        approval_workflow=LoggingGuardrail(),
    )

    response = await a.run("Read README.md", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
