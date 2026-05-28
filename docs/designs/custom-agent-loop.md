# Design Document: Custom Agent Loop

## Overview

This document provides the technical implementation design for Custom Agent Loop feature.

---

## Architecture

### 1. DefaultLoop Base Class

**Location**: `tinycua_sdk/agent/loop.py`

```python
from abc import ABC
from tinycua_sdk.models import RunResult

class DefaultLoop(ABC):
    """Base class for custom agent execution loops.
    
    Users extend this class to define custom execution strategies.
    Provides access to Runner helpers for tool execution and LLM calls.
    """
    
    def __init__(self, runner: "Runner"):
        """Initialize with runner instance.
        
        Args:
            runner: Runner instance for basic execution
        """
        self.runner = runner
    
    async def run(
        self,
        agent: "Agent",
        user_input: str,
        plan_mode: bool = False,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        **kwargs
    ) -> RunResult | str | AsyncIterator[StreamEvent]:
        """Execute the agent loop.
        
        Default implementation wraps Runner.run() or Runner.run_sse().
        Override to define custom execution strategy.
        
        Args:
            agent: The agent instance with tools
            user_input: The user's input
            plan_mode: If True, only allow plan-mode tools
            trace: If True, return RunResult with trace
            verbose: If True, log raw events
            stream_sse: If True, yield StreamEvents
            **kwargs: Additional parameters for custom loops
            
        Returns:
            RunResult if trace=True, string if not, AsyncIterator if stream_sse=True
        """
        # Apply runtime settings
        self.runner.trace = trace
        self.runner.verbose = verbose
        self.runner.stream_sse = stream_sse
        
        if stream_sse:
            return self.runner.run_sse(user_input)
        
        return await self.runner.run(user_input, trace=trace)
```

### 2. Runner - Minimal Interface

**Location**: `tinycua_sdk/runner/runner.py`

Rename methods and add helper methods:

```python
class Runner:
    """Minimal runner - provides basic execution toolbox."""
    
    def __init__(self, config, cancel_event=None):
        ...
    
    async def run(
        self,
        user_input: str,
        instructions: str | None = None,
        trace: bool = False,
    ) -> RunResult | str:
        """Execute agent with tool loop.
        
        Handles trace internally - returns RunResult if trace=True.
        
        Args:
            user_input: User message
            instructions: Optional system instructions
            trace: If True, return RunResult with trace
            
        Returns:
            RunResult if trace=True, string otherwise
        """
        # Current _chat_direct() logic
        ...
    
    async def run_sse(
        self,
        user_input: str,
        instructions: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream agent execution with SSE events.
        
        Yields StreamEvent objects for all operations.
        
        Args:
            user_input: User message
            instructions: Optional system instructions
            
        Yields:
            StreamEvent objects
        """
        # Current stream_with_tools() logic
        ...
    
    # Helper methods for custom loops:
    
    async def execute_tool(
        self, 
        tool_name: str, 
        tool_input: dict,
        plan_mode: bool = False
    ) -> Any:
        """Execute a single tool.
        
        Checks allowed_in_plan_mode if plan_mode=True.
        
        Args:
            tool_name: Name of tool to execute
            tool_input: Arguments for tool
            plan_mode: If True, block non-plan-mode tools
            
        Returns:
            Tool execution result
            
        Raises:
            PermissionError: If tool not allowed in plan mode
            ValueError: If tool not found
        """
        # Find tool
        for tool in self.tools:
            if tool.name == tool_name:
                if plan_mode and not getattr(tool, 'allowed_in_plan_mode', True):
                    raise PermissionError(f"Tool '{tool_name}' not allowed in plan mode")
                result = tool.invoke(**tool_input)
                if asyncio.iscoroutine(result):
                    result = await result
                return result
        raise ValueError(f"Tool '{tool_name}' not found")
    
    async def call_llm(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> "LLMResponse":
        """Call the LLM directly.
        
        Useful for custom loops that need to call LLM for planning/analysis.
        
        Args:
            messages: List of message dicts
            tools: Optional tool configurations
            
        Returns:
            LLM response object
        """
        request = ResponseRequest(
            model=self.model,
            input=messages,
            tools=tools or [],
        )
        return await self.client.create(request)
```

