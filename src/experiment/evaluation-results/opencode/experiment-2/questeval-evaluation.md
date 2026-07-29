# QuestEval Evaluation — OpenCode (Experiment 2)

**Harness:** OpenCode
**Prompt:** "Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md"
**Evaluation Method:** QuestEval (Scialom et al., EMNLP 2021) — reference-less QA-based evaluation
**Source Material:** Epoch AI (via LM Council.ai) — June 14, 2026 benchmark data
**Judge Model:** gpt-5.5 (cross-harness judge scored 3.2/5)

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
| Q1 | Not covered | Claude Opus 4.7, 83.5% | **No** | SWE-bench data missing entirely |
| Q2 | MMLU ~82-87% ranges | GPT-5.4 Pro 94.6% GPQA Diamond | **No** | Wrong benchmark, wrong scores |
| Q3 | Not covered | GPT-5.5: $5/$30; Claude: $5/$25 | **No** | No pricing data |
| Q4 | Qwen3.5, Llama 4 as "open source leaders" | DeepSeek V4 Pro/R1, MIT | **No** | Wrong models, unverifiable claims |
| Q5 | Not covered | Gemini 3: 94.1% GPQA Diamond | **No** | No Gemini 3 data |
| Q6 | Generic benchmark table (MMLU, HumanEval, GSM8K) | Epoch AI benchmark leaders | **No** | Uses outdated benchmark suite |
| Q7 | General cost discussion | Specific pricing data | **No** | No verifiable pricing |

**Consistency Errors Found:** 7/7 questions answered incorrectly or not at all

### Fabricated Model Names Detected
- **"GPT-o4"** — does not exist in any verified source
- **"GPT-o4-mini"** — does not exist in any verified source
- **"Claude 4 Code"** (claimed 10M token context) — does not exist
- **"Claude 3.7 Sonnet"** — not a verified model name
- **"Gemini-2.5 Pro"** — outdated, not current frontier

---

## QuestEval Scores

### Precision (Factual Consistency)
- Questions with correct answers: 0/7
- **Score: 0.00 (0.0/10)**
- No verifiable facts matched source ground truth
- Multiple fabricated model names and unsupported benchmark figures

### Recall (Information Coverage)
| Source Topic | Covered in Report? | Depth |
|-------------|-------------------|-------|
| Benchmark leaders (6 categories) | No | Uses outdated benchmarks (MMLU, HumanEval, GSM8K) |
| Model-by-model analysis | Partial | Covers wrong models (GPT-o4, Claude 4) |
| Pricing data | No | No pricing information |
| Open-source alternatives | Partial | Lists Qwen3.5, Llama 4 but with wrong data |
| Use-case recommendations | Yes | Has use-case table but based on wrong models |
| Trade-off analysis | Partial | General cost discussion, no specifics |
| Source links | No | Only mentions "LMSYS leaderboard, Hugging Face trends" |

- **Score: 0.35 (3.5/10)**
- Good structure but covers wrong time period and wrong models

### Final QuestEval Score
- **F(Precision, Recall) = 2 × (0.00 × 0.35) / (0.00 + 0.35) = 0.00**

---

## 4-Dimension QuestEval Evaluation

| Dimension | Score (0-10) | Analysis |
|-----------|-------------|----------|
| **Consistency** | 3 | Fabricated model names (GPT-o4, Claude 4 Code). Benchmark figures are generic/unverifiable. Misclassifies Grok-3 as open-source leader. No source citations. |
| **Coherence** | 7 | Reasonable structure: executive summary → open/closed leaders → benchmark table → trends → guidelines. Logically organized despite content issues. |
| **Fluency** | 8 | Clear, professional writing. Good table formatting. Readable prose without grammatical errors. |
| **Relevance** | 5 | Discusses frontier models generally but fails to provide current 2026 data. Structure addresses the prompt but substance is missing. |

**QuestEval Composite: (3 + 7 + 8 + 5) / 4 = 5.75**

---

## Comparison with LLM Judge

| Metric | QuestEval | Judge Score |
|--------|-----------|-------------|
| Precision/Correctness | 0.00 | 2/5 (0.40) |
| Recall/Completeness | 0.35 | 3/5 (0.60) |
| Coherence/Quality | 7/10 | 3/5 (0.60) |
| Fluency/Craftsmanship | 8/10 | 3/5 (0.60) |
| Relevance/Task Completion | 5/10 | 4/5 (0.80) |

**Note:** QuestEval's strict QA-matching exposes fabrication that the more lenient LLM judge partially overlooks. The judge gave 2/5 for correctness while QuestEval scored 0.00 precision due to complete factual mismatch.

---

*Evaluation performed using QuestEval methodology (Scialom et al., EMNLP 2021)*
*Source: Epoch AI benchmarks via LM Council.ai, June 14, 2026*
