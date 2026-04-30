"""03 - Permission System

Shows how to use Agent.tool_permissions to declaratively control
tool execution without writing custom guardrail logic.

Permission levels:
    "allow"  -> Tool executes normally.
    "ask"    -> Routes through the optional ApprovalWorkflow guardrail.
    "deny"   -> Tool execution is immediately blocked.

This is a lightweight, declarative layer on top of the guardrail system.
"""

import asyncio

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


# ---------------------------------------------------------------------------
# 1. Tools
# ---------------------------------------------------------------------------
@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression, {"__builtins__": {}}, {}))


@tool
def read_file(path: str) -> str:
    """Read a file."""
    with open(path, "r") as f:
        return f.read()


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote to {path}"


@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    import subprocess
    return subprocess.check_output(command, shell=True, text=True)


# ---------------------------------------------------------------------------
# 2. A simple guardrail that respects the "ask" permission
# ---------------------------------------------------------------------------
class SimpleAskGuardrail(ApprovalWorkflow):
    """For 'ask' permissions, prints a notice and auto-approves.
    In production this would ping a Slack channel, open a modal, etc.
    """

    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"[ASK] {tool_name}({arguments}) — auto-approved for demo")
        return {"approved": True, "notified": True}


# ---------------------------------------------------------------------------
# 3. Agent with a permission map
# ---------------------------------------------------------------------------
async def main() -> None:
    agent = Agent(
        name="permissioned_agent",
        instructions="You are an agent with restricted tool access.",
        llm_model=LanguageModel(
            provider="openai-compatible",
            base_url="http://localhost:1234/v1",
        ),
        tools=[calculator, read_file, write_file, shell_execute],
        # Declarative permission map
        tool_permissions={
            "calculator": "allow",      # Always OK
            "read_file": "allow",       # Always OK
            "write_file": "ask",        # Requires approval (goes to guardrail)
            "shell_execute": "deny",    # Never allowed
        },
        approval_workflow=SimpleAskGuardrail(),
    )

    # calculator -> executes immediately
    response = await agent.run("What is 12 * 12?")
    print("Calculator:", response)

    # write_file -> triggers SimpleAskGuardrail
    response = await agent.run('Write "hello" to /tmp/test.txt')
    print("WriteFile:", response)

    # shell_execute -> blocked immediately by permission system
    response = await agent.run("Run 'rm -rf /'")
    print("Shell:", response)
    # The agent will see that the tool call was blocked and explain why.

    # -----------------------------------------------------------------------
    # 4. Changing permissions at runtime
    # -----------------------------------------------------------------------
    print("\n--- Elevating permissions ---")
    agent.tool_permissions["shell_execute"] = "ask"

    response = await agent.run("Run 'echo hello world'")
    print("Elevated shell:", response)


if __name__ == "__main__":
    asyncio.run(main())
