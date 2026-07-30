# Historical TinyCUA and Hermes Comparison

## Scope and reading guide

This report compares the checked-in historical runs under
`src/experiment/evaluation-results/` with the new controlled-fixture runs under
`src/experiment/template-results/`. It covers only the full `tinycua` and
`hermes` configurations. TinyCUA ablations are outside this report.

- **[D] Direct evidence** means an observation or calculation from checked-in
  prompts, logs, artifacts, metadata, verdicts, or deterministic results. Every
  direct claim cites an exact repo-relative path and line or line range.
- **[I] Inference** means an interpretation, especially a causal claim. It is
  grounded in nearby direct evidence but is not directly established by this
  single-trial comparison.

Related material:

- [Report index](README.md)
- [Fixture versus prototype attribution](fixture-vs-prototype-attribution.md)
- [Experiment README](../../README.md)
- [TinyCUA ablation report](tinycua-ablation.md)
- [New-harness comparison](new-harness-comparison.md)

## Executive finding

**[D]** The historical and controlled runs are related task families, not exact
reruns. The old runs received short, open-ended prompts; the new runs received a
short prompt plus fixture-owned acceptance criteria. For example, old
Experiment 2 was one sentence, while the new fixture mandates an exact title,
five ordered chapters, a specific table, three model families, three URLs, six
evaluation dimensions, and five benchmark caveats
(`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/prompt.txt:1`;
`src/experiment/experiment-fixtures/experiments-list/experiment-2/manifest.yaml:1-7`;
`src/experiment/experiment-fixtures/experiments-list/experiment-2/workdir/TASK.md:10-31`).

**[I]** The user's hypothesis, "high-level planning causes less detail," is
**supported as an association, but causation is not established**. In the
two clearest documentation cases, new TinyCUA used shallower, requirement-shaped
task trees and produced much shorter artifacts. However, prompt scope,
acceptance criteria, TinyCUA implementation, request count, search outcomes,
evaluation method, and stochastic generation all changed at the same time.

**[D]** The detail ordering reverses in Experiments 2 and 5. Historical TinyCUA
was longer than historical Hermes (367 vs 267 lines in Experiment 2; 4,977 vs
579 in Experiment 5), while new Hermes is longer than new TinyCUA (174 vs 97;
1,236 vs 667). Length is only a detail proxy: the old qualitative judge
penalized TinyCUA Experiment 5 for duplication and errors, and the new
deterministic evaluator does not assess prose truth or code-example correctness
(`src/experiment/evaluation-results/judges_verdict/experiment_5/verdict.md:36-51`;
`src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:124-169`).

**[D]** Correctness also reverses between TinyCUA and Hermes in Experiment 3.
The old judge found Hermes' clock stopped by a missing `.center-dot`, while old
TinyCUA at least rendered but rotated counterclockwise. In the new run, Hermes
passes every browser-observed clock gate and TinyCUA fails the hour-hand and all
three movement gates
(`src/experiment/evaluation-results/judges_verdict/experiment_3/verdict.md:15-24,37-53`;
`src/experiment/template-results/experiment-3/hermes/result.json:14-17,48-80`;
`src/experiment/template-results/experiment-3/tinycua/result.json:48-74,84-98`).

**[D]** New TinyCUA records 1.8x to 9.4x lower durations than old TinyCUA on
Experiments 2-5, yet it remains the slowest of the four full harnesses in every
non-trivial new fixture. The old/new difference is substantial but confounded;
it does not make TinyCUA fast within the new cohort.

## Comparability and confounders

**[D]** Both snapshots name the evaluated model `qwen3.5-9b`. The historical
report records explicit server settings including temperature 0.6; the new
campaign records the model and provider but leaves temperature, top-p, and seed
as `null`
(`src/experiment/evaluation-results/report.md:14-40`;
`src/experiment/template-results/run_metadata.json:731-758`).

**[D]** The historical runs occurred on June 23-24, 2026, while the new full
runs occurred on July 29, 2026. The new campaign pins harness versions,
including Hermes 0.16.0 and TinyCUA commit `89d2402...`, but the historical
snapshot does not provide equivalent harness-version pins
(`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/metadata.json:4-8`;
`src/experiment/template-results/run_metadata.json:731-735`).

**[D]** The new campaign is one trial per pair with no retries and sequential
execution. Its invocation history also contains failed and interrupted campaign
invocations before the final set of pair results
(`src/experiment/template-results/run_metadata.json:223-338,759-764`).

**[I]** Therefore, old-to-new differences cannot be assigned to planning alone.
The strongest valid design is a within-snapshot comparison of observed plan
shape, execution behavior, and artifact shape, followed by a ranked explanatory
assessment rather than a single-cause conclusion.

## Prompt mapping

