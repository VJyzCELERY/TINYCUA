# Primary Agent AgentNode Spec Card

Source of truth: [`agent_sessions/primary_agent.md`](../agent_sessions/primary_agent.md).

## Summary

- General-purpose passthrough/final-response agent.
- Inherits parent session directly.
- Parses `QueryAnalystState` YAML front-matter.
- Appends QueryAnalyst context as assistant message; does not duplicate user query.
- Emits `PrimaryAgentState`.

## Related

- [PrimaryAgentState](../state/information.md#primaryagentstate)
- [TinyCUA passthrough](../orchestration/tinycua.md#passthrough-routing)
- [PrimaryAgentLoop](../loops/primary_agent_loop.md)
