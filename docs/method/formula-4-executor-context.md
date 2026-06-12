# Formula 4: Task Executor ReAct Model

## Problem Statement

Each task must be executed by a TaskExecutorNode using the ReAct pattern (Reason → Act → Observe). The executor receives only the active task context and selected outer Agent tools—no session history, no cross-task contamination.

## ReAct Execution Model

### Execution State

For task $t_k$, the executor maintains a state tuple:

$$s_k = (r_k, a_k, o_k)$$

where:
- $r_k$ = reasoning output (LLM analysis)
- $a_k$ = action taken (tool call)
- $o_k$ = observation (tool result)

### Execution Loop

The ReAct loop for task $t_k$ with maximum steps $M$:

$$\text{Algorithm: ReActExecution}(t_k, M)$$

**Input:** active task $t_k$, max steps $M$
**Output:** execution result $\rho_k$

```
step ← 0
history ← []
while step < M:
    r_k ← LLM_reason(task_context(t_k), history)
    if r_k = "complete":
        break
    a_k ← LLM_act(r_k, available_tools)
    o_k ← execute(a_k)
    history.append((r_k, a_k, o_k))
    step ← step + 1
ρ_k ← LLM_synthesize(task_context(t_k), history)
return ρ_k
```

### Context Composition

Each executor invocation operates with bounded, isolated context:

$$C(\text{executor}_k) = \text{task\_context}(t_k) \cup \text{selected\_tools}$$

where:

$$\text{task\_context}(t_k) = \{\text{name}(t_k), \text{desc}(t_k), \text{criteria}(t_k), \text{status}(t_k), \text{result}(t_k)\}$$

### Tool Scope

The TaskExecutorNode has a restricted tool set:

$$\mathcal{T}_{\text{exec}} = \mathcal{T}_{\text{task}} \cup \mathcal{T}_{\text{retrieval}} \cup \mathcal{T}_{\text{outer}} \cup \mathcal{T}_{\text{HITL}}$$

where:
- $\mathcal{T}_{\text{task}}$ = active task execution tools
- $\mathcal{T}_{\text{retrieval}}$ = enhanced_context_retrieval
- $\mathcal{T}_{\text{outer}}$ = selected outer Agent tools (per tool policy)
- $\mathcal{T}_{\text{HITL}}$ = HITL/mandatory passthrough tools

### Tool Restrictions

The executor cannot perform certain actions:

$$\text{forbidden}(\text{executor}) = \{\text{select\_active\_task}, \text{edit\_task}, \text{mutate\_tree}, \text{spawn\_digester}\}$$

## Isolation Properties

### Property 1: No Session History

The executor does not receive prior conversation history:

$$C(\text{executor}_k) \cap S_{\text{history}} = \emptyset$$

### Property 2: No Cross-Task Contamination

Other tasks' contexts are invisible:

$$\forall \, t_j \neq t_k: C(\text{executor}_k) \cap C(\text{executor}_j) = \emptyset$$

### Property 3: Tool-Bounded

The executor can only act within its restricted tool scope:

$$\text{actions}(\text{executor}_k) \subseteq \mathcal{T}_{\text{exec}}$$

### Property 4: ReAct Bounded

Execution is bounded by $M$, preventing unbounded context growth:

$$|\text{history}| \leq M$$

## Execution Result

The final execution result $\rho_k$ satisfies:

$$\rho_k = \text{synthesize}(t_k, \{(r_i, a_i, o_i)\}_{i=1}^{|\text{history}|})$$

where the synthesis consolidates the reasoning-action-observation history into a task result.

## Complexity

For task $t_k$ with max steps $M$:

- **LLM calls**: $O(M)$ (reasoning + action + synthesis)
- **Context size**: $O(|\text{task\_context}(t_k)| + M \cdot |\text{step\_result}|)$
- **Total across tasks**: $O(\sum_{k=1}^{|T|} M_k)$ where $M_k \leq M$

## Enhanced Context Retrieval

When the executor needs additional information beyond its isolated context:

$$\text{retrieve}(q_{\text{search}}) = \text{enhanced\_context\_retrieval}(q_{\text{search}}, S_{\text{selected}})$$

This creates a scoped session-context cache file and runs a limited ReAct-style search over that cache. The cache contains only selected context for that session/tool call.
