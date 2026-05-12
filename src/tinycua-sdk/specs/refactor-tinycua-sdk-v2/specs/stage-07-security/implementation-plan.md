# Implementation: Stage 7 Security - Guardrails and Permissions

Adds declarative tool permissions and approval guardrails to the tinycua-sdk tool execution path so consumers can block, allow, or request approval for tool calls without changing SDK internals.

## Context

- **Spec Reference**: `spec.md`
- **Design Reference**: `design.md`
- **Priority**: P1
- **Estimated Effort**: M

## Environment Pre-requisites

### Configuration

- [x] **None** - this feature has no configuration dependencies

### Running Services

| Service | Required | How to Start | Health Check |
|---------|----------|--------------|--------------|
| None | No | N/A | N/A |

### Data / Fixtures

- [x] **None** - no data or fixtures needed

### Access / Permissions

- [x] **None** - no special access required

### Developer Tooling

- [x] **Runtime**: Python 3.12+
- [x] **Package manager**: uv
- [x] **Additional CLI tools**: pytest via project dependencies

---

## Success Criteria - Integration Tests (TDD First)

The integration tests below are written before implementation changes. They prove that consumer-defined guardrails and mutable permission maps work through the public SDK surface.

**Note**: The first two code blocks validate `ToolExecutor.execute()` directly — focused executor coverage that proves permission and guardrail logic returns the correct dicts. The third code block drives the full `Agent.run()` loop to prove that a denied result propagates as a `tool`-role message in agent message history (the end-to-end security UX requirement).

```python
# Test file: tests/integration/goals/test_adv_02_guardrail_system.py
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

    result = await ToolExecutor.execute(shell_execute, {"command": "rm -rf /"}, agent)

    assert result == {"approved": False, "reason": "Dangerous tool blocked."}
    assert logging_guardrail.calls == [("shell_execute", {"command": "rm -rf /"})]
    assert invoked is False
```

```python
# Test file: tests/integration/goals/test_adv_02_guardrail_system.py (continued)
"""Agent-loop level test: denied result propagates as tool message."""


class MockReturningLanguageModel(LanguageModel):
    async def generate(self, messages, tools=None):
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "call_denied", "function": {"name": "delete_file", "arguments": '{"path": "secret.txt"}'}}
            ],
        }


async def test_agent_loop_propagates_denied_tool_as_message():
    """Denied tool result propagates through Agent.run() as a tool-role message."""
    invoked = False

    @tool(name="delete_file")
    def delete_file(path: str) -> str:
        nonlocal invoked
        invoked = True
        return f"deleted {path}"

    agent = Agent(
        llm_model=MockReturningLanguageModel(),
        tool_permissions={"delete_file": "ask"},
        approval_workflow=DangerousToolGuardrail(),
        tools=[delete_file],
    )

    messages = await Agent.run(agent, "Delete secret.txt")
    tool_messages = [m for m in messages if m.get("role") == "tool"]

    assert len(tool_messages) >= 1
    assert any("Dangerous tool blocked." in str(m.get("content", "")) for m in tool_messages)
    assert invoked is False
```

```python
# Test file: tests/integration/goals/test_adv_03_permission_system.py
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

    result = await ToolExecutor.execute(shell_execute, {"command": "whoami"}, agent)

    assert result == {"error": "Tool 'shell_execute' is denied by permission map."}
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
    assert denied == {"error": "Tool 'touch_file' is denied by permission map."}
    assert count == 1
```

### Key Test Scenarios

- [ ] **DangerousToolGuardrail Blocks**: a consumer guardrail can deny a dangerous tool call and prevent invocation.
- [ ] **LoggingGuardrail Logs Without Blocking**: an approving guardrail can observe a tool call while execution continues.
- [ ] **Chained guardrails**: when multiple workflows are configured, they run in order and the first denial wins.
- [ ] **Permission Map Deny**: `tool_permissions[tool_name] = "deny"` blocks before any approval workflow runs.
- [ ] **Permission Map Ask**: `tool_permissions[tool_name] = "ask"` calls the approval workflow before invoking the tool.
- [ ] **Runtime Permission Mutation**: mutating `agent.tool_permissions` affects subsequent tool executions immediately.
- [ ] **Agent Loop Denial Propagation**: a denied tool result is propagated through `Agent.run()` as a `tool`-role message in the conversation history.

## Verification Plan

### Automated Tests

- [ ] Integration tests: `cd src/tinycua-sdk && uv run pytest tests/integration/goals/test_adv_02_guardrail_system.py tests/integration/goals/test_adv_03_permission_system.py -v`
- [ ] Unit tests for `ToolExecutor.execute`: `cd src/tinycua-sdk && uv run pytest tests/unit/test_tool_executor.py tests/unit/test_approval.py -v`
- [ ] Existing SDK test suite: `cd src/tinycua-sdk && uv run pytest`

### Manual Verification

