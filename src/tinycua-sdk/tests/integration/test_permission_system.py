"""Integration tests for tool permission maps."""

from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.agent.executor import ToolExecutor
from tinycua_sdk.security.approval import ApprovalWorkflow


class RecordingApprovalWorkflow(ApprovalWorkflow):
    def __init__(self, approved=True):
        self.approved = approved
        self.calls = []

    async def request_approval(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return {"approved": self.approved}


async def test_permission_map_deny_blocks_without_guardrail():
    """The deny permission blocks immediately and never invokes the tool."""
    invoked = False

    @tool
    def shell_execute(command: str) -> str:
        nonlocal invoked
        invoked = True
        return command

    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"shell_execute": "deny"},
    )

    result = await ToolExecutor.execute(
        shell_execute, {"command": "whoami"}, agent
    )

    assert result == {
        "error": "Tool 'shell_execute' is denied by permission map."
    }
    assert invoked is False


async def test_permission_map_ask_triggers_guardrail():
    """The ask permission routes execution through the approval workflow."""
    workflow = RecordingApprovalWorkflow(approved=True)

    @tool
    def read_file(path: str) -> str:
        return f"read {path}"

    agent = Agent(
        llm_model=LanguageModel(),
        tool_permissions={"read_file": "ask"},
        approval_workflow=workflow,
    )

    result = await ToolExecutor.execute(read_file, {"path": "README.md"}, agent)

    assert result == "read README.md"
    assert workflow.calls == [("read_file", {"path": "README.md"})]


async def test_runtime_permission_mutation_applies_immediately():
    """Mutating Agent.tool_permissions changes the next execution result."""
    count = 0

    @tool
    def touch_file(path: str) -> str:
        nonlocal count
        count += 1
        return f"touched {path}"

    agent = Agent(llm_model=LanguageModel())

    allowed = await ToolExecutor.execute(touch_file, {"path": "a.txt"}, agent)
    agent.tool_permissions["touch_file"] = "deny"
    denied = await ToolExecutor.execute(touch_file, {"path": "b.txt"}, agent)

    assert allowed == "touched a.txt"
    assert denied == {
        "error": "Tool 'touch_file' is denied by permission map."
    }
    assert count == 1
