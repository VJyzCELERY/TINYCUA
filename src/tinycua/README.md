# tinycua

CLI/TUI project skeleton for TINYCUA.

Legacy application modules have been removed so the app can be rebuilt from a
clean baseline.

## Quick Start

```python
import asyncio
from tinycua.factory import create_tinycua_agent
from tinycua.config.session_config import SessionConfig

async def main():
    agent = create_tinycua_agent(
        name="my-agent",
        instructions="You are a helpful assistant.",
        session_config=SessionConfig(max_context_messages=50),
    )
    result = await agent.run("Hello!")
    print(result)

    # Access chat history
    for msg in agent.loop.root_session.chat_history:
        print(f"{msg['role']}: {msg['content']}")

asyncio.run(main())
```

## Module Structure

- `tinycua/factory.py` — `create_tinycua_agent()` factory function
- `tinycua/config/` — `SessionConfig` dataclass for session-level configuration
- `tinycua/models/` — `Session` model for tracking execution state
- `tinycua/loops/` — `TinyCUALoop` extending SDK BaseLoop, `NodeQueue` placeholder

## Documentation

- [Architecture](docs/architecture/README.md) — Agent orchestration, data flow, component responsibilities
- [Architecture Spec](specs/tinycua-architecture/spec.md) — Formal requirements and acceptance criteria
- [Architecture Design](specs/tinycua-architecture/design.md) — Directory structure, naming conventions, and doc templates
