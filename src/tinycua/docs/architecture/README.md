# TINYCUA Architecture

Architecture documentation for TINYCUA's agent orchestration, context flow, and component responsibilities.

Start with [overview.md](overview.md) for the top-level picture.

If you are new to TINYCUA's architecture, read in this order for a linear learning path:

1. [overview.md](overview.md) — Architecture thesis, routing modes, and the big picture
2. [main-workflow-pseudocode.md](main-workflow-pseudocode.md) — Reviewer-ready pseudocode for the main TINYCUA workflow
3. [session-architecture.md](session-architecture.md) — Session model: chat_history, Context, execution log, sub-sessions, and compaction (foundational)
4. [state-objects.md](state-objects.md) — Canonical shared data structures (reference as you read the other docs)
5. [query-analyst.md](query-analyst.md) — How queries are enriched and routing decisions are made
6. [context-retrieval.md](context-retrieval.md) — How context is retrieved when the session grows large
7. [task-classification.md](task-classification.md) — How classification labels determine routing
8. [information-digestion.md](information-digestion.md) — How broad session context is narrowed for precision
9. [worker-orchestration.md](worker-orchestration.md) — Inside the Worker: how tasks are orchestrated sequentially
10. [task-analysis.md](task-analysis.md) — How the Task Analyzer creates a sequential task roadmap (ReAct agent, no internal routing branches)
11. [task-creation.md](task-creation.md) — How the Task Creation loop decomposes complex tasks into nested sub-tasks
12. [task-assessor.md](task-assessor.md) — How the Task Assessor selects tasks for decomposition during Task Creation
13. [task-execution.md](task-execution.md) — How individual tasks are executed with isolated context
14. [result-reviewer.md](result-reviewer.md) — How results are reviewed and context is propagated between tasks
15. [primary-agent.md](primary-agent.md) — How the final user-facing response is synthesized
16. [analysis-digested-info-vs-query.md](analysis-digested-info-vs-query.md) — Design decision: digest vs. raw query

---

## Architecture Overview

| File | Description |
|------|-------------|
| [overview.md](overview.md) | Top-level routing modes and architecture thesis: decomposing context exposure |
| [main-workflow-pseudocode.md](main-workflow-pseudocode.md) | Reviewer-ready pseudocode for the main TINYCUA workflow |

## Agent Specifications

| File | Description |
|------|-------------|
| [query-analyst.md](query-analyst.md) | Produces high-level Context Enhanced Query and Classification |
| [information-digestion.md](information-digestion.md) | Performs Enhanced Context Retrieval and produces precision-oriented Digested Information |
| [primary-agent.md](primary-agent.md) | Final synthesis agent for Primary Agent and Worker modes |
| [task-analysis.md](task-analysis.md) | Inside Worker: creates a sequential task roadmap (ReAct agent, no internal routing branches) |
| [task-assessor.md](task-assessor.md) | Inside Worker: selects which tasks to decompose during upfront Task Creation |
| [task-execution.md](task-execution.md) | Inside Worker: executes one task with task-specific context |
| [result-reviewer.md](result-reviewer.md) | Inside Worker: reviews task result, propagates context, and decides next transition |

## Process Specifications

| File | Description |
|------|-------------|
| [session-architecture.md](session-architecture.md) | Session model: chat_history, Context, execution log, sub-sessions, and compaction |
| [worker-orchestration.md](worker-orchestration.md) | Internal Worker flow: Task Creation → Task Assessor → Task Analyzer → Task Executor → Result Reviewer |
| [task-creation.md](task-creation.md) | Inside Worker: iterative decomposition loop that builds a nested task tree |

## Tool Specifications

| File | Description |
|------|-------------|
| [context-retrieval.md](context-retrieval.md) | Enhanced context retrieval trigger, storage, and retrieval flow |

## Reference Specifications

| File | Description |
|------|-------------|
| [state-objects.md](state-objects.md) | Shared state/data objects used across architecture diagrams and specs |

## Design Notes

| File | Description |
|------|-------------|
| [task-classification.md](task-classification.md) | Classification via configurable labels: passthrough or worker |

## Decision Records

| File | Description |
|------|-------------|
| [analysis-digested-info-vs-query.md](analysis-digested-info-vs-query.md) | Analysis: should the Worker receive the original query alongside the digest? Resolves to digest + advisory instructions. |
