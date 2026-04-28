# Runner Documentation

The `runner/` package contains the local execution engine for agents.

**Package path:** `tinycua_sdk/runner/`

---

## runner.py - Runner Class

### Purpose

`Runner` is the core local execution engine. It handles LLM communication, tool execution, message management, sub-agent delegation, and streaming.

### Default Configuration

```python
DEFAULT_BASE_URLS = {
    "lmstudio": "http://localhost:1234/v1",
    "ollama": "http://localhost:11434/v1",
    "openai": "https://api.openai.com/v1",
}

DEFAULT_MODELS = {
    "lmstudio": "qwen/qwen3.5-9b",
    "ollama": "llama3",
    "openai": "gpt-4o-mini",
}
```

**Provider defaults:** Automatically resolves base URLs and models for known providers. This means users can just specify `provider="lmstudio"` without knowing the exact URL.

### Constructor

```python
def __init__(self, agent, cancel_event=None):
    from tinycua_sdk.agent import Agent
    
    if isinstance(agent, Agent):
        self.config = agent.config
        self._cancel_event = cancel_event or agent.cancel_event
        self.sub_agents = agent.sub_agents
    else:
        self.config = agent
        self._cancel_event = cancel_event
        self.sub_agents = getattr(agent, "sub_agents", [])
    
    # Resolve base URL
    if self.config.base_url:
        self.base_url = self.config.base_url
    elif self.config.provider in DEFAULT_BASE_URLS:
        self.base_url = DEFAULT_BASE_URLS[self.config.provider]
    else:
        self.base_url = "https://api.openai.com/v1"
    
    self.model = self.config.model or DEFAULT_MODELS.get(self.config.provider, "gpt-4o-mini")
    self.api_key = self.config.api_key
    self.tools = self.config.tools
    self.system_prompt = self.config.system_prompt
    self.max_tool_calls = self.config.policy.max_tool_calls
    self.strip_thinking_patterns = getattr(self.config, "strip_thinking", None)
    
    self.trace = False
    self.verbose = False
    self.stream_sse = False
    
    self.client = ResponsesClient(base_url=self.base_url, api_key=self.api_key)
    self.messages = []
```

**Accepts either Agent or AgentConfig:** This flexibility allows creating a Runner directly from config without instantiating a full Agent.

**Cancel event propagation:** If initialized from an Agent, shares the same cancel event for coordinated cancellation.

### run() - Main Execution

```python
async def run(self, user_input: str, instructions: str | None = None, trace: bool | None = None) -> Union[str, RunResult]:
    use_trace = trace if trace is not None else self.trace
    self._register_sub_agent_tools()
    return await self._chat_direct(user_input, instructions, use_trace)
```

### _chat_direct() - Core Chat Loop

```python
async def _chat_direct(self, user_input: str, instructions: str | None = None, trace: bool = False) -> Union[str, RunResult]:
    system_content = self.system_prompt
    if instructions:
        system_content += f"\n\n{instructions}"
    
    self.messages.append({"role": "user", "content": user_input})
    
    trace_data = []
    tool_call_records = []
    
    for _ in range(self.max_tool_calls):
        request_messages = [{"role": "system", "content": system_content}]
        request_messages.extend(self.messages)
        
        tool_configs = self._get_tool_configs()
        request = ResponseRequest(model=self.model, input=request_messages, tools=tool_configs)
        
        response = await self.client.create(request)
        
        choice = response.choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])
        
        content = self._strip_thinking(content)
        usage_data = response.usage.model_dump() if response.usage else {}
        
        trace_data.append({"request": request.model_dump(), "response": response.model_dump(), "usage": usage_data})
        
        assistant_message = str(content) if content else ""
        tool_calls_found = False
        
        if tool_calls:
            # Build tool call message
            tool_call_msg = {"role": "assistant", "tool_calls": [...]}
            self.messages.append(tool_call_msg)
            
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name")
                tool_input = json.loads(func.get("arguments", "{}"))
                
                result = await self._execute_tool_async(tool_name, tool_input)
                tool_call_records.append(ToolCall(id=tc.get("id", ""), name=tool_name, arguments=tool_input, result=result))
                
                self.messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": str(result)})
                tool_calls_found = True
        
        if not tool_calls_found:
            self.messages.append({"role": "assistant", "content": assistant_message})
            
            if trace:
                return RunResult(response=assistant_message, tool_calls=tool_call_records, usage=usage_data, trace=trace_data, finish_reason=choice.get("finish_reason"))
            return assistant_message
    
    # Max calls reached
    if trace:
        return RunResult(response=assistant_message, tool_calls=tool_call_records, usage=usage_data, trace=trace_data, finish_reason="max_calls")
    return assistant_message
```

