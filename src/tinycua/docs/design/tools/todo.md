# Todo Tools

> **Status:** Target architecture

Todo tools remain available to TinyCUA nodes that need plan/task tracking. Exposure is
controlled through `NodeToolPolicy` rather than global agent-node configuration.

Typical usage:

- `TinyCUATaskExecutorNode` may use todo/task tracking while executing work.
- `TinyCUAResponseNode` may use selected planning tools for direct response work if its
  tool policy allows selected outer Agent tools.

Todo state belongs to the relevant session/root context and should propagate according
to `PropagationRule`.

## Related

- [`../config/node_config.md`](../config/node_config.md)
- [`../loops/propagation.md`](../loops/propagation.md)
