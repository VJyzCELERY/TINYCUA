# TinyCUA: Architectural vs Prototype-Defect Token Cost

Each LLM-call's tokens are attributed to either *architectural-inherent* or *prototype-defect* overhead using a strict, codified signal catalog. A session's tokens count as defect if ANY signal fires inside it; otherwise they are architectural.

## Strict signal catalog

1. `multi_decision_reviewer_session` — a ResultReviewer session emits >=2 `task_review_decision` calls.
2. `triple_needs_revision_task` — one `task_id` accumulates >=3 revision-triggering verdicts (needs_revision / rejected / replan); every session touching that task is flagged.
3. `non_zero_shell` — `run_shell` / `run_python` returned `exit_code != 0` or any tool returned `timed_out=True`.
4. `oversize_listing` — `list_files` / `search_files` returned >=500 items.
5. `session_without_terminate` — a session's `completed:` was reached with no prior `tool=terminate` call.

Signal #6 from the experiment plan (consecutive reworks on the same file path) folds into #2 in practice: a task hitting the triple threshold is already flagged. The same-path detail is rendered as a citation in the worked example, not as a separate token-attribution signal.

## Per-experiment split

| Exp | Task | Total tokens | Architectural | Prototype defect | Arch % | Defect % | Sessions (defect/total) |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | Greeting conversation | 2,997 | 1,988 | 1,009 | 66.3% | 33.7% | 1/2 |
| 2 | Frontier-LLM research report | 1,513,185 | 635,068 | 878,117 | 42.0% | 58.0% | 23/42 |
| 3 | Analog clock (single HTML) | 731,277 | 271,979 | 459,298 | 37.2% | 62.8% | 14/38 |
| 4 | Notion-like application (Python + SQLite + web UI) | 16,115,407 | 3,459,245 | 12,656,162 | 21.5% | 78.5% | 102/178 |
| 5 | Neural Networks + Transformer study document | 4,641,831 | 2,148,256 | 2,493,575 | 46.3% | 53.7% | 38/66 |

## Signal counts per experiment

| Exp | multi_decision_reviewer_session | triple_needs_revision_task | non_zero_shell | oversize_listing | session_without_terminate |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 | 1 |
| 2 | 6 | 3 | 0 | 0 | 4 |
| 3 | 2 | 1 | 8 | 0 | 4 |
| 4 | 19 | 5 | 92 | 3 | 9 |
| 5 | 11 | 3 | 7 | 0 | 4 |

## Cross-experiment aggregate

- Total tokens across experiments 1-5: **23,004,697**
- Architectural-inherent tokens: **6,516,536 (28.3%)**
- Prototype-defect tokens: **16,488,161 (71.7%)**

Prototype-defect overhead dominates every non-trivial experiment. On the complex coding task alone (experiment-4), ~78.6% of TinyCUA's 16.1M token budget was consumed by multi-decision reviewing, repeated repair loops on the same defects, oversize file listings, and protocol stalls — not by the architecture's mandatory decomposition or executor/reviewer loop itself.

This split is what makes the 33x latency defensible in the cost-benefit discussion: the *architecture* costs only ~21% of TinyCUA's tokens on experiment-4; the remaining ~79% is acknowledged prototype-runtime defects the team is fixing (engineering work), not architectural evidence.

## Worked example: task `64c789e2` on experiment-4

This single task triggered **13 revision-triggering verdicts** from the reviewer against SQLite initialization code in `/workspace/experiment-4/src/config/init_db.py`. All subsequent executor and reviewer calls touching the same task_id are flagged by signal #2 (`triple_needs_revision_task`).

| seq | decision | status | cited cause |
|---:|---|---|---|
| 784 | needs_revision | in_progress | syntax_error |
| 982 | needs_revision | in_progress | missing_import |
| 1116 | needs_revision | in_progress | database_failed |
| 1239 | needs_revision | in_progress | unclassified |
| 1600 | needs_revision | in_progress | database_failed |
| 1638 | needs_revision | in_progress | database_failed |
| 2328 | needs_revision | in_progress | unclassified |
| 2483 | rejected | in_progress | database_failed |
| 2633 | replan | in_progress | database_failed |
| 2992 | needs_revision | in_progress | database_failed |
| 3180 | needs_revision | in_progress | unclassified |
| 3231 | needs_revision | in_progress | database_failed |
| 3403 | needs_revision | in_progress | unclassified |
| 3779 | approved | completed | unclassified |

Verdict sequence: `needs_revision` repeatedly raised against missing Field import, enum/type handling, and SQLAlchemy `create_engine()` URL construction. The verdict flips to `approved` at the final row without an intervening code fix; the reviewer's own preceding text then calls that approval wrong (`stdout.txt:2167-2201`). This is both a correctness miss and a latency multiplier — exactly the documented prototype defect class.

