# Design Document: Design Simplification

**Spec**: [./spec.md](./spec.md)
**Status**: Draft
**Last Updated**: 2026-06-03

---

## Overview

TINYCUA's current design uses 56 documentation files across 11 directories with multiple abstraction layers modeled as a multi-agent graph (AgentGraph, AgentNode, RouterNode, InputGate, OutputGate, Factory). This design collapses those layers into a **self-supervising loop** (`TinyCUALoop`) with a **sequential Node Queue** and **deterministic routing**. The queue always has an entry node (QueryAnalyst) and terminal node (PrimaryAgent). Nodes terminate themselves, spawn new nodes, and propagate sessions. The queue is the state machine — each node transitions to the next state. AgentConfig moves from AgentState to Session. Persistence, HITL, interrupt, and resume are documented as Agent Interactivity Features.

---

## Architecture

### Paradigm Shift

**Current: Multi-Agent Graph (parallel implied)**
```
AgentGraph (queue + routing)
  → AgentNode (Session + Agent coupling, 7 subclasses)
    → Agent (SDK)
      → AgentLoop (retry/output, 7 subclasses)
```

**Simplified: Self-Supervising Loop + Node Queue (sequential, deterministic routing)**
```
Agent (SDK)
  └── TinyCUALoop (extends BaseLoop with Session)
        ├── root_session (holds Task, TodoList, AgentConfig)
        └── NodeQueue
              → [QueryAnalyst] ← always at start (entry node)
              → ... (processing nodes, dynamically spawned)
              → [PrimaryAgent] ← always at end (terminal node)
```

### External API

```python
# Create
session = Session(
    agent_config=AgentConfig(
        entry_nodes={"query_analyst": QueryAnalystConfig(...)},
        worker_nodes={
            "digest": DigestConfig(...),
            "analyze": AnalyzeConfig(...),
            "execute": ExecuteConfig(...),
            "review": ReviewConfig(...),
        },
        terminal_nodes={"primary": PrimaryConfig(...)},
    )
)
agent = Agent(loop=TinyCUALoop(session=session))

# Run
async for event in agent.run(query="Implement the worker graph"):
    yield event

# Extend
class MyLoop(TinyCUALoop):
    def _build_queue(self):
        # custom queue configuration
        ...
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `AgentGraph` | **Replaced** | Becomes `NodeQueue` with deterministic routing |
| `AgentNode` (7 subclasses) | **Replaced** | Become concrete Node types with characteristics |
| `RouterNode` | **Deleted** | Routing is internal to nodes (FilterNode, DecisionNode) |
| `InputGate` / `OutputGate` | **Deleted** | Entry node and terminal node replace these |
| `Factory` (create_agent_node, load_agent_node) | **Deleted** | Just `Agent(loop=...)` |
| `AgentConfig` on `AgentState` | **Moved** | Now on Session directly |
| `NodeQueue` | **New** | Sequential queue with auto-append terminal |
| `Node` | **New** | Base processing unit with characteristics |
| `FilterNode` | **New** | Classifies input and routes (QueryAnalyst) |
| `DecisionNode` | **New** | Evaluates conditions and mutates queue (Worker) |
| `ProcessingNode` | **New** | Does work and produces output (Digest, Execute, etc.) |
| `TerminalNode` | **New** | Ends the loop (PrimaryAgent, ResultAggregator) |
| `TinyCUALoop` | **New** | Central self-supervising loop at `tinycua/loops/tinycua_loop.py` |
| `BaseLoop` extension | **New** | Extends SDK BaseLoop to include Session |
| `Session` | **Modified** | Now holds AgentConfig + TodoList; parent_id as reference |
| `Task` | **Unchanged** | Lives on root Session only |
| `AgentState` subclasses | **Modified** | No longer hold AgentConfig; still used for typed output |
| Tools | **Unchanged** | Task tools, classification, digester tools |

---

## Data Model

### NodeQueue

```python
class NodeQueue:
    """
    Sequential processing queue with deterministic routing.
    Always has an entry node and terminal node.
    """
    
    _queue: list[Node]
    _entry_node_id: str                     # always at position 0
    _terminal_node_ids: set[str]            # terminal nodes end the loop
    
    @property
    def current(self) -> Node | None:
        """The node at the front of the queue."""
        return self._queue[0] if self._queue else None
    
    @property
    def next_after_current(self) -> Node | None:
        """The node after the current one (for Worker to detect work in progress)."""
        return self._queue[1] if len(self._queue) > 1 else None
    
    @property
    def is_terminal_active(self) -> bool:
        """Whether the current node is a terminal node."""
        return self.current is not None and self.current.node_id in self._terminal_node_ids
    
    def advance(self) -> None:
        """Remove the current node from the front."""
        if self._queue:
            self._queue.pop(0)
    
    def spawn_after_current(self, nodes: list[Node]) -> None:
        """Insert nodes after the current node."""
        for i, node in enumerate(nodes):
            self._queue.insert(1 + i, node)
    
    def terminate_current(self) -> None:
        """Remove the current node (node terminates itself)."""
        self.advance()
    
    def clear_after_current(self) -> None:
        """Clear all nodes after current (for task recreation)."""
        if self._queue:
            self._queue = [self._queue[0]]
    
    def ensure_terminal(self, default_terminal: Node) -> None:
        """Auto-append terminal node if none exists after current."""
        has_terminal = any(
            node.node_id in self._terminal_node_ids
            for node in self._queue[1:]
        )
        if not has_terminal:
            self._queue.append(default_terminal)
    
    def is_empty(self) -> bool:
        return len(self._queue) == 0
