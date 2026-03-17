# Feature Specification: Agent Hierarchy

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

**Goals**: Enable agents to delegate tasks to sub-agents, allowing:
1. Complex task decomposition
2. Specialized sub-agents for specific domains
3. Hierarchical task execution

**Gaps**:
- No support for agent-to-agent delegation
- No hierarchy management

**Non-Goals**:
- Dynamic sub-agent creation (sub-agents must be pre-defined)
- Unlimited nesting (max depth: 3)

---

## User Scenarios

### Primary Scenario

A user has a main agent that can delegate to specialized sub-agents:
- Research sub-agent for web searches
- Code sub-agent for programming tasks
- Analysis sub-agent for data processing

### Acceptance Scenarios

1. **Given** an agent with sub-agents, **when** a task requires specialization, **then** the parent agent can delegate to the appropriate sub-agent.

2. **Given** a sub-agent completes its task, **when** control returns to the parent, **then** the parent can aggregate results.

3. **Given** the hierarchy exceeds max depth, **when** delegation is attempted, **then** an error is raised.

---

## Requirements

### FR-001

Agents MAY have a list of sub-agents.

### FR-002

Sub-agents MUST be pre-defined (not dynamically created).

### FR-003

The hierarchy depth MUST NOT exceed 3 levels.

### FR-004

Parent agents MUST be able to pass context to sub-agents.

### FR-005

Sub-agents MUST return results to parent agents.

---

## API Design

### Agent with Sub-agents

```python
class Agent:
    def __init__(
        self,
        name: str,
        sub_agents: list["Agent"] | None = None,
        max_depth: int = 3,
        # ... other params
    ):
        self.sub_agents = sub_agents or []
        self.max_depth = max_depth
    
    def add_sub_agent(self, agent: "Agent") -> None:
        """Add a sub-agent."""
        self.sub_agents.append(agent)
```

### Delegation

```python
async def run(self, user_input: str):
    # Analyze if delegation is needed
    if should_delegate(user_input):
        sub_agent = select_sub_agent(user_input)
        result = await sub_agent.run(user_input)
        return aggregate(result)
    
    # Normal execution
    return await self._execute_local(user_input)
```

---

## Status

| Component | Status |
|-----------|--------|
| Sub-agent definition | ⏳ |
| Delegation mechanism | ⏳ |
| Context passing | ⏳ |
| Result aggregation | ⏳ |
| Depth limiting | ⏳ |

---

## Review Checklist

- [ ] No implementation details
- [ ] All mandatory sections completed
- [ ] Requirements are testable
- [ ] Scope clearly bounded
