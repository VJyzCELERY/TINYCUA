# Information State

> **Package:** `tinycua.models.information`
> **Status:** Target architecture

## Role

Information models hold outputs from query analysis and information digestion.

```text
InformationState
  · information_id: str
  · source_node: str | None
  · summary: str
  · key_points: list[str]
  · related_message_ids: list[str]
  · metadata: dict
```

These are output/result models. Internal handoff should prefer `NodeInput` and
`NodePayload` instead of YAML/front-matter strings.

Examples:

- query classification/result state
- information digester result state
- context summary / key points / advisory instructions

## Related

- [`classification.md`](classification.md)
- [`digested_information.md`](digested_information.md)
- [`agent_state.md`](agent_state.md)
- [`../tools/digester.md`](../tools/digester.md)
