# Implementation Plan: QuestEval for Experiment 2

**Status**: Draft
**Created**: 2026-07-27

---

## Step-by-Step Evaluation Guide

### Step 1: Create Virtual Environment

```bash
cd src/experiment
python3 -m venv .questeval-venv
source .questeval-venv/bin/activate
```

### Step 2: Install PyTorch (CPU or CUDA)

```bash
# CPU only (macOS / no GPU)
pip install torch torchvision

# CUDA (Linux with GPU)
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Step 3: Install QuestEval + Dependencies

```bash
# Clone QuestEval
cd /tmp
git clone https://github.com/ThomasScialom/QuestEval.git
cd QuestEval

# Install in editable mode
pip install -e .

# Install spaCy language model
python -m spacy download en_core_web_sm
```

If QuestEval's pinned deps conflict with modern Python, install individually:

```bash
pip install transformers sentencepiece datasets bert_score spacy Unidecode
python -m spacy download en_core_web_sm
```

### Step 4: Prepare Source Document

Create `src/experiment/questeval_source.txt` with the Epoch AI ground truth data:

```bash
cat > src/experiment/questeval_source.txt << 'SOURCE'
Epoch AI Benchmark Data — June 14, 2026 (via LM Council.ai)

The current frontier LLM landscape as of June 2026 shows the following benchmark leaders across key evaluation categories.

SWE-bench Verified measures real-world software engineering capability by testing models on actual GitHub issues from open-source repositories. The leader is Claude Opus 4.7 with a score of 83.5% ±1.7, demonstrating superior multi-file code understanding and repair capability.

Terminal-Bench 2.0 evaluates command-line and system-level task execution. Claude Opus 4.7 leads with 90.2% ±2.1, showing strong terminal operation and system interaction skills.

GPQA Diamond tests graduate-level science reasoning with PhD-quality questions in biology, chemistry, and physics. Human expert average is approximately 65%. GPT-5.4 Pro (xhigh configuration) leads with 94.6% ±1.6, approaching saturation on this benchmark. Gemini 3 Preview high is competitive at 94.1% ±1.7.

FrontierMath Tiers 1-3 v2 evaluates advanced mathematical reasoning. GPT-5.5 Pro (xhigh) leads with 87.7% ±1.9.

OTIS Mock AIME 2024-25 tests competition-level mathematics. GPT-5.5 achieves a perfect score of 100.0% ±0.0.

Humanity's Last Exam (HLE) presents the most challenging general knowledge and reasoning problems. GPT-5.4 Pro leads with 44.3% ±2.0, indicating significant room for improvement on this frontier.

API Pricing as of June 2026:
- GPT-5.5: $5.00 input / $30.00 output per 1M tokens
- Claude Opus 4.7: $5.00 input / $25.00 output per 1M tokens
- Gemini 3.1 Pro: $2.00 input / $12.00 output per 1M tokens
- DeepSeek V4 Flash: $0.14 input / $0.28 output per 1M tokens

Open-Weight Models:
- DeepSeek V4 Pro/R1: Released under MIT license. Architecture: 1.6T total parameters, 49B active per token. Competitive with closed flagships on key benchmarks when using thinking mode, but with first-token latency measured in seconds rather than milliseconds.

Model Strengths by Use Case:
- Agentic Coding: Claude Opus 4.7 (SWE-bench leader, Terminal-Bench leader)
- General Reasoning: GPT-5.5 (GPQA near-saturation, perfect Mock AIME, FrontierMath leader)
- Cost-Efficient Frontier: Gemini 3.1 Pro (competitive GPQA, lowest frontier pricing)
- Self-Hosted Open-Weight: DeepSeek V4 Pro/R1 (MIT license, competitive benchmarks)
SOURCE
```

### Step 5: Create Evaluation Script

Create `src/experiment/questeval_evaluation.py`:

```python
#!/usr/bin/env python3
"""QuestEval evaluation for Experiment 2 — reference-less mode.

Runs the actual QuestEval library (T5-based QG/QA) against each harness's
report.md, producing reproducible numeric scores.

Usage:
    cd src/experiment
    source .questeval-venv/bin/activate
    python questeval_evaluation.py
"""

import json
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "evaluation-results"
SOURCE_PATH = EVAL_DIR / "questeval_source.txt"
SCORES_DIR = RESULTS_DIR / "questeval-scores"

HARNESSES = ["tinycua", "hermes", "opencode", "openclaw"]
EXPERIMENT_NUM = 2


def load_source() -> str:
    """Load the ground truth source document."""
    if not SOURCE_PATH.exists():
        print(f"ERROR: Source document not found: {SOURCE_PATH}")
        print("Run Step 4 from the implementation guide first.")
        sys.exit(1)
    return SOURCE_PATH.read_text()


def load_hypothesis(harness: str) -> str | None:
    """Load a harness's report.md as the hypothesis."""
    report_path = (
        RESULTS_DIR
        / harness
        / f"experiment-{EXPERIMENT_NUM}"
        / "workdir"
        / "report.md"
    )
    if not report_path.exists():
        print(f"  WARNING: No report.md for {harness}, skipping")
        return None
    return report_path.read_text()


