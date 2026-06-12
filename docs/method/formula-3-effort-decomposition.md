# Formula 3: Effort-Controlled Task Decomposition

## Problem Statement

For queries routed to the WorkerNode, task decomposition depth must be controlled to balance planning quality against computational cost. The AnalysisEffortNode gates how many passes the TaskAssessor→TaskAnalyzer loop runs before execution begins.

## Formalization

### Effort Parameter

Let $e \in \mathcal{E} = \{\text{none}, \text{low}, \text{medium}, \text{high}\}$ denote the effort level. The pass limit function maps effort to maximum decomposition passes:

$$L(e) = \begin{cases} 0 & \text{if } e = \text{none} \\ 1 & \text{if } e = \text{low} \\ 2 & \text{if } e = \text{medium} \\ 3 & \text{if } e = \text{high} \end{cases}$$

### Task Tree Model

Let $T$ denote the task tree where:
- $|T|$ is the total number of tasks
- $T_{\text{unfinished}} \subseteq T$ is the set of tasks requiring decomposition
- $\text{depth}(t)$ is the depth of task $t$ in the tree

### Decomposition Algorithm

The WorkerNode's $\text{task\_creation}$ route executes:

**Phase 1: Deterministic Root Creation**

$$T_0 = \text{TaskCreateNode.create}(q)$$

where $q$ is the user query. This produces a root task tree with $|T_0| = 1$.

**Phase 2: Effort-Gated Decomposition Loop**

$$\text{Algorithm: EffortControlledDecomposition}$$

**Input:** $T_0$, effort $e$
**Output:** $T_{\text{final}}$ (fully decomposed task tree)

```
T ← T_0
pass_count ← 0
while pass_count < L(e):
    T_unfinished ← TaskAssessorNode.select(T)
    if T_unfinished = ∅:
        break
    for task ∈ T_unfinished:
        T ← TaskAnalyzerNode.decompose(task)
    pass_count ← pass_count + 1
return T
```

### TaskAssessor Selection Function

The TaskAssessorNode selects tasks for further decomposition:

$$\text{select}(T) = \{t \in T : \text{status}(t) = \text{unfinished} \land \text{needs\_decomposition}(t)\}$$

where $\text{needs\_decomposition}(t)$ evaluates whether task $t$ can be meaningfully refined.

### TaskAnalyzer Decomposition Function

The TaskAnalyzerNode decomposes a task $t$ into subtasks:

$$\text{decompose}(t) = T' \cup \{t_1, t_2, \ldots, t_m\}$$

where $T'$ is the updated tree and $\{t_1, \ldots, t_m\}$ are the new subtasks with $m \geq 1$.

## Worker Route Variants

The decomposition behavior varies by route:

| Route | TaskCreate | TaskAnalyzer Mode | TaskInit Tools |
|-------|------------|-------------------|----------------|
| $\text{task\_creation}$ | Yes | initial | Yes |
| $\text{task\_recreation}$ | No | initial | Yes |
| $\text{task\_reanalysis}$ | No | initial | No |

### Route-Specific Decomposition

**task_creation:**
$$T_{\text{final}} = \text{Decompose}(\text{TaskCreate}(q), e)$$

**task_recreation:**
$$T_{\text{final}} = \text{Decompose}(T_{\text{existing}}, e) \quad \text{(full rebuild)}$$

**task_reanalysis:**
$$T_{\text{final}} = \text{Decompose}(T_{\text{existing}}, e) \quad \text{(refinement only)}$$

## Properties

- **Deterministic control flow**: The loop itself involves no LLM calls beyond the decompose/select steps. The pass limit $L(e)$ is a hard bound.
- **Progressive refinement**: Each pass refines the decomposition further. $\text{none}$ = immediate execution (no decomposition), $\text{high}$ = three rounds of analysis before execution.
- **Early termination**: If TaskAssessor finds no tasks needing further decomposition ($T_{\text{unfinished}} = \emptyset$), the loop exits early regardless of pass limit.
- **Computational cost**: Higher effort = more LLM calls upfront, but potentially fewer retries during execution. The tradeoff is tunable per-query.

## Complexity Analysis

Given $|T|$ tasks and pass limit $L(e)$:

- **Worst case**: $O(L(e) \cdot |T|)$ TaskAnalyzerNode calls
- **Best case**: $O(1)$ if TaskAssessor selects nothing on first pass
- **Total decomposition cost**: $O(L(e) \cdot |T| \cdot d_{\text{max}})$ where $d_{\text{max}}$ is max subtasks per decomposition

The total task count after decomposition satisfies:

$$|T_{\text{final}}| \leq |T_0| \cdot \prod_{i=1}^{L(e)} \alpha_i$$

where $\alpha_i$ is the average branching factor at pass $i$.

## Termination Guarantee

The decomposition loop terminates because:

1. $L(e)$ is finite (bounded by 3)
2. Each pass either reduces $|T_{\text{unfinished}}|$ or breaks early
3. No infinite recursion: $\text{decompose}(t)$ produces strictly finer tasks

$$\exists \, i \leq L(e) : T_{\text{unfinished}} = \emptyset \implies \text{termination}$$