| Experiment | Historical prompt | Controlled prompt and acceptance expansion | Material scope change |
|---:|---|---|---|
| 1 | **[D]** `Hello there` (`src/experiment/evaluation-results/tinycua/experiment-1/run_logs/prompt.txt:1`). | **[D]** Requires the exact response `Hello Reply` (`src/experiment/experiment-fixtures/experiments-list/experiment-1/manifest.yaml:1-3`). | Exact-match task replaces open conversation. |
| 2 | **[D]** Search the current latest/best frontier LLMs and write `report.md` (`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/prompt.txt:1`). | **[D]** Keeps the research topic but points to `TASK.md`, which fixes title, chapter order, table schema, coverage dimensions, citations, and benchmark caveats (`src/experiment/experiment-fixtures/experiments-list/experiment-2/manifest.yaml:1-7`; `src/experiment/experiment-fixtures/experiments-list/experiment-2/workdir/TASK.md:10-31`). | The new task is much more specific and format-bound. |
| 3 | **[D]** Build a simple animated analog clock in one HTML file (`src/experiment/evaluation-results/tinycua/experiment-3/run_logs/prompt.txt:1`). | **[D]** Fixes the filename, Canvas/SVG surface, current-time derivation, scheduler, clockwise direction, positive angles, and no external dependencies (`src/experiment/experiment-fixtures/experiments-list/experiment-3/manifest.yaml:1-5`; `src/experiment/experiment-fixtures/experiments-list/experiment-3/workdir/TASK.md:5-19`). | The new prompt directly targets the historical direction/runtime failures. |
| 4 | **[D]** Build a Notion-like Python/web/SQLite app; old Hermes alone additionally received `Do not ask question just implement` (`src/experiment/evaluation-results/tinycua/experiment-4/run_logs/prompt.txt:1`; `src/experiment/evaluation-results/hermes/experiment-4/run_logs/prompt.txt:1`). | **[D]** Defines one narrow block CRUD workflow, restart persistence, accessible controls, a portable `start.sh`, and explicitly forbids auth/accounts/sharing (`src/experiment/experiment-fixtures/experiments-list/experiment-4/workdir/TASK.md:5-37`). | The new task removes broad product features and adds executable acceptance behavior. |
| 5 | **[D]** Research neural networks and transformers and write comprehensive Markdown study docs (`src/experiment/evaluation-results/tinycua/experiment-5/run_logs/prompt.txt:1`). | **[D]** Fixes the filename and explicitly requires backpropagation, gradient descent, self-attention, positional encoding, encoders, decoders, one fenced example, and a practical plan (`src/experiment/experiment-fixtures/experiments-list/experiment-5/manifest.yaml:1-6`; `src/experiment/experiment-fixtures/experiments-list/experiment-5/workdir/TASK.md:8-13`). | "Comprehensive" becomes a finite checklist rather than an open-ended breadth request. |

**[I]** Prompt specificity is a major confounder for the planning hypothesis.
The new Experiment 5 plan almost exactly mirrors the seven requested output
components, so a shorter artifact can be explained by satisfying a closed list,
not only by abstract planning.

## Results: historical qualitative judge

**[D]** The historical judge was a GPT-5.5 `high` semantic judge running through
the Hermes judge container. Submissions were anonymized as Hermes `B` and
TinyCUA `D`
(`src/experiment/evaluation-results/report.md:42-53`;
`src/experiment/evaluation-results/judges_verdict/experiment_1/mapping.json:3-13`).

| Experiment | TinyCUA | Hermes | Qualitative outcome |
|---:|---:|---:|---|
| 1 | 4.8/5 | 4.6/5 | **[D]** Both answer appropriately; Hermes loses polish for initialization noise (`src/experiment/evaluation-results/judges_verdict/experiment_1/verdict.md:14-23,36-51`). |
| 2 | 4.6/5 | 4.2/5 | **[D]** TinyCUA is judged more complete, sourced, current, and useful, despite a serious cost arithmetic error; Hermes is detailed but less verifiable (`src/experiment/evaluation-results/judges_verdict/experiment_2/verdict.md:16-25,42-58`). |
| 3 | 3.2/5 | 1.8/5 | **[D]** TinyCUA renders but reverses hand direction; Hermes throws before animation (`src/experiment/evaluation-results/judges_verdict/experiment_3/verdict.md:15-24,37-53`). |
| 4 | 1.8/5 | 1.6/5 | **[D]** Both are nonfunctional; TinyCUA has somewhat more coherent components but poor integration, while Hermes is duplicated and internally inconsistent (`src/experiment/evaluation-results/judges_verdict/experiment_4/verdict.md:14-23,36-51`). |
| 5 | 3.2/5 | 4.4/5 | **[D]** TinyCUA is much broader but duplicated, malformed, and error-prone; Hermes is cleaner and more coherent (`src/experiment/evaluation-results/judges_verdict/experiment_5/verdict.md:14-23,36-51`). |

## Results: new deterministic evaluators

**[D]** These values are fixture-specific check totals and pass/fail outcomes,
not semantic ratings. They must not be numerically compared with the historical
five-point scores, or with totals from another fixture.

| Experiment | TinyCUA deterministic result | Hermes deterministic result | Decisive evidence |
|---:|---|---|---|
| 1 | Pass, 1 check | Pass, 1 check | **[D]** Both emit the exact required response (`src/experiment/template-results/experiment-1/tinycua/result.json:14-32`; `src/experiment/template-results/experiment-1/hermes/result.json:14-32`). |
| 2 | Pass, 19 checks | Fail, 16 checks | **[D]** TinyCUA has three URLs and names bundled reference model `Claude Fable 5`; Hermes lacks both three URLs and any bundled reference model, with model relevance a critical gate (`src/experiment/template-results/experiment-2/tinycua/result.json:62-74,139-186,237-250`; `src/experiment/template-results/experiment-2/hermes/result.json:62-74,139-145,245-257`). |
| 3 | Fail, 5 checks | Pass, 9 checks | **[D]** TinyCUA fails hour position and all movement checks; Hermes passes all frozen-time browser checks (`src/experiment/template-results/experiment-3/tinycua/result.json:48-74,84-98`; `src/experiment/template-results/experiment-3/hermes/result.json:48-97`). |
| 4 | Fail, 1 check | Fail, 1 check | **[D]** Both provide `start.sh`, but each exits with code 1 in the evaluator's copied workspace, so every behavioral gate is blocked (`src/experiment/template-results/experiment-4/tinycua/result.json:20-84`; `src/experiment/template-results/experiment-4/hermes/result.json:20-84`). |
| 5 | Pass, 13 checks | Pass, 14 checks | **[D]** Both meet required topic and exercise checks; Hermes also earns the optional linked-table-of-contents check (`src/experiment/template-results/experiment-5/tinycua/result.json:20-129`; `src/experiment/template-results/experiment-5/hermes/result.json:20-129`). |

