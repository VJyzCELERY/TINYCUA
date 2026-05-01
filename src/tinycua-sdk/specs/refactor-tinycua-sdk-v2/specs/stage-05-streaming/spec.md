# Stage 5: Streaming — Specification

## Objective
Implement all four streaming modes exactly as specified.

## Reference
- [`goals/getting-started/04_agent_streaming.py`](../goals/getting-started/04_agent_streaming.py)

## Requirements

### R-5.1: Streaming Modes

| Mode | Return Type | Content |
|------|-------------|---------|
| `stream="off"` | `str` | Final response text (default). |
| `stream="token"` | `AsyncIterator[dict]` | Raw LLM token deltas only. |
| `stream="event"` | `AsyncIterator[dict]` | Agent-level events only (no token deltas). |
| `stream="all"` | `AsyncIterator[dict]` | Interleaved token deltas + agent events. |

### R-5.2: Event Shapes

**Token delta:**
```python
{
    "type": "response.output_text.delta",
    "delta": "Hello",
    "item_id": "msg_abc123",
}
```

**Agent events:**
```python
{"type": "response.created"}
{"type": "response.output_item.added", "item": {"type": "tool_call", "name": "calculator", "arguments": {"expression": "2+2"}}}
{"type": "response.output_item.added", "item": {"type": "tool_output", "name": "calculator", "output": "4"}}
{"type": "response.completed"}
```

### R-5.3: Behavior with Tool Calls
When the LLM returns tool calls during a stream:
- The stream pauses while tools execute.
- Tool call events are emitted.
- Tool output events are emitted.
- The stream resumes with the next LLM response's tokens.

### R-5.4: Loop Integration
- `BaseLoop.run()` must support streaming by yielding events/tokens instead of returning a single string when `stream != "off"`.
- The same tool-calling logic from Stage 3 runs, but events are yielded at each stage.

### R-5.5: LLMClient Streaming
- `OpenAICompatibleClient.chat()` must accept `stream: bool = False`.
- When `stream=True`, it returns an async generator of SSE chunks.
- Each chunk is normalized to the same event dict shape.

## Success Criteria

### SC-5.1: stream="off" Returns String
**What:** Default mode returns `str`.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
r = asyncio.run(a.run('Say hello.', stream='off'))
assert isinstance(r, str)
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-5.2: stream="token" Yields Token Deltas
**What:** Returns async iterator of token chunks.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
stream = asyncio.run(a.run('Count to 3.', stream='token'))
tokens = []
async for chunk in stream:
    assert chunk['type'] == 'response.output_text.delta'
    tokens.append(chunk['delta'])
print('PASS: tokens =', tokens)
"
```
**Pass if:** prints `PASS`.

### SC-5.3: stream="event" Yields Agent Events
**What:** Returns async iterator of events without token deltas.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
stream = asyncio.run(a.run('What is 2+2?', stream='event'))
events = []
async for event in stream:
    events.append(event['type'])
    assert not event['type'].endswith('.delta')
print('PASS: events =', events)
"
```
**Pass if:** prints `PASS`.

### SC-5.4: stream="all" Yields Both
**What:** Interleaved token deltas and events.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel
a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'))
stream = asyncio.run(a.run('Tell me a fact.', stream='all'))
has_delta = False
has_event = False
async for item in stream:
    if item['type'].endswith('.delta'):
        has_delta = True
    else:
        has_event = True
assert has_delta and has_event
print('PASS')
"
```
**Pass if:** prints `PASS`.

### SC-5.5: Streaming with Tool Calls
**What:** Tool call events appear in event/all streams.  
**How to check:**
```bash
cd src/tinycua-sdk && python -c "
import asyncio
from tinycua_sdk import Agent, LanguageModel, tool

@tool
def calc(expr: str) -> str:
    return str(eval(expr))

a = Agent(llm_model=LanguageModel(base_url='http://localhost:1234/v1', api_key='dummy'), tools=[calc])
stream = asyncio.run(a.run('What is 5*5?', stream='event'))
tool_events = [e for e in stream if e.get('item', {}).get('type') == 'tool_call']
print('PASS: tool_events =', len(tool_events))
"
```
**Pass if:** prints `PASS`.

### SC-5.6: Integration Test Pass
**What:** `test_gs_04_agent_streaming.py` passes.  
**How to check:**
```bash
cd src/tinycua-sdk && pytest tests/integration/goals/test_gs_04_agent_streaming.py -v
```
**Pass if:** 1 passed, 0 failed.

## Integration Test File
- `tests/integration/goals/test_gs_04_agent_streaming.py`
