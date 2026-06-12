# Feature Specification: Design Simplification

**Status**: Draft
**Created**: 2026-06-03
**Last Updated**: 2026-06-03
**Subproject(s) Affected**: tinycua

---

## Problem Statement

- **Goals**: Simplify TINYCUA's design documentation and architecture so that the system is easier to understand, extend, and maintain — while preserving all existing capabilities.
- **Gaps**: The current design has 56 documentation files across 11 directories, with multiple abstraction layers modeled as a multi-agent graph (AgentGraph, AgentNode, AgentLoop, RouterNode, InputGate, OutputGate, Factory). The graph model implies parallel execution, but nodes actually run sequentially. The abstraction doesn't match the runtime reality.
- **Non-Goals**: This spec does NOT change the underlying SDK (`tinycua-sdk`), tool contracts, or core data structures. It restructures the architecture from a multi-agent graph to a self-supervising loop with a sequential node queue and deterministic routing.
- **Constraints**: Must preserve all existing capabilities (query analysis, information digestion, task analysis, task assessment, task execution, result review, primary response). Must keep the Task tree and all task tools intact. Per-node configurations (instructions, tools) must remain customizable.

---

## User Scenarios & Testing

### Primary Scenario

A developer wants to use TINYCUA to process a user query. Instead of understanding AgentGraph, AgentNode subclasses, factory functions, graph queue semantics, and routing rules, they should be able to:

1. Create a Session (which holds AgentConfig with all node configs)
2. Create an Agent with a Loop
3. Call `agent.run(query="...")` and get results

### Acceptance Scenarios

1. **Given** a developer has a Session with AgentConfig, **When** they create `Agent(loop=TinyCUALoop(session=session))`, **Then** the system initializes a queue with an entry node (QueryAnalyst) and terminal node (PrimaryAgent).

2. **Given** an active queue `[QueryAnalyst, PrimaryAgent]`, **When** QueryAnalyst classifies as "passthrough", **Then** QueryAnalyst terminates itself, and the queue becomes `[PrimaryAgent]`.

3. **Given** an active queue `[QueryAnalyst, PrimaryAgent]`, **When** QueryAnalyst classifies as "worker", **Then** QueryAnalyst spawns `[InformationDigester, Worker]`, and the queue becomes `[InformationDigester, Worker, PrimaryAgent]`.

4. **Given** a queue `[Worker, PrimaryAgent]`, **When** Worker detects the next node is PrimaryAgent (no work in progress), **Then** Worker spawns TaskAnalyzer with TaskInit enabled.

5. **Given** a queue `[TaskExecutor, PrimaryAgent]`, **When** a new query enters and QueryAnalyst classifies as "worker", **Then** QueryAnalyst spawns `[InformationDigester, Worker]`, Worker detects work in progress (next node is not PrimaryAgent), and spawns QueryAnalyst(Worker) for worker-level routing.

6. **Given** a queue with no terminal node, **When** the loop processes the queue, **Then** the loop auto-appends the default terminal node (PrimaryAgent).

7. **Given** a completed terminal node, **When** the terminal node finishes, **Then** the loop ends and returns the result.

### Edge Cases

- What happens when a node encounters an error? The node writes failure state to its session, and the queue decides whether to continue or abort.
- What happens when the queue is empty after node termination? The loop auto-appends the default terminal node.
- What happens with empty or invalid queries? The entry node (QueryAnalyst) validates input and writes appropriate error state.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST provide a single entry point: `Agent(loop=TinyCUALoop(session=session))` — no separate AgentGraph, Factory, or RouterNode classes needed.
- **FR-002**: System MUST use a sequential Node Queue to process queries. Nodes run one at a time. Each node processes the query, produces a result, and may terminate itself or spawn new nodes.
- **FR-003**: System MUST initialize the queue with an entry node (QueryAnalyst) and terminal node (PrimaryAgent). The entry node always runs first.
- **FR-004**: System MUST auto-append the default terminal node if the queue has no terminal node after processing.
- **FR-005**: System MUST support node termination — a node removes itself from the queue and propagates its session to the parent.
- **FR-006**: System MUST support node spawning — a node can add new nodes to the queue after itself.
- **FR-007**: System MUST support deterministic routing — QueryAnalyst routes based on classification (passthrough/worker), Worker routes based on queue context (work in progress vs. fresh start).
- **FR-008**: System MUST support pluggable terminal nodes — PrimaryAgent is the default, but ResultAggregator or other nodes can replace it.
- **FR-009**: System MUST preserve the Session model — each node has its own Session. Session keeps `parent_id` as a lightweight reference. Nodes inherit/propagate session per their own rules.
- **FR-010**: System MUST keep the Task tree on the root Session only. Task is not duplicated across nodes.
- **FR-011**: System MUST preserve all AgentState subclasses and YAML front-matter serialization for cross-node state communication.
- **FR-012**: System MUST keep per-node configurations (instructions, base tools) customizable via AgentConfig on Session.
- **FR-013**: System MUST maintain TinyCUAWorker as a DecisionNode in the queue — not a separate agent or subgraph.
- **FR-014**: System MUST define Agent Interactivity Features as a cross-cutting concern: persistence, HITL, interrupt, and resume.
- **FR-015**: System MUST provide TodoList per Session — each node's session has its own short-term goal tracking.
- **FR-016**: System MUST move AgentConfig from AgentState to Session directly. Session holds all node configs at once.
- **FR-017**: System MUST accept `input: str` as the universal node input, with flexible parsing inside each node for different data formats.
- **FR-018**: Design documentation MUST be reorganized with `state/` renamed to `models/` to reflect that these are data structures.
- **FR-019**: Design documentation MUST reduce from 56 files to approximately 20-25 files, with TinyCUALoop and Node Queue as the central design documents.

