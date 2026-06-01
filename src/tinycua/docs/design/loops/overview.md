# AgentLoop Overview

> **File:** `docs/design/loops/overview.md`
> **Package:** `tinycua.loops`
> **Last Updated:** 2026-06-01

---

## Role

AgentLoops are TinyCUA customizations of the SDK `BaseLoop`. They are passed to the SDK
agent as:

```text
agent = Agent(..., loop=CustomLoop(session=self.session))
```

The primary purpose of a custom loop is to let SDK `Agent.run()` execute with access to
TinyCUA-specific runtime data, especially `Session`, while preserving the SDK loop
contract and SSE behavior.

AgentNode docs describe **how the SDK Agent is built**. Loop docs describe **how the
custom `BaseLoop` subclass handles SDK events and session state from inside
`Agent.run()`**.

---

## SDK BaseLoop Contract

TinyCUA custom loops follow the SDK `BaseLoop` subclassing convention:

```text
class SomeAgentLoop(BaseLoop):
    def __init__(self, session: Session, ...):
        super().__init__(...)
        self.session = session

    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> str | AsyncIterator[dict[str, Any]]:
        ...
```

Do not invent a second public loop entry point. The design should describe the
algorithm inside the SDK-compatible `run(...)` override.

---

## Responsibilities

Within the `BaseLoop.run(...)` override, a TinyCUA loop may:

1. Access `self.session` and related state (`session.agent_state`, `session.task`,
   `session.session_context`, etc.).
2. Pass through SDK stream events when `stream=True`.
3. Observe SDK response/tool events while they pass through.
4. Send small retry prompts/messages to the LLM when a mandatory tool call is missing.
5. Keep retry-only context in memory unless a loop explicitly chooses to append it.
6. Convert observed text/tool results into a deterministic AgentState subclass.
7. Write that AgentState subclass to `self.session.agent_state`.
8. Add a final structured event after normal SSE events when the loop terminates.

---

## Event Passthrough Principle

For streaming calls, the custom loop must not hide the SDK stream. It may inspect events
for its own enforcement/output formatting, but ordinary events should still be yielded
to the caller.

```text
# Conceptual behavior inside BaseLoop.run(..., stream=True):
for each SDK event produced by BaseLoop/LLM/tool execution:
    observe event for loop-specific needs
    yield the same event outward

after termination:
    write self.session.agent_state
    yield deterministic final_result event
```

The exact internal SDK helper used to produce events should follow the TinyCUA SDK
implementation. The docs should not prescribe fake helper names.

---

## In-Memory Retry Context

Retry prompts are loop-local by default. They exist to repair a missing tool call or
complete a required output, not to become durable chat history automatically.

```text
retry_messages = messages + [{"role": "system", "content": retry_prompt}]
```

The loop decides whether any retry response is recorded to `chat_history` or
`session_context`. For most mandatory-tool retries, retry nudges should not overwrite
the original response-derived context.

---

## Final Result Event

When a loop reaches a terminal outcome, it should write the relevant AgentState subclass
and then yield a deterministic final event:

```text
self.session.agent_state = <AgentState subclass>

yield {
    "type": "tinycua.final_result",
    "agent": self.session.agent_state.type,
    "status": self.session.agent_state.status,
    "failure": self.session.agent_state.failure,
    "result": self.session.agent_state.to_dict(),
}
```

If a loop intentionally leaves the node active (for example ResultReviewer asking an
open question), it should not emit a terminal final-result event.

---

## Per-Loop Outputs

| Loop | Writes |
|------|--------|
| QueryAnalystLoop | `QueryAnalystState` |
| InformationDigestionLoop | `InformationDigesterState` |
| TaskAnalyzerLoop | `TaskAnalyzerState` |
| TaskAssessorLoop | `TaskAssessorState` |
| TaskExecutorLoop | `TaskExecutorState` |
| ResultReviewLoop | `ResultReviewerState` when terminal; otherwise active state |
| PrimaryAgentLoop | `PrimaryAgentState` |

---

## See also

- [Base AgentNode responsibility split](../agent_node/base.md)
- [AgentState output serialization](../state/agent_state.md)
- [SDK BaseLoop implementation](../../tinycua-sdk/tinycua_sdk/agent/loop.py)
