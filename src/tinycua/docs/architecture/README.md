# TINYCUA Architecture

Architecture documentation for TINYCUA's agent orchestration, data flow, and component responsibilities.

Start with [overview.md](overview.md) for the top-level picture.

---

## Agent Specifications

| File | Description |
|------|-------------|
| [query-analyst.md](query-analyst.md) | Retrieves context from chat history, produces a Context Enhanced Query and a Verdict (large/small task) |
| [information-digestion.md](information-digestion.md) | Compresses the CEQ + full session context into a digest with advisory instructions for the Worker |
| [primary-agent.md](primary-agent.md) | Final agent that produces the user-facing response from either Passthrough or Worker output |
| [task-analysis.md](task-analysis.md) | Inside the Worker: decomposes the digest into a structured list of atomic tasks |
| [task-execution.md](task-execution.md) | Inside the Worker: classic ReAct agent that executes a single task with tools |
| [task-reviewer.md](task-reviewer.md) | Inside the Worker: evaluates task results, accepts or requests re-execution |

---

## Non-Agent Processes

| File | Description |
|------|-------------|
| [overview.md](overview.md) | Top-level orchestration: two-mode architecture, data flow, agent loop types |
| [information-passthrough.md](information-passthrough.md) | Deterministic forwarder — passes CEQ directly to Primary Agent in Passthrough Mode |

---

## Design Decision Records

| File | Description |
|------|-------------|
| [analysis_digested_info_vs_query.md](analysis_digested_info_vs_query.md) | Analysis: should the Worker receive the original query alongside the digest? Resolves to digest + advisory instructions. |
