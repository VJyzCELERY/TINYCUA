# Stage 7: Security — Guardrails & Permissions — Design

## Implementation

No new files. This enhances `ToolExecutor.execute()` from Stage 3.

### `ToolExecutor.execute()` (updated)

```python
class ToolExecutor:
    @staticmethod
    async def execute(tool: Tool, arguments: dict, agent: Agent) -> Any:
        # 1. Permission check
        permission = agent.tool_permissions.get(tool.name, "allow")
        if permission == "deny":
            return {"error": f"Tool '{tool.name}' is denied by permission map."}

        # 2. Approval check
        if permission == "ask":
            workflows = agent.approval_workflow
            if workflows is None:
                # No workflow attached — treat as deny for safety
                return {"error": f"Tool '{tool.name}' requires approval but no workflow is configured."}

            # Normalize to list
            if not isinstance(workflows, list):
                workflows = [workflows]

            for workflow in workflows:
                approval = await workflow.request_approval(tool.name, arguments)
                if not approval.get("approved"):
                    return approval  # Return first denial

        # 3. Execute
        return tool.invoke(**arguments)
```

## Design Decisions

### Permission Check Order
1. **Lookup** `tool_permissions` map.
2. **Deny** immediately if `"deny"`.
3. **Ask** if `"ask"` — route through all workflows; first denial wins.
4. **Allow** if `"allow"` or not in map.

### Why "ask" without workflow is an error
If a consumer marks a tool as `"ask"` but forgets to attach a workflow, we fail safely by denying. This prevents accidental unrestricted execution.

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
When a tool is denied, the result is a dict. It gets stringified and appended to the message history as a `tool` role message:
```python
messages.append({
    "role": "tool",
    "tool_call_id": tc["id"],
    "name": tool_name,
    "content": str(denial_result),  # e.g., '{"approved": false, "reason": "Blocked"}'
})
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
