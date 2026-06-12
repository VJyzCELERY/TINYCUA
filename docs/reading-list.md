# Thesis Reading List — Supporting Sources

**Core argument:** *"As context grows, smaller language models tend to hallucinate more. To reduce this, we decompose tasks and engineer context — breaking work into focused chunks where each processing stage receives only the context it needs."*

---

### 📐 1. Transformer Foundation & Scaled Dot-Product Attention

| # | Paper | Why it matters |
|---|-------|----------------|
| 1 | **Vaswani et al. (2017)** — *Attention Is All You Need* <br> 🔗 https://arxiv.org/abs/1706.03762 | The original transformer paper. Defines **Scaled Dot-Product Attention** (Section 3.2.1) — the mechanism your argument starts from. |
| 2 | **Bahdanau et al. (2014)** — *Neural Machine Translation by Jointly Learning to Align and Translate* <br> 🔗 https://arxiv.org/abs/1409.0473 | Introduced the original attention mechanism that transformers built on. Good historical foundation. |
| 3 | **Miller (2023)** — *Attention Is Off By One* <br> 🔗 https://www.evanmiller.org/attention-is-off-by-one.html | Explains **why softmax forces attention on irrelevant tokens** — the mechanistic root cause of context noise. Complementary to TINYCUA's input-side solution. |

---

### 📏 2. Scaling Laws — Parameters, Neurons & Capacity

| # | Paper | Why it matters |
|---|-------|----------------|
| 4 | **Kaplan et al. (2020)** — *Scaling Laws for Neural Language Models* <br> 🔗 https://arxiv.org/abs/2001.08361 | Empirically shows **loss scales as a power-law with model size** — fewer parameters → higher loss → less capacity to handle complex/long inputs. |
| 5 | **Hoffmann et al. (2022)** — *Training Compute-Optimal Large Language Models* (Chinchilla) <br> 🔗 https://arxiv.org/abs/2203.15556 | Refines scaling laws; shows that for a given compute budget, smaller models trained on more data can match larger models — important context for SLM architecture. |
| 6 | **Tay et al. (2022)** — *Scaling Laws vs Model Architectures: How Does Inductive Bias Influence Scaling?* <br> 🔗 https://arxiv.org/abs/2207.10551 | Explores how architectural choices affect scaling — relevant when arguing about SLM capacity limits. |

---

### 🤯 3. Hallucination — Especially Context-Triggered

| # | Paper | Why it matters |
|---|-------|----------------|
| 7 | **Liu et al. (2023/2024)** — *Lost in the Middle: How Language Models Use Long Contexts* <br> 🔗 https://arxiv.org/abs/2307.03172 <br> Published: TACL 2024 | **Core paper for your argument.** Shows that as context grows longer, models perform worse at identifying and using relevant information — directly linking **longer context → degraded performance** (which manifests as hallucination). |
| 8 | **Hsieh et al. (2024)** — *RULER: What's the Real Context Size of Your Long-Context Language Models?* <br> 🔗 https://arxiv.org/abs/2404.06654 <br> Published: COLM 2024 | **Benchmark proof that claimed context sizes are misleading.** Models pass simple NIAH tests but fail on realistic multi-hop and aggregation tasks. Only half maintain quality at 32K. Supports TINYCUA's decomposition approach. |
| 9 | **Rawte, Chakraborty et al. (2023)** — *A Survey on Hallucination in Large Language Models* <br> 🔗 https://arxiv.org/abs/2311.05232 | Comprehensive taxonomy of hallucination types and causes. Good for grounding your "context-induced hallucination" category. |
| 10 | **Ji et al. (2023)** — *Survey of Hallucination in Natural Language Generation* <br> 🔗 https://dl.acm.org/doi/10.1145/3571730 | Earlier survey covering NLG hallucination broadly — useful for lit review chapter. |
| 11 | **Manakul et al. (2023)** — *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models* <br> 🔗 https://arxiv.org/abs/2303.08896 | Introduces a method for detecting hallucinations without external knowledge — useful if you need to evaluate your proposed system. |
| 12 | **Bubeck et al. (2023)** — *Sparks of Artificial General Intelligence: Early Experiments with GPT-4* <br> 🔗 https://arxiv.org/abs/2303.12712 | Discusses hallucination modes observed in GPT-4 experiments — relevant empirical grounding. |

---

### 🧠 4. Small Language Models — Parameter Constraints & Performance