**[D]** No new semantic `cross_verdict/` is present in the inspected snapshot.
The README describes semantic judging as a separate optional command whose
output would be written under each fixture's `cross_verdict/`
(`src/experiment/README.md:166-183`). Consequently, the new table establishes
deterministic compliance only, not a replacement qualitative ranking.

## Runtime and old/new duration ratios

The duration basis is historical `duration_seconds` versus new
`elapsed_prompt_to_finish_seconds`. Both start near model work, but they are
different runner fields, so small differences should not be overinterpreted.

| Experiment | Old TinyCUA | New TinyCUA | TinyCUA old/new duration ratio | Old Hermes | New Hermes |
|---:|---:|---:|---:|---:|---:|
| 1 | 5.4s | 8.6s | 0.6x | 5.5s | 14.9s |
| 2 | 1,135.0s | 252.7s | **4.5x** | 99.1s | 85.3s |
| 3 | 584.7s | 324.8s | **1.8x** | 31.8s | 72.7s |
| 4 | 8,394.9s | 929.9s | **9.0x** | 1,170.0s | 137.3s |
| 5 | 3,004.3s | 320.8s | **9.4x** | 106.1s | 181.9s |

**[D]** Historical duration sources are
`src/experiment/evaluation-results/tinycua/experiment-1/run_logs/metadata.json:7-9`,
`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/metadata.json:7-9`,
`src/experiment/evaluation-results/tinycua/experiment-3/run_logs/metadata.json:7-9`,
`src/experiment/evaluation-results/tinycua/experiment-4/run_logs/metadata.json:7-9`,
and `src/experiment/evaluation-results/tinycua/experiment-5/run_logs/metadata.json:7-9`.
Historical Hermes values are at
`src/experiment/evaluation-results/hermes/experiment-1/run_logs/metadata.json:7-9`,
`src/experiment/evaluation-results/hermes/experiment-2/run_logs/metadata.json:7-9`,
`src/experiment/evaluation-results/hermes/experiment-3/run_logs/metadata.json:7-9`,
`src/experiment/evaluation-results/hermes/experiment-4/run_logs/metadata.json:7-9`,
and `src/experiment/evaluation-results/hermes/experiment-5/run_logs/metadata.json:7-9`.
New elapsed values are at line 8 in the TinyCUA and Hermes `result.json` files:
`src/experiment/template-results/experiment-1/tinycua/result.json:8`,
`src/experiment/template-results/experiment-1/hermes/result.json:8`,
`src/experiment/template-results/experiment-2/tinycua/result.json:8`,
`src/experiment/template-results/experiment-2/hermes/result.json:8`,
`src/experiment/template-results/experiment-3/tinycua/result.json:8`,
`src/experiment/template-results/experiment-3/hermes/result.json:8`,
`src/experiment/template-results/experiment-4/tinycua/result.json:8`,
`src/experiment/template-results/experiment-4/hermes/result.json:8`,
`src/experiment/template-results/experiment-5/tinycua/result.json:8`, and
`src/experiment/template-results/experiment-5/hermes/result.json:8`.
Ratios are old TinyCUA duration divided by new TinyCUA duration. They describe these snapshots; they are not an isolated optimization estimate because task contracts and runner behavior changed.

**[D]** Despite these lower new durations, full TinyCUA is the slowest new base harness on
all four non-trivial fixtures:

| Experiment | New TinyCUA | Fastest new base harness | TinyCUA vs fastest |
|---:|---:|---|---:|
| 2 | 252.7s | Hermes, 85.3s | 3.0x slower |
| 3 | 324.8s | OpenClaw, 47.1s | 6.9x slower |
| 4 | 929.9s | Hermes, 137.3s | 6.8x slower |
| 5 | 320.8s | OpenClaw, 101.3s | 3.2x slower |

**[D]** The cohort comparison uses
`src/experiment/template-results/experiment-2/tinycua/result.json:8`,
`src/experiment/template-results/experiment-2/hermes/result.json:8`,
`src/experiment/template-results/experiment-3/tinycua/result.json:8`,
`src/experiment/template-results/experiment-3/openclaw/result.json:8`,
`src/experiment/template-results/experiment-4/tinycua/result.json:8`,
`src/experiment/template-results/experiment-4/hermes/result.json:8`,
`src/experiment/template-results/experiment-5/tinycua/result.json:8`, and
`src/experiment/template-results/experiment-5/openclaw/result.json:8`.

**[I]** New TinyCUA is therefore best described as "far less slow than old
TinyCUA," not "fast." Its remaining latency is associated with mandatory
analysis plus executor/reviewer processing, while the old/new reduction also
coincides with a sharp fall in repeated model requests and changed task scope.

## Process count and task-tree granularity

Here, **process count** means logged model-processing requests, not operating
system PIDs. TinyCUA counts are occurrences of HTTP `POST .../chat/completions`
in stderr; Hermes counts are the task turn's final `api_calls` value. This is
comparable old-to-new within each harness, but TinyCUA and Hermes counts should
not be treated as identical units because their orchestration boundaries differ.

