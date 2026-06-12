# Formula 10: Information Digestion Model

## Problem Statement

The InformationDigesterNode gathers and digests context for downstream nodes. It is optional and invoked only when direct accumulated context/tool access is insufficient. The digester creates a fresh session and accesses context lazily through enhanced_context_retrieval.

## Digestion Model

### Trigger Condition

Information digestion is triggered when the ResponseNode determines context insufficiency:

$$\text{trigger\_digest}(S_{\text{root}}) = \neg \text{sufficient}(S_{\text{root}}, q)$$

where:
- $S_{\text{root}}$ = root session context
- $q$ = user query
- $\text{sufficient}()$ evaluates whether available context can answer the query

### Input Construction

The digester receives selected input from the suspended parent:

$$I_{\text{digester}} = \text{select\_messages}(S_{\text{parent}}, \text{policy})$$

where:
- $S_{\text{parent}}$ = suspended parent node's session context
- $\text{policy}$ = selection policy (which messages to include)

### Fresh Session

The digester creates a fresh session:

$$S_{\text{digester}} = \text{new\_session}(\text{id}_{\text{digester}})$$

It does not inherit or reuse the parent session:

$$S_{\text{digester}} \cap S_{\text{parent}} = \emptyset \quad \text{(except } I_{\text{digester}}\text{)}$$

## Enhanced Context Retrieval

### Lazy Context Access

The digester accesses root/parent context lazily:

$$\text{retrieve}(q_{\text{search}}) = \text{enhanced\_context\_retrieval}(q_{\text{search}}, S_{\text{selected}})$$

This creates a scoped session-context cache file and runs a limited ReAct-style search.

### Cache Behavior

The cache contains only selected context for that session/tool call:

$$\text{cache}(S_{\text{selected}}) = \{m \in S_{\text{selected}} : \text{relevant}(m, q_{\text{search}})\}$$

### Search Tools

Search/read tools are limited to:
- Grep/search within the cache
- Paginated cache reads

$$\mathcal{T}_{\text{search}} = \{\text{grep}, \text{search}, \text{paginate}\}$$

## Digestion Process

### Algorithm

$$\text{Algorithm: InformationDigestion}(I_{\text{digester}}, q)$$

**Input:** Selected input $I_{\text{digester}}$, user query $q$
**Output:** Digested information $D$

```
S ← new_session()
cache ← create_cache(I_digester)
context ← []

// Lazy retrieval
for relevant_info in search(cache, q):
    context.append(relevant_info)

// Digest
if context empty:
    return fallback(q)
else:
    D ← LLM_digest(context, q)
    return D
```

### Fallback Behavior

When no useful context is found:

$$\text{fallback}(q) = \text{"The user asked } q \text{. No useful extra information was found. Downstream should proceed with the user request and plan carefully before action."}$$

This fallback is propagated as a continuation prompt.

## Output Model

### Digest Output

The digestion produces structured output:

$$D = (\text{content}, \text{sources}, \text{confidence})$$

where:
- $\text{content}$ = digested information
- $\text{sources}$ = source references
- $\text{confidence}$ = relevance confidence score

### Propagation to Parent

The digest is forwarded to the suspended parent:

$$\text{propagate\_to\_parent}(D) = D \in S_{\text{parent}}'$$

The digest lands in the parent node's session_context via selected-output propagation.

### No Re-Storage

The digester does not re-store copied input messages:

$$\text{store}(\text{digester}) = \{D\} \quad \text{(only new output)}$$

## Context Insufficiency Detection

### ResponseNode Check

The ResponseNode first analyzes whether available context is sufficient:

$$\text{sufficient}(S, q) = \begin{cases} \text{true} & \text{if } \text{coverage}(S, q) \geq \tau_{\text{cov}} \\ \text{false} & \text{otherwise} \end{cases}$$

where $\text{coverage}(S, q)$ measures how well the context addresses the query.

### Digestion Path

When context is insufficient:

$$\text{ResponseNode} \xrightarrow{\text{suspend}} \text{DigesterNode} \xrightarrow{\text{resume}} \text{ResponseNode}$$

The response node suspends, the digester completes, and the response node resumes with the digest.

## Complexity

For selected input size $|I|$ and query $q$:

- **Cache creation**: $O(|I|)$
- **Search**: $O(|I| \cdot |q|)$ (relevance scoring)
- **Digestion**: $O(|\text{context}| \cdot d)$ (LLM processing)
- **Total**: $O(|I| \cdot |q| + |\text{context}| \cdot d)$

## Properties

- **Optional**: Only invoked when context is insufficient
- **Fresh session**: Does not inherit parent session
- **Lazy access**: Context accessed on-demand via retrieval
- **No re-storage**: Only new output is stored
- **Fallback aware**: Provides clear guidance when no context found