| # | Paper | Why it matters |
|---|-------|----------------|
| 13 | **Arora et al. (2024)** — *A Comprehensive Survey of Small Language Models in the Era of Large Language Models* <br> 🔗 https://dl.acm.org/doi/10.1145/3768165 | Comprehensive survey covering SLMs up to 2024. Discusses trade-offs: fewer parameters → lower capacity → higher hallucination rates in complex/long-context tasks. |
| 14 | **Schick & Schütze (2024)** — *Small Language Models (SLMs) Can Still Pack a Punch: A Survey* <br> 🔗 https://arxiv.org/abs/2501.05465 | Survey of 1B–8B parameter models. Shows SLMs are competitive when given well-structured tasks — supports your context engineering approach. |
| 15 | **Touvron et al. (2023)** — *LLaMA: Open and Efficient Foundation Language Models* <br> 🔗 https://arxiv.org/abs/2302.13971 | Meta's LLaMA series demonstrates that smaller (7B) models can perform surprisingly well with quality data — useful as a reference point for SLM capability. |
| 16 | **Jiang et al. (2023)** — *Mistral 7B* <br> 🔗 https://arxiv.org/abs/2310.06825 | Demonstrates that 7B models can outperform larger ones (e.g., LLaMA 13B) with careful architecture — relevant when arguing SLMs + clean context can beat larger models. |

---

### 🔄 5. Retrieval-Augmented Generation (RAG) — Context Retrieval

| # | Paper | Why it matters |
|---|-------|----------------|
| 17 | **Lewis et al. (2020)** — *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* <br> 🔗 https://arxiv.org/abs/2005.11401 <br> Published: NeurIPS 2020 | **Foundational RAG paper.** Establishes retrieve-then-generate paradigm. Solves knowledge access but not context management — all retrieved docs go to one model. TINYCUA extends this with staged context isolation. |
| 18 | **Gao et al. (2024)** — *Retrieval-Augmented Generation for Large Language Models: A Survey* <br> 🔗 https://arxiv.org/abs/2312.10997 | Maps RAG evolution: Naive → Advanced → Modular. Identifies context bloat and untraceable reasoning as key challenges. Modular RAG concept parallels TINYCUA's composable architecture. |

---

### 💭 6. Reasoning — Chain-of-Thought to ReAct

| # | Paper | Why it matters |
|---|-------|----------------|
| 19 | **Wei et al. (2022)** — *Chain-of-Thought Prompting Elicits Reasoning in Large Language Models* <br> 🔗 https://arxiv.org/abs/2201.11903 | Establishes that LLMs **reason through intermediate steps** — your argument proposes that providing clean context upfront is better than relying on the model to internally filter + reason. |
| 20 | **Kojima et al. (2022)** — *Large Language Models are Zero-Shot Reasoners* <br> 🔗 https://arxiv.org/abs/2205.11916 | Shows LLMs can reason with just "Let's think step by step" — baseline for your "reasoning in one session" approach. |
| 21 | **Yao et al. (2022)** — *ReAct: Synergizing Reasoning and Acting in Language Models* <br> 🔗 https://arxiv.org/abs/2210.03629 | Interleaves reasoning traces with tool actions (Thought-Action-Observation loop). ReAct is the operational pattern for TINYCUA's execution stage — but runs in a single session with full context. TINYCUA adds the missing layer: staged processing with context isolation. |
| 22 | **Lampinen et al. (2022)** — *Can Language Models Learn from Explanations in Context?* <br> 🔗 https://arxiv.org/abs/2204.02329 | Explores how explanations in context affect model behavior — relevant to your "clean context vs. reasoning in-session" trade-off. |

---

### 🔪 7. Task Decomposition & Staged Processing

| # | Paper | Why it matters |
|---|-------|----------------|
| 23 | **Wang et al. (2023)** — *Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models* <br> 🔗 https://arxiv.org/abs/2305.04091 | Proposes a "plan → divide → execute" structure for complex tasks. Directly supports your idea of **decomposing tasks** so each sub-problem gets focused context. The bridge from ReAct (single-session) to TINYCUA (staged). |
| 24 | **Ning et al. (2023)** — *Skeleton-of-Thought: Large Language Models Can Do Parallel Decoding* <br> 🔗 https://arxiv.org/abs/2307.15337 | Breaks generation into skeleton (plan) → parallel expansion (sub-tasks). Good structural parallel to your task/staged architecture. |
| 25 | **TDAG (2024)** — *TDAG: A Multi-Agent Framework based on Dynamic Task Decomposition and Agent Generation* <br> 🔗 https://arxiv.org/abs/2402.10178 | **Directly implements your idea:** dynamically decomposes tasks into subtasks and assigns each to a generated sub-agent. Each sub-agent gets only its relevant context. TINYCUA uses fixed staged nodes instead of dynamic generation. |
| 26 | **Li et al. (2024)** — *A Survey on LLM-based Multi-Agent Systems: Workflow, Infrastructure, and Challenges* <br> 🔗 https://link.springer.com/article/10.1007/s44336-024-00009-2 | Comprehensive survey of multi-agent LLM systems — covers task decomposition, orchestration, context isolation. Good for mapping the landscape. |
| 27 | **Amazon Science (2024)** — *How Task Decomposition and Smaller LLMs Can Make AI More Affordable* <br> 🔗 https://www.amazon.science/blog/how-task-decomposition-and-smaller-llms-can-make-ai-more-affordable | Industry perspective: task decomposition → smaller, cheaper models per subtask → better overall accuracy. Directly validates TINYCUA's thesis. |

---

