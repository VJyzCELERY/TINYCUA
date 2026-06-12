# Formula 9: Result Aggregation BFS Traversal

## Problem Statement

After the root task is accepted/done, the ResultAggregationNode traverses the root task tree, inspects each task context/result/artifacts/reviewer decisions, consolidates information, and emits response-ready context for ResponseNode.

## Aggregation Model

### Input

The aggregation node receives the root task tree:

$$T_{\text{root}} = (V, E)$$

where:
- $V$ = set of task nodes
- $E$ = set of parent-child edges
- $|V|$ = total number of tasks

### Output

The aggregation produces an AggregatedResult:

$$\text{AggregatedResult} = (\text{id}_{\text{root}}, \mathcal{S}, \mathcal{R}, \mathcal{A}, \Phi, \Psi, \mathcal{M})$$

where:
- $\text{id}_{\text{root}}$ = root task identifier
- $\mathcal{S} = \{s_1, \ldots, s_{|V|}\}$ = task summaries
- $\mathcal{R} = \{r_1, \ldots, r_{|V|}\}$ = accepted results
- $\mathcal{A} = \{a_1, \ldots, a_p\}$ = artifacts
- $\Phi$ = final context string
- $\Psi$ = response continuation
- $\mathcal{M}$ = metadata dictionary

## Traversal Strategy

### Guided BFS Right-to-Left

The aggregation uses a guided BFS with right-to-left (most-recent-first) prioritization:

$$\text{Algorithm: GuidedBFS}(T_{\text{root}})$$

**Input:** Root task tree $T_{\text{root}}$
**Output:** AggregatedResult

```
queue ← [root_task]
visited ← {}
result ← empty_aggregate

while queue not empty:
    t ← queue.dequeue()  // right-to-left order
    if t in visited:
        continue
    visited.add(t)
    
    // Inspect task
    context_t ← inspect_context(t)
    result_t ← inspect_result(t)
    artifacts_t ← inspect_artifacts(t)
    decisions_t ← inspect_decisions(t)
    
    // Consolidate
    result.add_summary(summarize(t, context_t, result_t))
    result.add_result(result_t)
    result.extend_artifacts(artifacts_t)
    
    // Early termination check
    if sufficient_context(result):
        break
    
    // Enqueue children (right-to-left)
    children ← get_children(t)
    for child in reversed(children):
        if child not in visited:
            queue.enqueue(child)

result.final_context ← consolidate(result)
result.response_continuation ← synthesize(result)
return result
```

### Right-to-Left Ordering

For a task tree with children $[c_1, c_2, \ldots, c_n]$, right-to-left ordering processes $c_n$ first:

$$\text{order}(c_1, \ldots, c_n) = [c_n, c_{n-1}, \ldots, c_1]$$

This prioritizes most-recent work and recent reviewer decisions.

## Sufficiency Check

The aggregation may terminate early if enough response-ready context is found:

$$\text{sufficient\_context}(\text{result}) = \begin{cases} \text{true} & \text{if } |\text{result.summaries}| \geq \tau_{\text{min}} \land \text{coverage}(\text{result}) \geq \tau_{\text{cov}} \\ \text{false} & \text{otherwise} \end{cases}$$

where:
- $\tau_{\text{min}}$ = minimum summary count
- $\tau_{\text{cov}}$ = minimum coverage threshold

## Consolidation Functions

### Task Summary

Each task $t$ produces a summary:

$$\text{summarize}(t) = \text{LLM}_{\text{summarize}}(\text{context}(t), \text{result}(t), \text{decisions}(t))$$

### Final Context Consolidation

All summaries are consolidated:

$$\Phi = \text{consolidate}(\{s_1, \ldots, s_k\}) = \text{LLM}_{\text{consolidate}}(s_1 \oplus \cdots \oplus s_k)$$

### Response Continuation

The response continuation is synthesized:

$$\Psi = \text{synthesize}(\text{result}) = \text{LLM}_{\text{synthesize}}(\Phi, \mathcal{R}, \mathcal{A})$$

## Selective Deeper Reads

The aggregation does not need to perform exhaustive BFS. It may select any task node for deeper inspection:

$$\text{selective\_read}(t) = \begin{cases} \text{deep}(t) & \text{if } \text{needs\_detail}(t) \\ \text{shallow}(t) & \text{otherwise} \end{cases}$$

This allows the aggregation to focus on relevant tasks without traversing the entire tree.

## Complexity

For task tree with $|V|$ nodes and maximum branching factor $b$:

- **Worst case**: $O(|V|)$ (full BFS traversal)
- **Best case**: $O(\tau_{\text{min}})$ (early termination)
- **Average case**: $O(|V| \cdot p)$ where $p < 1$ is the pruning ratio

The aggregation cost is:

$$C_{\text{agg}} = O\left(\sum_{t \in V_{\text{visited}}} (|\text{context}(t)| + |\text{result}(t)|)\right)$$

## Properties

- **Non-destructive**: Traversal does not modify the task tree
- **Selective**: Can focus on relevant tasks without exhaustive traversal
- **Early termination**: Stops when sufficient context is found
- **Right-to-left priority**: Most-recent work processed first
