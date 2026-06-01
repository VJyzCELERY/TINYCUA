# QueryAnalystLoop

> **File:** `docs/design/loops/query_analyst_loop.md`
> **Package:** `tinycua.loops.query_analyst_loop`
> **Last Updated:** 2026-06-01

---

## Role

`QueryAnalystLoop` is a custom SDK `BaseLoop` subclass for QueryAnalyst. Its purpose is
to let the SDK `Agent.run()` process access the QueryAnalyst `Session`, preserve the
SDK event stream, enforce the required classification tool call, and write
`QueryAnalystState` when the loop terminates.

The AgentNode creates the SDK agent:

```text
Agent(..., tools=[ClassificationTool(labels=config.classification_labels), ...],
      loop=QueryAnalystLoop(session=self.session))
```

The loop defines the behavior inside SDK `Agent.run()`.

---

## SDK Loop Shape

```text
class QueryAnalystLoop(BaseLoop):
    def __init__(self, session: Session, max_classification_retries: int = 3):
        super().__init__()
        self.session = session
        self.max_classification_retries = max_classification_retries

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        ...  # follows SDK BaseLoop extension contract
```

The exact implementation should follow TinyCUA SDK conventions for streaming/non-
streaming `BaseLoop.run(...)` overrides.

---

## Loop-Local Data

The loop only needs minimal local data:

```text
original_query: str                         # messages[-1]["content"] from Agent.run()
context_text: str                           # first assistant response text
classification: str | None                  # selected label from ClassificationTool
retry_count: int
```

`context_text` maps directly to `QueryAnalystState.context`. `classification` maps
directly to `QueryAnalystState.classification`.

---

## Algorithm Inside `run(...)`

1. Run the SDK loop/LLM pass using the received `messages`, `tools`, and
   `override_instructions`.
2. If `stream=True`, yield every SDK-normalized event outward as it is produced.
3. While observing events/responses:
   - preserve the **first assistant response text** as `context_text`
   - detect the `ClassificationTool` call/result and extract the selected label
4. If classification was produced:
   - write `QueryAnalystState`
   - yield final-result event
   - terminate
5. If classification was missing and retry budget remains:
   - call the LLM again with an in-memory retry prompt requiring the classification tool
   - do not replace `context_text` with retry-only text
6. If classification is still missing after retries:
   - fallback to `config.classification_labels[0]`
   - write `QueryAnalystState(failure=1, ...)`
   - yield final-result event

---

## Retry Prompt Policy

Retry prompts are in-memory only by default. They should say only what is necessary,
for example:

```text
You must call the classification tool with one of the configured labels.
Do not answer the user directly.
```

Retry prompts and retry responses must not replace the first response context.

---

## Final State

```text
QueryAnalystState(
  type="query_analyst",
  status="terminated",
  failure=0 or 1,
  classification=<selected_or_fallback_label>,
  context=context_text,
  query=original_query,
)
```

No classification score/confidence fields are required unless a future
ClassificationTool contract explicitly adds them.

---

## Final Event

```text
{
  "type": "tinycua.final_result",
  "agent": "query_analyst",
  "status": self.session.agent_state.status,
  "failure": self.session.agent_state.failure,
  "result": self.session.agent_state.to_dict(),
}
```

---

## Related

- [QueryAnalyst AgentNode](../agent_node/query_analyst.md)
- [QueryAnalystState](../state/information.md#queryanalyststate)
- [AgentLoop overview](overview.md)
