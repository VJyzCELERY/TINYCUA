# Evaluation Results Snapshot — Provenance

This directory (`src/experiment/evaluation-results/`) is a frozen snapshot of
the cross-harness evaluation run. It records tinycua's behavior **before** the
markdown-synthesis / lazy-retry work (FR-087..FR-093) landed.

## Version Pin

| Item | Value |
|---|---|
| Git tag | `eval-snapshot-pre-markdown-synthesis` |
| Snapshot commit (this tree) | `fe456694` |
| Tinycua source commit that produced these results | `f1b0193f` |
| Predates | markdown-synthesis lazy retry (FR-087..FR-093) |

The tinycua source at `f1b0193f` is the last tinycua-source commit before the
lazy-retry feature was committed. The results in this directory were committed
at `fe456694`, which sits one commit later (the context-window protection +
eval-results replacement commit). Tagging `fe456694` keeps the tag pointed at
the commit whose tree actually contains these result files in their final
form.

## Evaluation Setup

All evaluated harnesses used the same local inference model:

| Setting | Value |
|---|---|
| Model | Qwen3.5 9B (`qwen3.5-9b`) |
| Provider/API | OpenAI-compatible local server via LM Studio |
| Context length | 262,144 tokens |
| GPU offload | 32 layers |
| CPU threads / thread pool | 9 |
| Max concurrent requests | 4 |
| Thinking | Enabled |
| Temperature | 0.6 |

Cross-submission judge: a **hermes-judge container** running
`openai/gpt-5.5` (variant `high`) via the `openai-codex` provider. Submissions
were anonymized during judging:

| Submission | Harness |
|---|---|
| A | opencode |
| B | hermes |
| C | openclaw |
| D | tinycua |

Anonymization reduces direct name bias, but the judge harness is still
hermes — a validity limitation since hermes is also one of the evaluated
systems.

## Contents

- `{harness}/experiment-N/run_logs/` — per-run stdout/stderr, metadata, prompt.
- `{harness}/experiment-N/workdir/` — per-run deliverables.
- `judges_verdict/experiment_N/` — cross-judge verdicts + mapping.json.
- `report.md` — full cross-harness analysis (scores, runtime, token usage,
  per-experiment findings, TinyCUA strengths/weaknesses).

See `report.md` for the full analysis. This file is provenance only.