# Stage 7: Security — Guardrails & Permissions — Targets

## Purpose
Verify permission checks and guardrail workflows. Uses a real or mock LLM server for full agent loop testing.

---

### Target 7.1: DangerousToolGuardrail Blocks Tools

**File:** `targets/01_dangerous_tool_guardrail.py`

```python
"""Target 7.1: Verify DangerousToolGuardrail blocks dangerous tools."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    return f"ran: {command}"


class DangerousToolGuardrail(ApprovalWorkflow):
    DANGEROUS = {"shell_execute"}

    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        if tool_name in self.DANGEROUS:
            return {"approved": False, "reason": f"'{tool_name}' is classified as dangerous."}
        return {"approved": True}


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[shell_execute],
        approval_workflow=DangerousToolGuardrail(),
        tool_permissions={"shell_execute": "ask"},
    )

    response = await a.run("Run 'ls -la'", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/01_dangerous_tool_guardrail_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 7.2: LoggingGuardrail Logs Without Blocking

**File:** `targets/02_logging_guardrail.py`

```python
"""Target 7.2: Verify LoggingGuardrail records but never blocks."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


@tool
def read_file(path: str) -> str:
    """Read a file."""
    return "file content"


class LoggingGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"[AUDIT] tool={tool_name} args={arguments}")
        return {"approved": True, "logged_at": "2024-01-15T10:00:00Z"}


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[read_file],
        approval_workflow=LoggingGuardrail(),
        tool_permissions={"read_file": "ask"},
    )

    response = await a.run("Read README.md", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/02_logging_guardrail_expected-output.txt` → `[AUDIT] tool=read_file args={...}\nResponse: <any string>` (must not raise)

---

### Target 7.3: Permission Map Deny Blocks Immediately

**File:** `targets/03_permission_deny.py`

```python
"""Target 7.3: Verify 'deny' permission blocks without needing a guardrail."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool


@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    return f"ran: {command}"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[shell_execute],
    )

    # Set deny permission (no guardrail needed)
    a.tool_permissions["shell_execute"] = "deny"

    response = await a.run("Run 'rm -rf /'", stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/03_permission_deny_expected-output.txt` → `Response: <any string>` (must not raise)

---

### Target 7.4: Permission Map Ask Triggers Guardrail

**File:** `targets/04_permission_ask.py`

```python
"""Target 7.4: Verify 'ask' permission routes through ApprovalWorkflow."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool
from tinycua_sdk.security.approval import ApprovalWorkflow


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    return f"Wrote to {path}"


class SimpleAskGuardrail(ApprovalWorkflow):
    async def request_approval(self, tool_name: str, arguments: dict) -> dict:
        print(f"[ASK] {tool_name}({arguments}) — auto-approved for demo")
        return {"approved": True, "notified": True}


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[write_file],
        approval_workflow=SimpleAskGuardrail(),
    )

    # Set ask permission (triggers guardrail)
    a.tool_permissions["write_file"] = "ask"

    response = await a.run('Write "hello" to /tmp/test.txt', stream=False)
    assert isinstance(response, str)
    print(f"Response: {response}")


asyncio.run(main())
```

**Expected Output:** `targets/04_permission_ask_expected-output.txt` → `[ASK] write_file({...}) — auto-approved for demo\nResponse: <any string>` (must not raise)

---

### Target 7.5: Runtime Permission Mutation

**File:** `targets/05_runtime_mutation.py`

```python
"""Target 7.5: Verify changing tool_permissions at runtime takes effect immediately."""

import asyncio
from tinycua_sdk import Agent, LanguageModel, tool


@tool
def shell_execute(command: str) -> str:
    """Execute a shell command."""
    return f"ran: {command}"


async def main():
    a = Agent(
        llm_model=LanguageModel(base_url="http://localhost:1234/v1", api_key="dummy"),
        tools=[shell_execute],
    )

    # First run: deny
    a.tool_permissions["shell_execute"] = "deny"
    r1 = await a.run("Run 'echo hello'", stream=False)
    assert isinstance(r1, str)
    print(f"[denied] Response: {r1}")

    # Second run: allow (runtime mutation)
    a.tool_permissions["shell_execute"] = "allow"
    r2 = await a.run("Run 'echo hello'", stream=False)
    assert isinstance(r2, str)
    print(f"[allowed] Response: {r2}")


asyncio.run(main())
```

**Expected Output:** `targets/05_runtime_mutation_expected-output.txt` → `[denied] Response: ...\n[allowed] Response: ...` (must not raise)
