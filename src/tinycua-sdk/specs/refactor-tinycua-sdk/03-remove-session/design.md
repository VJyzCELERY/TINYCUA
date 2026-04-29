# Stage 03 — Design: Remove Session & Utils

## Overview

Delete the `session/` package and `utils/session.py`. Session management (conversation state, message history, turn tracking) is a consumer concern. The SDK remains stateless.

## Design Decisions

### Why Delete Session?

1. **Stateful by definition**: A session holds conversation history across runs. This is runtime state.
2. **Consumer owns UX**: The consumer (backend application) decides how to structure sessions — per-user, per-room, ephemeral, persisted, etc.
3. **File I/O**: The session module performs file I/O (reading/writing session files), which violates SDK statelessness.

### What Replaces Session?

Nothing in the SDK. The consumer passes `messages` directly to `Agent.run()`:

```python
# Consumer manages session
messages = load_messages_from_db(session_id)
response = await agent.run(query, messages=messages)
save_messages_to_db(session_id, messages + [user_msg, assistant_msg])
```

## Files to Delete

| File | Reason |
|------|--------|
| `session/__init__.py` | Package init for deleted module |
| `session/session.py` | File-based session manager — stateful |
| `utils/session.py` | Session utility wrappers — stateful |

## Code Changes in Agent

### Remove session_id parameter

```python
# BEFORE
class Agent:
    def __init__(self, ..., session_id=None, ...):
        self.session_id = session_id

# AFTER
class Agent:
    def __init__(self, ..., loop=None, ...):
        # session_id removed
```

### Agent.run() accepts messages parameter

```python
# BEFORE
async def run(self, query):
    # Load messages from internal session state
    messages = self._load_session_messages()
    ...

# AFTER
async def run(self, query, messages=None, ...):
    # messages passed in by consumer
    messages = messages or []
    ...
```

## Impact Analysis

### Files that import from session/

```bash
# Find all imports of session modules
grep -r "from tinycua_sdk.session" src/
grep -r "import tinycua_sdk.session" src/
grep -r "from .session" src/
```

### Files that reference session_id

```bash
grep -r "session_id" src/tinycua-sdk/tinycua_sdk/
```

### Expected impact

- `agent/agent.py` — Remove `session_id` parameter
- `agent/executor.py` — Remove session loading/saving logic
- `agent/definition.py` — Remove `session_id` field
- `agent/config.py` — Remove `session_id` from `AgentConfig`

## Consumer Migration Guide

### Before (SDK manages session)
```python
from tinycua_sdk import Agent, Session

session = Session.create("user-123")
agent = Agent(session_id=session.id)
response = await agent.run("Hello")
```

### After (Consumer manages session)
```python
from tinycua_sdk import Agent, LLMModel

# Consumer's own session management
messages = []
agent = Agent(llm_model=LLMModel())
response = await agent.run("Hello", messages=messages)
messages.append({"role": "user", "content": "Hello"})
messages.append({"role": "assistant", "content": response})
```

## Acceptance Criteria

- [ ] `session/` package is deleted.
- [ ] `utils/session.py` is deleted.
- [ ] `Agent` does not accept `session_id` parameter.
- [ ] `Agent.run()` accepts `messages` as an optional parameter.
- [ ] No references to `session` in `tinycua_sdk/` (except possibly in comments).
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02.
- **Blocks**: None (can proceed in parallel with Stages 04–07).
