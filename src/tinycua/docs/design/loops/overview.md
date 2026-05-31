# Loop Strategies Overview

> **File:** `docs/design/loops/overview.md`
> **Package:** `tinycua.loops`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Hierarchy

```
tinycua_sdk.agent.loop.BaseLoop    (SDK — tool calling, streaming, cancellation)
├── ReActAgentLoop                  (shared — default ReAct behavior)
├── QueryAnalystLoop                (classification control flow)
├── InformationDigestionLoop        (iterative retrieval + gap evaluation)
├── ResultReviewLoop                (two-phase: deterministic + LLM review)
└── MainLoop                        (full orchestration)
```

---

## State Injection Pattern

All custom loops receive the orchestrator's state by reference via constructor.
State survives across Agent calls and persists if the stream is interrupted.

```python
# In orchestrator's run():
loop = QueryAnalystLoop(state=self.state)
agent = Agent(..., loop=loop)

# In loop:
class QueryAnalystLoop(BaseLoop):
    def __init__(self, state: QueryAnalystState):
        super().__init__()
        self.state = state  # direct reference — reads/writes synchronously
```

---

## Loop Input/Output

| Loop | Input (via agent.run query) | Writes to state | Behavior |
|------|-----|------|------|
| ReActAgentLoop | Agent-specific | — | Default ReAct via `super().run()` |
| QueryAnalystLoop | `{user_query, chat_history, session_context}` | — | Classification via ClassificationTool |
| InformationDigestionLoop | `ContextEnhancedQuery` | `retrieval_iterations` | Iterative retrieval with gap evaluation |
| ResultReviewLoop | `{task, task_result, execution_log}` | `deterministic_failures` | Two-phase: deterministic then LLM |
| MainLoop | User query + session state | `active_agent`, `token_usage` (on Session) | Full orchestration via orchestrator-call tools. All queries route through QueryAnalyst first. |

---

## Agent Loop Mapping

| Orchestrator | Loop | Custom Behavior |
|-------|------|-----------------|
| QueryAnalyst | QueryAnalystLoop | Classification |
| InformationDigester | InformationDigestionLoop | Iterative retrieval |
| TaskCreator | ReActAgentLoop | Wraps TaskAnalyzer + TaskAssessor |
| TaskAnalyzer | ReActAgentLoop | (none — shared ReAct) |
| TaskAssessor | ReActAgentLoop | (none — shared ReAct) |
| TaskExecutor | ReActAgentLoop | (none — shared ReAct) |
| ResultReviewer | ResultReviewLoop | Two-phase review |
| PrimaryAgent | ReActAgentLoop | (none — shared ReAct) |
| TinyCUA | MainLoop | Orchestration routing |

---

## Error Handling

All loops rely on SDK infrastructure — no custom retry logic:

| Error Case | SDK Behavior | Loop Responsibility |
|------------|-------------|---------------------|
| Transient LLM error | `LLMClient` retry/backoff | Propagate as `LoopTransientError` if exhausted |
| Permanent LLM error | SDK raises immediately | Propagate as `LoopPermanentError` |
| Output not valid JSON | — | Orchestrator raises after stream ends (future: retry loop) |
| Invalid input | — | Raise `ValueError` before any LLM call |
| Tool call failure | `ToolExecutor` returns error as observation | LLM decides next action |

---

## Common Patterns

1. All loops extend SDK `BaseLoop` and override `run()` for domain-specific control flow
2. Loops receive `state` via constructor — reads/writes synchronously to orchestrator state
3. Loops are passed to the SDK `Agent` via `Agent(loop=...)` inside the orchestrator's `run()`
4. The orchestrator's `run()` yields all stream events transparently
5. Loops define their own termination conditions (classification done, gaps addressed, review complete)
6. Loops do NOT define tools — those come from `*_BASE_TOOLS` and `config.extra_tools`


---


---


---

## See also

Prev : [`LoopError` Hierarchy](../exceptions/loops.md) | Next : [`ReActAgentLoop`](react_agent.md)
