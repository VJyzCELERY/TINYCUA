# Formula 7: Context Compaction

## Problem Statement

As nodes execute and context accumulates, the session context window may exceed configured limits. Context compaction manages window pressure by summarizing older context into a compact representation while preserving the audit trail.

## Compaction Trigger

Context compaction is triggered when the session context exceeds configured limits:

$$\text{compact}(S) \iff |S| > M_{\text{messages}} \lor \text{tokens}(S) > M_{\text{tokens}}$$

where:
- $|S|$ = number of messages in session context
- $M_{\text{messages}}$ = maximum context messages (configurable)
- $\text{tokens}(S)$ = total token count of session context
- $M_{\text{tokens}}$ = maximum context tokens (configurable)

Nodes call $\text{session.compact\_context()}$ when these thresholds would be exceeded.

## Compaction Strategy

### Strategy Contract

The CompactionStrategy produces exactly one assistant-role summary message:

$$\text{compact}: \mathcal{M} \rightarrow \mathcal{D}_{\text{assistant}}$$

where:
- $\mathcal{M}$ = list of message dicts (session context subset)
- $\mathcal{D}_{\text{assistant}}$ = $\{\text{role: "assistant", content: "summary"}\}$

### SimpleCompaction (Default)

The default compaction strategy:

$$\text{SimpleCompaction}(M) = \text{LLM}_{\text{compact}}(M, \text{instruction}_{\text{compact}})$$

where $\text{instruction}_{\text{compact}} = \text{"Summarize the provided session into one compact reusable summary."}$

**Behavior:**
1. Receives parent SDK Agent config snapshot during setup
2. Runs a small compaction Agent over selected session messages
3. No tools available to the compaction agent
4. Returns final response as one assistant-role message

## Compaction Invariants

### Invariant 1: Immutable Audit Trail

$\text{chat\_history}$ is never modified or deleted:

$$\text{compact}(S) \implies \Delta \text{chat\_history} = \emptyset$$

It serves as the ground-truth record of all interactions.

### Invariant 2: Mutable Working Context

$\text{session\_context}$ is the compactable working state:

$$\text{compact}(S) \implies S' = \text{summaries}(S) \oplus S_{\text{recent}}$$

where $\text{summaries}(S)$ are compacted summaries and $S_{\text{recent}}$ are recent uncompacted messages.

### Invariant 3: Node-Triggered

Nodes explicitly call $\text{session.compact\_context()}$ when thresholds are exceeded:

$$\text{triggered\_by}(\text{compaction}) = \text{node} \in \mathcal{N}$$

### Invariant 4: Single Summary

Compaction produces exactly ONE assistant-role message:

$$|\text{output}(\text{compact})| = 1 \land \text{role}(\text{output}) = \text{"assistant"}$$

### Invariant 5: System Message Exclusion

Compaction excludes system-role messages by default:

$$\text{compact}(M) \implies M' = \{m \in M : \text{role}(m) \neq \text{"system"}\}$$

## Compaction Process

### Step 1: Window Selection

The session selects the message window to compact:

$$W = \text{select\_window}(S, M_{\text{messages}}, M_{\text{tokens}})$$

### Step 2: Strategy Application

Apply the compaction strategy:

$$s = \text{strategy.compact}(W)$$

### Step 3: Context Update

Update session context with the summary:

$$S' = S \setminus W \cup \{s\}$$

### Step 4: Audit Preservation

Chat history remains unchanged:

$$\text{chat\_history}' = \text{chat\_history}$$

## Internal Agent Exception

Normal TinyCUA node execution does not create internal SDK Agents. CompactionStrategy is the explicit exception:

$$\text{agents}(\text{TinyCUALoop}) = \{\text{CompactionStrategy}\} \cup \emptyset = \{\text{CompactionStrategy}\}$$

The strategy may use its own internal Agent, direct model call, heuristic summarizer, or any other implementation.

## Compaction Cost

For session context $S$ with $|S|$ messages:

- **Window selection**: $O(|S|)$ to identify messages to compact
- **LLM summarization**: $O(|W| \cdot d)$ where $W$ is the selected window and $d$ is embedding dimension
- **Context update**: $O(|S| - |W| + 1)$ to rebuild session context
- **Total**: $O(|S| \cdot d)$ amortized over compaction cycles

## Compaction Frequency

The compaction frequency depends on:

$$\text{frequency} \propto \frac{\text{node\_activity} \times \text{context\_growth\_rate}}{M_{\text{tokens}}}$$

Higher node activity and context growth rate increase compaction frequency. The system balances between:
- **Too frequent**: Excessive summarization overhead
- **Too infrequent**: Context window overflow and truncation

## Properties

- **Lossy compression**: Information is summarized, not preserved verbatim
- **Audit preservation**: Chat history remains immutable for provenance
- **Node-controlled**: Compaction is explicitly triggered, not automatic
- **Single output**: Exactly one summary message per compaction cycle
- **Strategy-agnostic**: Different strategies can be plugged in
