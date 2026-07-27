# QuestEval Evaluation Results — Experiment 2 (Automated)

**Method**: QuestEval (Scialom et al., EMNLP 2021) — T5-based QG/QA, reference-less
**Models**: ThomasNLG/t5-qg_squad1-en (QG) + ThomasNLG/t5-qa_squad2neg-en (QA)
**Scores**: F1 + Answerability (BERTScore disabled — incompatible with Apple Silicon)
**Date**: 2026-07-27

---

## Scores

| Rank | Harness | QuestEval Score | Hypothesis Length |
|------|---------|----------------|-------------------|
| 1 | **tinycua** | **0.3157** | 19,880 chars |
| 2 | **hermes** | **0.0767** | 15,029 chars |
| 3 | **openclaw** | **0.0317** | 4,542 chars |
| 4 | **opencode** | **0.0167** | 6,356 chars |

## Comparison with Previous Manual "QuestEval"

| Harness | Manual (old) | Automated (real) | Notes |
|---------|-------------|-----------------|-------|
| tinycua | 0.90 F1 | 0.3157 | Manual was overly generous |
| hermes | 0.60 F1 | 0.0767 | Manual used LLM judgment, not T5 |
| opencode | 0.00 F1 | 0.0167 | Both detect fabrication |
| openclaw | 0.00 F1 | 0.0317 | Both detect staleness |

**Key difference**: Manual evaluation used an LLM (likely GPT-5.5) to judge answers. Automated uses T5-small QA model — much stricter, no LLM bias.

## What This Proves

1. **QuestEval works without LLM judge** — T5 QG/QA models produce reproducible scores
2. **Ranking is preserved** — tinycua > hermes > openclaw/opencode matches manual evaluation
3. **Absolute scores are lower** — T5-small is much stricter than LLM-as-judge
4. **Fabrication detection works** — opencode (0.0167) and openclaw (0.0317) score near zero

## Configuration

```json
{
  "task": "text2text",
  "language": "en",
  "scores": ["answerability", "f1"],
  "no_cuda": true,
  "use_cache": true,
  "models": {
    "QG": "ThomasNLG/t5-qg_squad1-en",
    "QA": "ThomasNLG/t5-qa_squad2neg-en"
  }
}
```

## Reproduction

```bash
conda activate questeval  # Python 3.11, transformers==4.44.2
cd src/experiment
python questeval_evaluation.py
```

## Known Limitations

- BERTScore disabled (hangs on Apple Silicon with transformers 4.x)
- T5-small models are weaker than LLMs for technical content
- Source document is simplified (not full Epoch AI data)
- No Coherence/Fluency scoring (QuestEval doesn't measure these)

---

*QuestEval v0.2.4, transformers 4.44.2, torch 2.6.0, Python 3.11*
