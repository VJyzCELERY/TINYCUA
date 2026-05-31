# TINYCUA Design

Implementation-level design documentation for TINYCUA's module layout, agent wrapper classes,
loop strategies, tool contracts, state management, and configuration.

Start with the directory structure below — each directory mirrors a `tinycua/` subpackage.
Read in order for a linear learning experience:

## Linear Reading Order

1. [`config/types.md`](config/types.md) — `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`
2. [`config/agents.md`](config/agents.md) — Per-agent config dataclasses
3. [`constants/tools.md`](constants/tools.md) — `*_BASE_TOOLS` pre-configured tool sets
4. [`constants/prompts.md`](constants/prompts.md) — System prompt contracts
5. [`exceptions/loops.md`](exceptions/loops.md) — `LoopError` hierarchy
6. [`utility/schema_validator.md`](utility/schema_validator.md) — Output validation + retry
7. [`loops/overview.md`](loops/overview.md) — Loop hierarchy and shared patterns
8. [`loops/react_agent.md`](loops/react_agent.md) — `ReActAgentLoop`
9. [`loops/query_analyst_loop.md`](loops/query_analyst_loop.md)
10. [`loops/information_digestion_loop.md`](loops/information_digestion_loop.md)
11. [`loops/result_review_loop.md`](loops/result_review_loop.md)
12. [`loops/main_loop.md`](loops/main_loop.md) — `MainLoop` orchestration
13. [`state/information.md`](state/information.md) — `StateInformation` ABC + subclasses
14. [`state/state_store.md`](state/state_store.md) — Continuation state store
15. [`agents/base.md`](agents/base.md) — `BaseAgentWrapper[S]`
16. [`agents/factory.md`](agents/factory.md) — `create_agent()`, `create_all_agents()`
17. [`agents/query_analyst.md`](agents/query_analyst.md) — `QueryAnalyst` wrapper
18. [`agents/information_digester.md`](agents/information_digester.md)
19. [`agents/task_analyzer.md`](agents/task_analyzer.md)
20. [`agents/task_assessor.md`](agents/task_assessor.md)
21. [`agents/task_executor.md`](agents/task_executor.md)
22. [`agents/result_reviewer.md`](agents/result_reviewer.md)
23. [`agents/primary_agent.md`](agents/primary_agent.md)
24. [`agents/tinycua.md`](agents/tinycua.md) — `TinyCUA` external wrapper
25. [`tools/agent_calls.md`](tools/agent_calls.md) — Agent-to-agent calling tools

---

## Design Foundations

| Directory | Content |
|-----------|---------|
| [`config/`](config/) | `AgentKind`, `TINYCUA_DEFAULT_MODEL`, per-agent config dataclasses |
| [`constants/`](constants/) | Pre-configured tool sets (`*_BASE_TOOLS`), system prompt contracts |
| [`exceptions/`](exceptions/) | `LoopError` hierarchy (thin wrappers around SDK exceptions) |
| [`utility/`](utility/) | `SchemaValidator` — output validation + SDK Agent retry |

## Execution

| Directory | Content |
|-----------|---------|
| [`loops/`](loops/) | Loop strategies: `ReActAgentLoop`, `QueryAnalystLoop`, `InformationDigestionLoop`, `ResultReviewLoop`, `MainLoop` |

## Agents

| Directory | Content |
|-----------|---------|
| [`agents/base.md`](agents/base.md) | `BaseAgentWrapper[S]` abstract class |
| [`agents/factory.md`](agents/factory.md) | `create_agent()`, `create_all_agents()` |
| [`agents/query_analyst.md`](agents/query_analyst.md) | `QueryAnalyst` — classification agent |
| [`agents/information_digester.md`](agents/information_digester.md) | `InformationDigester` — retrieval agent |
| [`agents/task_analyzer.md`](agents/task_analyzer.md) | `TaskAnalyzer` — task decomposition |
| [`agents/task_assessor.md`](agents/task_assessor.md) | `TaskAssessor` — decomposition selection |
| [`agents/task_executor.md`](agents/task_executor.md) | `TaskExecutor` — task execution |
| [`agents/result_reviewer.md`](agents/result_reviewer.md) | `ResultReviewer` — two-phase review |
| [`agents/primary_agent.md`](agents/primary_agent.md) | `PrimaryAgent` — final synthesis |
| [`agents/tinycua.md`](agents/tinycua.md) | `TinyCUA` — external wrapper + `MainLoop` |

## State & Tools

| Directory | Content |
|-----------|---------|
| [`state/`](state/) | `StateInformation` ABC + subclasses, `StateStore` design |
| [`tools/`](tools/) | Agent-to-agent calling tools |

---

*Design docs document concrete class structure, API contracts, module layout, and composition patterns.
Architecture docs ([`../architecture/`](../architecture/)) document conceptual agent responsibilities, flows, and decision rationales.*
