# Stage 7: Security — Guardrails & Permissions — Specification

## Objective
Declarative and custom guardrails control tool execution. Consumers can define permission levels and approval workflows without modifying core SDK code.

## References
- [`goals/advanced/02_guardrail_system.py`](../goals/advanced/02_guardrail_system.py)
- [`goals/advanced/03_permission_system.py`](../goals/advanced/03_permission_system.py)

## Requirements

### R-7.1: ApprovalWorkflow Integration

- `ToolExecutor` calls `approval_workflow.request_approval(tool_name, arguments)` before executing any tool.
- Must return a dict with at least `{"approved": bool}`.
- If `approved: False`, the tool is skipped and the agent receives the denial reason in the message history.
- Multiple guardrails can be chained (as a list). Checked in order; first denial wins.

### R-7.2: tool_permissions on Agent

- `Agent.tool_permissions: dict[str, Literal["allow", "ask", "deny"]] = {}`
- `"allow"` → execute immediately.
- `"deny"` → block immediately, return `{"error": "Tool 'X' is denied."}` to agent.
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

### SC-7.1: DangerousToolGuardrail Blocks
**What:** Dangerous tools are blocked by guardrail.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow

@tool
def shell_execute(command: str) -> str:
    return command

class DangerousToolGuardrail(ApprovalWorkflow):
    DANGEROUS = {'shell_execute'}
    async def request_approval(self, tool_name, arguments):
        if tool_name in self.DANGEROUS:
            return {'approved': False, 'reason': 'Blocked.'}
        return {'approved': True}

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[shell_execute], approval_workflow=DangerousToolGuardrail())
r = asyncio.run(a.run(\"Run 'ls'.\"))
assert 'Blocked' in r
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-7.2: LoggingGuardrail Logs Without Blocking
**What:** Logging guardrail records but does not block.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow

class LogGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name, arguments):
        return {'approved': True}

@tool
def read_file(path: str) -> str:
    return 'content'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[read_file], approval_workflow=LogGuardrail())
r = asyncio.run(a.run('Read README.md'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-7.3: Permission Map Deny
**What:** `"deny"` in `tool_permissions` blocks without guardrail.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

@tool
def shell_execute(command: str) -> str:
    return command

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[shell_execute])
a.tool_permissions['shell_execute'] = 'deny'
r = asyncio.run(a.run(\"Run 'rm -rf /'.\"))
assert 'denied' in r.lower()
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-7.4: Permission Map Ask
**What:** `"ask"` triggers guardrail.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow

class AskGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name, arguments):
        return {'approved': True, 'notified': True}

@tool
def write_file(path: str, content: str) -> str:
    return 'wrote'

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[write_file], approval_workflow=AskGuardrail())
a.tool_permissions['write_file'] = 'ask'
r = asyncio.run(a.run('Write hello to /tmp/test.txt'))
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-7.5: Runtime Permission Mutation
**What:** Changing `tool_permissions` at runtime works immediately.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

@tool
def shell_execute(command: str) -> str:
    return command

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[shell_execute])
a.tool_permissions['shell_execute'] = 'deny'
r1 = asyncio.run(a.run(\"Run 'echo hello'.\"))
assert 'denied' in r1.lower()
a.tool_permissions['shell_execute'] = 'allow'
r2 = asyncio.run(a.run(\"Run 'echo hello'.\"))
assert 'denied' not in r2.lower()
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-7.6: Integration Tests Pass
**What:** Both Stage 7 integration tests pass.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_adv_02_guardrail_system.py tests/integration/goals/test_adv_03_permission_system.py -v
```
**Pass if:** 2 passed, 0 failed.

## Integration Test Files
- `tests/integration/goals/test_adv_02_guardrail_system.py`
- `tests/integration/goals/test_adv_03_permission_system.py`