def run_questeval():
    """Main evaluation loop."""
    # Lazy import so script fails gracefully if QuestEval not installed
    try:
        from questeval.questeval_metric import QuestEval
    except ImportError:
        print("ERROR: QuestEval not installed.")
        print("Run: pip install -e /tmp/QuestEval")
        sys.exit(1)

    print("Loading QuestEval models (T5 QG + QA)... this may take a few minutes.")
    questeval = QuestEval(
        task="text2text",       # not summarization (avoids broken Weighter)
        language="en",
        no_cuda=True,           # CPU mode (set False if CUDA available)
        use_cache=True,         # cache QG/QA results for reproducibility
    )
    print(f"QuestEval hash: {questeval.__hash__()}\n")

    # Load source
    source = load_source()
    print(f"Source document: {len(source)} chars\n")

    # Evaluate each harness
    all_scores = {}
    for harness in HARNESSES:
        print(f"{'='*60}")
        print(f"Evaluating: {harness}")
        print(f"{'='*60}")

        hypothesis = load_hypothesis(harness)
        if hypothesis is None:
            continue

        print(f"  Hypothesis length: {len(hypothesis)} chars")

        # Run QuestEval — reference-less mode
        result = questeval.corpus_questeval(
            hypothesis=[hypothesis],
            sources=[source],
        )

        corpus_score = result["corpus_score"]
        ex_scores = result["ex_level_scores"]

        print(f"  QuestEval Score: {corpus_score:.4f}")
        print(f"  Per-example scores: {ex_scores}")

        # Get detailed logs
        try:
            log = questeval.open_log_from_text(source)
            asked_questions = list(log.get("asked", {}).keys())
            print(f"  Questions generated: {len(asked_questions)}")
            for i, q in enumerate(asked_questions[:5], 1):
                print(f"    Q{i}: {q[:80]}...")
        except Exception as e:
            print(f"  (Could not read logs: {e})")

        all_scores[harness] = {
            "corpus_score": corpus_score,
            "ex_level_scores": ex_scores,
            "hypothesis_length": len(hypothesis),
        }
        print()

    # Save scores
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "experiment": EXPERIMENT_NUM,
        "source": "Epoch AI benchmarks June 2026",
        "questeval_hash": questeval.__hash__(),
        "harnesses": all_scores,
    }
    scores_path = SCORES_DIR / "questeval_scores.json"
    scores_path.write_text(json.dumps(output, indent=2))
    print(f"\nScores saved to: {scores_path}")

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    ranked = sorted(all_scores.items(), key=lambda x: x[1]["corpus_score"], reverse=True)
    for rank, (harness, scores) in enumerate(ranked, 1):
        print(f"  {rank}. {harness:12s} — {scores['corpus_score']:.4f}")

    return all_scores


if __name__ == "__main__":
    run_questeval()
```

### Step 6: Run the Evaluation

```bash
cd src/experiment
source .questeval-venv/bin/activate
python questeval_evaluation.py
```

Expected output:
```
Loading QuestEval models (T5 QG + QA)... this may take a few minutes.
QuestEval hash: QuestEval_version=0.2.4_task=text2text_lang=en_...

Source document: 2847 chars

============================================================
Evaluating: tinycua
============================================================
  Hypothesis length: 12453 chars
  QuestEval Score: 0.XXXX
  Questions generated: N
    Q1: ...
    Q2: ...

============================================================
Evaluating: hermes
============================================================
...

============================================================
SUMMARY
============================================================
  1. tinycua      — 0.XXXX
  2. hermes       — 0.XXXX
  3. opencode     — 0.XXXX
  4. openclaw     — 0.XXXX
```

### Step 7: Generate Report

After scores are computed, generate the comparison report:

```bash
python -c "
import json
from pathlib import Path

scores = json.loads(Path('evaluation-results/questeval-scores/questeval_scores.json').read_text())

print('# QuestEval Evaluation — Experiment 2 (Automated)')
print()
print('**Method**: QuestEval (Scialom et al., EMNLP 2021) — T5-based QG/QA')
print('**Mode**: Reference-less (source + hypothesis only)')
print(f'**Models**: {scores[\"questeval_hash\"]}')
print()
print('## Scores')
print()
print('| Harness | QuestEval Score |')
print('|---------|----------------|')
ranked = sorted(scores['harnesses'].items(), key=lambda x: x[1]['corpus_score'], reverse=True)
for harness, data in ranked:
    print(f'| {harness} | {data[\"corpus_score\"]:.4f} |')
" > evaluation-results/questeval-scores/questeval_report.md
```

### Step 8: Compare with Previous Manual Evaluation

Compare automated QuestEval scores against the previous manual markdown scores to quantify the difference:

| Harness | Manual QuestEval | Automated QuestEval | Delta |
|---------|-----------------|-------------------|-------|
| tinycua | 0.90 F1 | TBD | — |
| hermes | 0.60 F1 | TBD | — |
| opencode | 0.00 F1 | TBD | — |
| openclaw | 0.00 F1 | TBD | — |

---

## Troubleshooting

### "No module named questeval"
QuestEval not installed. Run `pip install -e /tmp/QuestEval` from the venv.

### "transformers version incompatible"
QuestEval pins `transformers==4.8.1`. With modern Python, use `pip install transformers>=4.30.0` and patch if needed.

### "CUDA out of memory"
Use `no_cuda=True` in QuestEval constructor. T5-small runs fine on CPU.

### "BERTScore download slow"
First run downloads BERT model. Subsequent runs use cache. Set `HF_HOME` to control cache location.

### QuestEval code errors with new datasets/transformers
The QuestEval code uses deprecated APIs (`load_metric` → `evaluate.load`). Patch:
```python
# In questeval_metric.py, replace:
from datasets import load_metric
# With:
import evaluate
load_metric = evaluate.load
```

---

*Follows existing experiment structure under `src/experiment/`*