### 🔀 8. Multi-Agent Systems — Historical Lineage

These papers establish the multi-agent lineage that TINYCUA evolves from. Post-simplification, TINYCUA uses staged node processing rather than multiple agents — but the orchestration insights remain relevant.

| # | Paper | Why it matters |
|---|-------|----------------|
| 28 | **Li et al. (2023)** — *CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society* <br> 🔗 https://arxiv.org/abs/2303.17760 | **First multi-agent LLM system.** Proved autonomous cooperation is possible via role-playing + inception prompting. Lacks task decomposition and context isolation — TINYCUA addresses both. |
| 29 | **Hong et al. (2023)** — *MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework* <br> 🔗 https://arxiv.org/abs/2308.00352 | SOP-based multi-agent collaboration with assembly line paradigm. Shows structured workflows outperform chat-based systems. TINYCUA's staged processing inherits this assembly line insight. |
| 30 | **Wu et al. (2023)** — *AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation* <br> 🔗 https://arxiv.org/abs/2308.08155 | Microsoft's framework for multi-agent LLM systems. Demonstrates practical orchestration patterns. TINYCUA adds built-in context isolation on top of this infrastructure concept. |

---

### 🧹 9. Context Engineering — The Synthesis Vocabulary

| # | Paper | Why it matters |
|---|-------|----------------|
| 31 | **Mei et al. (2025)** — *A Survey of Context Engineering for Large Language Models* <br> 🔗 https://arxiv.org/abs/2507.13334 | Introduces **Context Engineering** as a formal discipline — optimizing what goes into the context window. TINYCUA's staged processing is a form of context engineering. |
| 32 | **Cheng et al. (2024)** — *xRAG: Extreme Context Compression for Retrieval-Augmented Generation with One Token* <br> 🔗 https://openreview.net/forum?id=6pTlXqrO0p | Compresses retrieved documents into extremely compact representations — supports the idea that **compacting context before generation reduces hallucination**. |
| 33 | **Xu et al. (2024)** — *Contextual Compression in Retrieval-Augmented Generation: A Survey* <br> 🔗 https://arxiv.org/abs/2409.13385 | Surveys context compression techniques — useful for your "compact context → meaningful pieces" argument. |
| 34 | **Belcak et al. (2025)** — *Small Language Models are the Future of Agentic AI* <br> 🔗 https://arxiv.org/abs/2506.02153 | Position paper: SLMs are sufficient, more suitable, and more economical for agentic AI. Directly supports TINYCUA's architectural philosophy. |

---

### 📋 Summary: How Each Paper Supports Your Argument

```
Your Claim                                              → Supporting Papers
─────────────────────────────────────────────────────────────────────────────────
Transformer uses Scaled Dot-Product Attention            → [1] Vaswani 2017, [2] Bahdanau 2014

Softmax forces attention on all tokens (context noise)   → [3] Miller 2023

Fewer parameters → higher loss → less capacity           → [4] Kaplan 2020, [5] Hoffmann 2022

Longer context → more hallucination                      → [7] Liu "Lost in the Middle", [8] RULER

SLMs are competitive with clean context                  → [13] Arora 2024, [14] Schick 2024

RAG retrieves context but single model sees all          → [17] Lewis 2020, [18] Gao 2024

ReAct interleaves reasoning + tools, but single-session  → [21] Yao 2022 ReAct

Task decomposition → focused chunks per stage            → [23] Wang Plan-and-Solve, [25] TDAG, [27] Amazon Science

MAS validates structured orchestration patterns          → [28] CAMEL, [29] MetaGPT, [30] AutoGen

Context compaction reduces hallucination                 → [31] Mei Context Engineering, [32] xRAG, [33] Contextual Compression

SLMs as future of agentic AI                            → [34] Belcak 2025

Clean context > model reasoning internally               → [19] Wei CoT, [20] Kojima Zero-Shot
```

---

### 🧭 Conceptual Chain

```
Transformer (Vaswani 2017)
  │  Softmax forces attention on all tokens
  ▼
Scaling Laws (Kaplan 2020)
  │  Fewer parameters = less capacity to handle noise
  ▼
Hallucination from Context (Liu 2023, Hsieh 2024)
  │  Longer context → worse performance
  ▼
SLMs (Arora 2024, Schick 2024)
  │  SLMs need clean context to compete
  ▼
RAG (Lewis 2020, Gao 2024)
  │  Retrieve context, but all docs go to one model
  ▼
ReAct (Yao 2022)
  │  Single-agent tool use — full context in one session
  ▼
Task Decomposition (Wang 2023, TDAG 2024)
  │  Break work into chunks, isolate per-task context
  ▼
Context Engineering (Mei 2025, xRAG 2024)
  │  Formalize context optimization as discipline
  ▼
TINYCUA
     Staged node processing + context isolation for SLMs
```

---

> **Tip:** Start with papers marked **bold** — they are the most directly relevant. Use the surveys ([9], [10], [13], [26]) for your literature review chapters to quickly map the landscape.