### Key Entities

- **TinyCUALoop**: The central self-supervising loop. Owns the root Session, Task tree, and Node Queue. Initializes queue with entry + terminal nodes. Auto-appends terminal if missing. Lives at `tinycua/loops/tinycua_loop.py`.
- **NodeQueue**: Sequential processing queue. Nodes run one at a time. Each node processes the query and may terminate itself or spawn new nodes.
- **Node**: Base processing unit. Has its own Session. Accepts `input: str`. Can terminate itself or spawn new nodes.
- **FilterNode**: Classifies input and routes. Example: QueryAnalyst (classifies passthrough/worker).
- **DecisionNode**: Evaluates conditions and mutates the queue. Example: Worker (detects work in progress, spawns appropriate nodes).
- **ProcessingNode**: Does work and produces output. Example: TaskExecutor, InformationDigester.
- **TerminalNode**: Ends the loop. Example: PrimaryAgent, ResultAggregator. When a terminal node completes, the loop ends.
- **Session**: Each node has its own Session. Keeps `parent_id` as reference. Holds chat_history, context, TodoList. AgentConfig lives on root Session. Nodes inherit/propagate session per their own rules.
- **AgentConfig**: Stores all node configs at once. Lives on root Session. Each node config includes instructions and base tools.
- **Task**: Tree of task nodes on root Session only. Retains current structure.
- **AgentState subclasses**: Typed output per node (QueryAnalystState, TaskExecutorState, etc.). Retain current structure but no longer hold AgentConfig.
- **Agent Interactivity Features**: Cross-cutting features — persistence, HITL, interrupt, resume.

---

## Success Criteria

- [ ] **Developer can create an agent in 2 lines**: `session = Session(...)` then `agent = Agent(loop=TinyCUALoop(session=session))`
- [ ] **Queue initializes correctly**: Entry node (QueryAnalyst) + terminal node (PrimaryAgent) at start
- [ ] **Auto-append terminal works**: If queue has no terminal node, loop appends default terminal
- [ ] **Node termination works**: Nodes remove themselves from queue and propagate session to parent
- [ ] **Node spawning works**: Nodes add new nodes to queue after themselves
- [ ] **Deterministic routing works**: QueryAnalyst routes passthrough/worker; Worker detects work in progress
- [ ] **Pluggable terminal nodes work**: PrimaryAgent can be replaced by ResultAggregator or other nodes
- [ ] **Task on root only**: Task tree lives on root Session, not duplicated across nodes
- [ ] **Per-node configs customizable**: Instructions and base tools can be overridden per node via AgentConfig on Session
- [ ] **Universal input**: All nodes accept `input: str` with flexible parsing
- [ ] **Documentation is compact**: Design docs organized under `models/` (renamed from `state/`), total file count under 25
- [ ] **No AgentGraph/RouterNode/InputGate/OutputGate/Factory/TreeNode references remain**

---

## Testing Plan

### Unit Tests

- Node Queue: initialization, auto-append terminal, node termination, node spawning
- FilterNode: classification and routing (passthrough/worker)
- DecisionNode: condition evaluation and queue mutation
- ProcessingNode: work execution and output
- TerminalNode: loop termination
- Session: AgentConfig storage, TodoList, parent_id reference, inherit/propagate rules
- Task tree: operations on root session only

### Integration Tests

- End-to-end query processing: QueryAnalyst → Worker → Digest → Analyze → Execute → Review → PrimaryAgent
- Passthrough flow: QueryAnalyst terminates → PrimaryAgent runs
- Worker with existing work: Worker detects work in progress → spawns QueryAnalyst(Worker)
- Queue continuity: resume from persisted queue state
- Pluggable terminal: ResultAggregator replaces PrimaryAgent
- Agent Interactivity Features: persistence, HITL, interrupt, resume

### Manual Tests

- Verify the external API is truly simple: `Agent(loop=TinyCUALoop(session=session)).run(query="...")`
- Verify queue lifecycle: init → process → terminate → auto-append terminal → done
- Verify node spawning and termination work correctly

---

## Status Tracker

| Item | Status | Notes |
|------|--------|-------|
| Spec | Draft | Awaiting review |
| Design | In Progress | Being updated with queue lifecycle rules |
| Documentation reorganization | TODO | Depends on design approval |
| Implementation | TODO | Depends on design approval |

---

## Open Questions

1. **How should the queue handle concurrent spawning (e.g., Worker spawns multiple nodes at once)?**
   - Status: Discussion
   - Current thinking: Nodes are added sequentially to the queue. No parallel spawning.

2. **Should terminal node completion propagate results to parent sessions?**
   - Status: Discussion
   - Current thinking: Yes — terminal node writes final result to root session.

---

## Review Checklist

- [ ] No implementation details (no code, framework, or architecture choices)
- [ ] All mandatory sections completed
- [ ] No `[NEEDS CLARIFICATION]` markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Scope is clearly bounded with explicit non-goals
- [ ] Success criteria are measurable
