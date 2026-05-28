# Tool Permissions and Approval

**Prerequisites**: [Skills and Skill Registry](./skills-and-skill-registry.md) —
you can define tools and inject skills into an agent.

## Overview

When an agent calls a tool, the SDK evaluates two independent layers of control:
**tool permissions** (a static map of `"allow"` / `"ask"` / `"deny"`) and an
**approval workflow** (a pluggable async callback). Together they let you decide
which tools run automatically, which require human confirmation, and which are
blocked outright.

This page covers the three permission levels, how to implement a custom
`ApprovalWorkflow`, the built-in `DefaultApprovalWorkflow`, and how to chain
multiple workflows for multi-tier approval.

## Tool Permissions

Pass a `dict[str, Literal["allow", "ask", "deny"]]` to `Agent` at construction
time or set it later via the `tool_permissions` property.

| Level | Behavior |
|-------|----------|
| `"allow"` | Tool executes immediately. No approval required. |
| `"ask"` | Tool requires approval via the configured `ApprovalWorkflow`. If no workflow is configured, returns an error. |
| `"deny"` | Tool is blocked. The agent receives an error message and cannot invoke it. |

Unlisted tools default to `"allow"`.

```python
import os

from tinycua_sdk import Agent, LanguageModel, tool


@tool
def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    return f"Contents of {path}"


@tool
def delete_file(path: str) -> str:
    """Delete a file from disk."""
    return f"Deleted {path}"


@tool
def list_files(directory: str) -> str:
    """List files in a directory."""
    return "file1.txt, file2.txt"


# Local — local LLM server
model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="file-manager",
    instructions="You manage files on the user's system.",
    llm_model=model,
    tools=[read_file, delete_file, list_files],
    tool_permissions={
        "read_file": "allow",       # safe — runs automatically
        "delete_file": "ask",       # dangerous — requires approval
        "list_files": "allow",      # read-only — runs automatically
    },
)
```

Remote (OpenAI):

```python
import os

from tinycua_sdk import Agent, LanguageModel, tool


@tool
def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    return f"Contents of {path}"


@tool
def delete_file(path: str) -> str:
    """Delete a file from disk."""
    return f"Deleted {path}"


model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="file-manager",
    instructions="You manage files on the user's system.",
    llm_model=model,
    tools=[read_file, delete_file],
    tool_permissions={
        "read_file": "allow",
        "delete_file": "ask",
    },
)
```

Update permissions after construction:

```python
agent.tool_permissions = {
    "read_file": "allow",
    "delete_file": "deny",    # change from "ask" to "deny"
    "list_files": "allow",
}
```

## Approval Workflow

### The ABC

`ApprovalWorkflow` is an abstract base class with one required method:

```python
from abc import abstractmethod
from typing import Any


class ApprovalWorkflow:
    @abstractmethod
    async def request_approval(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        ...
```

The method receives the tool name and resolved arguments. It must return a dict
with at least an `"approved"` key (`True` or `False`). Additional keys may be
added for logging or multi-step workflows.

### `DefaultApprovalWorkflow` — Always Approve

This is the built-in no-op workflow. Every tool marked `"ask"` is automatically
approved:

```python
import os
from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.security.approval import DefaultApprovalWorkflow

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

workflow = DefaultApprovalWorkflow()

agent = Agent(
    name="auto-approver",
    instructions="...",
    llm_model=model,
    tool_permissions={"delete_file": "ask"},
    approval_workflow=workflow,
)
```

### Custom Workflow

Implement a custom workflow to add real decision logic — console prompts,
external service calls, or human-in-the-loop gates:

```python
from typing import Any
from tinycua_sdk.security.approval import ApprovalWorkflow


class ConsoleApprovalWorkflow(ApprovalWorkflow):
    """Prompt the user in the console before executing a tool."""

    async def request_approval(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        print(f"\n=== Approval Required ===")
        print(f"Tool:     {tool_name}")
        print(f"Arguments: {arguments}")
        response = input("Approve? (y/n): ").strip().lower()
        return {"approved": response == "y"}
```

Attach it to the agent:

```python
agent = Agent(
    name="guarded-agent",
    instructions="You are a careful assistant.",
    llm_model=model,
    tool_permissions={"delete_file": "ask", "read_file": "allow"},
    approval_workflow=ConsoleApprovalWorkflow(),
)
```

With a remote provider:

```python
model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="guarded-agent",
    instructions="You are a careful assistant.",
    llm_model=model,
    tool_permissions={"delete_file": "ask", "read_file": "allow"},
    approval_workflow=ConsoleApprovalWorkflow(),
)
```

### Multi-Workflow Chaining

Pass a **list** of workflows to chain them. The SDK evaluates each workflow in
order. Execution stops at the first rejection; the tool only runs if all
workflows approve:

```python
import os
from typing import Any
from tinycua_sdk import Agent, LanguageModel
from tinycua_sdk.security.approval import ApprovalWorkflow, DefaultApprovalWorkflow

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),
)


class LoggingWorkflow(ApprovalWorkflow):
    """Log every approval request."""

    async def request_approval(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        print(f"[LOG] Tool {tool_name} called with {arguments}")
        return {"approved": True}


class RateLimitingWorkflow(ApprovalWorkflow):
    """Reject if more than 5 calls per minute."""

    def __init__(self):
        self._call_count = 0

    async def request_approval(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        self._call_count += 1
        if self._call_count > 5:
            return {"approved": False, "reason": "rate limit exceeded"}
        return {"approved": True}


agent = Agent(
    name="multi-gate-agent",
    instructions="...",
    llm_model=model,
    tool_permissions={"delete_file": "ask"},
    approval_workflow=[LoggingWorkflow(), RateLimitingWorkflow()],
)
```

## Common Pitfalls

**`"ask"` without a workflow**. If a tool is marked `"ask"` but
`approval_workflow` is `None` (the default), the tool call fails with an error
message appended to the conversation. Either set the tool to `"allow"` or
provide a workflow.

**Workflow returns unexpected shape**. The SDK reads the `"approved"` key from
the workflow's return dict. If your custom workflow returns `{"approved":
"yes"}` (string, not boolean), the truthiness check may behave unexpectedly.
Always return a boolean.

**Chaining order matters**. Workflows run in list order. Place blocking
gateways (console prompts, external approvals) after non-blocking ones
(logging, rate limiting) so that fast checks skip unnecessary I/O.

## Next Steps

- **[Streaming File Uploads](../advanced-file-handling/streaming-file-uploads.md)** —
  Upload large files without buffering in memory.
- **[Creating Tools](./creating-tools.md)** — Define the tools your agent calls.
