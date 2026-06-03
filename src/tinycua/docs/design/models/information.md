# Information State

> **Package:** `tinycua.models.information`
> **Status:** Target architecture

## Role

Information models hold outputs from query analysis and information digestion.

These are output/result models. Internal handoff should prefer `NodeInput` and
`NodePayload` instead of YAML/front-matter strings.

Examples:

- query classification/result state
- information digester result state
- context summary / key points / advisory instructions

## Related

- [`digested_information.md`](digested_information.md)
- [`../tools/digester.md`](../tools/digester.md)
