# Controlled Template Experiment Analysis

This report analyzes the behavior recorded in the controlled template campaign under `src/experiment/template-results/` and compares it with the historical snapshot under `src/experiment/evaluation-results/`.

The central questions are:

1. What do TinyCUA's Information Digester and Result Reviewer actually do?
2. How do those roles relate to the four TinyCUA ablation outcomes?
3. How does full TinyCUA behave relative to Hermes, OpenCode, and OpenClaw?
4. Why is new TinyCUA much faster than historical TinyCUA while often producing less detail?
5. Why did TinyCUA's internal review approve artifacts that deterministic evaluators later rejected?

## Reports

- [TinyCUA roles and 2x2 ablation](tinycua-ablation.md): detailed stdout/stderr traces for `tinycua`, `tinycua-nd`, `tinycua-nr`, and `tinycua-nd-nr`.
- [New full-harness comparison](new-harness-comparison.md): behavior and outcomes for TinyCUA, Hermes, OpenCode, and OpenClaw.
- [Historical TinyCUA and Hermes comparison](historical-comparison.md): prompt, planning, runtime, artifact-detail, verification, and evaluation changes between snapshots.
- [Fixture versus prototype attribution](fixture-vs-prototype-attribution.md): separates shared fixture effects, TinyCUA-specific process associations, and evaluator measurement effects.

## Evidence conventions

- **[D] Direct evidence** is present in a checked-in log, result, artifact, fixture, evaluator, or metadata file.
- **[I] Inference** interprets direct evidence but is not a causal estimate.
- Deterministic scores are compared only within the same fixture. A point in the research evaluator is not equivalent to a point in the browser evaluator.
- Historical semantic-judge scores and new deterministic scores remain separate because they measure different constructs.
- Artifact length is a breadth/volume measurement, not a correctness or usefulness score.

## Executive conclusions

### 1. Result Reviewer approval is not independent verification

**[D]** The Reviewer is instructed to inspect artifacts, runtime-check behavior, reject unsupported claims, and approve only when no findings remain (`src/tinycua/tinycua/loops/node_guidance.py:60-77`). In the observed runs it often performed a narrower operation: checking that source text or task reports appeared to contain required elements.

The clearest false approvals are:

| Experiment | Reviewer claim | Artifact/evaluator result | Interpretation |
|---|---|---|---|
| 3, clock | Smooth `requestAnimationFrame` updates and all acceptance criteria satisfied (`src/experiment/template-results/experiment-3/tinycua/stdout.log:247-255`). | `animate()` calculates fresh state but draws stale initial state; all movement categories fail (`src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:156-217`; `src/experiment/template-results/experiment-3/tinycua/result.json:55-74`). | Source-level intent was approved without verifying rendered time advancement. |
| 4, app | Startup, CRUD, reload, and restart persistence verified (`src/experiment/template-results/experiment-4/tinycua/stdout.log:386-415`). | The exported app exits before serving; its script is workspace-coupled, Python contains literal `\n` tokens, and initialization drops the persistence table (`src/experiment/template-results/experiment-4/tinycua/result.json:20-81`; `src/experiment/template-results/experiment-4/tinycua/workdir/start.sh:13-28`; `src/experiment/template-results/experiment-4/tinycua/workdir/app.py:20-46,115-130`). | Local construction-workspace checks were not equivalent to testing the exported deliverable. |
| 5, guide | All table-of-contents links work (`src/experiment/template-results/experiment-5/tinycua/stdout.log:102-107`). | The positional-encoding link targets the wrong anchor and loses the TOC point (`src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:3-11`; `src/experiment/template-results/experiment-5/tinycua/result.json:41-46`). | Even a directly inspectable structural defect passed review. |

**[I]** The Reviewer behaves more like a task-local consistency critic than an acceptance-test oracle. It can find defects, but approval should not be interpreted as evidence that the exported result works.

### 2. The Reviewer can still add value, but its cost and reliability vary

**[D]** The no-Digester Reviewer found real problems:

- Experiment 2: it rejected unsupported evidence claims and forced explicit source limitations, although it also invented a requirement for three URLs per model family and entered a long retry/replan loop.
- Experiment 4: it found a real mismatch between the new pages/blocks schema and API routes still using the old table. It later incorrectly predicted that a nullable foreign key would break block creation; runtime checks disproved that finding.
- Experiment 5: it detected missing Transformer sections and caused them to be added.

The same runs show the risk:

- `tinycua-nd` used 20 Reviewer passes in Experiment 2 and took 2,706.65 seconds.
- It used 17 Reviewer passes in Experiment 5 and took 1,642.91 seconds.
- Large or partial artifact views coincided with contradictory approvals and revision requests.

