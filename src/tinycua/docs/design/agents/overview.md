# Agent Specs Overview

> **File:** `docs/design/agents/overview.md`
> **Package:** `tinycua.agents` (spec cards)
> **Last Updated:** 2026-06-01
> **Status:** Navigation layer — source of truth lives in `agent_node/`

---

## Role

The `agents/` docs are thin spec cards that link to each AgentNode's source-of-truth
document under [`agent_node/`](../agent_node/). They should not duplicate full
design decisions.

---

## Domain Contract Table

| AgentNode | Role | Input | Output State |
|-----------|------|-------|--------------|
| [QueryAnalyst](query_analyst.md) | InputGate classification + context analysis | Plain query | `QueryAnalystState` |
| [InformationDigester](information_digester.md) | Dynamic context retrieval + digest | Plain query or AgentState YAML | `InformationDigesterState` |
| [TaskAnalyzer](task_analyzer.md) | Create/update task tree | AgentState YAML or plain query | `TaskAnalyzerState`; mutates `Session.task` |
| [TaskAssessor](task_assessor.md) | Decide whether more task analysis is needed | AgentState YAML or plain query | `TaskAssessorState` |
| [TaskExecutor](task_executor.md) | Execute active leaf task | AgentState YAML or plain query | `TaskExecutorState`; updates active `Task.task_result` |
| [ResultReviewer](result_reviewer.md) | Review execution result | `TaskExecutorState` YAML or plain query | `ResultReviewerState` or active open question |
| [PrimaryAgent](primary_agent.md) | Passthrough/final response | `QueryAnalystState` YAML or plain query | `PrimaryAgentState` |

---

## Input / Output Quick Reference

All AgentNodes follow:

```text
run(query: str) -> AsyncIterator[dict]
```

Structured input/output uses AgentState YAML front-matter:

```text
state = AgentState.from_string(query)
out = session.agent_state.to_yaml()
```

No graph edge passes dicts or typed Python objects.

---

## Transience / Graph Placement

| AgentNode | Transient? | Graph Placement |
|-----------|------------|-----------------|
| QueryAnalyst | Yes | TinyCUA InputGate; TinyCUAWorker InputGate |
| InformationDigester | Yes | Worker preprocessing when deeper context digestion is needed |
| TaskAnalyzer | No | TinyCUAWorker task creation/decomposition |
| TaskAssessor | No | TinyCUAWorker TaskDecompositionOuterLoop |
| TaskExecutor | No | TinyCUAWorker execution loop |
| ResultReviewer | No | TinyCUAWorker execution/review loop |
| PrimaryAgent | No | TinyCUA passthrough/output direction; inherits parent session |

---

## See also

- [AgentNode source-of-truth docs](../agent_node/)
- [AgentGraph overview](../orchestration/overview.md)
- [TinyCUA top-level graph](../orchestration/tinycua.md)
- [TinyCUAWorker subgraph](../orchestration/worker.md)
- [AgentState subclasses](../state/information.md)
- [Tool constants](../constants/tools.md)
