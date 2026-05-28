"""Target 7.4: Verify 'ask' permission routes through ApprovalWorkflow."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    return f"Wrote to {path}"


class SimpleAskGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"[ASK] {tool_name}({arguments}) — auto-approved for demo")
        return {"approved": True, "notified": True}


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[write_file],
        approval_workflow=SimpleAskGuardrail(),
    )

    # Set ask permission (triggers guardrail)
    a.tool_permissions["write_file"] = "ask"

    response = await a.run('Write "hello" to /tmp/test.txt', stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
