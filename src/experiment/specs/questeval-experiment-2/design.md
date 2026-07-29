# Design: QuestEval Implementation for Experiment 2

**Status**: Draft
**Created**: 2026-07-27
**Depends on**: QuestEval (Scialom et al., EMNLP 2021) — https://github.com/ThomasScialom/QuestEval

---

## Problem

The existing QuestEval evaluation for Experiment 2 is manually authored markdown — no executable code, no T5 QG/QA models, no automated pipeline. The "QA answer matching" and "4-dimension scoring" are subjective human judgments disguised as QuestEval methodology. This design replaces manual evaluation with the actual QuestEval library.

## Goal

Run the real QuestEval library (T5-based QG/QA models from HuggingFace) against each harness's Experiment 2 report.md, producing reproducible numeric scores without LLM-as-judge.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    QuestEval Evaluation Pipeline                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input Sources:                                                 │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │ source.txt           │  │ hypothesis_{harness}.txt          │ │
│  │ (Epoch AI benchmark  │  │ (report.md from each harness)    │ │
│  │  ground truth)       │  │                                  │ │
│  └──────────┬───────────┘  └──────────────┬───────────────────┘ │
│             │                             │                     │
│             ▼                             ▼                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              QuestEval (reference-less mode)             │    │
│  │                                                         │    │
│  │  T5-QG (ThomasNLG/t5-qg_squad1-en)                     │    │
│  │    → Generates questions from source                    │    │
│  │                                                         │    │
│  │  T5-QA (ThomasNLG/t5-qa_squad2neg-en)                  │    │
│  │    → Answers questions from source + hypothesis         │    │
│  │                                                         │    │
│  │  F1 + BERTScore + Answerability                         │    │
│  │    → Compares answers → final score [0-1]               │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Output                                │    │
│  │  • questeval_scores.json  (per-harness scores)          │    │
│  │  • questeval_logs/        (QG/QA details for audit)     │    │
│  │  • questeval_report.md    (summary comparison)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Input Design

### Source Document (`source.txt`)

The source is the **ground truth** that all harnesses were supposed to research. Based on the existing evaluation's verified data, this is the Epoch AI benchmark data:

```
Epoch AI Benchmark Data — June 14, 2026 (via LM Council.ai)

Benchmark Leaders:
- SWE-bench Verified: Claude Opus 4.7, 83.5% ±1.7
- Terminal-Bench 2.0: Claude Opus 4.7, 90.2% ±2.1
- GPQA Diamond: GPT-5.4 Pro (xhigh), 94.6% ±1.6
- FrontierMath Tiers 1-3 v2: GPT-5.5 Pro (xhigh), 87.7% ±1.9
- OTIS Mock AIME 2024-25: GPT-5.5, 100.0% ±0.0
- Humanity's Last Exam: GPT-5.4 Pro, 44.3% ±2.0

Pricing:
- GPT-5.5: $5.00 input / $30.00 output per 1M tokens
- Claude Opus 4.7: $5.00 input / $25.00 output per 1M tokens
- Gemini 3.1 Pro: $2.00 input / $12.00 output per 1M tokens
- DeepSeek V4 Flash: $0.14 input / $0.28 output per 1M tokens

Open-Weight Models:
- DeepSeek V4 Pro/R1: MIT license, 1.6T total parameters, 49B active
- Competitive with closed flagships on key benchmarks (thinking mode)

Model Analysis:
- Claude Opus 4.7: Leader in coding/execution (SWE-bench, Terminal-Bench)
- GPT-5.5: Leader in general reasoning (GPQA, FrontierMath, Mock AIME)
- Gemini 3: Competitive on GPQA Diamond (94.1%), strong cost efficiency
- DeepSeek V4 Pro: Best open-weight option, MIT license
```

### Hypotheses (per harness)

Each harness's `report.md` is the hypothesis:
- `tinycua/experiment-2/workdir/report.md`
- `hermes/experiment-2/workdir/report.md`
- `opencode/experiment-2/workdir/report.md`
- `openclaw/experiment-2/workdir/report.md`

---

## Key Design Decisions

### 1. QuestEval Mode: Reference-less

Experiment 2 is a **research task**, not summarization. There is no gold-standard summary to compare against. We use QuestEval's reference-less mode:

```python
score = questeval.corpus_questeval(
    hypothesis=[report_text],
    sources=[source_text]
)
```

This generates questions from the source, answers them from both source and report, and compares — measuring factual consistency and information coverage without references.

### 2. Task Type: `text2text` (not `summarization`)

Using `summarization` activates the Weighter (question importance scoring), which was trained on CNN/DM summaries. Our task is research report generation, not summarization. The `text2text` task is more appropriate and avoids the broken Weighter (noted in QuestEval README as not working with current code version).