| Experiment | TinyCUA model requests, old -> new | Hermes API calls, old -> new | TinyCUA visible child tasks, old -> new |
|---:|---:|---:|---:|
| 1 | 2 -> 2 | 1 -> 1 | 0 -> 0 |
| 2 | 203 -> 57 | 17 -> 17 | 7 -> 5 |
| 3 | 141 -> 70 | 2 -> 12 | 8 -> 7 |
| 4 | 1,422 -> 137 | 57 -> 25 | 16 -> 7 |
| 5 | 427 -> 65 | 6 -> 8 | 14 -> 7 |

**[D]** TinyCUA request counts were counted over the complete old/new stderr
files: historical files span 24, 1,338, 1,085, 19,308, and 3,311 lines for
Experiments 1-5, while new files span 38, 409, 518, 631, and 510 lines
(`src/experiment/evaluation-results/tinycua/experiment-1/run_logs/stderr.txt:1-24`;
`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/stderr.txt:1-1338`;
`src/experiment/evaluation-results/tinycua/experiment-3/run_logs/stderr.txt:1-1085`;
`src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stderr.txt:1-19308`;
`src/experiment/evaluation-results/tinycua/experiment-5/run_logs/stderr.txt:1-3311`;
`src/experiment/template-results/experiment-1/tinycua/stderr.log:1-38`;
`src/experiment/template-results/experiment-2/tinycua/stderr.log:1-409`;
`src/experiment/template-results/experiment-3/tinycua/stderr.log:1-518`;
`src/experiment/template-results/experiment-4/tinycua/stderr.log:1-631`;
`src/experiment/template-results/experiment-5/tinycua/stderr.log:1-510`).
Hermes exposes exact final task-turn counts at
`src/experiment/evaluation-results/hermes/experiment-1/run_logs/stderr.txt:86`,
`src/experiment/evaluation-results/hermes/experiment-2/run_logs/stderr.txt:838`,
`src/experiment/evaluation-results/hermes/experiment-3/run_logs/stderr.txt:105`,
`src/experiment/evaluation-results/hermes/experiment-4/run_logs/stderr.txt:1043`,
and `src/experiment/evaluation-results/hermes/experiment-5/run_logs/stderr.txt:284`;
new equivalents are
`src/experiment/template-results/experiment-1/hermes/stderr.log:94`,
`src/experiment/template-results/experiment-2/hermes/stderr.log:509`,
`src/experiment/template-results/experiment-3/hermes/stderr.log:271`,
`src/experiment/template-results/experiment-4/hermes/stderr.log:488`, and
`src/experiment/template-results/experiment-5/hermes/stderr.log:239`.

**[D]** Historical child-task counts are stated in the TinyCUA logs at
`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/stdout.txt:2476-2482`,
`src/experiment/evaluation-results/tinycua/experiment-3/run_logs/stdout.txt:1564-1582`,
`src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stdout.txt:15698-15707`,
and `src/experiment/evaluation-results/tinycua/experiment-5/run_logs/stdout.txt:4579-4595`.
New final trees are listed at
`src/experiment/template-results/experiment-2/tinycua/stderr.log:373-381`,
`src/experiment/template-results/experiment-3/tinycua/stderr.log:492-502`,
`src/experiment/template-results/experiment-4/tinycua/stderr.log:578-588`, and
`src/experiment/template-results/experiment-5/tinycua/stderr.log:485-495`.

**[I]** The request-count collapse is the strongest observed correlate of lower
runtime. Fewer requests mechanically leave fewer opportunities for iterative
artifact expansion, but request count is not independent of planning, scope, or
runner behavior in these runs.

## Token evidence and its limits

**[D]** Historical TinyCUA provides parseable per-node usage lines. The checked-in
historical analysis reports 183, 123, 1,331, and 394 logged calls for
Experiments 2-5 and shows that executor plus reviewer account for 98.2% of all
historical TinyCUA tokens
(`src/experiment/evaluation-results/report.md:213-256`).

**[D]** New TinyCUA does **not** provide complete equivalent token evidence in
its captured stdout. Each non-trivial run has usage records only for query
analysis, worker routing, result aggregation, and response. Executor, reviewer,
digester, task-create, analyzer, and assessor activity is visible, but their
token usage is absent. Examples are
`src/experiment/template-results/experiment-2/tinycua/stdout.log:19-28,46-56,85-106,108-143,232,251`,
`src/experiment/template-results/experiment-3/tinycua/stdout.log:26-35,49-61,90-113,262,282`,
and `src/experiment/template-results/experiment-5/tinycua/stdout.log:21-28,49-61,88-107,263,270`.

**[D]** The four visible new TinyCUA usage records sum to only about 10-11k
tokens per non-trivial run, but stderr records 57-137 model HTTP requests. The
visible sum is therefore a lower bound, not a run total
(`src/experiment/template-results/experiment-2/tinycua/stderr.log:1-238`;
`src/experiment/template-results/experiment-3/tinycua/stderr.log:1-389`;
`src/experiment/template-results/experiment-4/tinycua/stderr.log:1-477`;
`src/experiment/template-results/experiment-5/tinycua/stderr.log:1-377`).

**[D]** Hermes logs per-call prompt/completion usage and a final API-call count.
For example, new Experiment 5's artifact is generated in one 10,950-completion-
token call, followed by a short confirmation call
(`src/experiment/template-results/experiment-5/hermes/stderr.log:210-239`).
However, Hermes prompt totals are cumulative conversation contexts per call, so
summing them measures billed/requested context traffic rather than unique input
text.

**[I]** No defensible old-versus-new TinyCUA token reduction factor can be
reported. Runtime and request counts show less processing, but the new capture
omits the dominant specialized nodes, and Hermes uses a different accounting
surface.

## Behavior in stdout and stderr

### Query analyst and digester

