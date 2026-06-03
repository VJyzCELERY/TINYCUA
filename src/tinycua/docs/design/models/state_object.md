# StateObject

> **Package:** `tinycua.models.base`
> **Status:** Target architecture

## Role

`StateObject` is the serialization base for TinyCUA model dataclasses.

It remains suitable for:

- AgentState subclasses
- Task and task result models
- Session-related models
- `NodeInput`
- `NodePayload`

`AgentState` is lifecycle/result output. `NodeInput` and `NodePayload` are internal
transport models and should not require trusted string parsing.

## Contract

```text
StateObject
  · to_dict()
  · from_dict(data)
  · to_json()
  · from_json(json_str)
```

## Node Transport Models

```text
NodePayload <: StateObject
  · to_message() → assistant-role message
  · to_messages() → list[dict]

NodeInput <: StateObject
  · messages: list[dict]
  · payloads: list[NodePayload]
  · to_messages() → list[dict]
```

## Related

- [`agent_state.md`](agent_state.md)
- [`session.md`](session.md)
