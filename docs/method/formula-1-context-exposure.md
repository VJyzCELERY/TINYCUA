# Formula 1: Context Exposure Optimization

## Problem Statement

Small Language Models (SLMs, 1B–8B parameters) exhibit increased hallucination rates when processing large context windows. TINYCUA addresses this by decomposing not just work, but context exposure—each processing node receives only the context needed for its specific responsibility.

## Formalization

### System Model

Let $\mathcal{N} = \{n_1, n_2, \ldots, n_k\}$ denote the set of $k$ processing nodes in the NodeQueue. Each node $n_i \in \mathcal{N}$ is assigned a context window $C(n_i)$ representing the subset of total information available to that node during execution.

### Optimization Objective

$$\min_{\{C(n_i)\}} \max_{n_i \in \mathcal{N}} |C(n_i)|$$

subject to:

$$\bigcup_{n_i \in \mathcal{N}} C(n_i) \supseteq C_{\text{required}}$$

where $C_{\text{required}}$ is the minimum context needed to preserve task completeness.

### Completeness Constraint

The completeness constraint ensures no information critical to correctness is discarded:

$$\forall \, c \in C_{\text{required}}, \, \exists \, n_i \in \mathcal{N} : c \in C(n_i)$$

### Context Efficiency Ratio

Define the context efficiency ratio $\eta$ as:

$$\eta = \frac{|C_{\text{required}}|}{\sum_{n_i \in \mathcal{N}} |C(n_i)|}$$

For TINYCUA, $\eta \leq 1$ with equality when contexts are disjoint. In practice, some overlap exists for shared task state.

## Interpretation

- **Minimax objective**: We minimize the worst-case context exposure across all nodes. No single node bears the full context burden.
- **Completeness constraint**: The union of all node contexts must cover everything needed to solve the task. Information critical to correctness cannot be discarded.
- **Key insight**: A single SLM processing $C_{\text{required}}$ directly will hallucinate. Multiple nodes each processing a small subset $C(n_i) \ll C_{\text{required}}$ will not, as long as their combined coverage is sufficient.

## Relationship to Attention Theory

This formulation is grounded in:

- **Attention bottleneck** (Vaswani et al., 2017): Self-attention computes $\text{softmax}(QK^T/\sqrt{d_k})V$, where context length $n$ appears in the $QK^T$ matrix. Quadratic attention cost in $n$ creates information crowding.
- **Scaling laws** (Kaplan et al., 2020): SLMs have limited capacity to learn long-context patterns compared to larger models.
- **Hallucination correlation** (Miller, 2023): Empirical evidence that hallucination rate increases with context length in smaller models.

TINYCUA's approach keeps each node's $C(n_i)$ small enough that the SLM operates in a regime where hallucination rate is acceptably low, while distributing coverage across nodes.

## Node Context Allocation

The context allocation follows the node hierarchy:

| Node | Context Scope | Context Size |
|------|---------------|--------------|
| QueryAnalyst | Root session + active/queued contexts | O(\|S_root\| + Σ\|S_active\|) |
| Worker | QueryAnalyst output + session context | O(\|S_root\|) |
| TaskCreate | Worker output + task specification | O(1) deterministic |
| TaskAnalyzer | Task tree + mode-specific context | O(\|T\|) where \|T\| = task count |
| TaskAssessor | Full task tree (read-only) | O(\|T\|) |
| TaskExecutor | Active task + selected tools | O(1) per task |
| ResultReviewer | Executor output + task context | O(1) per task |
| ResultAggregation | Root task tree (traversal) | O(\|T\|) selective |
| Response | Aggregated result + session context | O(\|S_root\|) |
| InformationDigester | Selected input + retrieval cache | O(\|S_selected\|) |

## Complexity Analysis

Given $k$ nodes and total context size $|C_{\text{required}}|$:

- **Naive approach**: Single node processes $|C_{\text{required}}|$ tokens → $O(|C_{\text{required}}|^2)$ attention cost
- **TINYCUA**: Each node processes $|C(n_i)|$ tokens → $\sum_{i=1}^{k} O(|C(n_i)|^2)$ total attention cost

Since $|C(n_i)| \ll |C_{\text{required}}|$ for all $i$, and $\sum |C(n_i)|^2 < (\sum |C(n_i)|)^2$, TINYCUA reduces total quadratic attention cost while maintaining completeness.
