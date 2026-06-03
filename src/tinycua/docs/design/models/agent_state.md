# AgentState

> **Package:** `tinycua.models.agent_state`
> **Status:** Target architecture

## Role

`AgentState` represents node lifecycle/result output. It is not the general transport
envelope for internal node communication; that role belongs to `NodeInput` and
`NodePayload`.

AgentState subclasses remain useful for typed results:

- Query analysis result
- Information digest result
- Task analysis / assessment / execution result
- Result review decision
- Worker result
- Final response result

## Legacy YAML Front-Matter

The old docs used YAML front-matter strings for cross-node structured transport. In the
target architecture, normal internal communication uses typed `NodeInput`/`NodePayload`.
String/front-matter parsing is legacy/migration behavior and must not parse untrusted
external user strings as internal data.

## Related

- [`state_object.md`](state_object.md)
- [`../loops/node.md`](../loops/node.md)