**Execution loop:**
1. Build request messages (system + history + user input)
2. Call LLM with tools
3. Extract content and tool calls
4. Strip thinking tags
5. If tool calls: execute each tool, append results
6. If no tool calls: return final response
7. Repeat up to `max_tool_calls`

**Trace mode:** Returns `RunResult` with full request/response history, tool call records, and usage statistics.

**Why print tool results?** `print(f"[Tool] {tool_name} -> {result}")` provides visible feedback during execution.

### Sub-Agent Delegation

```python
def _register_sub_agent_tools(self) -> None:
    if not self.sub_agents:
        return
    
    for sub_agent in self.sub_agents:
        tool_name = f"delegate_to_{sub_agent.name}"
        if any(t.name == tool_name for t in self.tools):
            continue
        
        def create_delegate_fn(agent, verbose, trace):
            async def delegate_fn(task: str, context: str = "") -> str:
                if verbose:
                    logger.info("[Delegation] → Delegating to %s", agent.name)
                
                try:
                    result = await agent.run(task, instructions=context, verbose=verbose, trace=trace)
                    return result
                except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as e:
                    if verbose:
                        logger.error("[Delegation] × %s failed: %s", agent.name, e)
                    raise
            
            return delegate_fn
        
        delegate_fn = create_delegate_fn(sub_agent, self.verbose, self.trace)
        
        delegate_tool = Tool(
            name=tool_name,
            description=f"Delegate task to {sub_agent.name}...",
            parameters={"type": "object", "properties": {"task": {...}, "context": {...}}, "required": ["task"]},
            _fn=delegate_fn,
        )
        self.tools.append(delegate_tool)
```

**Closure pattern:** `create_delegate_fn()` creates a closure capturing the specific sub-agent instance. This is necessary because Python's default argument binding in loops is late-binding.

**Why `delegate_to_{name}`?** Creates unique tool names per sub-agent. The LLM sees these as regular tools and can invoke them like any other function.

### Thinking Tag Stripping

```python
DEFAULT_THINKING_PATTERNS = [
    r"<think>.*?</think>",
    r"<think>.*?</think>\s*",
    r"<thinking>.*?</thinking>",
    r"<think>[\s\S]*?</think>",
]

def _strip_thinking(self, content: str) -> str:
    if self.strip_thinking_patterns is False:
        return content
    
    patterns = self.strip_thinking_patterns or self.DEFAULT_THINKING_PATTERNS
    
    for pattern in patterns:
        content = re.sub(pattern, "", content, flags=re.DOTALL)
    
    return content.strip()
```

**Configuration:**
- `None` (default): Use default patterns
- `False`: Disable stripping
- `list[str]`: Custom regex patterns

**Why multiple patterns?** Different models use different thinking tag formats. The patterns cover common variants.

### Streaming

