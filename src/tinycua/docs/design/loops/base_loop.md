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

## System Messages

The SDK canonical message model includes system messages. Current OpenAI Chat
Completions and Responses translators pass system messages through. TinyCUA MUST
send **one final system message** per LLM call for provider portability and
deterministic prompt layout.

TinyCUA keeps system prompt fragments structured internally through the prompt builder
defined in [`node.md`](node.md). `build_messages()` renders the fragments into one
ordered system-role message at the LLM boundary:

```text
[
  {"role": "system", "content": <ordered merged system prompt>},
  {"role": "user", "content": <external user query when selected for this node call>},
  {"role": "assistant", "content": <internal context / continuation>},
]
```

SDK-provided user messages are first merged into the root session/input context. A node
LLM call includes external user messages only when `NodeMessagePolicy` or assigned
`NodeInput` selects them for that node. Internal node handoffs remain assistant-role
messages.

The session/history layer may store prompt fragments or metadata separately. The
LLM-bound output always has exactly one system prompt message.

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
