# Formula 5: Review Loop with Failure Threshold

## Problem Statement

After each task execution, the ResultReviewerNode evaluates the result and decides whether to accept, retry, replan, or ask an open question. A configurable failure threshold prevents infinite retry loops while allowing transient failures to recover.

## Decision Model

### Reviewer Decision Space

Let $\mathcal{D} = \{\text{accept}, \text{retry}, \text{replan}, \text{open\_question}\}$ denote the set of reviewer decisions. For task $t_k$ with execution result $\rho_k$:

$$d_k = \text{review}(t_k, \rho_k, \text{context}_k) \in \mathcal{D}$$

### Decision Semantics

| Decision $d$ | Meaning | Recovery Action |
|--------------|---------|-----------------|
| $\text{accept}$ | Quality bar met | Update task status, advance to next task or aggregation |
| $\text{retry}$ | Transient failure, same plan viable | Increment failure counter, re-execute same task |
| $\text{replan}$ | Plan failure | Local TaskAssessor + TaskAnalyzer, then re-execute |
| $\text{open\_question}$ | Needs user input | Install mandatory_passthrough, await continuation |

### Failure Counter

Let $f_k$ denote the consecutive failure count for task $t_k$. The counter evolves as:

$$f_k \leftarrow \begin{cases} 0 & \text{if } d_k = \text{accept} \\ f_k + 1 & \text{if } d_k = \text{retry} \end{cases}$$

### Threshold Constraint

The retry decision is constrained by a configurable threshold $\theta$ (default: $\theta = 5$):

$$d_k = \text{retry} \implies f_k < \theta$$

When $f_k \geq \theta$, the system must escalate or accept:

$$f_k \geq \theta \implies d_k \in \{\text{accept}, \text{replan}, \text{open\_question}\}$$

## Review Loop Algorithm

$$\text{Algorithm: ReviewLoop}(t_k, \theta)$$

**Input:** task $t_k$, failure threshold $\theta$
**Output:** task result $\rho_k$ or escalated state

```
f_k ← 0
while True:
    ρ_k ← TaskExecutorNode.execute(t_k)
    d_k ← ResultReviewerNode.review(t_k, ρ_k)
    match d_k:
        case accept:
            f_k ← 0
            update task status/result
            if root task done:
                advance to ResultAggregationNode
            else:
                advance to next TaskExecutorNode
            break
        case retry:
            f_k ← f_k + 1
            if f_k ≥ θ:
                escalate to user
                break
            else:
                record failure context in task
                re-execute same task
        case replan:
            spawn TaskAssessorNode(scope: active task)
            spawn TaskAnalyzerNode(mode: local_replan)
            re-execute
        case open_question:
            install mandatory_passthrough
            pause and wait for user continuation
            break
```

## Replan Path

Replan is a **local execution-time recovery** path. It MUST NOT spawn AnalysisEffortNode:

$$\text{replan}(t_k) = \text{TaskAssessor}(\text{scope}=t_k) \rightarrow \text{TaskAnalyzer}(\text{mode}=\text{local\_replan}) \rightarrow \text{TaskExecutor}$$

This differs from the Worker-owned effort-gated decomposition:

$$\text{Worker decomposition} = \text{TaskCreate/Analyzer} \rightarrow \text{AnalysisEffort} \rightarrow [\text{TaskAssessor}, \text{TaskAnalyzer}]^* \rightarrow \text{TaskExecutor}$$

## Threshold Justification

The default threshold $\theta = 5$ was chosen empirically:

| $\theta$ | Behavior | Justification |
|----------|----------|---------------|
| $< 3$ | Too aggressive | Transient failures (network, rate limits) cause premature escalation |
| $= 5$ | Balanced | Allows recovery from transient issues while capping waste |
| $> 7$ | Too lenient | Wastes compute on likely-futile retries |

## Properties

### Liveness Guarantee

The loop terminates in finite time:

$$\exists \, n \in \mathbb{N} : \text{termination after } n \text{ iterations}$$

This is guaranteed because:
1. $\theta$ is finite (bounded)
2. Each $\text{accept}$ breaks the loop
3. Each $\text{retry}$ increments $f_k$ toward $\theta$
4. $\text{replan}$ and $\text{open\_question}$ break the loop

### Reset Semantics

A successful review resets the counter, allowing later tasks to have their own failure budget:

$$d_k = \text{accept} \implies f_k \leftarrow 0$$

### Replan Scope

Replan is local to the current task, not a global re-decomposition:

$$\text{replan\_scope}(t_k) = \{t_k\} \cup \text{children}(t_k)$$

## Complexity

For task $t_k$ with threshold $\theta$:

- **Worst case**: $\theta$ retry iterations + 1 accept/replan
- **Best case**: 1 iteration (immediate accept)
- **Average case**: $O(\bar{f})$ where $\bar{f} < \theta$ is mean failures before success

Total review cost across all tasks:

$$O\left(\sum_{k=1}^{|T|} (f_k + 1)\right) \leq O(|T| \cdot \theta)$$
