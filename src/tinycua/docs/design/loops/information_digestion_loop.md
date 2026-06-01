# InformationDigestionLoop

> **File:** `docs/design/loops/information_digestion_loop.md`
> **Package:** `tinycua.loops.information_digestion_loop`
> **Last Updated:** 2026-06-01

---

## Role

`InformationDigestionLoop` is a custom SDK `BaseLoop` subclass for InformationDigester.
It lets the SDK Agent loop access `Session`, pass through stream events, enforce the
mandatory `digest_information` tool call, and write `InformationDigesterState`.

---

## SDK Loop Shape

```text
class InformationDigestionLoop(BaseLoop):
    def __init__(self, session: Session, max_digest_retries: int = 3):
        super().__init__()
        self.session = session
        self.max_digest_retries = max_digest_retries

    async def run(self, agent, messages, tools, override_instructions=None, stream=False):
        ...  # SDK BaseLoop-compatible override
```

---

## Loop-Local Data

Minimal local values:

```text
latest_digest: DigestedInformation | None
retrieval_iterations: int
retry_count: int
```

`latest_digest` maps directly to `InformationDigesterState` fields.

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass with the provided `messages` and `tools`.
2. If `stream=True`, yield every SDK-normalized event outward.
3. Observe tool events:
   - count `enhanced_context_retrieval` calls/results as retrieval iterations
   - parse `digest_information` tool output into `latest_digest`
4. If `latest_digest` exists:
   - write `InformationDigesterState`
   - yield final-result event
5. If digest is missing and retry budget remains:
   - send an in-memory retry prompt asking the model to call `digest_information`
6. If digest is still missing after retries:
   - write a partial `InformationDigesterState` with `failure=1` and known gap note

---

## Final State

```text
InformationDigesterState(
  type="information_digester",
  status="terminated",
  failure=0 or 1,
  context_summary=latest_digest.context_summary or fallback_summary,
  key_points=latest_digest.key_points or [],
  advisory_instructions=latest_digest.advisory_instructions,
  constraints=latest_digest.constraints,
  known_gaps=latest_digest.known_gaps,
  retrieval_iterations=retrieval_iterations,
)
```

---

## Related

- [InformationDigester AgentNode](../agent_node/information_digester.md)
- [InformationDigesterState](../state/information.md#informationdigesterstate)
- [InformationDigester tools](../tools/digester.md)
