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
8. [`config/node_config.md`](config/node_config.md) — node config dataclasses and policies
9. [`config/session_config.md`](config/session_config.md) — session-level configuration
10. [`models/session.md`](models/session.md) — root/per-node sessions and message context
11. [`models/state_object.md`](models/state_object.md) — `NodeInput`, `NodePayload`, and serialization base
12. [`models/chat_record.md`](models/chat_record.md) and [`models/execution_log.md`](models/execution_log.md) — audit and execution records
13. [`models/task.md`](models/task.md), [`models/todo.md`](models/todo.md), and [`models/reviewer_decision.md`](models/reviewer_decision.md) — task/todo/review models
14. [`models/classification.md`](models/classification.md), [`models/worker_result.md`](models/worker_result.md), [`models/information.md`](models/information.md), and [`models/digested_information.md`](models/digested_information.md) — decision and information models
15. [`constants/instructions.md`](constants/instructions.md) and [`constants/tools.md`](constants/tools.md) — instruction and tool-scope constants
16. [`tools/task.md`](tools/task.md), [`tools/todo.md`](tools/todo.md), and [`tools/digester.md`](tools/digester.md) — node tool families
17. [`utility/compaction.md`](utility/compaction.md) — compaction strategy contract
18. [`models/agent_state.md`](models/agent_state.md) and [`models/state_store.md`](models/state_store.md) — lifecycle output and persistence notes

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
