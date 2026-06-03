# SDK BaseLoop Contract

> **Package:** `tinycua_sdk.agent.loop`
> **Status:** Target contract TinyCUA builds around

## Role

TinyCUA does not modify the SDK. `TinyCUALoop` extends SDK `BaseLoop` and receives the
same inputs that any SDK loop receives.

```text
Agent.run(query, messages=None, instructions=None, stream=False, file_attachments=None)
  → builds user message
  → msgs = (messages or []) + [user_msg]
  → loop.run(agent, msgs, agent.tools, instructions, stream=stream)
```

`BaseLoop.run(...)` receives:

```text
agent: SDK Agent
messages: list[dict]
tools: list[Tool]
override_instructions: str | None
stream: bool
```

TinyCUA must preserve this contract.

## Design Rules

1. Do not require SDK changes.
2. Treat SDK `messages` as caller-provided context plus current user message.
3. Treat SDK `tools` as the outer tool pool for `NodeToolPolicy`.
4. Treat SDK `instructions` as an override input while preserving TinyCUA node instruction contracts.
5. Preserve `stream=True` as an async iterator of SDK-compatible event dicts.
6. Preserve `stream=False` as final string output.

## Related

- [`tinycua_loop.md`](tinycua_loop.md)
- [`node.md`](node.md)