**[D]** Historical TinyCUA routes non-trivial work through Query Analyst,
Digester, Worker, and Task Create. In Experiment 2 the old digester starts and
calls enhanced context retrieval, but no `digest_information` completion is
shown before Worker routing
(`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/stdout.txt:2-66`).

**[D]** New TinyCUA's digester explicitly reads seeded fixture context and calls
`digest_information`. In Experiment 4, its emitted summary captures the narrow
CRUD workflow, persistence, accessibility, and "no auth/sharing" constraint
before planning
(`src/experiment/template-results/experiment-4/tinycua/stdout.log:19-35`).

**[I]** New digestion visibly extracts fixture constraints, but relative
effectiveness versus the historical Digester cannot be established because the
old capture lacks an equivalent completed digest. In these fixtures its visible
output is primarily a compact `TASK.md` requirement summary, not deep domain
research.

### Planner and task tree

**[D]** Old TinyCUA repeatedly re-entered Task Analyzer and Task Assessor and
created nested decompositions. Historical Experiment 2 decomposes the research
task, then separately decomposes benchmark collection; historical Experiment 5
decomposes the guide, then decomposes neuron architecture again
(`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/stdout.txt:107-207`;
`src/experiment/evaluation-results/tinycua/experiment-5/run_logs/stdout.txt:85-297`).

**[D]** New TinyCUA performs one visible initial `task_decompose`, two scheduled
assessment passes, and then executes a flat list. The resulting trees contain
five tasks in Experiment 2 and seven each in Experiments 3-5
(`src/experiment/template-results/experiment-2/tinycua/stdout.log:51-83`;
`src/experiment/template-results/experiment-2/tinycua/stderr.log:373-381`;
`src/experiment/template-results/experiment-5/tinycua/stdout.log:54-86`;
`src/experiment/template-results/experiment-5/tinycua/stderr.log:485-495`).

**[I]** "High-level" here has a precise observed meaning: fewer, flatter tasks
whose titles align with deliverable chapters or acceptance categories, rather
than nested content-development subtasks. That shape coincides with less
cumulative expansion; no predictive relationship is estimated, and it does not
imply correctness.

### Executor

**[D]** In new Experiment 5, the first executor task, nominally "write Markdown
structure," writes the entire 667-line guide. The next six executor passes
mostly report that their assigned topic already exists, without materially
expanding the artifact
(`src/experiment/template-results/experiment-5/tinycua/stdout.log:88-117,128-180,199-249`).

**[D]** New Experiment 2 behaves similarly: the "Models" task writes a complete
report, after which Evidence, Benchmark Interpretation, Conclusion, and final
acceptance tasks are no-op verification passes
(`src/experiment/template-results/experiment-2/tinycua/stdout.log:108-143,145-226`).

**[D]** Historical TinyCUA's executors accumulate sections over many nested
tasks. Experiment 2's final report includes benchmark tables, use-case analysis,
pricing/TCO, and open-source alternatives; Experiment 5 records all 14 child
tasks integrated into a 188KB artifact
(`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/stdout.txt:2514-2562`;
`src/experiment/evaluation-results/tinycua/experiment-5/run_logs/stdout.txt:4579-4721`).

**[I]** The new first-leaf-overproduction pattern is an important mechanism:
later task-tree nodes become compliance checks instead of independent writing
passes. The plan can look decomposed while the actual artifact generation is
effectively one large shot.

### Result reviewer

**[D]** Historical review was expensive and frequently self-contradictory. In
Experiment 5, one review pass reports 496 literal Unicode escapes, a later pass
reports zero, and the parent is approved; the semantic judge later finds
malformed content, duplication, and technical errors
(`src/experiment/evaluation-results/tinycua/experiment-5/run_logs/stdout.txt:4733-4806`;
`src/experiment/evaluation-results/judges_verdict/experiment_5/verdict.md:36-45`).

**[D]** New reviewers are shorter and inspect each flat task, but still approve
claims that deterministic execution disproves. In Experiment 3 the reviewer
repeatedly approves current-time clockwise updates, although the animation loop
draws stale initial `handStates`; in Experiment 4 the reviewer approves
portability and persistence before the copied-workspace evaluator observes
`start.sh` exit 1
(`src/experiment/template-results/experiment-3/tinycua/stdout.log:227-257`;
`src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:109-110,156-160,186-217`;
`src/experiment/template-results/experiment-4/tinycua/stdout.log:397-423`;
`src/experiment/template-results/experiment-4/tinycua/result.json:27-81`).

**[I]** New review uses fewer visible invocations and is more
acceptance-oriented, but token cost cannot be compared because specialized-node
usage is absent. The external deterministic evaluator, rather than the internal
Result Reviewer, supplies the strongest new correctness signal.

### Hermes execution and log behavior

**[D]** Hermes exposes a `todo` tool in both snapshots, but historical Hermes
uses it only in Experiment 4 and new full Hermes does not visibly call it in any
of the five runs
(`src/experiment/evaluation-results/hermes/experiment-4/run_logs/stdout.txt:48-50`;
`src/experiment/evaluation-results/hermes/experiment-4/run_logs/stderr.txt:81`;
`src/experiment/evaluation-results/report.md:135-146`).

**[D]** Hermes instead follows one conversation/tool loop. New Experiment 5
tries searches, abandons them after zero results, then emits the 42KB guide in
one 10,950-token completion. New Experiment 2 similarly retries failed search
and extraction paths, then writes from established model knowledge
(`src/experiment/template-results/experiment-5/hermes/stderr.log:108-219`;
`src/experiment/template-results/experiment-2/hermes/stderr.log:480-504`).