```python
async def stream_with_tools(self, user_input: str, instructions: str | None = None) -> AsyncIterator[StreamEvent]:
    self._register_sub_agent_tools()
    
    # Build request
    request_messages = [{"role": "system", "content": system_content}]
    request_messages.extend(self.messages)
    request = ResponseRequest(model=self.model, input=request_messages, tools=self._get_tool_configs())
    
    # Collect tool calls from streaming response
    tool_calls_buffer, assistant_content, finish_reason = await self._collect_tool_calls(request)
    
    if not tool_calls_buffer:
        # No tools - yield content and done
        yield StreamEvent(type=StreamEventType.CONTENT, data={"content": assistant_content})
        yield StreamEvent(type=StreamEventType.DONE, data={"finish_reason": finish_reason})
        return
    
    # Yield tool call events
    yield StreamEvent(type=StreamEventType.TOOL_CALL_START, data={"tool_calls": tool_calls_buffer})
    yield StreamEvent(type=StreamEventType.TOOL_CALL_END, data={"tool_calls": tool_calls_buffer})
    
    # Execute tools and stream results
    tool_results = []
    for tc in tool_calls_buffer:
        async for event in self._stream_tool_execution(tc, inspect):
            yield event
            if event.type == StreamEventType.TOOL_RESULT_END:
                tool_results.append({"role": "tool", "tool_call_id": tc.get("id"), "content": event.data.get("result", "")})
    
    # Continue conversation with tool results
    continuation_request = ResponseRequest(
        model=self.model,
        input=request_messages + [{"role": "assistant", "content": assistant_content}] + tool_results,
    )
    
    async for event in self.client.stream(continuation_request):
        if event.data.get("choices"):
            delta = event.data["choices"][0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield StreamEvent(type=StreamEventType.CONTENT, data={"content": content})
    
    yield StreamEvent(type=StreamEventType.DONE, data={"finish_reason": finish_reason})
```

**Two-phase streaming:**
1. **Collection phase:** Stream LLM response, collecting tool calls
2. **Execution phase:** Execute tools, yield result chunks
3. **Continuation phase:** Send tool results back to LLM, stream final response

**Why separate phases?** Tool calls may be split across multiple SSE chunks. We need to collect the complete tool call before executing.

### Tool Call Collection

```python
async def _collect_tool_calls(self, request: ResponseRequest) -> tuple[list[dict[str, Any]], str, str]:
    tool_calls_buffer = []
    current_tool_call = None
    assistant_content = ""
    finish_reason = ""
    
    async for event in self.client.stream(request):
        if event.data.get("choices"):
            delta = event.data["choices"][0].get("delta", {})
            content = delta.get("content", "")
            tool_calls = delta.get("tool_calls", [])
            finish_reason = event.data["choices"][0].get("finish_reason", "")
            
            if content:
                assistant_content += content
            
            for tc in tool_calls:
                current_tool_call = self._update_tool_call_buffer(tc, current_tool_call, tool_calls_buffer)
    
    if current_tool_call and current_tool_call.get("name"):
        tool_calls_buffer.append(current_tool_call)
    
    return tool_calls_buffer, assistant_content, finish_reason
```

**Streaming delta handling:** LLM streaming APIs send tool calls as deltas (partial data). The buffer accumulates chunks until a complete tool call is formed.

### Tool Call Buffer Update

```python
def _update_tool_call_buffer(self, tc: dict[str, Any], current_tool_call: dict[str, Any] | None, tool_calls_buffer: list[dict[str, Any]]) -> dict[str, Any] | None:
    func = tc.get("function", {})
    tc_id = tc.get("id", "")
    func_name = func.get("name", "")
    func_args = func.get("arguments", "")
    
    is_new_call = func_name and (not current_tool_call or current_tool_call.get("id") != tc_id)
    is_continuation = bool(func_args) and current_tool_call and current_tool_call.get("name")
    
    if is_new_call:
        if current_tool_call and current_tool_call.get("name"):
            tool_calls_buffer.append(current_tool_call)
        current_tool_call = {"id": tc_id, "name": func_name, "arguments": func_args}
    elif is_continuation and current_tool_call:
        current_tool_call["arguments"] += func_args
    elif func_name and not current_tool_call:
        current_tool_call = {"id": tc_id, "name": func_name, "arguments": func_args}
    
    return current_tool_call
```

**State machine for streaming tool calls:**
- **New call:** `id` changes or `name` appears for first time
- **Continuation:** Same call, accumulating `arguments`
- **Complete:** When stream ends, append final call to buffer

