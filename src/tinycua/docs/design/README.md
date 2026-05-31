# TINYCUA Design

Implementation-level design documentation for TINYCUA's module layout, orchestrator classes,
loop strategies, tool contracts, state management, and configuration.

Start with the directory structure below — each directory mirrors a `tinycua/` subpackage.
Read in order for a linear learning experience:

## Linear Reading Order

1. [`config/types.md`](config/types.md) — `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`
2. [`config/agents.md`](config/agents.md) — Per-agent config dataclasses
 3. [`constants/tools.md`](constants/tools.md) — `*_BASE_TOOLS` pre-configured tool sets
 4. [`constants/prompts.md`](constants/prompts.md) — System prompt contracts
 5. [`exceptions/loops.md`](exceptions/loops.md) — `LoopError` hierarchy
 6. [`loops/overview.md`](loops/overview.md) — Loop hierarchy, state injection pattern
 7. [`loops/react_agent.md`](loops/react_agent.md) — `ReActAgentLoop`
 8. [`loops/query_analyst_loop.md`](loops/query_analyst_loop.md)
 9. [`loops/information_digestion_loop.md`](loops/information_digestion_loop.md)
10. [`loops/result_review_loop.md`](loops/result_review_loop.md)
11. [`loops/main_loop.md`](loops/main_loop.md) — `MainLoop` orchestration
12. [`state/information.md`](state/information.md) — `StateInformation` ABC + subclasses
13. [`state/state_store.md`](state/state_store.md) — Continuation state store
14. [`agents/base.md`](agents/base.md) — `BaseAgentOrchestrator[S]`
15. [`agents/factory.md`](agents/factory.md) — `create_orchestrator()`, `create_all_orchestrators()`
16. [`agents/query_analyst.md`](agents/query_analyst.md) — `QueryAnalyst` orchestrator
17. [`agents/information_digester.md`](agents/information_digester.md)
18. [`agents/task_analyzer.md`](agents/task_analyzer.md)
19. [`agents/task_assessor.md`](agents/task_assessor.md)
20. [`agents/task_executor.md`](agents/task_executor.md)
21. [`agents/result_reviewer.md`](agents/result_reviewer.md)
22. [`agents/primary_agent.md`](agents/primary_agent.md)
23. [`agents/tinycua.md`](agents/tinycua.md) — `TinyCUA` external orchestrator
24. [`tools/agent_calls.md`](tools/agent_calls.md) — Orchestrator-call tools

---

## Design Foundations

| Directory | Content |
|-----------|---------|
| [`config/`](config/) | `AgentKind`, `TINYCUA_DEFAULT_MODEL`, per-agent config dataclasses |
| [`constants/`](constants/) | Pre-configured tool sets (`*_BASE_TOOLS`), system prompt contracts |
| [`exceptions/`](exceptions/) | `LoopError` hierarchy (thin wrappers around SDK exceptions) |

## Execution

| Directory | Content |
|-----------|---------|
| [`loops/`](loops/) | Loop strategies: `ReActAgentLoop`, `QueryAnalystLoop`, `InformationDigestionLoop`, `ResultReviewLoop`, `MainLoop` |

## Agents

| Directory | Content |
|-----------|---------|
| [`agents/base.md`](agents/base.md) | `BaseAgentOrchestrator[S]` abstract class — per-call Agent construction, state injection |
| [`agents/factory.md`](agents/factory.md) | `create_orchestrator()`, `create_all_orchestrators()` |
| [`agents/query_analyst.md`](agents/query_analyst.md) | `QueryAnalyst` — classification orchestrator |
| [`agents/information_digester.md`](agents/information_digester.md) | `InformationDigester` — retrieval orchestrator |
| [`agents/task_analyzer.md`](agents/task_analyzer.md) | `TaskAnalyzer` — task decomposition |
| [`agents/task_assessor.md`](agents/task_assessor.md) | `TaskAssessor` — decomposition selection |
| [`agents/task_executor.md`](agents/task_executor.md) | `TaskExecutor` — task execution |
| [`agents/result_reviewer.md`](agents/result_reviewer.md) | `ResultReviewer` — two-phase review |
| [`agents/primary_agent.md`](agents/primary_agent.md) | `PrimaryAgent` — final synthesis |
| [`agents/tinycua.md`](agents/tinycua.md) | `TinyCUA` — external orchestrator + `MainLoop` + session resume |

## State & Tools

| Directory | Content |
|-----------|---------|
| [`state/`](state/) | `StateInformation` ABC + subclasses (incl. `SessionState`), `StateStore` design |
| [`tools/`](tools/) | Orchestrator-call tools — consume stream generator, return typed result |

---

*Design docs document concrete class structure, API contracts, module layout, and state injection patterns.
Architecture docs ([`../architecture/`](../architecture/)) document conceptual agent responsibilities, flows, and decision rationales.*
