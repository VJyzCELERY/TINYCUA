# TinyCUA Trace Evidence (Parser-Derived)

Every number below is regenerated from raw stdout by `uv run python src/experiment/trace_parser.py --all-glob src/experiment/evaluation-results/tinycua` followed by `uv run python src/experiment/trace_report.py`. No manual values are typed. Every cited event links to `stdout.txt:<seq>` for audit.
TinyCUA stdout carries no per-event wall-clock timestamp; event `seq` (the source line number) is the timeline index. Run duration comes from `metadata.json`.

## Per-experiment aggregate

| Exp | Task | Duration (s) | LLM calls | In tokens | Out tokens | Total tokens | Verdicts (A/N/R/P) |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | Greeting conversation | 5.4 | 2 | 2,731 | 266 | 2,997 | 0/0/0/0 |
| 2 | Frontier-LLM research report | 1135.0 | 183 | 1,453,014 | 60,171 | 1,513,185 | 8/11/1/0 |
| 3 | Analog clock (single HTML) | 584.7 | 123 | 695,302 | 35,975 | 731,277 | 9/5/0/0 |
| 4 | Notion-like application (Python + SQLite + web UI) | 8394.9 | 1331 | 15,694,617 | 420,790 | 16,115,407 | 41/54/3/1 |
| 5 | Neural Networks + Transformer study document | 3004.3 | 394 | 4,494,222 | 147,609 | 4,641,831 | 15/21/0/0 |

## Per-node token cost

Executor + Reviewer dominate every non-trivial run. Information Digester stays at a single call across every experiment — already a log-derived cost statement for the Digester ablation discussion.

| Exp | QueryAnalyst | InformationDigester | Worker | TaskCreate | TaskAnalyzer | TaskAssessor | TaskExecutor | ResultReviewer | ResultAggregation | Response |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 2 | 1 | 1 | 1 | 1 | 8 | 4 | 59 | 106 | 1 | 1 |
| 3 | 1 | 1 | 1 | 1 | 4 | 2 | 38 | 73 | 1 | 1 |
| 4 | 1 | 1 | 1 | 1 | 32 | 16 | 626 | 651 | 1 | 1 |
| 5 | 1 | 1 | 1 | 1 | 7 | 6 | 157 | 218 | 1 | 1 |

(Cells = LLM call count per node.)

## Top rework tasks per experiment

Tasks with >=3 revision-triggering verdicts (needs_revision / rejected / replan).

### Experiment 1 (Greeting conversation)

No task crossed the >=3 rework threshold.

### Experiment 2 (Frontier-LLM research report)

| Task ID | Rework count | Short id (for logs) |
|---|---:|---|
| `5278c6d15f244bd7b3cac8282f004c57` | 4 | `5278c6d1` |
| `d3ba37372c814a87b583d953d8a23cd3` | 4 | `d3ba3737` |
| `d18d0cba88274ecabc5c1ad0bd62d824` | 3 | `d18d0cba` |

### Experiment 3 (Analog clock (single HTML))

| Task ID | Rework count | Short id (for logs) |
|---|---:|---|
| `26571de541e9486db44b8b14652e1260` | 3 | `26571de5` |

### Experiment 4 (Notion-like application (Python + SQLite + web UI))

| Task ID | Rework count | Short id (for logs) |
|---|---:|---|
| `64c789e203a34b4caa12d711a94eea56` | 13 | `64c789e2` |
| `f148f9119919470f9e3b43b7e5496c05` | 11 | `f148f911` |
| `a53ab7e3faff4f4caa5361903730c31d` | 9 | `a53ab7e3` |
| `a764dd4282964305b38f0e85f7a68aba` | 5 | `a764dd42` |
| `2a5c1f0acd194af38807b352010068d0` | 3 | `2a5c1f0a` |

### Experiment 5 (Neural Networks + Transformer study document)

| Task ID | Rework count | Short id (for logs) |
|---|---:|---|
| `0c0dab3900b945aa9dffd3e885faece2` | 5 | `0c0dab39` |
| `b3b2b292bc434977b6331dde7408b31d` | 5 | `b3b2b292` |
| `604d1f197b174173b596285334e2dad4` | 4 | `604d1f19` |

## Worked example: task `64c789e2` — 13 rework cycles

Source: `src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stdout.txt`

| seq | event | decision | status | cited cause (anchored match) |
|---:|---|---|---|---|
| 784 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | syntax_error |
| 982 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | missing_import |
| 1116 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | database_failed |
| 1239 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | unclassified |
| 1600 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | database_failed |
| 1638 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | database_failed |
| 2328 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | unclassified |
| 2483 | tool_result ResultReviewer task_review_decision | rejected | in_progress | database_failed |
| 2633 | tool_result ResultReviewer task_review_decision | replan | in_progress | database_failed |
| 2992 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | database_failed |
| 3180 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | unclassified |
| 3231 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | database_failed |
| 3403 | tool_result ResultReviewer task_review_decision | needs_revision | in_progress | unclassified |
| 3779 | tool_result ResultReviewer task_review_decision | approved | completed | unclassified |

Reviewer-cited causes use the anchored-pattern catalog from `trace_parser.py` (`CAUSE_PATTERNS`). Non-matching preceding text is preserved verbatim in `run_summary.json` under `reviewer_causes` for manual reclassification.

