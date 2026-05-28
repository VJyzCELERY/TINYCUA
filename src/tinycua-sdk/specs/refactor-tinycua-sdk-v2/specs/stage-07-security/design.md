# Stage 7: Security — Guardrails & Permissions — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-07-security/spec.md`
**Last Updated**: 2026-05-15

## Implementation

No new files. This enhances `ToolExecutor.execute()` from Stage 3 and expands `Agent` / `AgentConfig` to carry permission and workflow policy.

### `ToolExecutor.execute()` (updated)

```python
class ToolExecutor:
    @staticmethod
    async def execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
        # 1. Permission check
        permission = agent.tool_permissions.get(tool.name, "allow")
        if permission == "deny":
            return {"error": f"Tool '{tool.name}' is denied by permission map."}

        # 2. Fail closed for invalid permission values
        if permission not in ("allow", "ask"):
            return {"error": f"Tool '{tool.name}' has invalid permission '{permission}'. Denying execution."}

        # 3. Approval check
        if permission == "ask":
            workflows = agent.approval_workflow
            if workflows is None:
                # No workflow attached — treat as deny for safety
                return {"error": f"Tool '{tool.name}' requires approval but no workflow is configured."}

            # Normalize to list
            if not isinstance(workflows, list):
                workflows = [workflows]

            # Fail closed for empty list — no workflow means no approval possible
            if not workflows:
                return {"error": f"Tool '{tool.name}' requires approval but no workflow is configured."}

            for workflow in workflows:
                approval = await workflow.request_approval(tool.name, arguments)
                if not approval.get("approved"):
                    return approval  # Return first denial

        # 4. Execute
        return tool.invoke(**arguments)
```

### `Agent` & `AgentConfig` API Changes

The `Agent` constructor accepts optional permission and workflow parameters:

```python
from tinycua_sdk.security.approval import ApprovalWorkflow
from typing import Literal

ToolPermission = Literal["allow", "ask", "deny"]


class AgentConfig:
    tool_permissions: dict[str, ToolPermission]  # per-agent default in __init__; use default_factory=dict
    approval_workflow: ApprovalWorkflow | list[ApprovalWorkflow] | None = None


class Agent:
    def __init__(
        self,
        ...,
        tool_permissions: dict[str, ToolPermission] | None = None,
        approval_workflow: ApprovalWorkflow | list[ApprovalWorkflow] | None = None,
    ):
        self._config.tool_permissions = tool_permissions or {}
        self._config.approval_workflow = approval_workflow
```

`Agent.tool_permissions` is a mutable property backed by `AgentConfig.tool_permissions`, allowing runtime mutation:

```python
agent.tool_permissions["shell_execute"] = "deny"   # blocks immediately
agent.tool_permissions["read_file"] = "ask"          # routes through guardrails
```

## Design Decisions

### Permission Check Order
1. **Lookup** `tool_permissions` map.
2. **Deny** immediately if `"deny"`.
3. **Ask** if `"ask"` — route through all workflows; first denial wins.
4. **Allow** if `"allow"` or not in map.

### Why "ask" without workflow is an error
If a consumer marks a tool as `"ask"` but forgets to attach a workflow, we fail safely by denying. This prevents accidental unrestricted execution.

### Invalid permissions fail closed
Any value in `tool_permissions` that is not `"allow"`, `"ask"`, or `"deny"` is treated as deny. This prevents a typo (e.g., `"denny"` or `"Allow"`) from silently allowing execution. The check runs after the explicit deny branch and before the approval/execution path, so every mutation of the permission map is validated at enforcement time.

### Chaining Workflows
`agent.approval_workflow` can be:
- A single `ApprovalWorkflow` instance.
- A list of `ApprovalWorkflow` instances.

This lets consumers compose guardrails:
```python
agent = Agent(
    approval_workflow=[LoggingGuardrail(), DangerousToolGuardrail()],
)
```

### Tool Result on Denial
When a tool is denied, the result is a dict. It gets stringified and appended to the conversation history as a `function_call_output` item, matching the SDK's existing loop contract in `Agent.run()` (`src/tinycua-sdk/tinycua_sdk/agent/loop.py:127-132`):
```python
from tinycua_sdk.models.response import FunctionCallOutput

# Inside Agent.run(), after execute returns a denial dict:
item = FunctionCallOutput(
    call_id=tc["id"],
    output=str(denial_result),  # e.g., '{"approved": false, "reason": "Blocked"}'
)
```

This lets the LLM see why the tool was blocked and respond accordingly.

## Data Flow

```
LLM requests tool call: calculator({"expression": "2+2"})
    │
    ▼
ToolExecutor.execute(calculator, {"expression": "2+2"}, agent)
    │
    ├──► agent.tool_permissions.get("calculator", "allow") → "allow"
    │
    └──► tool.invoke(expression="2+2") → "4"

LLM requests tool call: shell_execute({"command": "rm -rf /"})
    │
    ▼
ToolExecutor.execute(shell_execute, {"command": "rm -rf /"}, agent)
    │
    ├──► agent.tool_permissions.get("shell_execute", "allow") → "deny"
    │
    └──► Return {"error": "Tool 'shell_execute' is denied by permission map."}

LLM requests tool call: write_file({"path": "/tmp/x", "content": "y"})
    │
    ▼
ToolExecutor.execute(write_file, {...}, agent)
    │
    ├──► permission → "ask"
    │
    ├──► workflow.request_approval("write_file", {...})
    │       └──► LoggingGuardrail logs
    │       └──► DangerousToolGuardrail approves (not in dangerous list)
    │
    └──► tool.invoke(...) → "Wrote to /tmp/x"
```

## File Changes

| File | Change |
|------|--------|
| `agent/executor.py` | Update `ToolExecutor.execute()` with permission + approval logic |
| `agent/agent.py` | Accept `tool_permissions` and `approval_workflow` in constructor; expose mutable `tool_permissions` property |
| `agent/config.py` | Add `tool_permissions: dict[str, ToolPermission]` and `approval_workflow: ApprovalWorkflow | list[ApprovalWorkflow] | None` |
| `security/approval.py` | Already has ABC from Stage 3; ensure it supports all patterns |

## Testing Strategy

- Unit test `ToolExecutor.execute` with mock agent:
  - Permission "allow" → executes.
  - Permission "deny" → returns error dict.
  - Permission "ask" with workflow → calls workflow.
  - Permission "ask" without workflow → returns error.
  - Multiple workflows, first denies → stops at first.
  - Multiple workflows, all approve → executes.
- Integration tests validate full agent loop with guardrails.
