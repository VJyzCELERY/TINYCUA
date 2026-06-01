# PrimaryAgentLoop

> **File:** `docs/design/loops/primary_agent_loop.md`
> **Package:** `tinycua.loops.primary_agent_loop`
> **Last Updated:** 2026-06-01

---

## Role

`PrimaryAgentLoop` is a custom SDK `BaseLoop` subclass for PrimaryAgent. It lets the SDK
loop access `Session`, preserves streaming events, formats the final assistant response
and citations, appends the assistant response according to session policy, and writes
`PrimaryAgentState`.

---

## SDK Loop Shape

```text
class PrimaryAgentLoop(ReActLoop):
    def __init__(self, session: Session):
        super().__init__(session)
        self.session = session

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        ...  # SDK BaseLoop-compatible override
```

---

## Loop-Local Data

```text
final_response: str
citations: list[str]
failure: int
```

Citations are derived from tool results, returned metadata, or explicit source markers.

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass.
2. If `stream=True`, yield every SDK event outward.
3. Capture final assistant response text.
4. Extract citations/source references from observed tool results or response metadata.
5. Append the final assistant response to session history/context.
6. Write `PrimaryAgentState` and yield final-result event.

---

## Final State

```text
PrimaryAgentState(
  type="primary_agent",
  status="terminated",
  failure=failure,
  final_response=final_response,
  citations=citations,
)
```

---

## Related

- [PrimaryAgent AgentNode](../agent_node/primary_agent.md)
- [PrimaryAgentState](../state/information.md#primaryagentstate)
