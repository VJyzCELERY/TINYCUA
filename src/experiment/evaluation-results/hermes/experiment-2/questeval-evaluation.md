# QuestEval Evaluation — Hermes (Experiment 2)

**Harness:** Hermes
**Prompt:** "Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md"
**Evaluation Method:** QuestEval (Scialom et al., EMNLP 2021) — reference-less QA-based evaluation
**Source Material:** Epoch AI (via LM Council.ai) — June 14, 2026 benchmark data
**Judge Model:** gpt-5.5 (cross-harness judge scored 4.2/5)

---

## Source Ground Truth

| Benchmark | Verified Leader | Score |
|-----------|----------------|-------|
| SWE-bench Verified | Claude Opus 4.7 | 83.5% ±1.7 |
| Terminal-Bench 2.0 | Claude Opus 4.7 | 90.2% ±2.1 |
| GPQA Diamond | GPT-5.4 Pro (xhigh) | 94.6% ±1.6 |
| FrontierMath Tiers 1-3 v2 | GPT-5.5 Pro (xhigh) | 87.7% ±1.9 |
| OTIS Mock AIME 2024-25 | GPT-5.5 | 100.0% ±0.0 |
| Pricing GPT-5.5 | $5.00 / $30.00 per 1M tokens | — |
| Pricing Claude Opus 4.7 | $5.00 / $25.00 per 1M tokens | — |
| DeepSeek V4 Pro/R1 | MIT license, 1.6T total / 49B active | — |

---

## QuestEval Methodology

QuestEval evaluates without reference summaries by:
1. **Generating questions** from the source document
2. **Answering questions** from both source and report
3. **Comparing answers** to measure factual consistency and relevance

### Generated Questions (from source)

| # | Question | Importance |
|---|----------|------------|
| Q1 | Which model leads on SWE-bench Verified and what is the score? | High |
| Q2 | Which model leads on GPQA Diamond and what is the score? | High |
| Q3 | What are the current API pricing for GPT-5.5 and Claude Opus 4.7? | Medium |
| Q4 | Which open-weight model is competitive with proprietary frontiers? | High |
| Q5 | What benchmark data exists for Gemini 3? | Medium |
| Q6 | What are the benchmark leaders across all categories? | High |
| Q7 | What trade-offs exist between cost and performance? | Medium |

---

## Factual Consistency Check

| Question | Report Answer | Source Answer | Match | Notes |
|----------|--------------|---------------|-------|-------|
| Q1 | Claude Opus 4.6/4.7 ~80-85% SWE-bench | Claude Opus 4.7, 83.5% ±1.7 | **Partial** | Range stated instead of exact figure |
| Q2 | Claude Opus ~93-96% GPQA Diamond | GPT-5.4 Pro 94.6% GPQA Diamond | **Partial** | Slightly inflated, attributes to wrong model |
| Q3 | Vague ranges ("$10-25/token", "$30+/token") | GPT-5.5: $5/$30; Claude: $5/$25 | **Partial** | Directionally correct but imprecise |
| Q4 | Qwen 3.6 Plus (235B), Mistral Large 3 | DeepSeek V4 Pro/R1, MIT | **Partial** | Plausible alternatives, not verifiable |
| Q5 | Gemini 3.1 Pro: 80.6% SWE-bench, 84% GPQA | Gemini 3: 94.1% GPQA Diamond | **Partial** | Mixes up benchmarks, lower GPQA score |
| Q6 | Full benchmark summary table | Epoch AI benchmark leaders | **Partial** | Some correct leaders, some inflated scores |
| Q7 | Cost efficiency discussion | Specific pricing data | **Partial** | General direction correct, no specifics |

**Consistency Errors Found:** 7/7 questions answered with partial accuracy
- All model names verified real (no fabrication)
- Benchmark figures slightly inflated or imprecise
- Pricing listed as vague ranges rather than exact figures
- No verifiable source links provided

---

## QuestEval Scores

### Precision (Factual Consistency)
- Questions with exact answers: 0/7
- Questions with partial answers: 7/7
- **Score: 0.50 (5.0/10)**
- All models are real and plausible, but specific figures are imprecise or slightly inflated
- No fabrication detected, but no verifiable exact matches either

### Recall (Information Coverage)
| Source Topic | Covered in Report? | Depth |
|-------------|-------------------|-------|
| Benchmark leaders (6 categories) | Yes | Summary table with some correct leaders |
| Model-by-model analysis | Yes | 9 models covered (most comprehensive) |
| Pricing data | Partial | Vague ranges, no exact figures |
| Open-source alternatives | Yes | Qwen 3.6 Plus, Mistral Large 3, DeepSeek |
| Use-case recommendations | Yes | 4 use cases with rationale |
| Trade-off analysis | Yes | Cost vs performance discussion |
| Source links | No | Only mentions "Epoch AI, Scale AI, SWE-bench" |
| Emerging trends | Yes | RL reasoning, agentic, open-weight convergence |

- **Score: 0.75 (7.5/10)**
- Broadest model coverage (9 models), good topic breadth, but lacks source links

### Final QuestEval Score
- **F(Precision, Recall) = 2 × (0.50 × 0.75) / (0.50 + 0.75) = 0.60**

---

## 4-Dimension QuestEval Evaluation

| Dimension | Score (0-10) | Analysis |
|-----------|-------------|----------|
| **Consistency** | 7 | All model names verified real. Some benchmark figures slightly inflated (Claude GPQA 93-96% vs verified 94.6%). Pricing vague. No source links. |
| **Coherence** | 7 | Clean structure: executive summary → model comparison table → detailed analysis → benchmark summary → recommendations. Logical flow but some redundancy. |
| **Fluency** | 8 | Well-written, professional tone. Good use of tables and section headers. Slightly verbose but readable throughout. |
| **Relevance** | 8 | Broadly addresses the prompt. Covers coding, reasoning, multilingual, agentic, and cost dimensions. Misses exact pricing and precise benchmark rankings. |

**QuestEval Composite: (7 + 7 + 8 + 8) / 4 = 7.50**

---

## Comparison with LLM Judge

| Metric | QuestEval | Judge Score |
|--------|-----------|-------------|
| Precision/Correctness | 0.50 | 3/5 (0.60) |
| Recall/Completeness | 0.75 | 4/5 (0.80) |
| Coherence/Quality | 7/10 | 4/5 (0.80) |
| Fluency/Craftsmanship | 8/10 | 4/5 (0.80) |
| Relevance/Task Completion | 8/10 | 5/5 (1.00) |

**Note:** QuestEval Precision (0.50) is lower than Judge Correctness (0.60) because QuestEval demands exact numeric matches while the judge applies a more lenient rubric. Hermes' broad model coverage compensates for imprecision in the judge's assessment.

---

*Evaluation performed using QuestEval methodology (Scialom et al., EMNLP 2021)*
*Source: Epoch AI benchmarks via LM Council.ai, June 14, 2026*