```

### Node (Base Class)

```python
class Node(ABC):
    """
    Base processing unit in the queue.
    Has its own Session. Accepts input: str.
    Can terminate itself or spawn new nodes.
    """
    
    node_id: str                            # unique identifier
    session: Session                        # this node's session
    config: NodeConfig                      # instructions + base tools
    is_terminal: bool = False               # whether this node ends the loop
    
    @abstractmethod
    async def run(self, input: str) -> AsyncIterator[dict]:
        """Execute this node's logic. Accepts universal string input."""
        ...
    
    def on_complete(self, queue: NodeQueue, result: AgentState) -> None:
        """Called after run() completes. Default: no queue mutation."""
        pass
    
    def on_terminate(self, queue: NodeQueue) -> None:
        """Called when node terminates itself. Default: remove from queue."""
        queue.terminate_current()
```

### FilterNode

```python
class FilterNode(Node):
    """
    Classifies input and routes based on classification.
    Example: QueryAnalyst (classifies passthrough/worker).
    """
    
    async def run(self, input: str) -> AsyncIterator[dict]:
        """Classify the query and write QueryAnalystState."""
        ...
    
    def on_complete(self, queue: NodeQueue, result: AgentState) -> None:
        """Route based on classification."""
        if isinstance(result, QueryAnalystState):
            if result.classification == "passthrough":
                # Terminate self, let terminal node handle
                self.on_terminate(queue)
            elif result.classification == "worker":
                # Spawn worker nodes after self
                queue.spawn_after_current([
                    InformationDigestionNode(...),
                    WorkerDecisionNode(...),
                ])
                # Then terminate self
                self.on_terminate(queue)
```

### DecisionNode

```python
class DecisionNode(Node):
    """
    Evaluates conditions and mutates the queue.
    Example: Worker (detects work in progress, spawns appropriate nodes).
    """
    
    async def run(self, input: str) -> AsyncIterator[dict]:
        """Evaluate the current state and decide next action."""
        ...
    
    def on_complete(self, queue: NodeQueue, result: AgentState) -> None:
        """Detect context and spawn appropriate nodes."""
        next_node = queue.next_after_current
        
        if next_node is None or next_node.is_terminal:
            # No work in progress — spawn task analysis
            queue.spawn_after_current([
                TaskAnalyzerNode(with_task_init=True),
            ])
        else:
            # Work in progress — spawn worker-level QueryAnalyst
            queue.spawn_after_current([
                WorkerQueryAnalystNode(),
            ])
        
        # Worker terminates itself after spawning
        self.on_terminate(queue)
```

### ProcessingNode

```python
class ProcessingNode(Node):
    """
    Does work and produces output.
    Example: TaskExecutor, InformationDigester, PrimaryAgent.
    """
    
    async def run(self, input: str) -> AsyncIterator[dict]:
        """Execute work and write result to session."""
        ...
    
    # on_complete: default (no mutation) — processing nodes just do work
```

### TerminalNode

```python
class TerminalNode(Node):
    """
    Ends the loop. When a terminal node completes, the loop ends.
    Example: PrimaryAgent, ResultAggregator.
    """
    
    is_terminal: bool = True
    
    async def run(self, input: str) -> AsyncIterator[dict]:
        """Generate final response and write to root session."""
        ...
    
    def on_complete(self, queue: NodeQueue, result: AgentState) -> None:
        """Terminal node completes — loop will end."""
        pass  # Loop checks is_terminal_active and exits
