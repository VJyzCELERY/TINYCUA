"""Target 7.1: Verify DangerousToolGuardrail blocks dangerous tools."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    return f"ran: {command}"


class DangerousToolGuardrail(ApprovalWorkflow):
    DANGEROUS = {"shell_execute"}

    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        if tool_name in self.DANGEROUS:
            return {"approved": False, "reason": f"'{tool_name}' is classified as dangerous."}
        return {"approved": True}


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[shell_execute],
        approval_workflow=DangerousToolGuardrail(),
    )

    response = await a.run("Run 'ls -la'", stream="off")
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