### 3. Agent with Loop Loading

**Location**: `tinycua_sdk/agent/agent.py`

```python
class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self._loop_cache = None
        ...
    
    def _load_loop(self) -> DefaultLoop:
        """Load custom loop from config or use DefaultLoop."""
        if self._loop_cache:
            return self._loop_cache
        
        loop_code = getattr(self.config, 'loop_code', None)
        loop_class = getattr(self.config, 'loop_class', None)
        
        if loop_code and loop_class:
            # Load custom loop via exec
            namespace = {"DefaultLoop": DefaultLoop}
            exec(loop_code, namespace)
            loop_type = namespace[loop_class]
            runner = Runner(self.config)
            loop = loop_type(runner)
        else:
            # Use built-in DefaultLoop
            runner = Runner(self.config)
            loop = DefaultLoop(runner)
        
        self._loop_cache = loop
        return loop
    
    async def run(
        self,
        user_input: str,
        plan_mode: bool = False,
        trace: bool = False,
        verbose: bool = False,
        stream_sse: bool = False,
        force_local: bool = False,
        **kwargs
    ):
        """Run the agent with configured loop.
        
        Args:
            user_input: User message
            plan_mode: Runtime - if True, only allow plan-mode tools
            trace: If True, return RunResult with trace
            verbose: If True, log raw events
            stream_sse: If True, yield StreamEvents
            force_local: Run locally even if deployed
            **kwargs: Passed to loop
        """
        # Local vs Remote decision
        if self.is_deployed and not force_local:
            return await self._run_deployed(
                user_input,
                plan_mode=plan_mode,
                trace=trace,
                **kwargs
            )
        
        # Local execution with custom loop
        loop = self._load_loop()
        return await loop.run(
            self,
            user_input,
            plan_mode=plan_mode,
            trace=trace,
            verbose=verbose,
            stream_sse=stream_sse,
            **kwargs
        )
```

### 4. Tool Metadata

**Location**: `tinycua_sdk/tools/decorators.py`

```python
class Tool:
    def __init__(
        self,
        name: str,
        func: callable,
        description: str = "",
        parameters: dict = {},
        allowed_in_plan_mode: bool = True,  # NEW
    ):
        self.name = name
        self.func = func
        self.description = description
        self.parameters = parameters
        self.allowed_in_plan_mode = allowed_in_plan_mode
```

---

## Custom Loop Examples

### Example 1: Hierarchical Loop

```python
class HierarchicalLoop(DefaultLoop):
    """Break complex tasks into subtasks with isolated contexts."""
    
    async def run(self, agent, user_input, max_depth=3, **kwargs):
        # Custom: decompose task first
        plan = await self._decompose(user_input, max_depth)
        
        # Execute each subtask
        results = []
        for subtask in plan['subtasks']:
            result = await self.runner.call_llm(
                messages=[{"role": "user", "content": subtask}],
                tools=self.runner._get_tool_configs()
            )
            results.append(result)
        
        # Custom: aggregate results
        return await self._aggregate(results)
    
    async def _decompose(self, task, max_depth):
        # Custom logic
        ...
    
    async def _aggregate(self, results):
        # Custom logic
        ...
```

### Example 2: ReAct Loop (Reason + Act)

```python
class ReActLoop(DefaultLoop):
    """Reason + Act pattern."""
    
    async def run(self, agent, user_input, **kwargs):
        messages = [{"role": "user", "content": user_input}]
        
        for _ in range(self.runner.max_tool_calls):
            # Reason
            response = await self.runner.call_llm(messages)
            
            if not response.choices[0].message.tool_calls:
                # No tool call - we're done
                return response.choices[0].message.content
            
            # Act
            for tc in response.choices[0].message.tool_calls:
                result = await self.runner.execute_tool(
                    tc.function.name,
                    json.loads(tc.function.arguments),
                    plan_mode=kwargs.get('plan_mode', False)
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)
                })
        
        return "Max iterations reached"
```

