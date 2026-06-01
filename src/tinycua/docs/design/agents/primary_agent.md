# Primary Agent AgentNode Spec Card

Source of truth: [`agent_node/primary_agent.md`](../agent_node/primary_agent.md). This is a navigation summary — for implementation details, see the source-of-truth doc.

## Summary

- General-purpose passthrough/final-response agent.
- Inherits parent session directly.
- Parses `QueryAnalystState` YAML front-matter.
- Appends QueryAnalyst context as assistant message; does not duplicate user query.
- Uses `explore(query)` for transient context exploration instead of spawning an InformationDigester node/session.
- Emits `PrimaryAgentState`.

## Related

- [PrimaryAgentState](../state/information.md#primaryagentstate)
- [TinyCUA passthrough](../orchestration/tinycua.md#passthrough-routing)
- [PrimaryAgentLoop](../loops/primary_agent_loop.md)
