# Loop System Overview

> **Status:** Target architecture

TinyCUA uses one SDK-compatible loop: `TinyCUALoop`, which extends SDK `BaseLoop` and
processes a sequential `NodeQueue` of TinyCUA-specific nodes.

```text
SDK Agent
└── TinyCUALoop
    └── NodeQueue
        └── Node → DecisionNode | ProcessNode
```

Old per-agent loop responsibilities move to concrete node policies:

| Old Responsibility | New Owner |
|--------------------|-----------|
| required tool enforcement | `NodeRetryPolicy` / validation |
| final AgentState formatting | concrete TinyCUA node |
| graph routing | `DecisionNode` + `RouteMap` |
| stream handling | `TinyCUALoop` using SDK stream contract |
| session propagation | `PropagationRule` |

TinyCUA does not modify SDK loop APIs. It consumes the current `BaseLoop.run(agent,
messages, tools, override_instructions, stream)` contract.

## Related

- [`base_loop.md`](base_loop.md)
- [`tinycua_loop.md`](tinycua_loop.md)
- [`node.md`](node.md)
