# TINYCUA Design

Implementation-level design documentation for TINYCUA's AgentGraph system, AgentNode
nodes, loop strategies, tool contracts, state management, and configuration.

Start with the directory structure below — each directory mirrors a `tinycua/` subpackage.
Read in order for a linear learning experience:

## Linear Reading Order

1. [`config/types.md`](config/types.md) — `AgentKind` enum, `TINYCUA_DEFAULT_MODEL`
1. [`config/agents.md`](config/agents.md) — Per-agent config dataclasses
1. [`constants/tools.md`](constants/tools.md) — `*_BASE_TOOLS` pre-configured tool sets
1. [`constants/instructions.md`](constants/instructions.md) — Agent instruction constants
1. [`exceptions/loops.md`](exceptions/loops.md) — `LoopError` hierarchy
1. [`orchestration/overview.md`](orchestration/overview.md) — AgentGraph system source of truth
1. [`orchestration/graph_queue.md`](orchestration/graph_queue.md) — queue-based active-node tracking
1. [`orchestration/tinycua.md`](orchestration/tinycua.md) — `TinyCUA` AgentGraph runtime
1. [`orchestration/router_node.md`](orchestration/router_node.md) — deterministic exact-match RouterNode
1. [`orchestration/worker.md`](orchestration/worker.md) — `TinyCUAWorker` AgentGraph runtime
1. [`agents/overview.md`](agents/overview.md) — Agent spec card navigation
1. [`agents/query_analyst.md`](agents/query_analyst.md) — `QueryAnalyst` spec card
1. [`agents/information_digester.md`](agents/information_digester.md)
1. [`agents/task_analyzer.md`](agents/task_analyzer.md)
1. [`agents/task_assessor.md`](agents/task_assessor.md)
1. [`agents/task_creator.md`](agents/task_creator.md) **(deprecated/optional)**
1. [`agents/task_executor.md`](agents/task_executor.md)
1. [`agents/result_reviewer.md`](agents/result_reviewer.md)
1. [`agents/primary_agent.md`](agents/primary_agent.md)
1. [`agent_node/base.md`](agent_node/base.md) — `BaseAgentNode` (outer wrapper pattern)
1. [`agent_node/factory.md`](agent_node/factory.md) — `create_agent_node()`, `create_all_agent_nodes()`
1. [`agent_node/query_analyst.md`](agent_node/query_analyst.md) — `QueryAnalyst` AgentNode
1. [`agent_node/information_digester.md`](agent_node/information_digester.md)
1. [`agent_node/task_analyzer.md`](agent_node/task_analyzer.md)
1. [`agent_node/task_assessor.md`](agent_node/task_assessor.md)
1. [`agent_node/task_creator.md`](agent_node/task_creator.md) — optional/deprecated composite; Worker is source of truth
1. [`agent_node/task_executor.md`](agent_node/task_executor.md)
1. [`agent_node/result_reviewer.md`](agent_node/result_reviewer.md)
1. [`agent_node/primary_agent.md`](agent_node/primary_agent.md)
1. [`loops/overview.md`](loops/overview.md) — Inner loop hierarchy (SDK Agent `loop=` policies)
1. [`loops/react_agent.md`](loops/react_agent.md) — `ReActAgentLoop`
1. [`loops/query_analyst_loop.md`](loops/query_analyst_loop.md)
1. [`loops/information_digestion_loop.md`](loops/information_digestion_loop.md)
1. [`loops/task_analyzer_loop.md`](loops/task_analyzer_loop.md)
1. [`loops/task_assessor_loop.md`](loops/task_assessor_loop.md)
1. [`loops/task_executor_loop.md`](loops/task_executor_loop.md)
1. [`loops/result_review_loop.md`](loops/result_review_loop.md)
1. [`loops/primary_agent_loop.md`](loops/primary_agent_loop.md) — final-response formatting + citations
1. [`state/state_object.md`](state/state_object.md) — `StateObject` base class + serialization
1. [`state/information.md`](state/information.md) — AgentState subclasses
1. [`state/agent_state.md`](state/agent_state.md) — `AgentState` lifecycle + YAML serialization
1. [`state/task.md`](state/task.md) — `Task` tree + `TaskResult`
1. [`state/classification.md`](state/classification.md) — Classification + `ContextEnhancedQuery`
1. [`state/digested_information.md`](state/digested_information.md) — `DigestedInformation`
1. [`state/reviewer_decision.md`](state/reviewer_decision.md) — `ReviewerDecision` + `ContextUpdate`
1. [`state/worker_result.md`](state/worker_result.md) — `WorkerResult` + `WorkerConfig`
1. [`state/execution_log.md`](state/execution_log.md) — `ExecutionLog` + `ExecutionLogEntry`
1. [`state/session.md`](state/session.md) — Design `Session` (extends existing Session)
1. [`state/chat_record.md`](state/chat_record.md) — `ChatRecord` structured audit trail entry
1. [`state/state_store.md`](state/state_store.md) — Continuation state store
1. [`tools/agent_calls.md`](tools/agent_calls.md) — AgentNode-call tools
1. [`tools/digester.md`](tools/digester.md) — InformationDigester tools
1. [`tools/task.md`](tools/task.md) — Task tools: read + write/result updates
1. [`tools/todo.md`](tools/todo.md) — TodoList tool (short-term goal tracking, per-session)
1. [`utility/compaction.md`](utility/compaction.md) — `BaseCompaction` serializable compaction strategy

