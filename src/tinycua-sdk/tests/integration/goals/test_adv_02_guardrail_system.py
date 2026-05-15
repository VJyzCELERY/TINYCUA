"""Integration tests for guardrail approval workflows."""

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.security.approval import ApprovalWorkflow


class LoggingGuardrail(ApprovalWorkflow):
    def __init__(self):
        self.calls = []

    async def request_approval(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return {"approved": True, "logged_at": "test"}


class DangerousToolGuardrail(ApprovalWorkflow):
    DANGEROUS = {"shell_execute", "delete_file"}

    async def request_approval(self, tool_name, arguments):
        if tool_name in self.DANGEROUS:
            return {"approved": False, "reason": "Dangerous tool blocked."}
        return {"approved": True}


async def test_dangerous_tool_guardrail_blocks():
    """Dangerous tools are denied before invocation."""
    invoked = False

    @tool(name="delete_file")
    def delete_file(path: str) -> str:
        nonlocal invoked
        invoked = True
        return f"deleted {path}"

    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"delete_file": "ask"},
        approval_workflow=DangerousToolGuardrail(),
    )

    result = await ToolExecutor.execute(delete_file, {"path": "secret.txt"}, agent)

    assert result == {"approved": False, "reason": "Dangerous tool blocked."}
    assert invoked is False


async def test_logging_guardrail_logs_without_blocking():
    """Allowing guardrails can record calls while execution proceeds."""
    guardrail = LoggingGuardrail()

    @tool
    def calculator(expression: str) -> str:
        return "4" if expression == "2+2" else "unknown"

    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"calculator": "ask"},
        approval_workflow=guardrail,
    )

    result = await ToolExecutor.execute(calculator, {"expression": "2+2"}, agent)

    assert result == "4"
    assert guardrail.calls == [("calculator", {"expression": "2+2"})]


async def test_multiple_guardrails_first_denial_wins():
    """Chained guardrails stop at the first denial and do not invoke the tool."""
    logging_guardrail = LoggingGuardrail()
    dangerous_guardrail = DangerousToolGuardrail()
    invoked = False

    @tool(name="shell_execute")
    def shell_execute(command: str) -> str:
        nonlocal invoked
        invoked = True
        return command

    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"shell_execute": "ask"},
        approval_workflow=[logging_guardrail, dangerous_guardrail],
    )

    result = await ToolExecutor.execute(
        shell_execute, {"command": "rm -rf /"}, agent
    )

    assert result == {"approved": False, "reason": "Dangerous tool blocked."}
    assert logging_guardrail.calls == [("shell_execute", {"command": "rm -rf /"})]
    assert invoked is False


async def test_agent_loop_propagates_denied_tool_as_message():
    """Denied tool result propagates through Agent.run() as a denied response."""
    invoked = False

    @tool(name="delete_file")
    def delete_file(path: str) -> str:
        nonlocal invoked
        invoked = True
        return f"deleted {path}"

    call_count = 0
    second_call_messages = None

    async def fake_call_llm(messages, tools=None):
        nonlocal call_count, second_call_messages
        call_count += 1
        if call_count == 1:
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_denied",
                        "name": "delete_file",
                        "arguments": '{"path": "secret.txt"}',
                    }
                ],
            }
        second_call_messages = messages
        return {
            "content": "The tool delete_file was denied because it requires manual approval."
        }

    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"delete_file": "ask"},
        approval_workflow=DangerousToolGuardrail(),
        tools=[delete_file],
    )
    agent._call_llm = fake_call_llm

    result = await agent.run("Delete secret.txt")

    assert invoked is False
    assert call_count == 2
    assert any(
        isinstance(m, dict)
        and m.get("type") == "function_call_output"
        and "Dangerous tool blocked" in m.get("output", "")
        for m in (second_call_messages or [])
    )
    assert "denied" in result.lower() or "blocked" in result.lower()
