# TinyCUA Design Documentation

> **Status:** Draft — target architecture for TinyCUA simplification

This directory documents the planned TinyCUA architecture: a SDK `Agent` configured
with `TinyCUALoop`, which extends SDK `BaseLoop` and runs a sequential `NodeQueue` of
TinyCUA-specific nodes.

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
| `loops/` | TinyCUALoop, NodeQueue, node, routing, propagation, streaming behavior |
| `config/` | NodeConfig, SessionConfig, tool/stream/retry policies |
| `models/` | Session, StateObject, AgentState outputs, NodeInput/NodePayload, task/data models |
| `constants/` | Instruction, continuation, and tool constants |
| `tools/` | Task, todo, and information digestion tools |
| `utility/` | Compaction strategy notes |
| `loops/` | Also contains loop/node error concepts. |

## Removed Target Concepts

The previous graph docs are preserved only through migration notes in the spec/design
documents. Target runtime docs should not use these as active architecture concepts:

- `AgentGraph`
- `RouterNode`
- `AgentNode`
- per-agent `AgentLoop` subclasses
- worker QueryAnalyst input gate
- generic `PrimaryNode`
