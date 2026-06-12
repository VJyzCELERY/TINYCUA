# 3.X Processing Nodes

After the Worker DecisionNode routes to the appropriate decomposition path, seven ProcessNodes execute the task lifecycle. This section classifies each node and details the planning, execution, review, context, and synthesis stages.

## 3.X.1 Node Classification Table

Processing nodes are classified by their role in the task lifecycle:

| Type | Node | Role | Context Scope |
|------|------|------|---------------|
| **DecisionNodes** | QueryAnalyst | Route classification | Full session |
| | Worker | Decomposition routing | Full session + task tree |
| **ProcessNodes (Planning)** | TaskCreate | Deterministic root creation | Query only |
| | TaskAnalyzer | Task decomposition | Single task subtree |
| | TaskAssessor | Unfinished task selection | Full task tree |
| | AnalysisEffort | Pass-limit gating | Effort parameter $e$ |
| **ProcessNodes (Execution)** | TaskExecutor | ReAct task execution | $C(\text{executor}_k)$ |
| **ProcessNodes (Review)** | ResultReviewer | Quality gate | Task + execution result |
| **ProcessNodes (Output)** | ResultAggregation | BFS tree traversal | Full task tree |
| | Response | Final synthesis | AggregatedResult + $S_{\text{root}}$ |
| **ProcessNodes (Support)** | InformationDigester | Lazy context retrieval | Fresh session + cache |

Transient nodes (QueryAnalyst, Worker) do not backward-propagate their assembled context — their output becomes durable only through the next node's input. All ProcessNodes propagate normally via the segmented model.

## 3.X.2 Planning Pipeline

For complex queries, Worker initiates task decomposition. The planning pipeline has four stages:

**Stage 1 — Root Creation.** TaskCreateNode performs deterministic root task creation from the user query $q$. No LLM call is involved; the root task $T_0$ is constructed directly:

$$T_0 = \text{TaskCreateNode.create}(q) \quad \text{where} \quad |T_0| = 1$$

**Stage 2 — Decomposition Loop.** TaskAnalyzerNode decomposes tasks in modes controlled by the Worker route:

| Worker Route | TaskAnalyzer Mode | TaskInit Tools | Description |
|--------------|-------------------|----------------|-------------|
| `task_creation` | initial | Yes | Full new decomposition |
| `task_recreation` | initial | Yes | Rebuild from existing tree |
| `task_reanalysis` | initial | No | Refine without reinitialization |
| `local_replan` | local_replan | No | Execution-time local recovery |

**Stage 3 — Assessment Gate.** TaskAssessorNode selects unfinished tasks requiring further decomposition:

$$\text{select}(T) = \{t \in T : \text{status}(t) = \text{unfinished} \land \text{needs decomposition}(t)\}$$

**Stage 4 — Effort Gating.** AnalysisEffortNode controls the number of decomposition passes via $L(e)$:

$$L(e) = \begin{cases} 0 & \text{if } e = \text{none} \\ 1 & \text{if } e = \text{low} \\ 2 & \text{if } e = \text{medium} \\ 3 & \text{if } e = \text{high} \end{cases}$$

The loop runs until $\text{pass count} \geq L(e)$ or $T_{\text{unfinished}} = \emptyset$:

$$T_{\text{final}} = \text{Decompose}(T_0, e) \quad \text{where} \quad |\text{passes}| \leq L(e)$$

Termination is guaranteed because $L(e)$ is finite and each pass either reduces $|T_{\text{unfinished}}|$ or breaks early.

## 3.X.3 Execution & Review Loop

After decomposition, each task enters the execute→review cycle.

**Execution.** TaskExecutorNode executes each task using ReAct with bounded context. The executor receives only the active task context and selected outer Agent tools — no session history, no cross-task contamination:

$$C(\text{executor}_k) = \text{task context}(t_k) \cup \text{selected tools}$$

where $\text{task context}(t_k) = \{\text{name}, \text{desc}, \text{criteria}, \text{status}, \text{result}\}$. Execution is bounded by maximum steps $M$:

$$|\text{history}| \leq M \quad \text{and} \quad \rho_k = \text{synthesize}(t_k, \{(r_i, a_i, o_i)\}_{i=1}^{|\text{history}|})$$