- [ ] Confirm `Agent.tool_permissions` defaults to `{}` and missing tool names default to `"allow"`.
- [ ] Confirm public imports still expose `Agent`, `tool`, and approval workflow classes needed by consumer code.

### Performance Considerations

- [ ] Permission lookup is a single dictionary read per tool execution.
- [ ] Approval workflow chaining is only evaluated for `"ask"` tools and stops at the first denial.

## Proposed Changes

### Integration Tests

#### [NEW] `tests/integration/goals/test_adv_02_guardrail_system.py`

- **Description of change**: Add goal-level tests for custom `ApprovalWorkflow` implementations, logging guardrails, dangerous-tool denials, and workflow chaining.
- **Rationale**: These tests prove the consumer-defined guardrail patterns from the spec work through the SDK's public execution path.

#### [NEW] `tests/integration/goals/test_adv_03_permission_system.py`

- **Description of change**: Add goal-level tests for `"allow"`, `"ask"`, `"deny"`, missing permission defaults, and runtime permission mutation.
- **Rationale**: The permission map is the primary consumer-facing API for declarative tool control.

#### [MODIFY] `tests/unit/test_tool_executor.py`

- **Description of change**: Extend unit coverage for multiple approval workflows, first-denial short-circuiting, all-approved execution, and `"ask"` without workflow failure.
- **Rationale**: Unit tests should isolate the executor branch logic from goal-level integration behavior.

### Agent Configuration

#### [MODIFY] `tinycua_sdk/agent/config.py`

- **Description of change**: Ensure `tool_permissions` is modeled as `dict[str, Literal["allow", "ask", "deny"]]` and `approval_workflow` accepts either one `ApprovalWorkflow` or a list of workflows.
- **Rationale**: `Agent` stores execution policy in config, and chained guardrails require list-compatible typing.

#### [MODIFY] `tinycua_sdk/agent/agent.py`

- **Description of change**: Keep `tool_permissions` mutable through the `Agent.tool_permissions` property and accept list-based approval workflows in the constructor.
- **Rationale**: Runtime permission mutation is required by R-7.2, and list workflows are required by R-7.1/R-7.3.

### Tool Execution

#### [MODIFY] `tinycua_sdk/agent/executor.py`

- **Description of change**: Update `ToolExecutor.execute()` to check permission before invocation, fail safely for `"ask"` without a workflow, normalize approval workflow(s) to a list, run workflows in order, and return the first denial result.
- **Rationale**: This is the central enforcement point for guardrails and permissions.

### Security API

#### [MODIFY] `tinycua_sdk/security/approval.py`

- **Description of change**: Keep `ApprovalWorkflow.request_approval(tool_name, arguments)` as the consumer extension point and retain `DefaultApprovalWorkflow` as an always-approve implementation.
- **Rationale**: The spec relies on user-defined subclasses and does not require built-in concrete guardrail classes.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `Agent` | Modify | Stores mutable tool permission policy and optional approval workflow(s). |
| `AgentConfig` | Modify | Carries permission and approval settings in serialized agent configuration. |
| `ToolExecutor` | Modify | Enforces permission and approval checks before invoking tools. |
| `ApprovalWorkflow` | Existing | Provides the async consumer-defined approval contract. |
| Integration goal tests | New | Validates guardrail and permission behavior against the stage-07 goals. |

## Data Model Changes

```python
from typing import Literal

ToolPermission = Literal["allow", "ask", "deny"]

class AgentConfig:
    tool_permissions: dict[str, ToolPermission]
    approval_workflow: ApprovalWorkflow | list[ApprovalWorkflow] | None
```

## API Changes

### New Endpoints

No HTTP endpoints are introduced.

### Modified Public SDK API

| API | Change |
|-----|--------|
| `Agent(..., tool_permissions=...)` | Accepts declarative per-tool permissions. |
| `Agent(..., approval_workflow=...)` | Accepts one workflow or a list of workflows. |
| `Agent.tool_permissions` | Mutable dict used immediately by `ToolExecutor.execute()`. |
| `ToolExecutor.execute(tool, arguments, agent)` | Returns denial/error dicts when permissions or guardrails block execution. |

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| None | N/A | Uses existing SDK dependencies only. |

### Internal Dependencies

- [x] Depends on Stage 3 tool execution and approval workflow abstractions.
- [ ] Blocks consumers from safely composing tool guardrails until implemented.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `"ask"` without workflow accidentally executes | High | Fail safely with an error dict before tool invocation. |
| Chained workflow support breaks existing single-workflow behavior | Medium | Normalize non-list workflows to a one-item list inside `ToolExecutor.execute()`. |
| Denial result shape is inconsistent | Medium | Preserve workflow denial dicts and use stable permission error strings in tests. |
| Runtime mutation does not affect config-backed state | Medium | Expose `Agent.tool_permissions` as a property backed by `AgentConfig.tool_permissions`. |
| Tool invocation happens before approval | High | Integration tests track invocation side effects and assert blocked tools are never called. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-12*
