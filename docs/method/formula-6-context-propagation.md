# Formula 6: Segmented Context Propagation

## Problem Statement

Context flows between nodes using a segmented model that controls what information is durable vs. transient. This model preserves useful old `Session.terminate_child(...)` behavior while making it explicit and configurable.

## Session Context Composition

### Segmented Model

For each node $n_i$, its session context is segmented into three parts:

$$S(n_i) = P(n_i) \oplus I(n_i) \oplus O(n_i)$$

where:
- $P(n_i)$ = **prior_context**: Context inherited from parent/ancestor nodes (immutable for this execution)
- $I(n_i)$ = **input_segment**: Context specific to this node's task (received as NodeInput)
- $O(n_i)$ = **output_segment**: Context produced by this node's execution

### Propagation Rules

On node termination, context flows in two directions:

**Upward propagation (to parent/root):**

$$\text{propagate\_to\_parent}(n_i) = S(n_i) \setminus O(n_i) = P(n_i) \oplus I(n_i)$$

**Forward propagation (to next node):**

$$\text{forward\_to\_next}(n_i) = O(n_i)$$

The parent receives everything **except** the output segment. The next node receives **only** the output segment as its input.

## Transient Nodes

### Transient Property

Nodes like QueryAnalyst and Worker are transient — their assembled context is **not** backward-propagated to the parent:

$$n_i \in \text{Transient} \implies \text{propagate\_to\_parent}(n_i) = \emptyset$$

Their output becomes durable only when a subsequent non-transient node ingests it as input:

$$\text{durability}(O(n_i)) = \exists \, n_j \notin \text{Transient} : O(n_i) \in I(n_j)$$

### Transient Node Examples

| Node | Transient | Propagation Behavior |
|------|-----------|---------------------|
| QueryAnalyst | Yes | Output forwarded, not committed to parent |
| Worker | Yes | Output forwarded, not committed to parent |
| TaskCreate | No | Output propagates to parent |
| TaskAnalyzer | No | Output propagates to parent |
| TaskExecutor | No | Output propagates to parent |
| ResultReviewer | No | Output propagates to parent |
| Response | No | Terminal node, output returned to SDK |

## Deduplication

### Origin Record Tracking

Each context record carries metadata:

$$\text{record} = (\text{id}, \text{origin\_id}, \text{segment}, \text{source}, \text{created})$$

where:
- $\text{id}$ = unique record identifier
- $\text{origin\_id}$ = original record id (preserved on copy)
- $\text{segment}$ = $\{\text{prior}, \text{input}, \text{output}\}$
- $\text{source}$ = source node/session id
- $\text{created}$ = creation sequence number

### Deduplication Rule

When merging contexts across propagation boundaries:

$$\text{dedupe}(r) = \begin{cases} \text{keep earliest}(r) & \text{if } \exists \, r' : \text{origin}(r) = \text{origin}(r') \\ \text{add}(r) & \text{otherwise} \end{cases}$$

where $\text{origin}(r) = \text{origin\_id}(r)$ if present, else $\text{id}(r)$.

### Deduplication Levels

Deduplication operates at two levels:

1. **Propagation dedupe**: $\text{PropagationRule.dedupe}$ filters writes during propagation
2. **Message dedupe**: $\text{NodeMessagePolicy.dedupe\_by\_origin\_record\_id}$ filters LLM-bound input

## Propagation Rule

### Rule Definition

$$\text{PropagationRule} = (\text{chat\_history}, \text{context\_target}, \text{context\_mode}, \text{token\_usage}, \text{failure}, \text{dedupe})$$

where:
- $\text{chat\_history} \in \{\text{none}, \text{parent}, \text{root}\}$
- $\text{context\_target} \in \{\text{none}, \text{parent}, \text{root}, \text{parent\_and\_root}\}$
- $\text{context\_mode} \in \{\text{none}, \text{final}, \text{full}, \text{selected}\}$
- $\text{token\_usage} \in \{\text{none}, \text{parent}, \text{root}, \text{parent\_and\_root}\}$
- $\text{failure} \in \{\text{none}, \text{parent}, \text{root}, \text{parent\_and\_root}\}$
- $\text{dedupe} \in \{\text{true}, \text{false}\}$

### Propagation Profiles

| Profile | chat_history | context_target | context_mode | token_usage | failure |
|---------|--------------|----------------|--------------|-------------|---------|
| transient | parent_and_root | none | none | parent_and_root | parent_and_root |
| natural_termination | parent_and_root | parent_and_root | final | parent_and_root | parent_and_root |
| mid_progress | parent_and_root | parent_and_root | full | parent_and_root | parent_and_root |
| selected_internal | root | root | selected | root | root |

## Chat History vs Session Context

$$\text{chat\_history} = \text{durable append-only audit transcript}$$
$$\text{session\_context} = \text{mutable, selected, deduped LLM-reusable context}$$

- $\text{chat\_history}$ records node I/O provenance and is not the LLM memory itself
- $\text{session\_context}$ is mutable and can compact/lose prior messages
- $\text{chat\_history}$ preserves provenance for audit

## Example Propagation

### Node₁ Execution

$$S(n_1) = P_1 \oplus I_1 \oplus O_1$$

On termination:
- Parent receives: $P_1 \oplus I_1$ (output excluded)
- Node₂ receives: $O_1$ (becomes Node₂'s input_segment)

### Node₂ Execution

$$S(n_2) = O_1 \oplus I_2 \oplus O_2$$

On termination:
- Parent receives: $O_1 \oplus I_2$ (output excluded)
- Node₃ receives: $O_2$

## Complexity

For $k$ nodes with average context size $|S|$:

- **Propagation cost**: $O(k \cdot |S|)$ per full pipeline execution
- **Deduplication cost**: $O(|S|^2)$ in worst case (pairwise comparison)
- **Storage**: $O(k \cdot |S|)$ for all node contexts