---

## Backend Changes

### 1. Run Request (Backend)

**Location**: `tinycua_backend/routers/run.py`

```python
class RunRequest(BaseModel):
    user_input: str
    plan_mode: bool = False  # NEW
    trace: bool = False      # NEW
    verbose: bool = False    # NEW
    stream_sse: bool = False # NEW
```

### 2. Agent Config

Loop code stored in agent config JSON:
```json
{
  "loop_code": "class MyLoop(DefaultLoop):\n    ...",
  "loop_class": "MyLoop"
}
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Agent Creation                                             │
├─────────────────────────────────────────────────────────────┤
│ POST /v1/agents                                            │
│ {                                                          │
│   "name": "my-agent",                                      │
│   "config": {                                              │
│     "loop_code": "class MyLoop(DefaultLoop): ...",        │
│     "loop_class": "MyLoop"                                 │
│   }                                                        │
│ }                                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent Config Storage (agents table - config JSON)           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Agent Execution                                            │
├─────────────────────────────────────────────────────────────┤
│ POST /v1/agents/{id}/run                                   │
│ {                                                          │
│   "user_input": "Do something",                          │
│   "plan_mode": false,   # Runtime param                   │
│   "trace": false,       # Runtime param                   │
│   "verbose": false,     # Runtime param                   │
│   "stream_sse": false   # Runtime param                   │
│ }                                                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent.run()                                                │
├─────────────────────────────────────────────────────────────┤
│ 1. Check is_deployed → _run_deployed()                     │
│ 2. Local: loop = _load_loop()                              │
│    - If loop_code + loop_class → exec() and instantiate    │
│    - Else → DefaultLoop(runner)                           │
│ 4. loop.run(agent, user_input, plan_mode, trace, ...)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Loop.run()                                                 │
├─────────────────────────────────────────────────────────────┤
│ DefaultLoop.run():                                         │
│   - Apply trace/verbose/stream_sse to runner              │
│   - Call runner.run() or runner.run_sse()                │
│   - Returns RunResult/string/StreamEvents                  │
│                                                             │
│ Custom loops can:                                          │
│   - Override run() completely                             │
│   - Use runner.execute_tool() for single tool calls       │
│   - Use runner.call_llm() for custom LLM calls            │
│   - Call super().run() for default behavior              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Runner (Toolbox)                                           │
├─────────────────────────────────────────────────────────────┤
│ runner.run():      → execute tool loop, handle trace      │
│ runner.run_sse():  → yield StreamEvents                    │
│ runner.execute_tool(): → single tool, check plan_mode     │
│ runner.call_llm(): → direct LLM call                      │
└─────────────────────────────────────────────────────────────┘
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `tinycua_sdk/agent/loop.py` | NEW - DefaultLoop base class |
| `tinycua_sdk/runner/runner.py` | Rename chat→run, add run_sse, add helpers |
| `tinycua_sdk/tools/decorators.py` | Add `allowed_in_plan_mode` |
| `tinycua_sdk/agent/agent.py` | Add `_load_loop()`, update run() |
| `tinycua_sdk/agent/config.py` | Add `loop_code`, `loop_class` fields |
| `tinycua_backend/routers/run.py` | Add plan_mode, trace, verbose, stream_sse to RunRequest |
| `tinycua-runner/executor/__init__.py` | Pass loop config + plan_mode to runner |

---

## Backward Compatibility

- If `loop_code`/`loop_class` not provided → use built-in DefaultLoop
- If `plan_mode` not provided in request → default to `False`
- Existing `plan_mode` config field can be removed (now runtime)
- trace/verbose/stream_sse work the same as before
- Agent.run() signature mostly unchanged (added plan_mode)

---

## Subagent Handling

Each subagent is an independent Agent instance with its own config:

```python
searcher = Agent(name="searcher", ...)  # Own loop_code/loop_class
coder = Agent(name="coder", ...)        # Own loop_code/loop_class
coordinator = Agent(sub_agents=[searcher, coder])
```

When coordinator runs, subagents use their own loop, not coordinator's.
