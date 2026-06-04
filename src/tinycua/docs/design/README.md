# TinyCUA Design Documentation

> **Status:** Draft — target architecture for TinyCUA simplification

This directory documents the planned TinyCUA architecture: a SDK `Agent` configured
with `TinyCUALoop`, which extends SDK `BaseLoop` and runs a sequential `NodeQueue` of
TinyCUA-specific nodes.

## Document Authority / Source of Truth

`src/tinycua/specs/design-simplification/design.md` is the blueprint and design-decision
record for this PR. `src/tinycua/docs/design/` is the refined implementation-facing target
design. Refined docs may add detail, specialize examples, or clarify implementation
contracts as long as they preserve the same semantics. Treat a difference as an issue only
when it creates incompatible implementation behavior, contradicts a MUST-level design
decision, duplicates competing sources of truth, or leaves the canonical implementation
contract ambiguous.

## Reading Order

1. [`loops/base_loop.md`](loops/base_loop.md) — SDK `BaseLoop` contract TinyCUA builds around
2. [`loops/tinycua_loop.md`](loops/tinycua_loop.md) — TinyCUALoop architecture
3. [`loops/node_queue.md`](loops/node_queue.md) — queue execution, terminal handling, suspension/prepend
4. [`loops/node.md`](loops/node.md) — Node, DecisionNode, ProcessNode, and concrete TinyCUA nodes
5. [`loops/route_map.md`](loops/route_map.md) — DecisionNode-owned routing dispatch
6. [`loops/propagation.md`](loops/propagation.md) — propagation, dedupe, chat history vs session context
7. [`loops/worker_concept.md`](loops/worker_concept.md) — Worker as a DecisionNode, no Worker QueryAnalyst
8. Node contracts (per-node implementation-facing behavior):
   - [`loops/query_analyst.md`](loops/query_analyst.md) — QueryAnalyst routing, two-step decision, uncertain mode
   - [`loops/worker.md`](loops/worker.md) — Worker routing, task_creation/recreation/reanalysis/proceed_execution
   - [`loops/task_create.md`](loops/task_create.md) — Deterministic root task creation
   - [`loops/task_analyzer.md`](loops/task_analyzer.md) — Mode-specific task analysis and decomposition
   - [`loops/task_assessor.md`](loops/task_assessor.md) — Task tree evaluation and unfinished task selection
   - [`loops/task_executor.md`](loops/task_executor.md) — ReAct-style task execution, tool restrictions
   - [`loops/result_reviewer.md`](loops/result_reviewer.md) — Accept/retry/replan/open_question, failure threshold
   - [`loops/information_digester.md`](loops/information_digester.md) — Context digestion, fallback behavior
   - [`loops/result_aggregation.md`](loops/result_aggregation.md) — Guided BFS right-to-left traversal
   - [`loops/response.md`](loops/response.md) — Final synthesis, suspension for digestion
9. [`loops/expected_scenarios.md`](loops/expected_scenarios.md) — End-to-end flow audits with Mermaid diagrams
10. [`config/node_config.md`](config/node_config.md) — node config dataclasses and policies
11. [`config/session_config.md`](config/session_config.md) — session-level configuration
12. [`models/session.md`](models/session.md) — root/per-node sessions and message context
13. [`models/state_object.md`](models/state_object.md) — `NodeInput`, `NodePayload`, and serialization base
14. [`models/chat_record.md`](models/chat_record.md) and [`models/execution_log.md`](models/execution_log.md) — audit and execution records
15. [`models/task.md`](models/task.md), [`models/todo.md`](models/todo.md), and [`models/reviewer_decision.md`](models/reviewer_decision.md) — task/todo/review models
16. [`models/classification.md`](models/classification.md), [`models/worker_result.md`](models/worker_result.md), [`models/information.md`](models/information.md), and [`models/digested_information.md`](models/digested_information.md) — decision and information models
17. [`constants/instructions.md`](constants/instructions.md) and [`constants/tools.md`](constants/tools.md) — instruction and tool-scope constants
18. [`tools/task.md`](tools/task.md), [`tools/todo.md`](tools/todo.md), and [`tools/digester.md`](tools/digester.md) — node tool families
19. [`utility/compaction.md`](utility/compaction.md) — compaction strategy contract
20. [`models/agent_state.md`](models/agent_state.md) and [`models/state_store.md`](models/state_store.md) — lifecycle output and persistence notes

## Architecture Summary

```text
SDK Agent
└── TinyCUALoop extends SDK BaseLoop
    ├── root Session
    └── NodeQueue
        ├── TinyCUAQueryAnalystNode        : DecisionNode
        ├── TinyCUAInformationDigesterNode : ProcessNode
        ├── TinyCUAWorkerNode              : DecisionNode
        ├── TinyCUATaskAnalyzerNode        : ProcessNode
        ├── TinyCUATaskAssessorNode        : ProcessNode
        ├── TinyCUATaskExecutorNode        : ProcessNode
        ├── TinyCUAResultReviewerNode      : ProcessNode
        ├── TinyCUAResultAggregationNode   : ProcessNode
        └── TinyCUAResponseNode            : ProcessNode, terminal/suspendable
```

TinyCUA builds around the existing SDK contract:

```text
Agent.run(query, messages=None, instructions=None, stream=False, file_attachments=None)
  → loop.run(agent, messages, tools, override_instructions, stream)
```

No SDK modification is required by this design.

## Directory Map

| Directory | Purpose |
|-----------|---------|
| `loops/` | TinyCUALoop, NodeQueue, node, routing, propagation, streaming, error handling |
| `config/` | NodeConfig, SessionConfig, tool/stream/retry policies and message strategy |
| `models/` | Session, StateObject, AgentState outputs, NodeInput/NodePayload, task/data models |
| `constants/` | Instruction, continuation, and tool constants |
| `tools/` | Task, todo, and information digestion tools |
| `utility/` | Compaction strategy notes |

## Naming Convention: Rule vs Policy vs Strategy

TinyCUA uses suffixes to signal how a behavior object is owned and applied:

| Suffix | Meaning | Examples |
|--------|---------|----------|
| `Rule` | Cross-node or cross-session data movement contract. Rules describe what may move across boundaries. | `PropagationRule` |
| `Policy` | Declarative behavior configuration evaluated by a node/session/loop. Policies do not own large algorithms. | `NodeToolPolicy`, `NodeStreamPolicy`, `NodeRetryPolicy`, `NodeMessagePolicy` |
| `Strategy` | Pluggable algorithm or implementation choice that owns behavior details and may have its own configuration. | `CompactionStrategy` |

Use `Policy` for lightweight per-node/session decisions, `Rule` for boundary/propagation
contracts, and `Strategy` when implementations are swappable algorithms.

## Removed Target Concepts

The previous graph docs are preserved only through migration notes in the spec/design
documents. Target runtime docs should not use these as active architecture concepts:

- `AgentGraph`
- `RouterNode`
- `AgentNode`
- per-agent `AgentLoop` subclasses
- worker QueryAnalyst input gate
- generic `PrimaryNode`
