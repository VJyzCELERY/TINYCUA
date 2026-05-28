# Feature Specification: Remote Runner SDK

**Status**: Draft
**Created**: 2026-03-16
**Last Updated**: 2026-03-16
**Subproject(s) Affected**: tinycua-sdk

---

## Quick Guidelines

- Focus on **WHAT** users/callers need and **WHY** — not HOW to implement
- Every requirement must be independently testable

---

## Problem Statement

**Goals**: Provide an SDK for building custom runners that can execute agent tasks remotely, enabling:
1. Custom execution environments
2. Distributed agent execution
3. Resource-intensive tool execution offloaded to remote runners

**Gaps**:
- No standard interface for remote runners
- No SDK to build custom runners
- Backend doesn't have a runner SDK to work with

**Non-Goals**:
- Implementing actual remote runner (users build their own)
- Cloud infrastructure
- Runner orchestration/management

---

## User Scenarios

### Primary Scenario

A developer wants to build a custom runner that:
1. Receives agent tasks from the SDK
2. Executes tools in a specific environment (e.g., Docker container)
3. Returns results to the SDK

### Acceptance Scenarios

1. **Given** a developer using the Remote Runner SDK, **when** they implement a custom runner, **then** the SDK can send tasks to it seamlessly.

2. **Given** an agent configured to use a remote runner, **when** `.run()` is called, **then** the task is executed by the remote runner.

3. **Given** a remote runner is unavailable, **when** an agent attempts to run, **then** appropriate error handling occurs.

---

## Requirements

### FR-001

The Remote Runner SDK MUST provide a base class or interface for implementing custom runners.

### FR-002

The SDK MUST support sending tool definitions to the runner.

### FR-003

The SDK MUST support streaming tool execution results.

### FR-004

The SDK MUST handle authentication between SDK and runner.

### FR-005

The runner MUST be able to run locally (localhost) or remotely (network).

---

## API Design

### Runner Interface

```python
class RemoteRunner(ABC):
    """Base class for remote runners."""

    @abstractmethod
    async def execute(
        self,
        messages: list[dict],
        tools: list[Tool],
        options: RunnerOptions
    ) -> AsyncIterator[StreamEvent]:
        """Execute agent task."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if runner is healthy."""
        pass
```

### SDK Integration

```python
class Agent:
    def __init__(self, ..., runner: RemoteRunner | None = None):
        self.runner = runner

    async def run(self, user_input: str):
        if self.runner:
            return await self.runner.execute(...)
        return await self._local_run(...)
```

---

## Status

| Component | Status |
|-----------|--------|
| Runner Interface | ⏳ |
| SDK Integration | ⏳ |
| Authentication | ⏳ |
| Streaming Support | ⏳ |

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] Requirements are testable
- [ ] Scope clearly bounded