**[D]** Hermes stdout remains dominated by initialization, enabled-tool, thought,
and tool-result output; stderr remains dominated by unavailable tools,
auxiliary-provider warnings, and per-call debug logs. This is visible even for
the exact-response greeting
(`src/experiment/evaluation-results/hermes/experiment-1/run_logs/stdout.txt:1-52`;
`src/experiment/evaluation-results/hermes/experiment-1/run_logs/stderr.txt:4-86`;
`src/experiment/template-results/experiment-1/hermes/stdout.log:7-58`;
`src/experiment/template-results/experiment-1/hermes/stderr.log:10-95`).

**[I]** Hermes artifact detail in these runs is controlled mainly by the size of
its final write generation, not by an explicit maintained task tree. Detail
differs across tasks: Experiment 5 expands to 1,236 lines in one large write,
while Experiment 2 remains shorter after search failures. One run per task does
not establish cross-trial variability.

## Artifact line counts and comprehensiveness

Line count is the newline-terminated `wc -l` count and includes blank lines and
code blocks. It is a reproducible breadth proxy, not a quality score. The old
TinyCUA and new Hermes Experiment 2 files each have one final unterminated
logical line beyond that count. For Experiment 4, the total covers first-party
text source/config/documentation files and excludes seeded `TASK.md`, databases,
binary assets, logs, temporary tool results, and generated lockfiles.

| Experiment | TinyCUA old -> new | Hermes old -> new | Detail observation |
|---:|---:|---:|---|
| 1 | 0 -> 0 | 0 -> 0 | Exact response only. |
| 2 | 367 -> 97 | 267 -> 174 | Detail ordering reverses: TinyCUA > Hermes historically, Hermes > TinyCUA now. |
| 3 | 240 -> 237 | 171 -> 137 | TinyCUA length is almost unchanged despite fewer tasks; correctness changes independently of length. |
| 4 | 3,104 -> 541 | 3,939 -> 638 | Both new implementations are much smaller and target the narrowed CRUD workflow. |
| 5 | 4,977 -> 667 | 579 -> 1,236 | Detail ordering reverses strongly: old TinyCUA is 8.6x old Hermes; new Hermes is 1.9x new TinyCUA. |

**[D]** Primary single-file ranges are
`src/experiment/evaluation-results/tinycua/experiment-2/workdir/report.md:1-368`,
`src/experiment/evaluation-results/hermes/experiment-2/workdir/report.md:1-267`,
`src/experiment/template-results/experiment-2/tinycua/workdir/report.md:1-97`,
`src/experiment/template-results/experiment-2/hermes/workdir/report.md:1-175`,
`src/experiment/evaluation-results/tinycua/experiment-3/workdir/clock.html:1-240`,
`src/experiment/evaluation-results/hermes/experiment-3/workdir/analog-clock.html:1-171`,
`src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:1-237`,
`src/experiment/template-results/experiment-3/hermes/workdir/clock.html:1-137`,
`src/experiment/evaluation-results/tinycua/experiment-5/workdir/neural_networks_transformers_study_guide.md:1-4977`,
`src/experiment/evaluation-results/hermes/experiment-5/workdir/Neural_Networks_and_Transformers_Comprehensive_Guide.md:1-579`,
`src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:1-667`, and
`src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:1-1236`.

**[D]** Experiment 4 aggregate evidence spans the old/new workdirs. Representative
core files include historical TinyCUA's backend and React components
(`src/experiment/evaluation-results/tinycua/experiment-4/workdir/src/main.py:1-425`;
`src/experiment/evaluation-results/tinycua/experiment-4/workdir/frontend/src/components/DocumentView.tsx:1-237`),
historical Hermes' duplicated entrypoints
(`src/experiment/evaluation-results/hermes/experiment-4/workdir/notion-app/main.py:1-903`;
`src/experiment/evaluation-results/hermes/experiment-4/workdir/notion-app/main_clean.py:1-261`),
and the new compact Flask apps
(`src/experiment/template-results/experiment-4/tinycua/workdir/app.py:1-141`;
`src/experiment/template-results/experiment-4/hermes/workdir/app.py:1-172`).

### Experiment 2 detail reversal

**[D]** Historical TinyCUA covers benchmark leaders, use-case recommendations,
pricing/TCO, and open-source alternatives across 367 lines. Historical Hermes
covers more named families but has no direct source URLs and relies heavily on
unsupported exact claims
(`src/experiment/evaluation-results/tinycua/experiment-2/workdir/report.md:8-100,103-187,190-269,272-367`;
`src/experiment/evaluation-results/hermes/experiment-2/workdir/report.md:41-205,245-267`;
`src/experiment/evaluation-results/judges_verdict/experiment_2/verdict.md:16-25,42-58`).

**[D]** New TinyCUA narrows itself to three families and the exact five-chapter
contract in 97 lines. New Hermes provides six families and more benchmark,
safety, and recommendation prose in 174 lines, but it cites source names without
three literal URLs and misses every bundled reference model
(`src/experiment/template-results/experiment-2/tinycua/workdir/report.md:1-97`;
`src/experiment/template-results/experiment-2/hermes/workdir/report.md:1-174`;
`src/experiment/template-results/experiment-2/hermes/result.json:62-67,139-145`).

**[I]** This is the clearest association relevant to the planning-detail
hypothesis: five high-level chapter tasks coincide with a concise
checklist-shaped artifact. It is not a causal test because the exact chapter
checklist and critical reference-model gate were absent historically.

### Experiment 5 detail reversal

**[D]** Historical TinyCUA's 4,977-line guide covers a very broad curriculum but
contains obvious structural duplication, including separate `Weights and
Biases` and `Weights and Biases: Comprehensive Deep Dive` sections. The old
judge finds breadth but poor editing and factual/technical problems
(`src/experiment/evaluation-results/tinycua/experiment-5/workdir/neural_networks_transformers_study_guide.md:229-447`;
`src/experiment/evaluation-results/judges_verdict/experiment_5/verdict.md:36-45`).

