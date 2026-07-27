#!/usr/bin/env python3
"""QuestEval evaluation for Experiment 2 — reference-less mode.

Runs the actual QuestEval library (T5-based QG/QA from HuggingFace)
against each harness's report.md, producing reproducible numeric scores.

Usage:
    cd src/experiment
    source .questeval-venv/bin/activate
    python questeval_evaluation.py
"""

import json
import sys
from pathlib import Path

# ── QuestEval path (patched for modern deps) ──────────────────────
QE_PATH = Path("/tmp/QuestEval")
if str(QE_PATH) not in sys.path:
    sys.path.insert(0, str(QE_PATH))

# Suppress warnings
import warnings
warnings.filterwarnings("ignore")

# ── Paths ──────────────────────────────────────────────────────────
EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "evaluation-results"
SOURCE_PATH = EVAL_DIR / "questeval_source.txt"
SCORES_DIR = RESULTS_DIR / "questeval-scores"

HARNESSES = ["tinycua", "hermes", "opencode", "openclaw"]
EXPERIMENT_NUM = 2


def load_source() -> str:
    if not SOURCE_PATH.exists():
        print(f"ERROR: Source document not found: {SOURCE_PATH}")
        print("Create questeval_source.txt first (see implementation-plan.md Step 4).")
        sys.exit(1)
    return SOURCE_PATH.read_text()


def load_hypothesis(harness: str) -> str | None:
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
    try:
        from questeval.questeval_metric import QuestEval
    except ImportError:
        print("ERROR: QuestEval not installed.")
        print("Run: pip install -e /tmp/QuestEval")
        print("Or:  pip install transformers sentencepiece datasets bert_score spacy Unidecode")
        sys.exit(1)

    print("Loading QuestEval models (T5 QG + QA)...", flush=True)
    print("  First run downloads ~2GB of models from HuggingFace.", flush=True)
    print("  Subsequent runs use cached models.\n", flush=True)
    # Disable BERTScore (hangs on Apple Silicon) — use F1 + answerability only
    questeval = QuestEval(
        task="text2text",
        language="en",
        no_cuda=True,
        use_cache=True,
        list_scores=('answerability', 'f1'),
    )
    print(f"QuestEval config: {questeval.__hash__()}\n")

    source = load_source()
    print(f"Source document: {len(source)} chars\n")

    all_scores = {}
    for harness in HARNESSES:
        print(f"{'='*60}")
        print(f"Evaluating: {harness}")
        print(f"{'='*60}")

        hypothesis = load_hypothesis(harness)
        if hypothesis is None:
            continue

        print(f"  Hypothesis length: {len(hypothesis)} chars")

        result = questeval.corpus_questeval(
            hypothesis=[hypothesis],
            sources=[source],
        )

        corpus_score = result["corpus_score"]
        ex_scores = result["ex_level_scores"]

        print(f"  QuestEval Score: {corpus_score:.4f}")

        try:
            log = questeval.open_log_from_text(source)
            asked = list(log.get("asked", {}).keys())
            print(f"  Questions generated from source: {len(asked)}")
            for i, q in enumerate(asked[:5], 1):
                print(f"    Q{i}: {q[:100]}")
            if len(asked) > 5:
                print(f"    ... and {len(asked) - 5} more")
        except Exception as e:
            print(f"  (log read skipped: {e})")

        all_scores[harness] = {
            "corpus_score": round(corpus_score, 4),
            "ex_level_scores": [round(s, 4) for s in ex_scores],
            "hypothesis_chars": len(hypothesis),
        }
        print()

    # ── Save scores ────────────────────────────────────────────────
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "experiment": EXPERIMENT_NUM,
        "source": "Epoch AI benchmarks June 2026",
        "questeval_hash": questeval.__hash__(),
        "harnesses": all_scores,
    }
    scores_path = SCORES_DIR / "questeval_scores.json"
    scores_path.write_text(json.dumps(output, indent=2))
    print(f"Scores saved: {scores_path}")

    # ── Print summary ──────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("FINAL RANKINGS")
    print(f"{'='*60}")
    ranked = sorted(all_scores.items(), key=lambda x: x[1]["corpus_score"], reverse=True)
    for rank, (harness, scores) in enumerate(ranked, 1):
        print(f"  {rank}. {harness:12s}  {scores['corpus_score']:.4f}")

    return all_scores


if __name__ == "__main__":
    run_questeval()
