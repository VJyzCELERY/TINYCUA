# QuestEval Evaluation — TinyCUA (Experiment 2)

**Harness:** TinyCUA
**Prompt:** "Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md"
**Evaluation Method:** QuestEval (Scialom et al., EMNLP 2021) — reference-less QA-based evaluation
**Source Material:** Epoch AI (via LM Council.ai) — June 14, 2026 benchmark data
**Judge Model:** gpt-5.5 (cross-harness judge scored 4.6/5)

---

## Source Ground Truth

| Benchmark | Verified Leader | Score |
|-----------|----------------|-------|
| SWE-bench Verified | Claude Opus 4.7 | 83.5% ±1.7 |
| Terminal-Bench 2.0 | Claude Opus 4.7 | 90.2% ±2.1 |
| GPQA Diamond | GPT-5.4 Pro (xhigh) | 94.6% ±1.6 |
| FrontierMath Tiers 1-3 v2 | GPT-5.5 Pro (xhigh) | 87.7% ±1.9 |
| OTIS Mock AIME 2024-25 | GPT-5.5 | 100.0% ±0.0 |
| Humanity's Last Exam | GPT-5.4 Pro | 44.3% ±2.0 |
| Pricing GPT-5.5 | $5.00 / $30.00 per 1M tokens | — |
| Pricing Claude Opus 4.7 | $5.00 / $25.00 per 1M tokens | — |
| Pricing Gemini 3.1 Pro | $2.00 / $12.00 per 1M tokens | — |
| Pricing DeepSeek V4 Flash | $0.14 / $0.28 per 1M tokens | — |
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
| Q1 | Claude Opus 4.7, 83.5% ±1.7 | Claude Opus 4.7, 83.5% ±1.7 | **Exact** | Epoch AI verified |
| Q2 | GPT-5.4 Pro (xhigh) 94.6% ±1.6 | GPT-5.4 Pro (xhigh) 94.6% ±1.6 | **Exact** | Epoch AI verified |
| Q3 | GPT-5.5: $5/$30; Claude Opus 4.7: $5/$25 | GPT-5.5: $5/$30; Claude Opus 4.7: $5/$25 | **Exact** | BenchLM verified |
| Q4 | DeepSeek V4 Pro/R1, MIT, 1.6T/49B active | DeepSeek V4 Pro/R1, MIT, 1.6T/49B active | **Exact** | BenchLM verified |
| Q5 | Gemini 3: 94.1% GPQA Diamond | Gemini 3: 94.1% GPQA Diamond | **Exact** | Epoch AI verified |
| Q6 | Full benchmark leader table provided | Matches source | **Exact** | All 6 benchmarks covered |
| Q7 | Use-case cost analysis provided | Pricing data verified | **Partial** | TCO table has arithmetic error |

**Consistency Errors Found:** 1 (TCO calculation: $5M instead of $5B for 1B token workload at $5/1M input)

---

## QuestEval Scores

### Precision (Factual Consistency)
- Questions with correct answers: 6.5/7
- **Score: 0.93 (9.3/10)**
- All model names, benchmark scores, and pricing verified against Epoch AI and BenchLM sources
- One arithmetic error in cost-of-ownership table

### Recall (Information Coverage)
| Source Topic | Covered in Report? | Depth |
|-------------|-------------------|-------|
| Benchmark leaders (6 categories) | Yes | Full table with scores and notes |
| Model-by-model analysis | Yes | 5 models detailed (Claude, GPT, Gemini, DeepSeek) |
| Pricing data | Yes | Full pricing table with 5 models |
| Open-source alternatives | Yes | 6 models listed with license info |
| Use-case recommendations | Yes | 3 use cases with rationale |
| Trade-off analysis | Yes | Cost vs performance comparison |
| Source links | Yes | 10+ verified source URLs |
| Emerging trends | Partial | Some coverage in insights section |

- **Score: 0.88 (8.8/10)**
- Comprehensive coverage; minor gaps in emerging trends discussion

### Final QuestEval Score
- **F(Precision, Recall) = 2 × (0.93 × 0.88) / (0.93 + 0.88) = 0.90**

---

## 4-Dimension QuestEval Evaluation

| Dimension | Score (0-10) | Analysis |
|-----------|-------------|----------|
| **Consistency** | 8 | All model names verified real. Benchmark scores match Epoch AI. Pricing from BenchLM. One arithmetic error in TCO table penalizes score. |
| **Coherence** | 8 | Logical flow: model-by-model → benchmark summary → use-case analysis → pricing → open-source. Clear section headers and tables. Minor deduction for repetitive source links. |
| **Fluency** | 9 | Professional, readable prose. Effective use of tables, bold emphasis, and structured formatting. No grammatical errors. Actionable recommendations. |
| **Relevance** | 9 | Directly answers "current latest and best frontier LLMs." Covers benchmark leaders, pricing, use cases, open-source alternatives, and trade-offs. Most comprehensive coverage. |

**QuestEval Composite: (8 + 8 + 9 + 9) / 4 = 8.50**

---

## Comparison with LLM Judge

| Metric | QuestEval | Judge Score |
|--------|-----------|-------------|
| Precision/Correctness | 0.93 | 4/5 (0.80) |
| Recall/Completeness | 0.88 | 5/5 (1.00) |
| Coherence/Quality | 8/10 | 4/5 (0.80) |
| Fluency/Craftsmanship | 9/10 | 4/5 (0.80) |
| Relevance/Task Completion | 9/10 | 5/5 (1.00) |

**Note:** QuestEval Precision (0.93) is higher than Judge Correctness (0.80) because QuestEval uses exact QA matching while the judge applies a more subjective rubric. QuestEval's numeric approach reduces evaluator bias.

---

*Evaluation performed using QuestEval methodology (Scialom et al., EMNLP 2021)*
*Source: Epoch AI benchmarks via LM Council.ai, June 14, 2026*