**[D]** New TinyCUA's 667-line guide has seven numbered content chapters matching
its seven tasks, plus a table of contents. New Hermes' 1,236-line guide adds more neural-network fundamentals,
optimizer material, encoder/decoder implementation, six practical exercises,
resources, and quick-reference equations
(`src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:1-667`;
`src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:25-302,302-821,822-1236`).

**[D]** Both pass the deterministic evaluator because it checks headings,
required term presence, code fences, and a practical plan. It does not execute
examples or assess factual and pedagogical quality
(`src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:108-177`).

**[I]** The reversal is consistent with, but does not establish, shallower
planning reducing expansion. It also shows why detail must be separated from
usefulness: old TinyCUA's extreme detail was partly duplication, while the new
evaluator cannot establish whether Hermes' larger guide is more correct.

### Experiment 3 correctness reversal

**[D]** Old TinyCUA calculates positive degree values but applies negative Canvas
rotations, directly producing the counterclockwise motion found by the old judge
(`src/experiment/evaluation-results/tinycua/experiment-3/workdir/clock.html:165-180,183-219`;
`src/experiment/evaluation-results/judges_verdict/experiment_3/verdict.md:37-46`).

**[D]** Old Hermes builds its hands correctly but then calls
`clock.querySelector('.center-dot').appendChild(...)` without ever creating a
`.center-dot`, preventing the update loop from starting
(`src/experiment/evaluation-results/hermes/experiment-3/workdir/analog-clock.html:90-146`;
`src/experiment/evaluation-results/judges_verdict/experiment_3/verdict.md:15-24`).

**[D]** New Hermes recomputes time inside `drawClock()` and maps positive angles
from twelve o'clock on every scheduled frame, which the frozen-time browser
evaluator verifies
(`src/experiment/template-results/experiment-3/hermes/workdir/clock.html:33-39,90-134`;
`src/experiment/template-results/experiment-3/hermes/result.json:48-80`).

**[D]** New TinyCUA computes `currentHandStates` inside the animation loop but
draws the outer, once-initialized `handStates` instead. Its radians also use
`pi/2 - angle`, which points zero seconds downward and progresses in the wrong
orientation for Canvas coordinates
(`src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:72-110,156-160,186-217`).

**[I]** The correctness reversal is not evidence that Hermes' lack of a task
tree is superior. It is a generation-level bug combined with a stronger new
dynamic evaluator. TinyCUA's seven tasks and repeated reviews did not protect
against a stale-variable integration defect.

## Verification and evaluator differences

### Internal verification

**[D]** Historical TinyCUA often verified textual proxies or local claims rather
than end-to-end behavior. The historical report documents 77 executor starts
and 75 reviewer starts for Experiment 4 even though the app remained
nonfunctional, and notes that Experiment 5 integrity checks missed duplication
and factual errors
(`src/experiment/evaluation-results/report.md:264-303`).

**[D]** New TinyCUA performs more concrete shell/browser work in Experiment 4;
its retained app log shows successful local HTTP CRUD operations. But it tests
in `/workspace`, while the deterministic evaluator copies the submission to a
new directory before running `sh start.sh`
(`src/experiment/template-results/experiment-4/tinycua/workdir/logs/app.log:1-41`;
`src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:93-116,266-285`).

**[D]** TinyCUA's `start.sh` hardcodes `/workspace/venv`,
`/workspace/requirements.txt`, and `/workspace/app.py`; Hermes uses Bash-only
`${BASH_SOURCE[0]}` and `source` despite the required evaluator invocation being
`sh start.sh`. These portability defects explain the shared new Experiment 4
failure better than missing artifact volume
(`src/experiment/template-results/experiment-4/tinycua/workdir/start.sh:13-28`;
`src/experiment/template-results/experiment-4/hermes/workdir/start.sh:1-22,36-37`;
`src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:93-108`).

### External evaluation

**[D]** The old semantic judge can discuss correctness, coherence, sourcing,
stdout noise, and craftsmanship, but its verdict is model-mediated and the
judge harness is Hermes. Anonymization reduces name bias but does not remove
judge-model or judge-harness effects
(`src/experiment/evaluation-results/report.md:42-53,334-340`).

**[D]** The new coding evaluators execute behavior. Experiment 3 freezes time,
captures Canvas/SVG line geometry, advances scheduled callbacks, and tests exact
clockwise angles. Experiment 4 launches the app in an isolated copied workspace,
drives accessible controls in Chromium, inspects SQLite, and restarts the app
(`src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:24-94,139-245,248-297`;
`src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:93-145,175-233,266-341`).

**[D]** The new research evaluators are much weaker semantic instruments.
Experiment 5 checks mostly term presence and Markdown structure. Experiment 2
uses lexical checks plus a critical requirement that the report mention at
least one model from a fixed bundled list; that list includes `GPT-5.6-Sol`,
`Claude Fable 5`, and other campaign reference names
(`src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:124-169`;
`src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py:122-218`;
`src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/evidence.json:2-20`).

**[I]** New pass/fail is stronger than the old judge for executable clock and app
behavior, but weaker for research truth, code-example correctness, editorial
quality, and pedagogy. The two result systems answer different questions, so
their scores are intentionally kept in separate tables.

## Hypothesis test: does high-level planning cause less detail?

### Evidence supporting the hypothesis

