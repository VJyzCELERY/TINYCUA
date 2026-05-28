# TINYCUA Architecture

Architecture documentation for TINYCUA's agent orchestration, context flow, and component responsibilities.

Start with [overview.md](overview.md) for the top-level picture.

If you are new to TINYCUA's architecture, read in this order for a linear learning path:

1. [overview.md](overview.md) — Architecture thesis, routing modes, and the big picture
2. [session-architecture.md](session-architecture.md) — Session model: chat_history, Context, execution log, sub-sessions, and compaction (foundational)
3. [state-objects.md](state-objects.md) — Canonical shared data structures (reference as you read the other docs)
4. [query-analyst.md](query-analyst.md) — How queries are enriched and routing decisions are made
5. [context-retrieval.md](context-retrieval.md) — How context is retrieved when the session grows large
6. [task-classification.md](task-classification.md) — The scoring rubric for routing decisions
7. [information-digestion.md](information-digestion.md) — How broad session context is narrowed for precision
8. [worker-orchestration.md](worker-orchestration.md) — Inside the Worker: how tasks are orchestrated sequentially
9. [task-analysis.md](task-analysis.md) — How the Task Analyzer creates a sequential task roadmap
10. [task-execution.md](task-execution.md) — How individual tasks are executed with isolated context
11. [task-reviewer.md](task-reviewer.md) — How results are reviewed and context is propagated between tasks
12. [primary-agent.md](primary-agent.md) — How the final user-facing response is synthesized
13. [analysis-digested-info-vs-query.md](analysis-digested-info-vs-query.md) — Design decision: digest vs. raw query

---

## Architecture Overview

| File | Description |
|------|-------------|
| [overview.md](overview.md) | Top-level routing modes and architecture thesis: decomposing context exposure |

## Agent Specifications

| File | Description |
|------|-------------|
| [query-analyst.md](query-analyst.md) | Produces high-level Context Enhanced Query and Mode Decision |
| [information-digestion.md](information-digestion.md) | Performs Enhanced Context Retrieval and produces precision-oriented Digested Information |
| [primary-agent.md](primary-agent.md) | Final synthesis agent for Primary Agent and Worker modes |
| [task-analysis.md](task-analysis.md) | Inside Worker: creates a sequential task roadmap |
| [task-execution.md](task-execution.md) | Inside Worker: executes one task with task-specific context |
| [task-reviewer.md](task-reviewer.md) | Inside Worker: reviews task result, propagates context, and decides next transition |

## Process Specifications

| File | Description |
|------|-------------|
| [session-architecture.md](session-architecture.md) | Session model: chat_history, Context, execution log, sub-sessions, and compaction |
| [context-retrieval.md](context-retrieval.md) | Enhanced context retrieval trigger, storage, and retrieval flow |
| [worker-orchestration.md](worker-orchestration.md) | Internal Worker flow: Task Analyzer → Task Executor → Task Reviewer |

## Reference Specifications

| File | Description |
|------|-------------|
| [state-objects.md](state-objects.md) | Shared state/data objects used across architecture diagrams and specs |

## Design Notes

| File | Description |
|------|-------------|
| [task-classification.md](task-classification.md) | Score-based routing: primary-agent, worker, or uncertain |

## Decision Records

| File | Description |
|------|-------------|
| [analysis-digested-info-vs-query.md](analysis-digested-info-vs-query.md) | Analysis: should the Worker receive the original query alongside the digest? Resolves to digest + advisory instructions. |
