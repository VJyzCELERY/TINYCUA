# Stage 7: Security — Guardrails & Permissions — Specification

**Status**: Draft | In Progress | Complete
**Created**: 2026-05-02
**Last Updated**: 2026-05-02
**Subproject(s) Affected**: tinycua-sdk

## Objective
Declarative and custom guardrails control tool execution. Consumers can define permission levels and approval workflows without modifying core SDK code.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## References
- [`goals/advanced/02_guardrail_system.py`](../../goals/advanced/02_guardrail_system.py)
- [`goals/advanced/03_permission_system.py`](../../goals/advanced/03_permission_system.py)

## Requirements

### R-7.1: ApprovalWorkflow Integration

- `ToolExecutor` evaluates `agent.tool_permissions[tool_name]` first: when the effective permission is "ask", it calls `approval_workflow.request_approval(tool_name, arguments)`; "allow" executes immediately; "deny" blocks before any workflow.
- Must return a dict with at least `{"approved": bool}`.
- If `approved: False`, the tool is skipped and the agent receives the denial reason in the message history.
- Multiple guardrails can be chained (as a list). Checked in order; first denial wins.

### R-7.2: tool_permissions on Agent

- `Agent.tool_permissions: dict[str, Literal["allow", "ask", "deny"]] = {}`
- `"allow"` → execute immediately.
- `"deny"` → block immediately, return `{"error": "Tool 'X' is denied by permission map."}` to agent.
- `"ask"` → route through `ApprovalWorkflow`.
- Default is `"allow"` when tool name is not in the map.
- Can be mutated at runtime: `agent.tool_permissions["shell_execute"] = "deny"`.

### R-7.3: Built-in Guardrail Patterns

The spec must support these consumer-defined patterns:

**LoggingGuardrail:**
```python
class LoggingGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name, arguments):
        print(f"[AUDIT] {tool_name}({arguments})")
        return {"approved": True, "logged_at": "..."}
```

**DangerousToolGuardrail:**
```python
class DangerousToolGuardrail(ApprovalWorkflow):
    DANGEROUS = {"shell_execute", "delete_file"}
    async def request_approval(self, tool_name, arguments):
        if tool_name in self.DANGEROUS:
            return {"approved": False, "reason": "Dangerous tool blocked."}
        return {"approved": True}
```

**SimpleAskGuardrail:**
```python
class SimpleAskGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name, arguments):
        print(f"[ASK] {tool_name} — auto-approved")
        return {"approved": True, "notified": True}
```

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] DangerousToolGuardrail Blocks - tests/integration/goals/test_adv_02_guardrail_system.py - PASS - `print('PASS')`
  Description: Dangerous tools are blocked by guardrail.

- [ ] LoggingGuardrail Logs Without Blocking - tests/integration/goals/test_adv_02_guardrail_system.py - PASS - `print('PASS')`
  Description: Logging guardrail records but does not block.

- [ ] Permission Map Deny - tests/integration/goals/test_adv_03_permission_system.py - PASS - `print('PASS')`
  Description: `"deny"` in `tool_permissions` blocks without guardrail.

- [ ] Permission Map Ask - tests/integration/goals/test_adv_03_permission_system.py - PASS - `print('PASS')`
  Description: `"ask"` triggers guardrail.

- [ ] Runtime Permission Mutation - tests/integration/goals/test_adv_03_permission_system.py - PASS - `print('PASS')`
  Description: Changing `tool_permissions` at runtime works immediately.

- [ ] Chained guardrails First Denial Wins - tests/integration/goals/test_adv_02_guardrail_system.py - PASS - `print('PASS')`
  Description: Multiple chained guardrails stop at the first denial; later guardrails and tool invocation are skipped.

- [ ] Agent Loop Denial Propagation - tests/integration/goals/test_adv_02_guardrail_system.py - PASS - `print('PASS')`
  Description: A denied tool result propagates through `Agent.run()` as a `tool`-role message in message history.

- [ ] Integration Tests Pass - tests/integration/goals/test_adv_02_guardrail_system.py, tests/integration/goals/test_adv_03_permission_system.py - 7 passed, 0 failed - pytest -v

## Integration Test Files
- `tests/integration/goals/test_adv_02_guardrail_system.py`
- `tests/integration/goals/test_adv_03_permission_system.py`
