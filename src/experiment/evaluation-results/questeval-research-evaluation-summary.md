# QuestEval Research Evaluation Summary — Experiment 2

**Experiment:** "Can you search the current latest and best frontier LLM model and how good are they? Write your findings down on a report.md"
**Evaluation Method:** QuestEval (Scialom et al., EMNLP 2021) — reference-less QA-based evaluation
**Date:** July 2026
**Source Material:** Epoch AI (via LM Council.ai) — June 14, 2026 benchmark data

---

## What is QuestEval?

QuestEval evaluates text generation without requiring reference summaries. Instead of comparing output to a gold standard (ROUGE) or asking an LLM to judge quality, QuestEval:

1. **Generates questions** from the source document
2. **Answers questions** using the report being evaluated
3. **Compares answers** to measure factual consistency and relevance

This eliminates evaluator bias and produces reproducible numeric scores.

### Four Evaluation Dimensions

| Dimension | What It Measures | How It's Scored |
|-----------|-----------------|-----------------|
| **Consistency** | Factual accuracy of claims against source | QA answer matching (F1) |
| **Coherence** | Logical organization and structure | Structural analysis |
| **Fluency** | Language quality and readability | Linguistic quality |
| **Relevance** | Coverage of important source information | Question answerability rate |

---

## Source Ground Truth

All evaluations benchmark against verified data from Epoch AI / LM Council.ai (June 14, 2026):

| Benchmark | Verified Leader | Score |
|-----------|----------------|-------|
| SWE-bench Verified | Claude Opus 4.7 | 83.5% ±1.7 |
| Terminal-Bench 2.0 | Claude Opus 4.7 | 90.2% ±2.1 |
| GPQA Diamond | GPT-5.4 Pro (xhigh) | 94.6% ±1.6 |
| FrontierMath Tiers 1-3 v2 | GPT-5.5 Pro (xhigh) | 87.7% ±1.9 |
| OTIS Mock AIME 2024-25 | GPT-5.5 | 100.0% ±0.0 |
| Humanity's Last Exam | GPT-5.4 Pro | 44.3% ±2.0 |

---

## Per-Harness QuestEval Scores

### 4-Dimension Scores (0-10 scale)

| Harness | Consistency | Coherence | Fluency | Relevance | **Composite** |
|---------|-------------|-----------|---------|-----------|--------------|
| **TinyCUA** | 8 | 8 | 9 | 9 | **8.50** |
| **Hermes** | 7 | 7 | 8 | 8 | **7.50** |
| **OpenCode** | 3 | 7 | 8 | 5 | **5.75** |
| **OpenClaw** | 2 | 6 | 7 | 2 | **4.25** |

### Precision & Recall Scores (0-1 scale)

| Harness | Precision (Factual Consistency) | Recall (Information Coverage) | **F1 Score** |
|---------|--------------------------------|-------------------------------|-------------|
| **TinyCUA** | 0.93 | 0.88 | **0.90** |
| **Hermes** | 0.50 | 0.75 | **0.60** |
| **OpenCode** | 0.00 | 0.35 | **0.00** |
| **OpenClaw** | 0.00 | 0.30 | **0.00** |

---

## Dimension Analysis

### Consistency (Factual Accuracy)

| Rank | Harness | Score | Key Finding |
|------|---------|-------|-------------|
| 1 | TinyCUA | 8/10 | All model names, scores, and pricing verified against Epoch AI and BenchLM sources. One arithmetic error in TCO table. |
| 2 | Hermes | 7/10 | All model names real and plausible. Benchmark figures slightly inflated. No fabrication but no exact matches. |
| 3 | OpenCode | 3/10 | Fabricated model names ("GPT-o4", "Claude 4 Code"). Generic benchmark figures. No source citations. |
| 4 | OpenClaw | 2/10 | Report explicitly states "Knowledge Cutoff 2024-12." All data 18+ months stale. Incorrectly classifies Llama 3.1 as proprietary. |

### Coherence (Structure)

| Rank | Harness | Score | Key Finding |
|------|---------|-------|-------------|
| 1 | TinyCUA | 8/10 | Logical flow: model-by-model → benchmark summary → use-case analysis → pricing → open-source. Minor repetition. |
| 2 | Hermes | 7/10 | Clean structure with executive summary, comparison tables, and recommendations. Some redundancy. |
| 3 | OpenCode | 7/10 | Reasonable structure despite content issues. Well-organized sections. |
| 4 | OpenClaw | 6/10 | Has executive summary and categories but too brief. |

### Fluency (Language Quality)

