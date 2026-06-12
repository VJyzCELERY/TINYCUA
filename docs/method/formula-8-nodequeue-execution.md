# Formula 8: NodeQueue Sequential Execution

## Problem Statement

TINYCUA uses a sequential NodeQueue as its execution structure. The active node is always at position 0, and queue position controls execution order. This formula models the queue operations and their effects on node execution.

## Queue Model

### State Definition

The NodeQueue maintains a sequence of nodes:

$$Q = (n_1, n_2, \ldots, n_m)$$

where:
- $n_1$ = current active node (head)
- $m$ = queue length
- Position determines execution order

### Queue Operations

The queue supports the following operations:

| Operation | Effect | Post-condition |
|-----------|--------|----------------|
| $\text{current}(Q)$ | Returns $n_1$ | $Q$ unchanged |
| $\text{advance}(Q)$ | Removes $n_1$, propagates | $Q' = (n_2, \ldots, n_m)$ |
| $\text{spawn\_after}(Q, \mathcal{N}')$ | Inserts $\mathcal{N}'$ after $n_1$ | $Q' = (n_1, \mathcal{N}', n_2, \ldots, n_m)$ |
| $\text{suspend\_prepend}(Q, \mathcal{N}')$ | Keeps $n_1$, prepends $\mathcal{N}'$ | $Q' = (\mathcal{N}', n_1, n_2, \ldots, n_m)$ |
| $\text{clear\_after}(Q)$ | Removes nodes after $n_1$ | $Q' = (n_1)$ |
| $\text{ensure\_terminal}(Q, n_{\text{term}})$ | Appends terminal if missing | $Q' = Q \oplus (n_{\text{term}})$ |

### Input Function

The input for the current node is determined by:

$$\text{input\_for\_current}(Q) = \begin{cases} \text{root\_input} & \text{if } n_1 = \text{QueryAnalyst} \\ O(n_{\text{prev}}) & \text{otherwise (output of previous node)} \end{cases}$$

## Execution Loop

### TinyCUALoop Execution

The main execution loop:

$$\text{Algorithm: TinyCUALoop}(Q, S_{\text{root}})$$

**Input:** NodeQueue $Q$, root session $S_{\text{root}}$
**Output:** Final response or stream events

```
while not empty(Q):
    n ← current(Q)
    S_n ← ensure_session(n, S_root)
    input_n ← input_for_current(Q)
    messages_n ← build_messages(n, S_root, input_n)
    instr_n ← build_instruction(n)
    tools_n ← resolve_tools(n)
    result ← call_llm(messages_n, instr_n, tools_n)
    validate_retry(n, result)
    record_history(n, result)
    on_complete(n, Q, result)
return final_response(Q)
```

### Node.on_complete() Ownership

Each node owns its queue transitions via $\text{on\_complete()}$:

$$\text{on\_complete}(n_i, Q, r) \rightarrow Q'$$

The loop never calls $\text{advance()}$ after $\text{on\_complete()}$; it re-reads $\text{current}(Q)$ on the next iteration.

## Bootstrap Invariants

Every $\text{TinyCUALoop.run()}$ enforces:

### Invariant 1: QueryAnalyst Entry

$$\text{current}(Q) = \text{QueryAnalyst} \lor \text{prepend}(Q, \text{QueryAnalyst})$$

### Invariant 2: Terminal Safety

$$\exists \, n_{\text{term}} \in Q : \text{is\_terminal}(n_{\text{term}}) \lor \text{append}(Q, \text{ResponseNode})$$

These invariants ensure predictable queue state for crash recovery, HITL continuation, and terminal safety.

## Suspension Model

A node is suspended when it remains queued but is no longer at position 0:

$$\text{suspended}(n_i) = n_i \in Q \land n_i \neq \text{current}(Q)$$

### Suspension Example

$$Q_0 = (\text{ResponseNode})$$
$$Q_1 = \text{suspend\_prepend}(Q_0, [\text{DigesterNode}]) = (\text{DigesterNode}, \text{ResponseNode})$$
$$Q_2 = \text{advance}(Q_1) = (\text{ResponseNode})$$

The digester completes and the response node resumes.

## Queue Shape for Worker Paths

### task_creation

$$Q_{\text{creation}} = (\text{TaskCreate}, \text{TaskAnalyzer}, \text{Effort}, \text{Executor}, \text{Reviewer}, \text{Response})$$

### task_recreation

$$Q_{\text{recreation}} = (\text{TaskAnalyzer}_{+}, \text{Effort}, \text{Executor}, \text{Reviewer}, \text{Response})$$

### task_reanalysis

$$Q_{\text{reanalysis}} = (\text{TaskAnalyzer}, \text{Effort}, \text{Executor}, \text{Reviewer}, \text{Response})$$

### proceed_execution

$$Q_{\text{proceed}} = (\text{Executor}, \text{Reviewer}, \text{Response})$$

## Complexity

For queue length $m$:

- **advance**: $O(1)$ amortized (list pop)
- **spawn_after**: $O(1)$ (list insert)
- **suspend_prepend**: $O(1)$ (list insert)
- **clear_after**: $O(m)$ (list slice)
- **ensure_terminal**: $O(m)$ (linear scan)

Total execution: $O(m \cdot k)$ where $k$ is number of queue mutations per pipeline.