**Why check `func_name` before appending?** Ensures we only buffer valid tool calls (not empty deltas).

### Tool Execution

```python
async def _execute_tool_async(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
    from tinycua_sdk.agent.executor import AgentExecutor
    
    if not AgentExecutor.check_tool_permission(tool_name):
        return {"success": False, "error": f"Permission denied for tool: {tool_name}", "tool_name": tool_name}
    
    if AgentExecutor.check_tool_approval_required(tool_name):
        logger.warning("Tool %s requires approval before execution", tool_name)
    
    for tool in self.tools:
        if tool.name == tool_name:
            result = tool.invoke(**tool_input)
            if asyncio.iscoroutine(result):
                result = await result
            return {"success": True, "result": result, "tool_name": tool_name}
    
    return {"success": False, "error": f"Tool '{tool_name}' not found", "tool_name": tool_name}
```

**Security integration:** Checks permissions before execution. Returns structured error dicts for missing tools or denied permissions.

**Async handling:** Awaits coroutine results from async tools.

### Context Manager Support

```python
def __enter__(self) -> "Runner":
    return self

def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
    asyncio.get_event_loop().run_until_complete(self.close())
```

Supports `with Runner(config) as runner:` pattern. Automatically closes the HTTP client on exit.

**Why `get_event_loop().run_until_complete()`?** `__exit__` is synchronous but `close()` is async. This bridges the gap, though it may fail if no event loop is running.

---

## RemoteRunner and HTTPRunner

### RemoteRunner (ABC)

```python
class RemoteRunner(ABC):
    def __init__(self, base_url: str, api_key: str | None = None)
    
    @abstractmethod
    async def execute(self, messages, tools, options) -> AsyncIterator[str]: ...
    
    @abstractmethod
    async def health_check(self) -> bool: ...
```

Abstract base for remote runner implementations.

### HTTPRunner

```python
class HTTPRunner(RemoteRunner):
    def __init__(self, base_url: str, api_key: str | None = None, timeout: int = 30)
```

**execute():**
```python
async def execute(self, messages, tools, options) -> AsyncIterator[str]:
    payload = {
        "messages": messages,
        "tools": tools,
        "model": options.model,
        "temperature": options.temperature,
        "stream": options.stream,
    }
    if options.max_tokens:
        payload["max_tokens"] = options.max_tokens
    
    async with httpx.AsyncClient(timeout=self.timeout) as client:
        async with client.stream("POST", f"{self.base_url}/execute", json=payload, headers=self._get_headers()) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]
                elif line:
                    yield line
```

Streams execution results from a remote runner service via SSE.

**Error handling:**
- `httpx.ConnectError` → raises `ConnectionError`
- `httpx.TimeoutException` → raises `TimeoutError`

---

## RunnerOptions

```python
@dataclass
class RunnerOptions:
    model: str
    temperature: float = 1.0
    max_tokens: int | None = None
    stream: bool = True
```

Simple configuration dataclass for remote runner execution.

---

## Inter-Module Data Flow

### Local Execution Flow
```
Agent.run(user_input)
  → AgentExecutor.run()
    → Runner.run()
      → _register_sub_agent_tools()
        → Create delegate Tool for each sub-agent
      → _chat_direct()
        → Build messages
        → ResponsesClient.create(request)
          → HTTP POST /v1/chat/completions
        → Extract tool calls
        → _execute_tool_async()
          → Permission check
          → Tool.invoke()
        → Append results
        → Loop (up to max_tool_calls)
        → Return response
```

### Streaming Flow
```
Agent.stream(user_input)
  → Runner.stream_with_tools()
    → _collect_tool_calls()
      → Stream LLM response
      → Buffer tool call deltas
      → Return complete tool calls
    → If no tool calls:
      → Yield CONTENT events
      → Yield DONE event
    → If tool calls:
      → Yield TOOL_CALL_START/END
      → _stream_tool_execution()
        → Yield TOOL_RESULT_CHUNK events
        → Yield TOOL_RESULT_END
      → Continue with continuation_request
        → Yield CONTENT events
        → Yield DONE event
```