```

### Session (Modified)

```python
class Session(StateObject):
    # --- Identity ---
    session_id: str
    parent_id: str | None = None            # lightweight reference to parent
    
    # --- State ---
    agent_state: AgentState                 # lifecycle + typed output (no agent_config)
    agent_config: AgentConfig               # NEW: holds all node configs (on root session)
    
    # --- Context ---
    chat_history: list[ChatRecord]
    session_context: list[dict]
    task: Task | None                       # only on root session
    todo_list: list[dict[str, str]] | None  # per-session short-term goals
    
    # --- Methods ---
    def append_user(self, content: str) -> None: ...
    def append_assistant(self, content: str, **kwargs) -> None: ...
    def get_messages(self) -> list[dict]: ...
```

### AgentConfig (On Root Session)

```python
class AgentConfig(StateObject):
    """Stores all node configs. Lives on root Session."""
    
    # Node configs organized by role
    entry_nodes: dict[str, NodeConfig]      # always at queue start (QueryAnalyst)
    worker_nodes: dict[str, NodeConfig]     # worker processing nodes
    terminal_nodes: dict[str, NodeConfig]   # terminal nodes (PrimaryAgent)
    
    # Default terminal node
    default_terminal: str = "primary"       # node_id of default terminal
    
    # Shared config
    model: LanguageModel
    compaction_strategy: BaseCompaction | None = None
    hitl_enabled: bool = False

class NodeConfig(StateObject):
    """Base config for a Node."""
    instructions: str
    base_tools: list[Tool]
    model: LanguageModel | None = None      # override shared model
```

### AgentState (Modified)

```python
class AgentState(StateObject):
    type: str                               # node identity
    status: AgentStatus = "idle"            # idle | running | terminated | blocked
    failure: int = 0
    # agent_config REMOVED — now on Session
```

### Task (Unchanged)

```python
class Task(StateObject):
    task_id: str
    task_name: str
    task_description: str
    child_tasks: list[Task] | None = None
    task_result: TaskResult | None = None
    # Lives on root Session only. Not duplicated across nodes.
```

### TodoList (Per Session)

```python
# On each Session:
todo_list: list[dict[str, str]] | None = None
# Each item: {"status": "incomplete" | "completed", "todo": str}
```

### Agent Interactivity Features

| Feature | Description | Integration Point |
|---------|-------------|-------------------|
| **Persistence** | Save/load session state across runs | Session serialization + StateStore |
| **HITL** | Human-in-the-loop decision points | Node can pause and await human input |
| **Interrupt** | Stop execution mid-node | Loop checks interrupt flag between node transitions |
| **Resume** | Continue from saved state | Load Session, pass to Loop, resume from next node in queue |

---

## Queue Lifecycle Examples

### Example 1: Simple Passthrough

```
INIT: [QueryAnalyst, PrimaryAgent]

Step 1: QueryAnalyst runs
  → QueryAnalystState(classification="passthrough")
  → on_complete: terminate self
  → Queue: [PrimaryAgent]

Step 2: PrimaryAgent runs (terminal)
  → PrimaryAgentState(final_response="...")
  → Queue: [] (empty, terminal completed)
  → LOOP ENDS
```

### Example 2: Worker Flow

```
INIT: [QueryAnalyst, PrimaryAgent]

Step 1: QueryAnalyst runs
  → QueryAnalystState(classification="worker")
  → on_complete: spawn [InformationDigester, Worker], terminate self
  → Queue: [InformationDigester, Worker, PrimaryAgent]

Step 2: InformationDigester runs
  → InformationDigesterState(...)
  → on_complete: no mutation (ProcessingNode)
  → Queue: [Worker, PrimaryAgent]

Step 3: Worker runs (DecisionNode)
  → Detects: next node is PrimaryAgent (no work in progress)
  → on_complete: spawn [TaskAnalyzer], terminate self
  → Queue: [TaskAnalyzer, PrimaryAgent]

Step 4: TaskAnalyzer runs
  → TaskAnalyzerState(...)
  → Queue: [PrimaryAgent]

Step 5: PrimaryAgent runs (terminal)
  → PrimaryAgentState(final_response="...")
  → LOOP ENDS
