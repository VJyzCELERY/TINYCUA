# Query Analyst AgentNode Spec Card

Source of truth: [`agent_node/query_analyst.md`](../agent_node/query_analyst.md).

This card exists only as a navigation/summary layer. Do not duplicate detailed design
decisions here.

## Summary

- Transient InputGate AgentNode.
- Uses `QueryAnalystConfig.classification_labels`.
- Root labels: `TINYCUA_INPUT_GATE_CLASSIFICATION = ["passthrough", "worker"]`.
- Worker labels: `TINYCUA_WORKER_INPUT_GATE_CLASSIFICATION`.
- Emits `QueryAnalystState` to `session.agent_state`.
- Structured pass-through uses `QueryAnalystState.to_yaml()`.
- `uncertain` mode is removed; indecision means fallback/open-question behavior.

## Related

- [QueryAnalystState](../state/information.md#queryanalyststate)
- [Classification constants](../constants/tools.md)
- [TinyCUA InputGate](../orchestration/tinycua.md)
- [TinyCUAWorker InputGate](../orchestration/worker.md)
