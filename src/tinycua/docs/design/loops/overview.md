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

## Loop Input/Output

| Loop | Input | Output |
|------|-------|--------|
| ReActAgentLoop | Agent-specific (via wrapper `run()`) | Agent-specific (validated by wrapper `run()`) |
| QueryAnalystLoop | `{user_query, chat_history, session_context}` | `{context_enhanced_query, mode_decision}` |
| InformationDigestionLoop | `ContextEnhancedQuery` | `DigestedInformation` |
| ResultReviewLoop | `{task, task_result, execution_log}` | `ReviewerDecision` |
| MainLoop | User query + session state | Final response |

---

## Agent Loop Mapping

| Agent | Loop | Custom Behavior |
|-------|------|-----------------|
| QueryAnalyst | QueryAnalystLoop | Classification |
| InformationDigester | InformationDigestionLoop | Iterative retrieval |
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
| Output validation failure | `SchemaValidator` retries | Raise `LoopOutputValidationError` after max retries |
| Invalid input | — | Raise `ValueError` before any LLM call |
| Tool call failure | `ToolExecutor` returns error as observation | LLM decides next action |

---

## Common Patterns

1. All loops extend SDK `BaseLoop` and override `run()` to add domain-specific control flow
2. Loops are passed to the composed SDK `Agent` via `Agent(loop=...)` inside the wrapper's `_build_agent()`
3. The wrapper `run()` method handles pre-processing (building messages) and post-processing (validation, state updates)
4. Loops do NOT store state — that's the wrapper's responsibility
5. Loops do NOT define tools — those come from `*_BASE_TOOLS` and `config.extra_tools`
