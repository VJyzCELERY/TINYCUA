# Formula 11: Response Synthesis

## Problem Statement

The ResponseNode is the terminal/suspendable response node that steers final synthesis from prior node response/continuation input and produces the user-facing answer. It is not a generic PrimaryNode but a specialized synthesis node.

## Synthesis Model

### Input

The ResponseNode receives multiple input sources:

$$\text{input}_{\text{response}} = (\text{AggResult}, S_{\text{root}}, O_{\text{latest}}, D_{\text{optional}})$$

where:
- $\text{AggResult}$ = AggregatedResult from ResultAggregationNode
- $S_{\text{root}}$ = accumulated root/session context
- $O_{\text{latest}}$ = latest propagated node output
- $D_{\text{optional}}$ = optional digested information from InformationDigesterNode

### Output

The ResponseNode produces a final user-facing response:

$$\text{response} = \text{synthesize}(\text{input}_{\text{response}})$$

## Context Sufficiency Check

### Analysis

On every call, the ResponseNode first analyzes whether available context is sufficient:

$$\text{sufficient}(S_{\text{root}}, q) = \begin{cases} \text{true} & \text{if } \text{coverage}(S_{\text{root}}, q) \geq \tau_{\text{cov}} \\ \text{false} & \text{otherwise} \end{cases}$$

### Decision Paths

$$\text{ResponseNode enters:}$$

1. Analyze available context
2. If sufficient: produce final answer
3. If insufficient:
   - Option A: Use allowed tools directly
   - Option B: Request InformationDigesterNode (if enabled)

$$\text{path} = \begin{cases} \text{answer} & \text{if sufficient} \\ \text{tools} & \text{if insufficient} \land \text{tools\_enabled} \\ \text{digest} & \text{if insufficient} \land \text{digest\_enabled} \end{cases}$$

## Suspension Model

### Suspension Trigger

When the ResponseNode determines it needs more information:

$$\text{suspend\_for\_digest}(R) = \text{queue.suspend\_current\_and\_prepend}([\text{DigesterNode}(\text{parent}=R)])$$

### Suspension Process

1. Constructs $\text{NodeInput}$ from selected session_context messages
2. Calls $\text{queue.suspend\_current\_and\_prepend}([\text{DigesterNode}])$
3. Digester uses selected-output propagation targeting its parent
4. Digest lands in suspended ResponseNode's session_context
5. ResponseNode resumes only after digest output has propagated back

### Resume Condition

$$\text{resume}(R) = \text{digest}(D) \in S_{\text{response}}$$

The response node resumes when the digest is in its session context.

## Synthesis Algorithm

### Algorithm

$$\text{Algorithm: ResponseSynthesis}(\text{input}_{\text{response}}, q)$$

**Input:** Multiple input sources, user query $q$
**Output:** Final user-facing response

```
// Check sufficiency
if sufficient(S_root, q):
    // Direct synthesis
    response ← LLM_synthesize(AggResult, S_root, O_latest)
    return response
else:
    // Request digestion
    if digest_enabled:
        suspend_for_digest(R)
        // Resume after digestion
        return LLM_synthesize(AggResult, S_root, O_latest, D)
    elif tools_enabled:
        // Use tools directly
        context ← gather_with_tools(q)
        return LLM_synthesize(AggResult, context)
    else:
        // Fallback
        return "I don't have enough information to answer this question."
```

### Synthesis Function

The synthesis function combines all available context:

$$\text{synthesize}(\text{inputs}) = \text{LLM}_{\text{response}}(I_{\text{system}}, I_{\text{user}}, I_{\text{context}})$$

where:
- $I_{\text{system}}$ = system prompt for response generation
- $I_{\text{user}}$ = user query
- $I_{\text{context}}$ = combined context from all inputs

## LLM Input Construction

The ResponseNode's LLM input is built primarily from:

1. Accumulated root/session_context
2. Latest propagated node output

$$\text{LLM\_input} = \text{build\_messages}(S_{\text{root}}, O_{\text{latest}})$$

The response node may maintain a session for audit/todo/tool execution, but its message policy treats it as a continuation of the current TinyCUA session.

## Tool Scope

| Tool | Description |
|------|-------------|
| Information digestion request | May request InformationDigesterNode for additional context |
| Direct tool access | May use allowed tools directly when context is insufficient |

$$\mathcal{T}_{\text{response}} = \mathcal{T}_{\text{digest}} \cup \mathcal{T}_{\text{direct}}$$

## Termination

As the terminal node:

$$\text{on\_complete}(R, Q, \text{response}) = \text{queue processing ends}$$

The final response string is returned to TinyCUALoop.

## Complexity

For context size $|S|$ and query $q$:

- **Sufficiency check**: $O(|S| \cdot |q|)$ (coverage scoring)
- **Synthesis**: $O(|S| \cdot d)$ (LLM processing)
- **Suspension overhead**: $O(|I_{\text{digester}}|)$ (input selection)
- **Total (no digest)**: $O(|S| \cdot |q| + |S| \cdot d)$
- **Total (with digest)**: $O(|S| \cdot |q| + |S| \cdot d + |D| \cdot d)$

## Properties

- **Terminal**: Always the last node in the queue
- **Suspendable**: Can suspend for information digestion
- **Context-aware**: Checks sufficiency before synthesis
- **Tool-enabled**: Can use tools directly when needed
- **Audit-preserving**: Maintains session for provenance