See [Reviewer decision patterns](tinycua-ablation.md#reviewer-decision-pattern) and the per-experiment ablation case studies.

### 3. Information Digester is bounded and most visibly useful for targeting

**[D]** The Digester runs once before Worker on every non-passthrough enabled run. It normally reads task/workspace context, retrieves context, and emits a compact digest. It does not create a separate deliverable.

The strongest visible research contribution is `tinycua-nr` Experiment 2, where the Digester performs four web searches and a URL fetch before summarizing a current model landscape (`src/experiment/template-results/experiment-2/tinycua-nr/stdout.log:19-36`). That run covers more current evaluator-reference names than the both-off run.

The role does not guarantee downstream compliance:

- In Experiment 3 no-Reviewer, the digest explicitly notices that `clock.html` is a directory, but execution still writes a nested file and scores 0/9.
- In Experiments 3 and 4, every Digester configuration still fails the executable evaluator.

**[I]** Digestion appears best understood as context compression and research targeting, not verification or coding-quality control.

### 4. The TinyCUA ablation has no stable winner

| Configuration | Digester | Reviewer | Passed fixtures | Nontrivial runtime |
|---|---:|---:|---:|---:|
| `tinycua` | On | On | 3/5 | 1,828.12 s |
| `tinycua-nd` | Off | On | 3/5 | 5,419.88 s |
| `tinycua-nr` | On | Off | 3/5 | 2,565.39 s |
| `tinycua-nd-nr` | Off | Off | 2/5 | 1,173.46 s |

Nontrivial runtime excludes the exact-response fixture. Full, no-Digester, and no-Reviewer each pass two of four nontrivial fixtures. Both-off passes one.

**[D]** Role score contrasts change sign by task. Reviewer-on is +5 points in one no-Digester research comparison but -3 in the no-Digester clock comparison. Digester-on is +4 in the no-review research comparison but -3 in the no-review clock comparison.

**[I]** One unseeded run per pair is insufficient to estimate role effects. The evidence identifies failure modes and associations, not a causal winner.

### 5. Hermes and TinyCUA tie on passes, with task-specific strengths

| Harness | Passed fixtures | Cumulative runtime | Distinctive result |
|---|---:|---:|---|
| Hermes | 3/5 | 8.20 min | Only 9/9 clock and only 14/14 guide. |
| TinyCUA | 3/5 | 30.61 min | Only core harness to pass Experiment 2's hidden relevancy gate. |
| OpenCode | 2/5 | 14.06 min | Deep tool-driven research and local API testing, but missed hidden and export assumptions. |
| OpenClaw | 1/5 | 8.04 min | Only exported app to start, but no usable initial workflow and no Experiment 5 artifact. |

These aggregate descriptions are not a universal quality ranking:

- Experiment 2 pass/fail depends on mentioning at least one name from an evaluator-only synthetic model list. TinyCUA happened to mention `Claude Fable 5`; the other substantial reports exceeded the numeric threshold but failed the critical lexical gate.
- Experiment 5 structurally checks headings, terms, code fences, and a plan. It does not execute examples. Hermes' 14/14 guide is the longest and broadest, but it contains non-runnable snippets.
- Experiment 3 is the cleanest correctness comparison because the evaluator observes browser geometry and movement. Hermes' simple 137-line implementation passes; TinyCUA's reviewed 237-line implementation fails.
- Experiment 4 rejects every harness and exposes different delivery failures. OpenClaw alone starts after export, but its empty state offers no usable route to create the first page/block.

See [the full behavior comparison](new-harness-comparison.md).

### 6. New TinyCUA is much faster than historical TinyCUA, not fast within the new cohort

| Experiment | Historical TinyCUA | New TinyCUA | Old/new duration ratio |
|---:|---:|---:|---:|
| 2 | 1,135.0 s | 252.7 s | 4.5x |
| 3 | 584.7 s | 324.8 s | 1.8x |
| 4 | 8,394.9 s | 929.9 s | 9.0x |
| 5 | 3,004.3 s | 320.8 s | 9.4x |

The old/new ratios are descriptive, not an isolated optimization estimate: prompts, acceptance criteria, runner behavior, TinyCUA implementation, and model-processing counts changed.

Within the new campaign, TinyCUA is the slowest core harness on every nontrivial fixture: approximately 3.0x the fastest runtime in Experiment 2, 6.9x in Experiment 3, 6.8x in Experiment 4, and 3.2x in Experiment 5.

### 7. Less-detailed new TinyCUA output correlates with flatter planning and fewer requests

| Experiment | TinyCUA artifact, old -> new | TinyCUA child tasks, old -> new | TinyCUA model requests, old -> new |
|---:|---:|---:|---:|
| 2 | 367 -> 97 report lines | 7 -> 5 | 203 -> 57 |
| 3 | 240 -> 237 clock lines | 8 -> 7 | 141 -> 70 |
| 4 | 3,104 -> 541 selected text lines | 16 -> 7 | 1,422 -> 137 |
| 5 | 4,977 -> 667 guide lines | 14 -> 7 | 427 -> 65 |

**[D]** New Experiments 2 and 5 use one flat task list shaped around required chapters. The first substantial executor writes nearly the complete artifact; later executors and Reviewers mostly report that their assigned section already exists (`src/experiment/template-results/experiment-2/tinycua/stdout.log:108-226`; `src/experiment/template-results/experiment-5/tinycua/stdout.log:88-249`).

Historical TinyCUA recursively decomposes broader prompts and repeatedly appends sections. This creates broader artifacts but also duplication, malformed content, unintegrated scaffolding, and enormous runtime. The historical semantic judge explicitly criticizes the 4,977-line study guide for repetition and technical errors (`src/experiment/evaluation-results/judges_verdict/experiment_5/verdict.md:36-45`).

**[I]** High-level, acceptance-shaped planning is a plausible explanation for reduced detail because broad leaves are completed once and later leaves become no-op checks. It is not the only explanation: the new prompts impose finite stopping boundaries and model-request counts collapse at the same time.

### 8. The TinyCUA/Hermes detail reversal is real but task-specific

| Artifact | Historical TinyCUA | Historical Hermes | New TinyCUA | New Hermes |
|---|---:|---:|---:|---:|
| Experiment 2 report | 367 lines | 267 lines | 97 lines | 174 lines |
| Experiment 5 guide | 4,977 lines | 579 lines | 667 lines | 1,236 lines |

Historical TinyCUA is larger in both documentation tasks; new Hermes is larger in both. Experiment 3 correctness also reverses: historical TinyCUA at least renders while historical Hermes crashes, whereas new Hermes passes all checks and new TinyCUA fails movement.

This is not a global hierarchy reversal. Hermes already led the old semantic judgment for Experiment 5, TinyCUA still has the higher new Experiment 2 deterministic total, and both fail Experiment 4.

### 9. Experiment 4's narrower code is primarily fixture-associated

Using the linked attribution report's logical-line `str.splitlines()` inventory, rather than the newline-terminated `wc -l` convention used in sections 7-8, all four harnesses produce 77-84% smaller Experiment 4 text inventories under the new fixture. TinyCUA contracts 82.7%; the three non-TinyCUA harnesses contract 81.0% in aggregate. The new task explicitly removes authentication, accounts, sharing, and unrelated collaboration while defining one block CRUD/persistence workflow.

The newer TinyCUA prototype is consistent with the flat seven-child plan rather than recursive expansion. Historical Experiment 4 reached 40 retained nodes; controlled Experiment 4 had eight. The cross-harness contraction argues against a TinyCUA-only explanation and makes fixture scope the strongest observed association, but it does not identify a primary causal contribution.

This pattern does not generalize to every fixture. In Experiment 5, TinyCUA shrinks 86.6% while Hermes more than doubles and OpenCode stays nearly unchanged. See [the full fixture-versus-prototype attribution](fixture-vs-prototype-attribution.md).

## New full-harness result matrix

`P` means all threshold and critical-category requirements passed.

| Experiment | TinyCUA | Hermes | OpenCode | OpenClaw |
|---|---:|---:|---:|---:|
| 1, exact reply | 1/1 P | 1/1 P | 1/1 P | 1/1 P |
| 2, frontier report | 19/32 P | 16/32 F | 17/32 F | 17/32 F |
| 3, analog clock | 5/9 F | 9/9 P | 3/9 F | 3/9 F |
| 4, Notion-like app | 1/9 F | 1/9 F | 1/9 F | 3/9 F |
| 5, study guide | 13/14 P | 14/14 P | 13/14 P | 2/14 F |

Source: `src/experiment/template-results/outcomes.json` and the individual `result.json` files.

## Implications for further discussion

The evidence suggests four concrete design questions:

1. **Reviewer verification boundary:** Should approval require executing the exact public entrypoint or evaluator-equivalent behavioral check rather than accepting executor reports?
2. **Reviewer retry budget:** Should repeated `needs_revision` cycles have a hard cap and require re-reading the original acceptance criteria before replanning?
3. **Artifact ownership:** Should one task own the final integrated artifact while later tasks produce explicit patches, preventing both first-task overcompletion and concatenated duplicate guides?
4. **Telemetry:** Should every specialized node report tokens, tool calls, decision payloads, and verification commands so role cost and effectiveness can be measured directly?

## Limits

- One unseeded trial per pair; no variance or confidence intervals.
- Full TinyCUA and the ablations were preserved under different result-generation revisions.
- Harness prompts, tools, permissions, and thinking settings differ. OpenClaw was explicitly configured with thinking off.
- The sequential campaign encountered changing search availability and service backoff.
- New TinyCUA token telemetry omits Digester, Executor, Reviewer, and several planning nodes.
- Historical tasks, runner fields, harness versions, and semantic evaluation differ from the controlled fixtures.
- Experiment 2's hidden model list weakens its value as a general research-quality test.
- Experiment 5's structural evaluator cannot establish factual or code-example correctness.
- No new semantic cross-verdict was generated, so qualitative conclusions come from manual log/artifact inspection plus deterministic results.

## Bottom line

The new runs record fewer requests, flatter task trees, shorter artifacts, and much shorter observed runtimes than the historical runs. These changes coincide with less exploratory detail; the design does not isolate architecture or control as its cause. The Information Digester is a bounded context stage with its clearest visible association in research targeting. The Result Reviewer is far more consequential and expensive, but its approvals frequently validate textual intent rather than exported behavior. In this campaign, external deterministic execution—not internal review—provides the reliable verification signal.
