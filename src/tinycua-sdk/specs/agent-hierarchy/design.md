# Design Document: Agent Hierarchy

**Spec**: `specs/agent-hierarchy/spec.md`
**Status**: Draft
**Last Updated**: 2026-03-16

---

## Overview

Agent hierarchy allows a parent agent to delegate tasks to pre-defined sub-agents. This enables:
- Task decomposition
- Specialized agents for different domains
- Hierarchical execution with result aggregation

---

## Architecture

```
┌─────────────────────────────────────────┐
│            Parent Agent                   │
│  ┌─────────────────────────────────┐     │
│  │  Task Analysis                  │     │
│  │  Sub-agent Selection            │     │
│  │  Result Aggregation             │     │
│  └─────────────────────────────────┘     │
│                   │                        │
│         ┌─────────┴─────────┐              │
│         ▼                   ▼              │
│  ┌───────────┐      ┌───────────┐        │
│  │ Sub-agent │      │ Sub-agent │        │
│  │ (Research)│      │  (Code)   │        │
│  └───────────┘      └───────────┘        │
└─────────────────────────────────────────┘
```

---

## Implementation

### Agent with Sub-agents

```python
class Agent:
    def __init__(
        self,
        name: str,
        instructions: str = "",
        sub_agents: list["Agent"] | None = None,
        max_depth: int = 3,
        current_depth: int = 0,
        # ... other params
    ):
        self.name = name
        self.instructions = instructions
        self.sub_agents = sub_agents or []
        self.max_depth = max_depth
        self.current_depth = current_depth
    
    def add_sub_agent(self, agent: "Agent") -> None:
        """Add a sub-agent to this agent."""
        if len(self.sub_agents) >= 10:
            raise ValueError("Maximum 10 sub-agents per agent")
        self.sub_agents.append(agent)
    
    def _get_all_sub_agents(self, depth: int = 1) -> dict[str, "Agent"]:
        """Get all sub-agents up to max depth."""
        if depth >= self.max_depth:
            return {self.name: self}
        
        result = {self.name: self}
        for sub in self.sub_agents:
            result.update(sub._get_all_sub_agents(depth + 1))
        return result
```

### Delegation Logic

```python
async def run(self, user_input: str, instructions: str | None = None):
    # Check depth
    if self.current_depth >= self.max_depth:
        return await self._execute_local(user_input)
    
    # Analyze if delegation is needed
    should_delegate, target_sub_agent = await self._analyze_delegation(
        user_input
    )
    
    if should_delegate and target_sub_agent:
        # Delegate to sub-agent
        sub_result = await target_sub_agent.run(
            user_input,
            instructions=instructions,
            _depth=self.current_depth + 1,
        )
        
        # Aggregate results
        return await self._aggregate_results(sub_result, target_sub_agent)
    
    # Normal execution
    return await self._execute_local(user_input)

async def _analyze_delegation(self, user_input: str) -> tuple[bool, "Agent | None"]:
    """Analyze if task should be delegated."""
    if not self.sub_agents:
        return False, None
    
    # Simple keyword matching (can be enhanced with LLM)
    for sub in self.sub_agents:
        if self._matches_sub_agent(user_input, sub):
            return True, sub
    
    return False, None

def _matches_sub_agent(self, user_input: str, sub_agent: "Agent") -> bool:
    """Check if sub-agent can handle the task."""
    # Simple keyword matching based on sub-agent name/instructions
    keywords = {
        "research": ["search", "find", "look up", "research"],
        "code": ["code", "program", "implement", "write code"],
        "analysis": ["analyze", "calculate", "process"],
    }
    
    keywords_lower = [k.lower() for k in keywords.get(sub_agent.name.lower(), [])]
    return any(kw in user_input.lower() for kw in keywords_lower)
```

### Context Passing

```python
async def _pass_context(
    self,
    user_input: str,
    sub_agent: "Agent",
) -> str:
    """Pass relevant context to sub-agent."""
    context = f"""
    Parent Task: {user_input}
    Parent Agent: {self.name}
    Instructions: {self.instructions}
    
    Please complete this task and return results.
    """
    return context
```

### Result Aggregation

```python
async def _aggregate_results(
    self,
    sub_result: str,
    sub_agent: "Agent",
) -> str:
    """Aggregate results from sub-agent."""
    return f"""
    [Sub-agent: {sub_agent.name}]
    Result: {sub_result}
    
    Summary: Completed via delegation to {sub_agent.name}
    """
```

---

## Usage Example

```python
# Create specialized sub-agents
research_agent = Agent(
    name="research",
    instructions="You are a research assistant. Search for information.",
)

code_agent = Agent(
    name="code",
    instructions="You are a coding assistant. Write code.",
)

# Create parent agent with sub-agents
main_agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant. Delegate tasks when appropriate.",
    sub_agents=[research_agent, code_agent],
)

# Use
result = await main_agent.run("Search for Python tutorials and write a hello world program")
```

---

## Constraints

1. **Max Depth**: 3 levels
2. **Max Sub-agents**: 10 per agent
3. **Pre-defined**: Sub-agents must be created beforehand
4. **No Dynamic Creation**: Cannot create agents at runtime

---

## Error Handling

```python
async def run(self, user_input: str):
    if self.current_depth >= self.max_depth:
        raise AgentHierarchyError(
            f"Max depth {self.max_depth} reached"
        )
    
    if len(self.sub_agents) > 10:
        raise AgentHierarchyError(
            "Maximum 10 sub-agents allowed"
        )
```

---

## Future Enhancements

- LLM-based sub-agent selection
- Parallel sub-agent execution
- Result merging
- Context caching