```

### Example 3: Worker with Existing Work

```
EXISTING QUEUE: [TaskExecutor, PrimaryAgent]
NEW QUERY enters → QueryAnalyst at start

INIT: [QueryAnalyst, TaskExecutor, PrimaryAgent]

Step 1: QueryAnalyst runs
  → QueryAnalystState(classification="worker")
  → on_complete: spawn [InformationDigester, Worker], terminate self
  → Queue: [InformationDigester, Worker, TaskExecutor, PrimaryAgent]

Step 2: InformationDigester runs → terminates
  → Queue: [Worker, TaskExecutor, PrimaryAgent]

Step 3: Worker runs (DecisionNode)
  → Detects: next node is TaskExecutor (work in progress)
  → on_complete: spawn [WorkerQueryAnalyst], terminate self
  → Queue: [WorkerQueryAnalyst, TaskExecutor, PrimaryAgent]

Step 4: WorkerQueryAnalyst runs
  → QueryAnalystState(classification="task_reanalysis")
  → on_complete: terminate self
  → Queue: [TaskExecutor, PrimaryAgent]

Step 5: TaskExecutor continues execution
  → Queue: [PrimaryAgent]

Step 6: PrimaryAgent runs (terminal)
  → LOOP ENDS
```

### Example 4: Task Recreation

```
INIT: [QueryAnalyst, Worker, TaskExecutor, PrimaryAgent]

... (previous steps) ...

Step N: WorkerQueryAnalyst runs
  → QueryAnalystState(classification="task_recreation")
  → on_complete: clear queue after self, spawn [TaskAnalyzer(+TaskInit)], terminate self
  → Queue: [TaskAnalyzer, PrimaryAgent]

Step N+1: TaskAnalyzer runs (with TaskInit)
  → Creates new task tree
  → Queue: [PrimaryAgent]

Step N+2: PrimaryAgent runs (terminal)
  → LOOP ENDS