### 3. Source Preprocessing: None

The source is already plain text (benchmark data). No table linearization or special preprocessing needed.

### 4. Model Override: Optional

QuestEval defaults to T5-small/T5-base models from HuggingFace. These are general-purpose QA/QG models. For better results on technical benchmark data, we could fine-tune or use larger models, but the default models provide a baseline.

### 5. Scoring Dimensions

QuestEval produces a single composite score [0-1]. For the 4-dimension analysis (Consistency, Coherence, Fluency, Relevance), we use:

| Dimension | QuestEval Component | How |
|-----------|-------------------|-----|
| **Consistency** | Precision (F1 between source answers and report answers) | Questions generated from report, answered from both |
| **Relevance** | Recall (answerability rate of source questions by report) | Questions generated from source, checked if report can answer |
| **Coherence** | Manual/LLM scoring (QuestEval doesn't measure this) | Separate evaluation needed |
| **Fluency** | Manual/LLM scoring (QuestEval doesn't measure this) | Separate evaluation needed |

QuestEval's F-score (harmonic mean of Precision and Recall) gives the overall factual quality. Coherence and Fluency require separate evaluation methods.

---

## Output Design

### `questeval_scores.json`

```json
{
  "experiment": 2,
  "source": "Epoch AI benchmarks June 2026",
  "questeval_config": {
    "task": "text2text",
    "language": "en",
    "scores": ["answerability", "bertscore", "f1"],
    "no_cuda": true,
    "models": {
      "QG": "ThomasNLG/t5-qg_squad1-en",
      "QA": "ThomasNLG/t5-qa_squad2neg-en"
    }
  },
  "harnesses": {
    "tinycua": {
      "corpus_score": 0.85,
      "ex_level_scores": [0.85],
      "precision": 0.90,
      "recall": 0.82,
      "f1": 0.86
    },
    "hermes": { ... },
    "opencode": { ... },
    "openclaw": { ... }
  }
}
```

### `questeval_report.md`

Markdown summary comparing all harnesses with QuestEval scores, replacing the manual markdown evaluations.

---

## File Layout

```
src/experiment/
├── questeval_evaluation.py          # Main evaluation script
├── questeval_source.txt             # Ground truth source document
├── questeval_config.json            # Configuration (models, scoring params)
├── evaluation-results/
│   └── questeval-scores/            # Output directory
│       ├── questeval_scores.json    # Machine-readable scores
│       ├── questeval_report.md      # Human-readable report
│       └── logs/                    # QuestEval QG/QA logs per harness
│           ├── tinycua/
│           ├── hermes/
│           ├── opencode/
│           └── openclaw/
```

---

## Dependencies

### Option A: Use QuestEval's pinned (old) versions

```
transformers==4.8.1
sentencepiece==0.1.95
datasets==1.7.0
bert_score==0.3.9
spacy==3.0.6
```

Risk: These are very old (2021). May not work with current Python/HuggingFace.

### Option B: Use QuestEval with modern dependencies (Recommended)

```
transformers>=4.30.0
sentencepiece>=0.1.99
datasets>=2.0.0
bert_score>=0.3.13
spacy>=3.5.0
torch>=2.0.0
```

The QuestEval code may need minor patches for API changes in newer `datasets` and `transformers` versions.

### Option C: Reimplement QuestEval core logic

Extract the core QG/QA/compare logic from QuestEval and reimplement with current libraries. More control, but more work.

**Recommendation**: Start with Option B (modern deps), fall back to Option C if QuestEval's code is incompatible.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| QuestEval dependencies too old | Can't install | Use modern deps + patches, or reimplement core logic |
| T5 models too weak for technical content | Low discrimination between harnesses | Use larger models (T5-base/large) or fine-tune on benchmark QA data |
| BERTScore requires large download | Slow first run | Cache after first run, document disk requirements |
| Source document too short | QuestEval generates trivial questions | Expand source with detailed benchmark descriptions |
| CUDA not available | Slow CPU inference | Use `no_cuda=True`, accept slower runtime |
| QuestEval logs directory hardcoded | Path conflicts | Override `log_dir` in QuestEval constructor |

---

## Open Questions

1. Should we expand the source document with more detailed benchmark descriptions to give QuestEval richer material for question generation?
2. Should we use the `do_consistency=True` flag (round-trip consistency check)?
3. How do we handle Coherence and Fluency scoring — leave them out, or supplement with a lightweight heuristic?
4. Should we run multiple QuestEval configurations (different model sizes) and compare?

---

*Design follows existing experiment structure under `src/experiment/specs/`*
