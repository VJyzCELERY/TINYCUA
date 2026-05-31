# TINYCUA Design

Implementation-level design documentation for TINYCUA's module layout, orchestrator classes,
loop strategies, tool contracts, state management, and configuration.

Start with the directory structure below — each directory mirrors a `tinycua/` subpackage.
Read in order for a linear learning experience:

## Linear Reading Order

1. [`config/types.md`](config/types.md) — `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`
2. [`config/agents.md`](config/agents.md) — Per-agent config dataclasses
 3. [`constants/tools.md`](constants/tools.md) — `*_BASE_TOOLS` pre-configured tool sets
 4. [`constants/instructions.md`](constants/instructions.md) — Agent instruction constants
 5. [`exceptions/loops.md`](exceptions/loops.md) — `LoopError` hierarchy
 6. [`loops/overview.md`](loops/overview.md) — Loop hierarchy, state injection pattern
 7. [`loops/react_agent.md`](loops/react_agent.md) — `ReActAgentLoop`
 8. [`loops/query_analyst_loop.md`](loops/query_analyst_loop.md)
 9. [`loops/information_digestion_loop.md`](loops/information_digestion_loop.md)
10. [`loops/result_review_loop.md`](loops/result_review_loop.md)
11. [`loops/main_loop.md`](loops/main_loop.md) — `MainLoop` orchestration
12. [`state/state_object.md`](state/state_object.md) — `StateObject` base class + serialization
13. [`state/information.md`](state/information.md) — Per-agent state classes
14. [`state/agent_state.md`](state/agent_state.md) — `AgentState` lifecycle tracking
15. [`state/task.md`](state/task.md) — `Task` tree + `TaskResult`
16. [`state/mode_decision.md`](state/mode_decision.md) — `ModeDecision` + `ContextEnhancedQuery`
17. [`state/digested_information.md`](state/digested_information.md) — `DigestedInformation`
18. [`state/reviewer_decision.md`](state/reviewer_decision.md) — `ReviewerDecision` + `ContextUpdate`
19. [`state/worker_result.md`](state/worker_result.md) — `WorkerResult` + `WorkerConfig`
20. [`state/execution_log.md`](state/execution_log.md) — `ExecutionLog` + `ExecutionLogEntry`
21. [`state/session.md`](state/session.md) — Design `Session` (extends existing Session)
22. [`state/state_store.md`](state/state_store.md) — Continuation state store
23. [`agents/base.md`](agents/base.md) — `BaseAgentOrchestrator[S]`
24. [`agents/factory.md`](agents/factory.md) — `create_orchestrator()`, `create_all_orchestrators()`
25. [`agents/query_analyst.md`](agents/query_analyst.md) — `QueryAnalyst` orchestrator
26. [`agents/information_digester.md`](agents/information_digester.md)
27. [`agents/task_analyzer.md`](agents/task_analyzer.md)
28. [`agents/task_assessor.md`](agents/task_assessor.md)
29. [`agents/task_creator.md`](agents/task_creator.md) — `TaskCreator` wraps TaskAnalyzer + TaskAssessor
30. [`agents/task_executor.md`](agents/task_executor.md)
31. [`agents/result_reviewer.md`](agents/result_reviewer.md)
32. [`agents/primary_agent.md`](agents/primary_agent.md)
33. [`agents/tinycua.md`](agents/tinycua.md) — `TinyCUA` external orchestrator
34. [`tools/agent_calls.md`](tools/agent_calls.md) — Orchestrator-call tools
35. [`utility/compaction.md`](utility/compaction.md) — `BaseCompaction` serializable compaction strategy

---

## Design Foundations

| Directory | Content |
|-----------|---------|
| [`config/`](config/) | `AgentKind`, `TINYCUA_DEFAULT_MODEL`, per-agent config dataclasses |
| [`constants/`](constants/) | Pre-configured tool sets (`*_BASE_TOOLS`), agent instruction constants |
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
| [`agents/task_creator.md`](agents/task_creator.md) | `TaskCreator` — wraps TaskAnalyzer + TaskAssessor |
| [`agents/task_executor.md`](agents/task_executor.md) | `TaskExecutor` — task execution |
| [`agents/result_reviewer.md`](agents/result_reviewer.md) | `ResultReviewer` — two-phase review |
| [`agents/primary_agent.md`](agents/primary_agent.md) | `PrimaryAgent` — final synthesis |
| [`agents/tinycua.md`](agents/tinycua.md) | `TinyCUA` — external orchestrator + `MainLoop` + session resume |

## State & Tools

| Directory | Content |
|-----------|---------|
| [`state/`](state/) | `StateObject` base + per-agent state subclasses, `Session` (state container + tree), `StateStore` design |
| [`tools/`](tools/) | Orchestrator-call tools — consume stream generator, return typed result |

## Utility

| Directory | Content |
|-----------|---------|
| [`utility/`](utility/) | `BaseCompaction` — serializable compaction strategy for session context |

---

*Design docs document concrete class structure, API contracts, module layout, and state injection patterns.
Architecture docs ([`../architecture/`](../architecture/)) document conceptual agent responsibilities, flows, and decision rationales.*