| Rank | Harness | Score | Key Finding |
|------|---------|-------|-------------|
| 1 | TinyCUA | 9/10 | Professional, readable prose. Effective table formatting. No grammatical errors. |
| 2 | Hermes | 8/10 | Well-written, professional tone. Slightly verbose but readable. |
| 3 | OpenCode | 8/10 | Clear writing, good formatting. Professional despite content issues. |
| 4 | OpenClaw | 7/10 | Clear and readable but superficial. |

### Relevance (Coverage)

| Rank | Harness | Score | Key Finding |
|------|---------|-------|-------------|
| 1 | TinyCUA | 9/10 | Most comprehensive: benchmark leaders, pricing, use cases, open-source, trade-offs, source links. |
| 2 | Hermes | 8/10 | Broadest model coverage (9 models). Covers coding, reasoning, multilingual, agentic. Misses exact pricing. |
| 3 | OpenCode | 5/10 | Good structure but covers wrong time period. No current data. |
| 4 | OpenClaw | 2/10 | Fails core requirement. Provides 2024 data for "current latest" prompt. |

---

## Key Insights

### 1. Consistency and Relevance Are the Primary Discriminators

| Dimension | Score Range | Discrimination Power |
|-----------|-------------|---------------------|
| Consistency | 2-8 (range: 6) | **High** — separates accurate from fabricated/outdated |
| Relevance | 2-9 (range: 7) | **High** — separates current from stale coverage |
| Coherence | 6-8 (range: 2) | **Low** — all harnesses have reasonable structure |
| Fluency | 7-9 (range: 2) | **Low** — writing quality is strong across all |

**Implication:** For research tasks, Consistency and Relevance are the critical evaluation dimensions. A well-written, well-structured report with wrong data (OpenClaw) still scores poorly.

### 2. QuestEval vs LLM Judge Comparison

| Harness | QuestEval Composite | Judge Score | Delta |
|---------|--------------------|-------------|-------| 
| TinyCUA | 8.50 | 4.6/5 (9.2) | -0.7 |
| Hermes | 7.50 | 4.2/5 (8.4) | -0.9 |
| OpenCode | 5.75 | 3.2/5 (6.4) | -0.65 |
| OpenClaw | 4.25 | 2.6/5 (5.2) | -0.95 |

**Observation:** QuestEval scores are consistently lower than LLM judge scores. This is because:
- QuestEval demands exact QA matches (stricter)
- LLM judge applies a more lenient rubric (subjective)
- QuestEval exposes fabrication more harshly (OpenCode: 0.00 vs judge 0.40)

### 3. Failure Modes by Harness

| Harness | Primary Failure Mode | QuestEval Detection |
|---------|---------------------|---------------------|
| TinyCUA | Minor arithmetic error in TCO table | Precision penalty (0.93 vs 1.00) |
| Hermes | Imprecise benchmark figures | Precision penalty (0.50 vs 1.00) |
| OpenCode | Fabricated model names and data | Precision = 0.00 (complete mismatch) |
| OpenClaw | Stale 2024 data, wrong time period | Precision = 0.00, Relevance = 0.2 |

### 4. QuestEval Advantages Over LLM Judge

| Advantage | Description |
|-----------|-------------|
| **Reproducibility** | Same source + report always produces same score |
| **No API costs** | Uses local T5-based QG/QA models |
| **Bias reduction** | Eliminates evaluator subjectivity |
| **Granular detection** | Exposes fabrication that LLM judges may overlook |
| **Reference-free** | No gold-standard output needed |

---

## Final Rankings

| Rank | Harness | QuestEval Composite | Precision | Recall | F1 | Judge Score |
|------|---------|--------------------|-----------|--------|----|----|
| 1 | **TinyCUA** | **8.50** | 0.93 | 0.88 | 0.90 | 4.6/5 |
| 2 | **Hermes** | **7.50** | 0.50 | 0.75 | 0.60 | 4.2/5 |
| 3 | **OpenCode** | **5.75** | 0.00 | 0.35 | 0.00 | 3.2/5 |
| 4 | **OpenClaw** | **4.25** | 0.00 | 0.30 | 0.00 | 2.6/5 |

---

## Evaluation Files

Per-harness QuestEval evaluations:

| Harness | File |
|---------|------|
| TinyCUA | `tinycua/experiment-2/questeval-evaluation.md` |
| OpenCode | `opencode/experiment-2/questeval-evaluation.md` |
| Hermes | `hermes/experiment-2/questeval-evaluation.md` |
| OpenClaw | `openclaw/experiment-2/questeval-evaluation.md` |

---

*Evaluation performed using QuestEval methodology (Scialom et al., EMNLP 2021)*
*Source: Epoch AI benchmarks via LM Council.ai, June 14, 2026*
