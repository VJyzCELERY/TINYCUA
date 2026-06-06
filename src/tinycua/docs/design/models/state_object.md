# StateObject

> **Package:** `tinycua.models.state_object`
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
  · payload_type: str
  · source_node: str | None
  · content: str | dict | StateObject | list[dict]
  · metadata: dict
  · to_message() → assistant-role message
  · to_messages() → list[dict]

NodeInput <: StateObject
  · input_type: str
  · source_node: str | None
  · target_node: str | None
  · messages: list[dict]
  · payloads: list[NodePayload]
  · metadata: dict
  · to_messages() → list[dict]
```

`NodeInputLike = str | NodeInput | NodePayload | list[dict]`.

Conversion rules:

- external user strings become `{"role": "user", "content": query}`
- internal strings become `{"role": "assistant", "content": text}`
- `NodeInput` and `NodePayload` are trusted internal transport objects
- user strings are never parsed as structured internal input

## Related

- [`agent_state.md`](agent_state.md)
- [`session.md`](session.md)