---

## Design Foundations

| Directory | Content |
|-----------|---------|
| [`config/`](config/) | `AgentKind`, `TINYCUA_DEFAULT_MODEL`, per-agent config dataclasses |
| [`constants/`](constants/) | Pre-configured tool sets (`*_BASE_TOOLS`), agent instruction constants |
| [`exceptions/`](exceptions/) | `LoopError` hierarchy (thin wrappers around SDK exceptions) |

## Orchestration

| Directory | Content |
|-----------|---------|
| [`orchestration/`](orchestration/) | AgentGraph system, queue-based active-node tracking, routing, graph-level TinyCUA runtime. TinyCUA itself is not an SDK `Agent`; it routes to AgentNodes/subgraphs. |

## Execution

| Directory | Content |
|-----------|---------|
| [`loops/`](loops/) | Inner loops — SDK Agent `loop=` policies (retry, enforcement, output) |
| [`agent_node/`](agent_node/) | AgentNode wrappers — `run(query: str)` builds Agent + inner loop, yields events |

## Agent Specs

| Directory | Content |
|-----------|---------|
| [`agents/overview.md`](agents/overview.md) | Agent spec cards: tools, I/O, config, loop assignments |
| [`agents/query_analyst.md`](agents/query_analyst.md) | `QueryAnalyst` — purpose, tools, InputGate target |
| [`agents/information_digester.md`](agents/information_digester.md) | `InformationDigester` — purpose, tools |
| [`agents/task_analyzer.md`](agents/task_analyzer.md) | `TaskAnalyzer` — purpose, tools |
| [`agents/task_assessor.md`](agents/task_assessor.md) | `TaskAssessor` — purpose, tools |
| [`agents/task_creator.md`](agents/task_creator.md) | `TaskCreator` — optional/deprecated composite; Worker is source of truth |
| [`agents/task_executor.md`](agents/task_executor.md) | `TaskExecutor` — purpose, tools, termination |
| [`agents/result_reviewer.md`](agents/result_reviewer.md) | `ResultReviewer` — purpose, tools, decisions |
| [`agents/primary_agent.md`](agents/primary_agent.md) | `PrimaryAgent` — purpose, OutputGate target |

## AgentNodes

| Directory | Content |
|-----------|---------|
| [`agent_node/base.md`](agent_node/base.md) | `BaseAgentNode` — outer wrapper pattern |
| [`agent_node/factory.md`](agent_node/factory.md) | `create_agent_node()`, `create_all_agent_nodes()` |
| [`agent_node/query_analyst.md`](agent_node/query_analyst.md) | `QueryAnalyst` — Session management, context assembly |
| [`agent_node/information_digester.md`](agent_node/information_digester.md) | `InformationDigester` — Session + cache management |
| [`agent_node/task_analyzer.md`](agent_node/task_analyzer.md) | `TaskAnalyzer` — Session + tool wiring |
| [`agent_node/task_assessor.md`](agent_node/task_assessor.md) | `TaskAssessor` — Session + tool wiring |
| [`agent_node/task_creator.md`](agent_node/task_creator.md) | `TaskCreator` — optional/deprecated composite; Worker is source of truth |
| [`agent_node/task_executor.md`](agent_node/task_executor.md) | `TaskExecutor` — Session + active-task lifecycle |
| [`agent_node/result_reviewer.md`](agent_node/result_reviewer.md) | `ResultReviewer` — Session + deterministic rules |
| [`agent_node/primary_agent.md`](agent_node/primary_agent.md) | `PrimaryAgent` — Session + final synthesis |

## State & Tools

| Directory | Content |
|-----------|---------|
| [`state/`](state/) | `StateObject` base + result payloads, `Session` (state container + tree, including `todo_list`), `StateStore` design |
| [`tools/`](tools/) | SDK Tool contracts: AgentNode-call tools, task tools, digester tools, [TodoList](tools/todo.md) (short-term goal tracking, per-session) |

## Utility

| Directory | Content |
|-----------|---------|
| [`utility/`](utility/) | `BaseCompaction` — serializable compaction strategy for session context |

---

*Design docs document concrete class structure, API contracts, module layout, and state injection patterns.
Architecture docs ([`../architecture/`](../architecture/)) document conceptual agent responsibilities, flows, and decision rationales.*