The executor cannot select or edit tasks. Task ownership belongs to the loop. If more context is needed, the executor calls `enhanced_context_retrieval` directly — it does not spawn InformationDigesterNode.

**Review.** ResultReviewerNode evaluates outcomes with four decisions:

| Decision | Meaning | Action |
|----------|---------|--------|
| `accept` | Quality bar met | Update task status, advance |
| `retry` | Transient failure | Increment failure counter, re-execute |
| `replan` | Plan failure | Local TaskAssessor + TaskAnalyzer, then re-execute |
| `open_question` | Needs user input | Install mandatory_passthrough, await continuation |

A failure threshold $\theta$ (default: 5) prevents infinite retries:

$$d_k = \text{retry} \implies f_k < \theta \quad \text{where} \quad f_k \leftarrow \begin{cases} 0 & \text{if } d_k = \text{accept} \\ f_k + 1 & \text{if } d_k = \text{retry} \end{cases}$$

When $f_k \geq \theta$, the system must escalate to accept, replan, or open_question. Replan is a local execution-time recovery — it does NOT spawn AnalysisEffortNode or run the Worker-owned effort-gated decomposition loop.

## 3.X.4 Context Management

Context flows via segmented propagation controlled by PropagationRule. Each node's session context is composed of three segments:

$$S(n_i) = P(n_i) \oplus I(n_i) \oplus O(n_i)$$

where $P(n_i)$ is prior_context (inherited from ancestors), $I(n_i)$ is input_segment (received as NodeInput), and $O(n_i)$ is output_segment (produced during execution).

On node termination, context flows in two directions:

$$\text{propagate to parent}(n_i) = P(n_i) \oplus I(n_i) \qquad \text{forward to next}(n_i) = O(n_i)$$

Transient nodes (QueryAnalyst, Worker) do not backward-propagate — their output becomes durable only when ingested by a non-transient node. Deduplication via `origin_record_id` prevents information duplication across propagation boundaries.

**Compaction** manages window pressure. Nodes call `session.compact_context()` when message count or token count exceeds configured limits:

$$\text{compact}(S) \iff |S| > M_{\text{messages}} \lor \text{tokens}(S) > M_{\text{tokens}}$$

The CompactionStrategy produces exactly one assistant-role summary message. The `chat_history` remains immutable as an audit trail, while `session_context` is compactable:

$$\text{compact}(S) \implies \Delta \text{chat history} = \emptyset \quad \land \quad S' = \text{summaries}(S) \oplus S_{\text{recent}}$$

## 3.X.5 Output Synthesis

After root task completion, the output pipeline aggregates results and synthesizes the final response.

**Aggregation.** ResultAggregationNode traverses the task tree via guided BFS right-to-left. It inspects each task's context, result, artifacts, and reviewer decisions, then consolidates into an AggregatedResult:

$$\text{AggregatedResult} = (\text{id}_{\text{root}}, \mathcal{S}, \mathcal{R}, \mathcal{A}, \Phi, \Psi, \mathcal{M})$$

where $\mathcal{S}$ is task summaries, $\mathcal{R}$ is accepted results, $\mathcal{A}$ is artifacts, $\Phi$ is consolidated context, $\Psi$ is response continuation, and $\mathcal{M}$ is metadata. Right-to-left ordering prioritizes most-recent work. The aggregation may terminate early when sufficient response-ready context is found, avoiding exhaustive traversal.

**Response.** ResponseNode produces the final answer. It first checks context sufficiency:

$$\text{sufficient}(S, q) = \begin{cases} \text{true} & \text{if } \text{coverage}(S, q) \geq \tau_{\text{cov}} \\ \text{false} & \text{otherwise} \end{cases}$$

If sufficient, it synthesizes directly. If insufficient, it may suspend for InformationDigesterNode:

$$\text{suspend for digest}(R) = \text{queue.suspend current and prepend}([\text{DigesterNode}(\text{parent}=R)])$$

The digester creates a fresh session, accesses context lazily via `enhanced_context_retrieval`, and propagates results back via selected-output propagation. ResponseNode resumes only after the digest output has propagated back.
