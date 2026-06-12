# 3. Methodology

## 3.1 Problem Formulation & Core Insight

Small Language Models (SLMs, 1B–8B parameters) struggle with agentic tasks that require processing large context windows. Attention mechanism cost scales quadratically with context length (Vaswani et al., 2017), and hallucination rate increases with context size in smaller models (Miller, 2023). Scaling laws (Kaplan et al., 2020) confirm that SLMs lack the capacity to learn long-context patterns that larger models handle naturally.

TINYCUA's core insight is that context exposure—not just work—must be decomposed. Rather than feeding the full task context to a single SLM, TINYCUA distributes coverage across specialized processing nodes, each receiving only the context it needs:

$$\min_{\{C(n_i)\}} \max_{n_i \in \mathcal{N}} |C(n_i)| \quad \text{subject to} \quad \bigcup_{n_i \in \mathcal{N}} C(n_i) \supseteq C_{\text{required}}$$

where $\mathcal{N} = \{n_1, \ldots, n_k\}$ is the set of processing nodes and $C(n_i)$ is the context window allocated to node $n_i$. The completeness constraint ensures no information critical to correctness is discarded.

TINYCUA is not a multi-agent system. It operates as a single SDK Agent with a sequential NodeQueue where nine specialist nodes execute in order. The user experiences one agent; internally, context is isolated across nodes.

![Figure 1: System Architecture](fig1-architecture.mmd)

## 3.2 Query Routing

Incoming user queries are classified by the QueryAnalystNode using a two-step LLM decision process: (1) an analysis call where the LLM examines the request, then (2) a verdict call where the LLM invokes a classification tool with one of three route labels: **passthrough** (forward to active node/session), **worker** (complex multi-step tasks), or **uncertain** (ambiguous cases requiring user clarification).

The classification is formalized as:

$$d = \text{LLM}_{\text{verdict}}(\text{LLM}_{\text{analysis}}(q, S_{\text{root}}, \mathcal{C}_{\text{active}}), \mathcal{L})$$

where $\mathcal{L} = \{\text{passthrough}, \text{worker}, \text{uncertain}\}$ is the set of valid route labels.

The QueryAnalystNode is a DecisionNode that does not plan or execute tasks—it only directs traffic. It always occupies the first position in the NodeQueue.

![Figure 2: Query Routing](fig2-query-routing.mmd)

## 3.3 Effort-Controlled Task Decomposition

For queries routed to the WorkerNode, task decomposition is controlled by the AnalysisEffortNode, a ProcessNode that gates how many passes the TaskAssessor→TaskAnalyzer loop runs before execution begins:

$$L(e) = \begin{cases} 0 & \text{if } e = \text{none} \\ 1 & \text{if } e = \text{low} \\ 2 & \text{if } e = \text{medium} \\ 3 & \text{if } e = \text{high} \end{cases}$$

First, the TaskCreateNode performs deterministic root creation ($T_0$). Then the TaskAnalyzerNode decomposes the initial task, and the TaskAssessorNode selects subtasks requiring further refinement. This repeats until pass_count reaches $L(e)$ or no tasks remain:

$$T_{\text{final}} = \text{Decompose}(T_0, e) \quad \text{where} \quad |\text{passes}| \leq L(e)$$

The decomposition terminates because $L(e)$ is finite and each pass either reduces $|T_{\text{unfinished}}|$ or breaks early.

![Figure 3: Decomposition Loop](fig3-decomposition-loop.mmd)

## 3.4 Task Execution with ReAct

Each task is executed by the TaskExecutorNode using the ReAct pattern (Reason → Act → Observe). The executor receives only the active task context and selected outer Agent tools—no session history, no cross-task contamination:

$$C(\text{executor}_k) = \text{task\_context}(t_k) \cup \text{selected\_tools}$$

The execution is bounded by maximum steps $M$:

$$|\text{history}| \leq M \quad \text{and} \quad \rho_k = \text{synthesize}(t_k, \{(r_i, a_i, o_i)\}_{i=1}^{|\text{history}|})$$

Key constraint: TaskExecutorNode cannot select or edit tasks. Task ownership belongs to the loop. If more context is needed, the executor calls `enhanced_context_retrieval` directly—it does not spawn InformationDigesterNode.

![Figure 4: ReAct Execution Loop](fig4-react-loop.mmd)

## 3.5 Review & Error Recovery

After each task execution, the ResultReviewerNode evaluates the result and decides:

| Decision | Meaning | Action |
|----------|---------|--------|
| `accept` | Quality bar met | Update task status, advance to next task or ResultAggregationNode |
| `retry` | Transient failure | Increment failure counter, re-execute same task |
| `replan` | Plan failure | Spawn TaskAssessor + TaskAnalyzer (local, not global), then re-execute |
| `open_question` | Needs user input | Install mandatory_passthrough, await user continuation |

The review loop is constrained by a configurable failure threshold $\theta$ (default: 5):

$$d_k = \text{retry} \implies f_k < \theta \quad \text{where} \quad f_k \leftarrow \begin{cases} 0 & \text{if } d_k = \text{accept} \\ f_k + 1 & \text{if } d_k = \text{retry} \end{cases}$$

