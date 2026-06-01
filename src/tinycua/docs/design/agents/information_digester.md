# Information Digester AgentNode Spec Card

Source of truth: [`agent_node/information_digester.md`](../agent_node/information_digester.md).

## Summary

- Transient AgentNode.
- Parses AgentState YAML front-matter when present.
- Writes full context into a cache file and uses `enhanced_context_retrieval`.
- Inner retrieval agents receive cache-scoped tools (`grep_context`, `read_context`) plus `EXPLORATION_TOOL`.
- Emits `InformationDigesterState` to `session.agent_state`.

## Related

- [InformationDigesterState](../state/information.md#informationdigesterstate)
- [EXPLORATION_TOOL](../constants/tools.md)
- [Digester tools](../tools/digester.md)