1. **[D] Fewer and flatter tasks coincide with shorter TinyCUA artifacts.**
   Experiment 2 moves from seven nested/iteratively handled child tasks to five
   flat chapter tasks and from 367 to 97 lines. Experiment 5 moves from fourteen
   child tasks to seven flat topic tasks and from 4,977 to 667 lines
   (`src/experiment/evaluation-results/tinycua/experiment-2/run_logs/stdout.txt:2476-2482`;
   `src/experiment/template-results/experiment-2/tinycua/stderr.log:373-381`;
   `src/experiment/evaluation-results/tinycua/experiment-5/run_logs/stdout.txt:4579-4595`;
   `src/experiment/template-results/experiment-5/tinycua/stderr.log:485-495`).
2. **[D] New downstream tasks mostly verify prior content instead of adding it.**
   The first substantial write already satisfies later nodes in Experiments 2
   and 5 (`src/experiment/template-results/experiment-2/tinycua/stdout.log:108-226`;
   `src/experiment/template-results/experiment-5/tinycua/stdout.log:88-249`).
3. **[D] The historical expansion came from repeated executor/reviewer traffic.**
   Historical usage shows 98.2% of tokens in those two roles
   (`src/experiment/evaluation-results/report.md:228-256`).

### Evidence against a simple causal claim

1. **[D] Prompt scope changed.** New Experiment 5 requests a finite six-concept
   curriculum plus one example and plan, while old Experiment 5 asks for
   "comprehensive" research without a ceiling
   (`src/experiment/evaluation-results/tinycua/experiment-5/run_logs/prompt.txt:1`;
   `src/experiment/experiment-fixtures/experiments-list/experiment-5/workdir/TASK.md:8-13`).
2. **[D] Process count changed sharply.** TinyCUA model requests fall from 203
   to 57 in Experiment 2 and 427 to 65 in Experiment 5, mechanically limiting
   opportunities for iterative expansion but remaining confounded with planning.
3. **[D] Less detail is not universal.** TinyCUA Experiment 3 remains almost the
   same length (240 vs 237) even though the new tree is flatter, and its new
   deterministic correctness is worse than Hermes despite detailed planning and
   review (`src/experiment/evaluation-results/tinycua/experiment-3/workdir/clock.html:1-240`;
   `src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:1-237`;
   `src/experiment/template-results/experiment-3/tinycua/result.json:48-98`).
4. **[D] Hermes reverses detail without adopting a persistent task tree.** New
   Hermes Experiment 5 expands in a single 10,950-token write
   (`src/experiment/template-results/experiment-5/hermes/stderr.log:210-223`).
5. **[D] No repeated trials or fixed seed isolate stochastic variation.** The
   campaign records one trial, no retries, and a null seed
   (`src/experiment/template-results/run_metadata.json:754-764`).

### Verdict

**[I]** Flatter plans, fewer requests, and shorter artifacts are associated.
High-level planning remains a plausible explanatory hypothesis because broad
leaves are over-completed once and then merely checked, but the evidence does
not establish it as a causal contributor. Prompt specificity and the large
reduction in model requests are equally plausible explanations.

## Ranked explanatory hypotheses

1. **[I] Strongest: fewer model-processing/revision cycles plausibly reduced
   cumulative expansion.** The request-count reductions align with both shorter
   runtime and shorter documentation artifacts, but changed scope and runtime
   behavior remain confounded.
2. **[I] Strong: flatter, acceptance-shaped planning is consistent with later leaves becoming
   no-op verification.** This mechanism is visible line-by-line in new
   Experiments 2 and 5 and directly matches the user's hypothesis.
3. **[I] Strong confounder: the new prompts impose finite, narrower acceptance
   contracts.** The controlled tasks reward satisfying named gates, not
   open-ended elaboration; Experiment 4 also explicitly removes auth and broad
   collaboration features.
4. **[I] Moderate: reviewer objectives favor checklist compliance over
   editorial expansion or integration skepticism.** New reviewers repeatedly
   approve "already present" sections and miss the Experiment 3 stale-state bug
   and Experiment 4 portability defects.
5. **[I] Moderate: search/tool outcomes and one-shot generation size change
   detail independently of planning.** New Hermes Experiment 2 retries failed
   search and writes 174 lines from prior knowledge; Experiment 5 emits 1,236
   lines in one giant generation.
6. **[I] Moderate-to-weak: harness-version and model-sampling drift affected
   behavior.** The model name is shared, but harness versions, date, server
   defaults, and unseeded sampling are not held constant across snapshots.
7. **[I] Evaluation explains observed ranking reversals but not artifact
   creation.** Dynamic evaluators expose correctness that internal reviewers
   miss; lexical research evaluators can reward a shorter report that happens to
   name a critical bundled model. This changes measured outcomes, not the files
   the agents originally wrote.

## Limits

- **[D]** There is one trial per new pair and no fixed seed
  (`src/experiment/template-results/run_metadata.json:754-764`).
- **[D]** Historical and new prompts, runner fields, harness versions, dates,
  and evaluator types differ; this is not a controlled ablation of planning.
- **[D]** New TinyCUA token capture omits the executor/reviewer and other
  specialized-node usage, preventing a numeric old/new token comparison.
- **[D]** Artifact line count measures volume, not correctness, originality,
  source reliability, coherence, or learner value.
- **[D]** The old judge is semantic but model-mediated; the new research
  evaluators are deterministic but mostly lexical/structural. Neither alone is
  ground truth.
- **[D]** No new semantic cross-verdict was available, so new TinyCUA/Hermes
  prose quality was not independently judged.
- **[I]** The explanatory ranking organizes plausible interpretations; it is not
  a causal estimate. Isolating the planning hypothesis requires rerunning the same
  prompt, model snapshot, seed policy, process budget, tools, and evaluator while
  changing only task-tree granularity.
