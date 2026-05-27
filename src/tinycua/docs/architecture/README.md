# TINYCUA Architecture

Architecture documentation for TINYCUA's agent orchestration, context flow, and component responsibilities.

Start with [overview.md](overview.md) for the top-level picture.

---

## Core Architecture

| File | Description |
|------|-------------|
| [overview.md](overview.md) | Top-level routing modes and architecture thesis: decomposing context exposure |
| [session-architecture.md](session-architecture.md) | Session model: Chat_History, Context, sub sessions, and compaction |
| [state-objects.md](state-objects.md) | Shared state/data objects used across architecture diagrams and specs |
| [worker-orchestration.md](worker-orchestration.md) | Internal Worker flow: Task Analysis → Task Execution → Task Reviewer |

---

## Agent Specifications

| File | Description |
|------|-------------|
| [query-analyst.md](query-analyst.md) | Produces Context Enhanced Query and Mode Decision |
| [information-digestion.md](information-digestion.md) | Produces precision-oriented Digested Information |
| [primary-agent.md](primary-agent.md) | Final synthesis agent for Primary Agent and Worker modes |
| [task-analysis.md](task-analysis.md) | Inside Worker: creates a sequential task roadmap |
| [task-execution.md](task-execution.md) | Inside Worker: executes one task with task-specific context |
| [task-reviewer.md](task-reviewer.md) | Inside Worker: reviews task result, propagates context, and decides next transition |

---

## Process and Design Notes

| File | Description |
|------|-------------|
| [information-passthrough.md](information-passthrough.md) | Historical/simple forwarder retained for direct Primary Agent routing reference |
| [context-retrieval.md](context-retrieval.md) | Enhanced context retrieval trigger, storage, and retrieval flow |
| [task-classification.md](task-classification.md) | Score-based routing: primary-agent, worker, or uncertain |

---

## Design Decision Records

| File | Description |
|------|-------------|
| [analysis_digested_info_vs_query.md](analysis_digested_info_vs_query.md) | Analysis: should the Worker receive the original query alongside the digest? Resolves to digest + advisory instructions. |
