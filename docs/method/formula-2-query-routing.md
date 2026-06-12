# Formula 2: Query Routing Decision Process

## Problem Statement

Incoming user queries must be classified and routed to the appropriate processing path. The QueryAnalystNode uses a two-step LLM decision process to classify queries into one of three route labels: **passthrough**, **worker**, or **uncertain**.

## Decision Model

### Query Classification

Let $q$ denote the user query. The QueryAnalystNode applies a two-step decision process:

**Step 1: Analysis Call**

The LLM examines the request and produces an analysis output $a$:

$$a = \text{LLM}_{\text{analysis}}(q, S_{\text{root}}, \mathcal{C}_{\text{active}})$$

where:
- $S_{\text{root}}$ is the root session context
- $\mathcal{C}_{\text{active}}$ represents active/queued node contexts

**Step 2: Verdict Call**

A second LLM call invokes the classification tool:

$$d = \text{LLM}_{\text{verdict}}(a, \mathcal{L})$$

where $\mathcal{L} = \{\text{passthrough}, \text{worker}, \text{uncertain}\}$ is the set of valid route labels.

### Route Semantics

The decision $d \in \mathcal{L}$ maps to queue operations:

| Route $d$ | Queue Operation | Description |
|-----------|-----------------|-------------|
| $\text{passthrough}$ | $\text{forward}(q, \text{target})$ | Forward to active node/session |
| $\text{worker}$ | $\text{spawn}(\text{WorkerNode})$ | Complex multi-step tasks |
| $\text{uncertain}$ | $\text{await\_continuation}()$ | Ambiguous cases requiring clarification |

### Transient Context Property

QueryAnalyst is a transient routing node. Its assembled context window $W_{\text{QA}}$ is ephemeral:

$$W_{\text{QA}} = S_{\text{root}} \oplus \bigoplus_{n_j \in \mathcal{N}_{\text{active}}} S(n_j) \oplus q$$

where $\oplus$ denotes concatenation. This context is used only for the current LLM classification call and is not backward-propagated.

### Output Propagation

QueryAnalyst forwards durable output to the next node:

$$\text{output}_{\text{QA}} = (q, d, \text{metadata})$$

This output becomes the next node's $\text{input\_segment}$ and propagates upward only when that next node terminates.

## Two-Step Decision Properties

| Property | Description |
|----------|-------------|
| **Determinism** | Invalid/missing labels retry via NodeRetryPolicy |
| **Separation** | Analysis (understanding) separated from verdict (classification) |
| **Transience** | Assembled context not committed to parent/root |
| **Auditability** | Raw LLM output preserved in DecisionResult.raw_output |

## Decision Confidence

The verdict call may include a confidence score $c \in [0, 1]$:

$$d^* = \arg\max_{d \in \mathcal{L}} P(d | a)$$

When $c < \tau_{\text{min}}$ (minimum confidence threshold), the system may retry or escalate to uncertain route.

## Complexity

- **LLM calls per query**: 2 (analysis + verdict)
- **Context size**: $O(|S_{\text{root}}| + \sum |S_{\text{active}}|)$ transient
- **Decision latency**: $O(1)$ classification with bounded retry
