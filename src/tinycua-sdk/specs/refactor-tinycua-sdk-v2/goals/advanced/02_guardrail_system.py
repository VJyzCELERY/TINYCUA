"""02 - Guardrail System

Shows how to implement a custom ApprovalWorkflow to act as a guardrail
before tool execution. The guardrail is called by ToolExecutor before
invoking any tool.

The ApprovalWorkflow ABC:
    async def request_approval(tool_name: str, arguments: dict) -> dict

Must return a dict with at least:
    {"approved": bool}

Consumers can add arbitrary keys for their own UI/auditing needs.
"""

import asyncio

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


# ---------------------------------------------------------------------------
# 1. A logging guardrail (always approves, but logs everything)
# ---------------------------------------------------------------------------
class LoggingGuardrail(ApprovalWorkflow):
    """Logs every tool call for audit. Never blocks."""

    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"[AUDIT] tool={tool_name} args={arguments}")
        return {
            "approved": True,
            "logged_at": "2024-01-15T10:00:00Z",
            "guardrail": "LoggingGuardrail",
        }


# ---------------------------------------------------------------------------
# 2. A dangerous-tool guardrail (blocks high-risk tools)
# ---------------------------------------------------------------------------
class DangerousToolGuardrail(ApprovalWorkflow):
    """Blocks execution of tools deemed dangerous unless explicitly allowed."""

    DANGEROUS_TOOLS = {"shell_execute", "delete_file", "send_email", "transfer_money"}

    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        if tool_name in self.DANGEROUS_TOOLS:
            return {
                "approved": False,
                "reason": f"'{tool_name}' is classified as dangerous.",
                "action_required": "Explicit user confirmation needed.",
            }
        return {"approved": True}


# ---------------------------------------------------------------------------
# 3. An interactive guardrail (simulates a human-in-the-loop)
# ---------------------------------------------------------------------------
class InteractiveGuardrail(ApprovalWorkflow):
    """Prompts a human operator for approval on every tool call."""

    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"\n🔒 Tool request: {tool_name}")
        print(f"   Arguments: {arguments}")
        answer = input("   Approve? [y/n]: ").strip().lower()

        if answer in ("y", "yes"):
            return {"approved": True, "approved_by": "human_operator"}
        return {
            "approved": False,
            "reason": "Denied by human operator",
            "tool_name": tool_name,
        }


# ---------------------------------------------------------------------------
# 4. Usage — attach the guardrail to an Agent
# ---------------------------------------------------------------------------
@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    import subprocess
    return subprocess.check_output(command, shell=True, text=True)


@tool
def read_file(path: str) -> str:
    """Read a file."""
    with open(path, "r") as f:
        return f.read()


async def main() -> None:
    # Agent with logging + dangerous-tool guardrails
    # ToolExecutor checks them in order (if a list is provided)
    safe_agent = Agent(
        name="safe_agent",
        instructions="You are a safe agent with guardrails.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            model_name="qwen/qwen3.5-9b",
            base_url="http://localhost:1234/v1",
            api_key="dummy",
        ),
        tools=[shell_execute, read_file],
        approval_workflow=DangerousToolGuardrail(),
    )

    # read_file will pass the guardrail and execute
    response = await safe_agent.run("Read the file README.md")
    print("Read response:", response)

    # shell_execute will be blocked by the guardrail
    response = await safe_agent.run("Run 'ls -la'")
    print("Shell response:", response)
    # The response will explain that the tool was blocked and why.

    # -----------------------------------------------------------------------
    # Agent with interactive human-in-the-loop
    # -----------------------------------------------------------------------
    # interactive_agent = Agent(
    #     name="interactive_agent",
    #     tools=[shell_execute, read_file],
    #     approval_workflow=InteractiveGuardrail(),
    # )
    # await interactive_agent.run("Run 'ls -la'")


if __name__ == "__main__":
    asyncio.run(main())