```

---

## API / Interface Contracts

### TinyCUALoop

```python
class TinyCUALoop(BaseLoop):
    """
    Central self-supervising loop for TINYCUA.
    
    Owns the root Session, Task tree, and Node Queue.
    Initializes queue with entry + terminal nodes.
    Auto-appends terminal if missing.
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.task = session.task
        self.nodes = self._build_nodes()
        self.queue = self._build_queue()
        self._default_terminal = self._build_default_terminal()
    
    def _build_nodes(self) -> dict[str, Node]:
        """Build Node instances from session.agent_config."""
        config = self.session.agent_config
        nodes = {}
        
        for name, node_config in config.entry_nodes.items():
            nodes[name] = FilterNode(
                node_id=name,
                session=Session(parent_id=self.session.session_id),
                config=node_config,
            )
        
        for name, node_config in config.worker_nodes.items():
            nodes[name] = DecisionNode(
                node_id=name,
                session=Session(parent_id=self.session.session_id),
                config=node_config,
            )
        
        for name, node_config in config.terminal_nodes.items():
            nodes[name] = TerminalNode(
                node_id=name,
                session=Session(parent_id=self.session.session_id),
                config=node_config,
            )
        
        return nodes
    
    def _build_queue(self) -> NodeQueue:
        """Build the initial queue: entry node + terminal node."""
        config = self.session.agent_config
        queue = NodeQueue(
            entry_node_id=list(config.entry_nodes.keys())[0],
            terminal_node_ids=set(config.terminal_nodes.keys()),
        )
        
        # Entry node always first
        entry = self.nodes[config.entry_nodes.keys()[0]]
        queue._queue.append(entry)
        
        # Terminal node always last
        terminal = self.nodes[config.default_terminal]
        queue._queue.append(terminal)
        
        return queue
    
    def _build_default_terminal(self) -> Node:
        """Build the default terminal node for auto-append."""
        config = self.session.agent_config
        return self.nodes[config.default_terminal]
    
    async def run(
        self,
        agent: Agent,
        messages: list[dict],
        tools: list[Tool],
        override_instructions: str | None = None,
        stream: bool = False,
    ) -> AsyncIterator[dict]:
        """Main entry point. Processes query through the node queue."""
        query = messages[-1]["content"] if messages else ""
        
        # Insert entry node at start for this query
        entry = self.nodes[self.queue._entry_node_id]
        self.queue._queue.insert(0, entry)
        
        while not self.queue.is_empty():
            node = self.queue.current
            if node is None:
                break
            
            # Run the current node
            last_result = None
            async for event in node.run(query):
                if event.get("type") == "tinycua.final_result":
                    last_result = event["result"]
                    self.session.agent_state = last_result
                yield event
            
            # Let the node handle completion (spawn/terminate)
            if last_result is not None:
                node.on_complete(self.queue, last_result)
            
            # Auto-append terminal if queue has no terminal after current
            self.queue.ensure_terminal(self._default_terminal)
            
            # If current node is terminal and completed, end loop
            if node.is_terminal:
                break
```

### Error Handling

| Error Case | Exception | Notes |
|------------|-----------|-------|
| Missing classification after retries | `LoopOutputValidationError` | Fallback to first configured label |
| Missing digest after retries | `LoopOutputValidationError` | Partial digest with failure=1 |
| Invalid task tree mutation | `ValueError` | From task tools |
| Session not provided | `ValueError` | Raised in `__init__` |
| Node not found in queue | `KeyError` | Invalid node reference |

---

## Documentation Reorganization

```
docs/design/
├── models/                    ← renamed from state/
│   ├── state_object.md        ← StateObject base
│   ├── agent_state.md         ← AgentState lifecycle (agent_config removed)
│   ├── information.md         ← AgentState subclasses
│   ├── task.md                ← Task tree + TaskResult
│   ├── classification.md      ← ContextEnhancedQuery
│   ├── digested_information.md
│   ├── reviewer_decision.md
│   ├── worker_result.md
│   ├── execution_log.md
│   ├── session.md             ← updated: AgentConfig on Session, TodoList, parent_id ref
│   ├── chat_record.md
│   └── state_store.md
├── loop/                      ← new central section
│   ├── overview.md            ← self-supervising loop + node queue architecture
│   ├── tinycua_loop.md        ← TinyCUALoop class contract
│   ├── base_loop.md           ← BaseLoop extension with Session
│   ├── node_queue.md          ← NodeQueue (replaces AgentGraph) + lifecycle rules
│   ├── node.md                ← Node base class + FilterNode, DecisionNode, ProcessingNode, TerminalNode
│   ├── worker_concept.md      ← TinyCUAWorker as DecisionNode
│   └── interactivity.md       ← Agent Interactivity Features
├── config/                    ← simplified
│   ├── agent_config.md        ← AgentConfig on Session (all node configs)
│   └── node_config.md         ← per-node config (instructions, base tools)
├── tools/                     ← kept as-is
│   ├── digester.md
│   ├── task.md
│   └── todo.md
├── constants/                 ← simplified
│   ├── tools.md
│   └── instructions.md
├── exceptions/                ← kept
│   └── loops.md
├── utility/                   ← kept
│   └── compaction.md
└── README.md                  ← updated
```

**Eliminated sections:**
- `agent_node/` (9 files) → replaced by `loop/node.md`
- `agents/` (8 files) → replaced by node configs in `config/node_config.md`
- `orchestration/` (5 files) → replaced by `loop/node_queue.md` + `loop/tinycua_loop.md`

**Net reduction:** 56 files → ~25 files

---

## Implementation Phases

### Phase 1 — Documentation Reorganization (this PR)

- [ ] Create `docs/design/models/` directory (rename from `state/`)
- [ ] Move all `state/*.md` files to `models/*.md`
- [ ] Update `models/session.md` to reflect AgentConfig on Session, TodoList, parent_id reference
- [ ] Update `models/agent_state.md` to reflect agent_config removed
- [ ] Create `docs/design/loop/` directory
- [ ] Create `docs/design/loop/overview.md` — self-supervising loop + node queue architecture
- [ ] Create `docs/design/loop/tinycua_loop.md` — TinyCUALoop class contract
- [ ] Create `docs/design/loop/base_loop.md` — BaseLoop extension with Session
- [ ] Create `docs/design/loop/node_queue.md` — NodeQueue + lifecycle rules (entry, terminal, auto-append)
- [ ] Create `docs/design/loop/node.md` — Node base class + FilterNode, DecisionNode, ProcessingNode, TerminalNode
- [ ] Create `docs/design/loop/worker_concept.md` — TinyCUAWorker as DecisionNode
- [ ] Create `docs/design/loop/interactivity.md` — Agent Interactivity Features
- [ ] Create `docs/design/config/agent_config.md` — AgentConfig on Session
- [ ] Create `docs/design/config/node_config.md` — per-node config
- [ ] Simplify `docs/design/constants/` — consolidate tool/instruction constants
- [ ] Delete `docs/design/agent_node/` (9 files)
- [ ] Delete `docs/design/agents/` (8 files)
- [ ] Delete `docs/design/orchestration/` (5 files)
- [ ] Update `docs/design/README.md` to reflect new structure
- [ ] Update all internal cross-references

### Phase 2 — Implementation (future PR)

- [ ] Implement NodeQueue and Node base class
- [ ] Implement FilterNode, DecisionNode, ProcessingNode, TerminalNode
- [ ] Implement TinyCUALoop with queue routing and auto-append terminal
- [ ] Move AgentConfig from AgentState to Session
- [ ] Add TodoList to Session
- [ ] Remove AgentGraph, RouterNode, Factory classes
- [ ] Update imports and module structure
- [ ] Run full test suite

> **Note**: Phase 2 must NOT be implemented until Phase 1 is complete and reviewed.

---

## Technical Decisions

1. **Decision**: Queue with entry + terminal nodes
   - **Reason**: Ensures predictable flow. Entry node always runs first. Terminal node always ends the loop. Auto-append ensures terminal exists.
   - **Alternatives Considered**: Free-form queue — rejected because it loses predictability.

2. **Decision**: Nodes terminate themselves
   - **Reason**: Each node decides when it's done. It removes itself from the queue and propagates its session. This is explicit and simple.
   - **Alternatives Considered**: External termination — rejected because it adds indirection.

3. **Decision**: Nodes spawn new nodes
   - **Reason**: This is the routing mechanism. A FilterNode can spawn worker nodes. A DecisionNode can spawn analysis nodes. This is explicit and flexible.
   - **Alternatives Considered**: External router — rejected because it adds indirection.

4. **Decision**: Worker detects work in progress via queue context
   - **Reason**: Worker checks the next node in the queue. If it's a terminal node, no work is in progress. If it's something else, work is ongoing. This is deterministic and simple.
   - **Alternatives Considered**: Session-based detection — rejected because queue context is more reliable.

5. **Decision**: Pluggable terminal nodes
   - **Reason**: PrimaryAgent is the default terminal, but ResultAggregator or other nodes can replace it. This allows flexibility without changing the core loop.
   - **Alternatives Considered**: Fixed terminal — rejected because it limits extensibility.

6. **Decision**: Universal `input: str` for all nodes
   - **Reason**: All nodes accept a string input. Internal parsing handles different data formats. This keeps the interface simple and consistent.
   - **Alternatives Considered**: Typed inputs — rejected because it complicates the queue.

7. **Decision**: AgentConfig on Session, not AgentState
   - **Reason**: Session is the single source of truth. AgentConfig stores all node configs at once. AgentState is for typed output, not configuration.
   - **Alternatives Considered**: Keep AgentConfig on AgentState — rejected because it splits configuration across two objects.

8. **Decision**: TinyCUAWorker as DecisionNode, not separate agent
   - **Reason**: Worker is a node that detects context and routes. It doesn't need its own agent, session, or subgraph.
   - **Alternatives Considered**: Keep TinyCUAWorker as separate agent — rejected because it reintroduces multi-agent complexity.

9. **Decision**: TinyCUALoop at `tinycua/loops/tinycua_loop.py`
   - **Reason**: Consistent with existing loop module structure. The loop is the primary extension point.
   - **Alternatives Considered**: `tinycua/loop.py` as top-level — rejected for consistency.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Queue becomes too long | Low | Medium | Keep queue shallow; nodes terminate quickly |
| Node spawning complexity | Medium | Medium | Start with deterministic spawning; make configurable later |
| Session changes break existing behavior | Medium | High | Keep Session model mostly unchanged; only add AgentConfig + TodoList |
| Documentation drift during reorganization | Medium | Low | Cross-reference audit before merging |

---

## Open Questions

1. **Should the queue support batch spawning (multiple nodes at once)?**
   - Status: Discussion
   - Current thinking: Yes — `spawn_after_current(nodes: list[Node])` already supports this.

2. **How should queue persistence work?**
   - Status: Discussion
   - Current thinking: Serialize queue state (node IDs + positions) as part of Session. On resume, reconstruct queue from persisted state.

---

## References

- Spec: [./spec.md](./spec.md)
- Current design docs: `src/tinycua/docs/design/` (to be reorganized)
- Current specs: `src/tinycua/specs/`
