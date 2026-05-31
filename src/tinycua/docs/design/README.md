# TINYCUA Design

Implementation-level design documentation for TINYCUA's agent wrapper classes,
loop strategies, tool contracts, and project structure.

Start with [overview.md](overview.md) for the top-level picture.

If you are new to TINYCUA's design, read in this order for a linear learning path:

1. [overview.md](overview.md) — Project structure, module layout, layer separation, tool sources pattern
2. [base-agent-wrapper.md](base-agent-wrapper.md) — `BaseAgentWrapper` abstract class and `StateInformation`
3. [loop-strategies.md](loop-strategies.md) — All loop types: `ReActAgentLoop`, `QueryAnalystLoop`, `InformationDigestionLoop`, `ResultReviewLoop`, future `MainLoop`
4. [query-analyst.md](query-analyst.md) — `QueryAnalyst` wrapper: config, state, loop, tools, classification contract
5. [information-digester.md](information-digester.md) — `InformationDigester` wrapper: config, state, loop, retrieval tool contract
6. [task-analyzer.md](task-analyzer.md) — `TaskAnalyzer` wrapper: config, state, ReActAgentLoop
7. [task-assessor.md](task-assessor.md) — `TaskAssessor` wrapper: config, state, ReActAgentLoop
8. [task-executor.md](task-executor.md) — `TaskExecutor` wrapper: config, state, native tools, ReActAgentLoop
9. [result-reviewer.md](result-reviewer.md) — `ResultReviewer` wrapper: config, state, result review loop, deterministic rules
10. [primary-agent.md](primary-agent.md) — `PrimaryAgent` wrapper: config, state, ReActAgentLoop
11. [agent-calls.md](agent-calls.md) — Agent-to-agent calling tools: how they receive wrapper instances and delegate through `run()`
12. [tinycua-agent.md](tinycua-agent.md) — `TinyCUA` external wrapper class contract and `MainLoop` integration point

---

## Design Foundations

| File | Description |
|------|-------------|
| [overview.md](overview.md) | Project structure, module layout, layer separation (wrapper vs loop), tool sources pattern |
| [base-agent-wrapper.md](base-agent-wrapper.md) | `BaseAgentWrapper[S]` abstract class, `StateInformation` ABC + per-agent subclasses |
| [loop-strategies.md](loop-strategies.md) | All execution loop classes: `ReActAgentLoop`, `QueryAnalystLoop`, `InformationDigestionLoop`, `ResultReviewLoop`, `MainLoop` |

## Agent Design Docs

| File | Description |
|------|-------------|
| [query-analyst.md](query-analyst.md) | `QueryAnalyst`: Classification Loop, ClassificationTool, `QueryAnalystState`, config, prompt contract |
| [information-digester.md](information-digester.md) | `InformationDigester`: Iterative Retrieval Loop, retrieval tool, `InformationDigesterState`, config |
| [task-analyzer.md](task-analyzer.md) | `TaskAnalyzer`: ReActAgentLoop, `TaskAnalyzerState`, config |
| [task-assessor.md](task-assessor.md) | `TaskAssessor`: ReActAgentLoop, `TaskAssessorState`, config |
| [task-executor.md](task-executor.md) | `TaskExecutor`: ReActAgentLoop, native benchmark tools, `TaskExecutorState`, config |
| [result-reviewer.md](result-reviewer.md) | `ResultReviewer`: Two-Phase Review Loop, deterministic rules, `ResultReviewerState`, config |
| [primary-agent.md](primary-agent.md) | `PrimaryAgent`: ReActAgentLoop, `PrimaryAgentState`, config |

## Integration Design

| File | Description |
|------|-------------|
| [agent-calls.md](agent-calls.md) | Agent-to-agent SDK `Tool` wrappers — receive wrapper instances, delegate through `run()` |
| [tinycua-agent.md](tinycua-agent.md) | `TinyCUA` external wrapper class contract and `MainLoop` integration point (future M6) |

---

*Design docs document concrete class structure, API contracts, module layout, and composition patterns.
Architecture docs ([`../architecture/`](../architecture/)) document conceptual agent responsibilities, flows, and decision rationales.*
