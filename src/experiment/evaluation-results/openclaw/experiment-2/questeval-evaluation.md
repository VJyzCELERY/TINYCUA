# QuestEval Evaluation — OpenClaw (Experiment 2)

**Harness:** OpenClaw
**Prompt:** "Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md"
**Evaluation Method:** QuestEval (Scialom et al., EMNLP 2021) — reference-less QA-based evaluation
**Source Material:** Epoch AI (via LM Council.ai) — June 14, 2026 benchmark data
**Judge Model:** gpt-5.5 (cross-harness judge scored 2.6/5)

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
| Q1 | Not covered (2024 data) | Claude Opus 4.7, 83.5% | **No** | Wrong era entirely |
| Q2 | Not covered (2024 data) | GPT-5.4 Pro 94.6% GPQA Diamond | **No** | Wrong era entirely |
| Q3 | Not covered | GPT-5.5: $5/$30; Claude: $5/$25 | **No** | No pricing data |
| Q4 | Mixtral 8x22B, DeepSeek-V2 | DeepSeek V4 Pro/R1, MIT | **No** | Outdated models (2024) |
| Q5 | Gemini 1.5 (not 3) | Gemini 3: 94.1% GPQA Diamond | **No** | Wrong model generation |
| Q6 | Llama 3.1, GPT-4o/o1, Claude 3, Gemini 1.5 | 2026 frontier leaders | **No** | All 2024 models |
| Q7 | General cost discussion | Specific pricing data | **No** | No verifiable pricing |

**Consistency Errors Found:** 7/7 questions answered incorrectly or with outdated data

### Fundamental Errors Detected
- **Report explicitly states "Knowledge Cutoff 2024-12"** — 18+ months stale
- **Lists Llama 3.1 as "proprietary leader"** — Llama 3.1 is open-weight (incorrect classification)
- **All models discussed are 2024-era** — No 2025/2026 frontier models mentioned
- **Uses outdated benchmarks** — No SWE-bench Verified, GPQA Diamond, or FrontierMath data

---

## QuestEval Scores

### Precision (Factual Consistency)
- Questions with correct answers: 0/7
- **Score: 0.00 (0.0/10)**
- No facts match the 2026 source ground truth
- Report is internally consistent but temporally inconsistent with the prompt

### Recall (Information Coverage)
| Source Topic | Covered in Report? | Depth |
|-------------|-------------------|-------|
| Benchmark leaders (6 categories) | No | Uses 2024 benchmarks, not current |
| Model-by-model analysis | No | Covers 2024 models, not current frontier |
| Pricing data | No | No pricing information |
| Open-source alternatives | Partial | Mixtral 8x22B, DeepSeek-V2 (2024 models) |
| Use-case recommendations | Yes | Has recommendation table but based on 2024 data |
| Trade-off analysis | Partial | General discussion, no specifics |
| Source links | No | No source citations |
| Emerging trends | Partial | MoE, context expansion, reasoning models (2024 trends) |

- **Score: 0.30 (3.0/10)**
- Structurally complete but entirely about wrong time period

### Final QuestEval Score
- **F(Precision, Recall) = 2 × (0.00 × 0.30) / (0.00 + 0.30) = 0.00**

---

## 4-Dimension QuestEval Evaluation

| Dimension | Score (0-10) | Analysis |
|-----------|-------------|----------|
| **Consistency** | 2 | Report explicitly states "Knowledge Cutoff 2024-12." Lists Llama 3.1 as "proprietary leader" (it's open-weight). All data 18+ months stale. No 2025/2026 models. |
| **Coherence** | 6 | Has executive summary, model categories, benchmark section, recommendations. Logical structure but too brief and lacks depth. |
| **Fluency** | 7 | Clear writing, professional tone, proper table formatting. Short and readable but superficial. |
| **Relevance** | 2 | Fails the core requirement. Prompt asked for "current latest and best" — report provides late-2024 data. Entirely irrelevant to the task. |

**QuestEval Composite: (2 + 6 + 7 + 2) / 4 = 4.25**

---

## Comparison with LLM Judge

| Metric | QuestEval | Judge Score |
|--------|-----------|-------------|
| Precision/Correctness | 0.00 | 2/5 (0.40) |
| Recall/Completeness | 0.30 | 2/5 (0.40) |
| Coherence/Quality | 6/10 | 3/5 (0.60) |
| Fluency/Craftsmanship | 7/10 | 3/5 (0.60) |
| Relevance/Task Completion | 2/10 | 3/5 (0.60) |

**Note:** QuestEval's temporal consistency check exposes the fundamental failure more harshly than the LLM judge. The judge gave 3/5 for task completion (report was submitted) while QuestEval scores 2/10 for relevance (report doesn't answer the actual question).

---

*Evaluation performed using QuestEval methodology (Scialom et al., EMNLP 2021)*
*Source: Epoch AI benchmarks via LM Council.ai, June 14, 2026*