Replan is a local execution-time recovery—it does NOT spawn AnalysisEffortNode or run the Worker-owned effort-gated decomposition loop.

![Figure 5: Review Decision Tree](fig5-review-loop.mmd)

## 3.6 Context Propagation & Compaction

Context flows between nodes using a segmented model controlled by PropagationRule. On node termination, the parent receives everything except the output segment, while the next node receives only the output segment as input:

$$S(n_i) = P(n_i) \oplus I(n_i) \oplus O(n_i)$$
$$\text{propagate\_to\_parent} = S(n_i) \setminus O(n_i) = P(n_i) \oplus I(n_i)$$
$$\text{forward\_to\_next} = O(n_i)$$

Transient nodes (QueryAnalystNode, WorkerNode) do not backward-propagate their assembled context—their output becomes durable only through the next node's input. Deduplication via origin_record_id prevents information duplication across propagation boundaries.

Context compaction manages window pressure. Nodes call `session.compact_context()` when $|S| > M_{\text{messages}}$ or $\text{tokens}(S) > M_{\text{tokens}}$ would be exceeded. The CompactionStrategy produces exactly one assistant-role summary message. The chat_history remains immutable as an audit trail, while session_context is compactable.

![Figure 6: Context Propagation](fig6-context-propagation.mmd)

## 3.7 NodeQueue Execution Model

TINYCUA uses a sequential NodeQueue as its execution structure. The active node is always at position 0, and queue position controls execution order. The execution loop processes nodes until the queue is empty:

$$\text{while } |Q| > 0: n \leftarrow \text{current}(Q); \text{on\_complete}(n, Q, \text{execute}(n))$$

Each node owns its queue transitions via $\text{on\_complete()}$. The loop never calls $\text{advance()}$ after $\text{on\_complete()}$; it re-reads $\text{current}(Q)$ on the next iteration.

Queue operations include:
- $\text{advance}(Q)$: Remove current node, propagate output to next
- $\text{spawn\_after}(Q, \mathcal{N}')$: Insert nodes after current
- $\text{suspend\_prepend}(Q, \mathcal{N}')$: Keep current, prepend new nodes
- $\text{clear\_after}(Q)$: Remove all nodes after current
- $\text{ensure\_terminal}(Q, n_{\text{term}})$: Append terminal node if missing

![Figure 7: NodeQueue Operations](fig7-compaction.mmd)

## 3.8 Result Aggregation

After the root task is accepted/done, the ResultAggregationNode traverses the root task tree using guided BFS right-to-left traversal. It inspects each task context/result/artifacts/reviewer decisions, consolidates information, and emits response-ready context for ResponseNode:

$$\text{AggregatedResult} = (\text{id}_{\text{root}}, \mathcal{S}, \mathcal{R}, \mathcal{A}, \Phi, \Psi, \mathcal{M})$$

The aggregation may terminate early if enough response-ready context is found, avoiding exhaustive traversal. Right-to-left ordering prioritizes most-recent work and recent reviewer decisions.

## 3.9 Information Digestion

The InformationDigesterNode is optional and invoked only when direct accumulated context/tool access is insufficient. It creates a fresh session and accesses context lazily through enhanced_context_retrieval:

$$\text{trigger\_digest}(S_{\text{root}}) = \neg \text{sufficient}(S_{\text{root}}, q)$$

When no useful context is found, the digester returns a fallback continuation prompt ensuring downstream nodes are aware that no additional context was found. The digest propagates to the suspended parent via selected-output propagation.

## 3.10 Response Synthesis

The ResponseNode is the terminal/suspendable response node. It first analyzes whether available context is sufficient:

$$\text{sufficient}(S, q) = \begin{cases} \text{true} & \text{if } \text{coverage}(S, q) \geq \tau_{\text{cov}} \\ \text{false} & \text{otherwise} \end{cases}$$

If sufficient, it produces the final answer. If insufficient, it may use allowed tools directly or request InformationDigesterNode for additional context. The response node suspends for digestion and resumes only after the digest output has propagated back.

![Figure 8: Long Query Flow](fig8-long-query-flow.mmd)

## 3.11 System Integration

The complete TINYCUA pipeline integrates all components:

$$\text{TinyCUA}(q) = \text{Response}(\text{Aggregate}(\text{Review}(\text{Execute}(\text{Decompose}(\text{Route}(q))))))$$

The system maintains:
- **Context isolation**: Each node operates with bounded context $C(n_i) \ll C_{\text{required}}$
- **Error recovery**: Review loop with failure threshold prevents infinite retries
- **Context management**: Propagation rules and compaction manage window pressure
- **Audit trail**: Chat history preserves provenance while session context is compactable

This architecture enables SLMs to handle complex agentic tasks by distributing context exposure across specialized nodes while maintaining task completeness through structured propagation and review mechanisms.

![Figure 9: Query Analyst Flow](fig9-query-analyst-flow.mmd)

![Figure 10: Big Picture Architecture](fig10-big-picture-architecture.mmd)
