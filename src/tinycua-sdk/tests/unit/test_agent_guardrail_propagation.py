"""Unit tests for guardrail/tool-denial propagation through Agent.run().

These tests verify that denied tool results propagate through Agent.run()
as denied response messages. They use fake _call_llm() responses to control
the LLM output deterministically.

Moved from tests/integration/goals/test_adv_02_guardrail_system.py as part
of the Stage 8 cleanup (ISSUE-001): this test validates control flow against
stubs, not integration with a live LLM endpoint.
"""

import pytest

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


class DangerousToolGuardrail(ApprovalWorkflow):
    """Guardrail that blocks dangerous tools."""
    DANGEROUS = {"shell_execute", "delete_file"}

    async def request_approval(self, tool_name, arguments):
        if tool_name in self.DANGEROUS:
            return {"approved": False, "reason": "Dangerous tool blocked."}
        return {"approved": True}


class TestGuardrailPropagation:
    """Test that denied tool results propagate through Agent.run()."""

    @pytest.mark.asyncio
    async def test_agent_loop_propagates_denied_tool_as_message(self):
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
