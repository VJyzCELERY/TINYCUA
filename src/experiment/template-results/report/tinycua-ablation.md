# TinyCUA Controlled-Template 2x2 Ablation

[README](README.md) | [Why orchestration did not improve quality](why-orchestration-did-not-improve-quality.md) | [Evaluator validity](evaluator-validity-and-artifact-quality.md) | [Reviewer limitations](reviewer-verification-limitations.md) | [Harness specialties](harness-specialties.md) | [Fixture vs prototype](fixture-vs-prototype-attribution.md) | [New-harness comparison](new-harness-comparison.md) | [Historical comparison](historical-comparison.md)

This report analyzes campaign `1eb78b68-d840-4e0d-9437-3a674c0194d3` across the four TinyCUA configurations: both Information Digester and Result Reviewer enabled (`tinycua`), Digester disabled (`tinycua-nd`), Reviewer disabled (`tinycua-nr`), and both disabled (`tinycua-nd-nr`). The aliases and flags are recorded directly in the campaign metadata ([`src/experiment/template-results/run_metadata.json:23-43`](../run_metadata.json#L23-L43)).

## Evidence notation

- **[D] Direct evidence**: observed in committed source, generated artifacts, logs, or deterministic evaluator output.
- **[I] Inference**: an interpretation of direct evidence. It is not a causal claim.
- **Digester** means `TinyCUAInformationDigesterNode`; **Reviewer** means `TinyCUAResultReviewerNode`.
- **Score** means deterministic category points for that fixture. Scores are not normalized across fixtures and must not be summed as if they shared a scale.
- **Runtime** means `elapsed_prompt_to_finish_seconds`, rounded to two decimals.
- In role-count tables, `D 1[4]` means one Digester invocation and four logged Digester tool-result events. `R 6[19]` means six Reviewer invocations and nineteen logged Reviewer tool-result events. `A`, `N`, and `Rp` are visible `approved`, `needs_revision`, and `replan` decision payloads, respectively.
- Artifact line counts use logical lines (`str.splitlines()`). The no-Digester experiment-5 guide has 3,185 logical lines but 3,184 newline terminators because its final line is unterminated.

## Executive findings

1. **[D] No enabled-role configuration won consistently.** Full TinyCUA, no-Digester, and no-Reviewer each passed 3/5 fixtures; both-off passed 2/5. Excluding the passthrough fixture, those rates are 2/4, 2/4, 2/4, and 1/4. The only pass/fail separation among role configurations occurred in experiment 2; experiments 3 and 4 failed in every cell, and experiments 1 and 5 passed in every cell ([`outcomes.json:19-75`](../outcomes.json#L19-L75), [`outcomes.json:104-135`](../outcomes.json#L104-L135), [`outcomes.json:162-193`](../outcomes.json#L162-L193), [`outcomes.json:213-231`](../outcomes.json#L213-L231)).
2. **[D] Reviewer activity was expensive and did not guarantee executable correctness.** The Reviewer ran once after every executor pass in review-enabled cells: 30 times for full TinyCUA and 50 times for no-Digester across experiments 2-5. The no-Digester Reviewer loop reached 20 invocations in experiment 2 and 17 in experiment 5 ([`experiment-2/tinycua-nd/stderr.log:806-869`](../experiment-2/tinycua-nd/stderr.log#L806-L869), [`experiment-5/tinycua-nd/stderr.log:984-1031`](../experiment-5/tinycua-nd/stderr.log#L984-L1031)). It nevertheless approved a static clock as animated and a Notion app that did not start in the evaluator ([`experiment-3/tinycua/stdout.log:247-255`](../experiment-3/tinycua/stdout.log#L247-L255), [`experiment-4/tinycua/result.json:27-81`](../experiment-4/tinycua/result.json#L27-L81)).
3. **[D] The Digester was a single, bounded pre-planning stage.** It ran once in every non-passthrough Digester-enabled cell and never ran in a no-Digester cell. Most calls read the task/workspace and retrieved context; only experiment 2 no-Reviewer visibly used web search and URL fetching during digestion ([`experiment-2/tinycua-nr/stdout.log:19-36`](../experiment-2/tinycua-nr/stdout.log#L19-L36)).
4. **[I] Digestion is associated with more concise research artifacts, but the evidence is not causal.** In experiment 5, Digester-enabled guides were 667 and 490 logical lines; Digester-disabled guides were 3,185 and 3,083 logical lines and contained repeated headings/sections. The same directional size pattern appears in experiment 2, though less strongly. Single trials, unseeded sampling, and mixed runner revisions prevent attributing this difference to the Digester alone.
5. **[D] Deterministic scores and usable quality diverged.** Experiment 2 no-Digester scored highest despite documenting an invented source constraint and centering older model families. Experiment 5 allowed duplicated multi-guide artifacts to pass because its gate checks existence, structure, required substrings, code fences, a plan, and task integrity rather than technical correctness ([`experiment-5/eval/check.py:124-170`](../../experiment-fixtures/experiments-list/experiment-5/eval/check.py#L124-L170)).
6. **[I] Neither role has a demonstrated net quality benefit.** The Digester is operationally bounded and associated with shorter documents, but this is not isolated from changed planning trajectories. The Reviewer redirects work, but its retry behavior, acceptance-criteria drift, and weak evaluator-equivalent verification add cost without a consistent final-outcome gain.

## Experimental design

### Configuration matrix

| Configuration | Digester | Reviewer | Campaign flags |
|---|---:|---:|---|
| `tinycua` | On | On | `no_digest=false`, `no_review=false` |
| `tinycua-nd` | Off | On | `no_digest=true`, `no_review=false` |
| `tinycua-nr` | On | Off | `no_digest=false`, `no_review=true` |
| `tinycua-nd-nr` | Off | Off | `no_digest=true`, `no_review=true` |

**[D]** The controlled runner defines the aliases and maps them to the same TinyCUA service with only the two role flags changed ([`run_template_experiment.py:26-33`](../../run_template_experiment.py#L26-L33), [`run_template_experiment.py:298-306`](../../run_template_experiment.py#L298-L306)); the user-facing runner documentation defines the same mapping ([`src/experiment/README.md:79-92`](../../README.md#L79-L92)).

### Shared conditions

- **[D]** The campaign used `qwen3.5-9b` through an OpenAI-compatible local endpoint, a 14,400-second timeout, and TinyCUA commit `89d2402e5dd6626390e9c5e09b52a21898e0cf2c` ([`run_metadata.json:731-752`](../run_metadata.json#L731-L752)).
- **[D]** Temperature, top-p, and seed were unset. Each pair had one trial, `pass_at_k=1`, no retries, and sequential execution ([`run_metadata.json:754-764`](../run_metadata.json#L754-L764)).
- **[D]** Fixtures 1-5 cover one exact-response conversation, two research documents, one single-file browser app, and one Python/SQLite browser app ([`run_metadata.json:54-79`](../run_metadata.json#L54-L79)).
- **[D]** Candidate image IDs are identical among the four TinyCUA variants within each fixture; experiments 3 and 4 use fixture-specific decorators ([`run_metadata.json:471-705`](../run_metadata.json#L471-L705)).

### Evaluator semantics

| Experiment | Max | Pass rule | Important implication |
|---|---:|---|---|
| 1 | 1 | Exact response, threshold 1 | Exercises passthrough only. |
| 2 | 32 | At least 12 points and all three critical categories | `model_relevancy` is critical, so a 16-point report can still fail ([`experiment-2/eval/check.py:13-19`](../../experiment-fixtures/experiments-list/experiment-2/eval/check.py#L13-L19), [`experiment-2/eval/check.py:109-119`](../../experiment-fixtures/experiments-list/experiment-2/eval/check.py#L109-L119)). |
| 3 | 9 | 9/9; every category is critical | Browser-observed rendering and time movement are mandatory ([`experiment-3/eval/check.py:12-23`](../../experiment-fixtures/experiments-list/experiment-3/eval/check.py#L12-L23), [`experiment-3/eval/check.py:262-297`](../../experiment-fixtures/experiments-list/experiment-3/eval/check.py#L262-L297)). |
| 4 | 9 | 9/9; every category is critical | Startup, Python process, browser CRUD, reload, SQLite, and restart persistence are mandatory ([`experiment-4/eval/check.py:22-33`](../../experiment-fixtures/experiments-list/experiment-4/eval/check.py#L22-L33), [`experiment-4/eval/check.py:323-336`](../../experiment-fixtures/experiments-list/experiment-4/eval/check.py#L323-L336)). |
| 5 | 14 | At least 9 points and three critical categories | Most topic checks are substring/structure checks; technical correctness is not a gate ([`experiment-5/eval/check.py:13-18`](../../experiment-fixtures/experiments-list/experiment-5/eval/check.py#L13-L18), [`experiment-5/eval/check.py:124-170`](../../experiment-fixtures/experiments-list/experiment-5/eval/check.py#L124-L170)). |

## Aggregate outcomes

| Configuration | Passed, all 5 | Passed, nontrivial 4 | Total runtime | Fastest nontrivial cell | Slowest nontrivial cell |
|---|---:|---:|---:|---|---|
| `tinycua` | 3/5 | 2/4 | 1,836.71 s (30.61 min) | Exp. 2: 252.69 s | Exp. 4: 929.91 s |
| `tinycua-nd` | 3/5 | 2/4 | 5,428.29 s (90.47 min) | Exp. 3: 301.08 s | Exp. 2: 2,706.65 s |
| `tinycua-nr` | 3/5 | 2/4 | 2,573.70 s (42.89 min) | Exp. 3: 196.10 s | Exp. 4: 1,374.20 s |
| `tinycua-nd-nr` | 2/5 | 1/4 | 1,182.00 s (19.70 min) | Exp. 3: 131.30 s | Exp. 5: 581.08 s |

**[D]** The both-off configuration was fastest in experiments 2-4, while full TinyCUA was fastest in experiment 5; both-off also had the lowest pass count. **[I]** This is a work/latency trade-off, not evidence that role overhead is wasted: the configurations generated different task trees and artifacts, not the same work with two isolated calls added.

### Descriptive role contrasts

Positive values favor the named role. These are score-point differences within one trial, not effect estimates.

| Controlled contrast | Exp. 2 | Exp. 3 | Exp. 4 | Exp. 5 |
|---|---:|---:|---:|---:|
| Reviewer on vs. off, Digester on: `tinycua - tinycua-nr` | -1 | +5 | 0 | 0 |
| Reviewer on vs. off, Digester off: `tinycua-nd - tinycua-nd-nr` | +5 | -3 | +2 | +1 |
| Digester on vs. off, Reviewer on: `tinycua - tinycua-nd` | -2 | +5 | -2 | 0 |
| Digester on vs. off, Reviewer off: `tinycua-nr - tinycua-nd-nr` | +4 | -3 | 0 | +1 |

**[D]** Every role contrast changes sign or reaches zero across fixtures. **[I]** No stable directional main-effect pattern is visible; interaction magnitude cannot be estimated from one trial on differently scaled fixtures.

## Role behavior and activity

### Intended behavior

**[D] Information Digester.** Its instruction is exploration-only: inspect referenced files, retrieve session context, use web search only for remaining uncertainty, then emit a concise structured digest for downstream planning ([`information_digester.py:21-51`](../../../tinycua/tinycua/loops/information_digester.py#L21-L51)). QueryAnalyst inserts it immediately before Worker when digestion is enabled and routes directly to Worker otherwise ([`query_analyst.py:98-134`](../../../tinycua/tinycua/loops/query_analyst.py#L98-L134)).

**[D] Result Reviewer.** Its instruction says to inspect artifacts, runtime-check behavior, match claims to acceptance criteria, reject unsupported claims, and approve only with no open findings ([`node_guidance.py:60-77`](../../../tinycua/tinycua/loops/node_guidance.py#L60-L77)). Worker reads the review flag and conditionally schedules review after execution ([`worker.py:154-164`](../../../tinycua/tinycua/loops/worker.py#L154-L164), [`worker.py:291-298`](../../../tinycua/tinycua/loops/worker.py#L291-L298), [`worker.py:327-334`](../../../tinycua/tinycua/loops/worker.py#L327-L334), [`worker.py:381-388`](../../../tinycua/tinycua/loops/worker.py#L381-L388)).

### Observed invocation counts

| Experiment | `tinycua` | `tinycua-nd` | `tinycua-nr` | `tinycua-nd-nr` | Trace evidence |
|---|---|---|---|---|---|
| 1 | D 0, E 0, R 0 | D 0, E 0, R 0 | D 0, E 0, R 0 | D 0, E 0, R 0 | All route `query_analyst -> response` ([full](../experiment-1/tinycua/stderr.log#L18-L30), [ND](../experiment-1/tinycua-nd/stderr.log#L18-L30), [NR](../experiment-1/tinycua-nr/stderr.log#L18-L30), [both off](../experiment-1/tinycua-nd-nr/stderr.log#L18-L30)). |
| 2 | D 1[4], E 6, R 6[19], 5A | D 0, E 20, R 20[84], 3A/7N/1Rp | D 1[8], E 8, R 0 | D 0, E 5, R 0 | [full](../experiment-2/tinycua/stderr.log#L253-L278), [ND](../experiment-2/tinycua-nd/stderr.log#L806-L870), [NR](../experiment-2/tinycua-nr/stderr.log#L296-L310), [both off](../experiment-2/tinycua-nd-nr/stderr.log#L186-L199) |
| 3 | D 1[4], E 8, R 8[23], 2A | D 0, E 6, R 6[30], no visible commit payload | D 1[6], E 2, R 0 | D 0, E 7, R 0 | [full](../experiment-3/tinycua/stderr.log#L386-L415), [ND](../experiment-3/tinycua-nd/stderr.log#L277-L301), [NR](../experiment-3/tinycua-nr/stderr.log#L82-L96), [both off](../experiment-3/tinycua-nd-nr/stderr.log#L228-L241) |
| 4 | D 1[5], E 8, R 8[48], 6A | D 0, E 7, R 7[47], 4A/2N | D 1[4], E 7, R 0 | D 0, E 6, R 0 | [full](../experiment-4/tinycua/stderr.log#L461-L490), [ND](../experiment-4/tinycua-nd/stderr.log#L431-L460), [NR](../experiment-4/tinycua-nr/stderr.log#L359-L373), [both off](../experiment-4/tinycua-nd-nr/stderr.log#L200-L213) |
| 5 | D 1[3], E 8, R 8[26], 6A | D 0, E 17, R 17[85], 9A/7N | D 1[3], E 7, R 0 | D 0, E 8, R 0 | [full](../experiment-5/tinycua/stderr.log#L378-L407), [ND](../experiment-5/tinycua-nd/stderr.log#L984-L1032), [NR](../experiment-5/tinycua-nr/stderr.log#L220-L234), [both off](../experiment-5/tinycua-nd-nr/stderr.log#L304-L317) |

The visible decision counts are lower bounds. **[D]** Some Reviewer invocations completed with tool calls but no visible decision payload, and large payloads are truncated in the text log. For example, experiment 3 no-Digester records Reviewer starts and decision-tool completion without exposing the decision body ([`experiment-3/tinycua-nd/stdout.log:111-149`](../experiment-3/tinycua-nd/stdout.log#L111-L149)). Reviewer and executor token usage is also absent from the captured usage summaries.

### Digester tool pattern

- **[D]** Across experiments 2-5, full TinyCUA produced 4 Digester invocations and 16 Digester tool-result events; no-Reviewer produced 4 invocations and 21 events. No-Digester variants produced none.
- **[D]** The common pattern was `read_file`, `list_files`, `enhanced_context_retrieval`, and `digest_information`, as shown in experiment 3 full ([`experiment-3/tinycua/stdout.log:26-35`](../experiment-3/tinycua/stdout.log#L26-L35)).
- **[D]** Experiment 2 no-Reviewer was the only observed Digester cell that expanded into four web searches and a URL fetch before emitting its digest ([`experiment-2/tinycua-nr/stdout.log:19-36`](../experiment-2/tinycua-nr/stdout.log#L19-L36)).
- **[I]** The one-call placement bounded direct Digester overhead, but a digest could still shape the downstream task decomposition and therefore total runtime.

### Reviewer decision pattern

- **[D]** Full TinyCUA produced visible approvals but no visible `needs_revision` payloads in experiments 2-5. No-Digester produced 16 visible approvals, 16 visible revisions, and one replan across 50 invocations.
- **[D]** In experiment 2 no-Digester, the Reviewer repeatedly rejected evidence work. The false claim that the task required three URLs **per model family** first appears explicitly at line 315 and recurs through the later rework loop; the log exposes seven `needs_revision` payloads and one `replan`, while some payloads self-report more accumulated cycles ([`experiment-2/tinycua-nd/stdout.log:312-372`](../experiment-2/tinycua-nd/stdout.log#L312-L372), [`experiment-2/tinycua-nd/stdout.log:539-586`](../experiment-2/tinycua-nd/stdout.log#L539-L586)). The actual task requires three distinct URLs total ([`experiment-2/workdir/TASK.md:23-29`](../../experiment-fixtures/experiments-list/experiment-2/workdir/TASK.md#L23-L29)). It eventually approved a documented compromise rather than satisfaction of its invented rule ([`experiment-2/tinycua-nd/stdout.log:755-795`](../experiment-2/tinycua-nd/stdout.log#L755-L795)).
- **[D]** In experiment 5 no-Digester, the Reviewer first approved substantial sections, later rejected the same 3,185-logical-line file as containing only one section or only a title, then approved it again ([`experiment-5/tinycua-nd/stdout.log:491-562`](../experiment-5/tinycua-nd/stdout.log#L491-L562)).
- **[I]** The Reviewer is sensitive to partial artifact views and generated task descriptions. Its repeated checks are not equivalent to a stable independent test oracle.

## Experiment 1: exact-response passthrough

| Configuration | Score | Pass | Runtime | Traversal |
|---|---:|---:|---:|---|
| `tinycua` | 1/1 | Yes | [8.59 s](../experiment-1/tinycua/result.json#L6-L16) | QueryAnalyst, Response |
| `tinycua-nd` | 1/1 | Yes | [8.41 s](../experiment-1/tinycua-nd/result.json#L6-L16) | QueryAnalyst, Response |
| `tinycua-nr` | 1/1 | Yes | [8.31 s](../experiment-1/tinycua-nr/result.json#L6-L16) | QueryAnalyst, Response |
| `tinycua-nd-nr` | 1/1 | Yes | [8.54 s](../experiment-1/tinycua-nd-nr/result.json#L6-L16) | QueryAnalyst, Response |

**[D]** Every cell routed to passthrough, returned exactly `Hello Reply`, created no tasks, and skipped both roles ([`experiment-1/tinycua/stderr.log:13-30`](../experiment-1/tinycua/stderr.log#L13-L30)). **[I]** Experiment 1 validates that the flags do not disrupt the short-response route; it provides no evidence about either role's quality because neither role executed.

## Experiment 2 case study: frontier LLM report

The task requires a fixed report structure, at least three named model families, at least three distinct source URLs total, six comparison dimensions, and benchmark-methodology caveats ([`experiment-2/workdir/TASK.md:10-31`](../../experiment-fixtures/experiments-list/experiment-2/workdir/TASK.md#L10-L31)). The evaluator additionally awards one point for each of twelve bundled reference-model names and makes any one such match a critical gate ([`experiment-2/eval/check.py:139-211`](../../experiment-fixtures/experiments-list/experiment-2/eval/check.py#L139-L211)).

| Configuration | Score / pass | Runtime | Artifact | Decisive evaluator result |
|---|---|---:|---|---|
| `tinycua` | 19/32, pass | [252.69 s](../experiment-2/tinycua/result.json#L6-L16) | 97-line report plus `research_scope.md` | Matched `Claude Fable 5`; missed bonus chapter, 11 other references, and reference coverage ([`result.json:139-255`](../experiment-2/tinycua/result.json#L139-L255)). |
| `tinycua-nd` | 21/32, pass | [2,706.65 s](../experiment-2/tinycua-nd/result.json#L6-L16) | 183-line report | Highest score; matched `GPT-5.6` and `Kimi K3`, added a bonus H2, missed reference coverage ([`result.json:139-255`](../experiment-2/tinycua-nd/result.json#L139-L255)). |
| `tinycua-nr` | 20/32, pass | [220.64 s](../experiment-2/tinycua-nr/result.json#L6-L16) | 159-line report | Matched three reference models but failed the three-URL check ([`result.json:62-235`](../experiment-2/tinycua-nr/result.json#L62-L235)). |
| `tinycua-nd-nr` | 16/32, fail | [191.44 s](../experiment-2/tinycua-nd-nr/result.json#L6-L17) | 199-line report | Exceeded threshold 12 but failed critical `model_relevancy` ([`result.json:139-257`](../experiment-2/tinycua-nd-nr/result.json#L139-L257)). |

### Artifact quality

- **[D] Full:** The report follows the required structure and cites multiple URLs, but its evidence table bundles leaderboard links rather than primary evidence, and many exact capability, cost, and context claims reuse the same generic sources ([`tinycua/workdir/report.md:13-45`](../experiment-2/tinycua/workdir/report.md#L13-L45)). It is concise and evaluator-compliant.
- **[D] No-Digester:** The main comparison is GPT-4o/o1, Gemini 2.0, and Claude 3.5, while hidden 2026 reference names only appear later in an "acceptable alternatives" description ([`tinycua-nd/workdir/report.md:5-17`](../experiment-2/tinycua-nd/workdir/report.md#L5-L17), [`tinycua-nd/workdir/report.md:144-165`](../experiment-2/tinycua-nd/workdir/report.md#L144-L165)). It labels unsupported prices as estimates and appends an erroneous claim that the task requires three URLs per family ([`tinycua-nd/workdir/report.md:24-32`](../experiment-2/tinycua-nd/workdir/report.md#L24-L32), [`tinycua-nd/workdir/report.md:93-113`](../experiment-2/tinycua-nd/workdir/report.md#L93-L113)).
- **[D] No-Reviewer:** The report covers three bundled reference names and all requested comparison dimensions, but `[1]`, `[2]`, and `[3]` name sources without providing three parseable URLs, which explains the evaluator failure for source citations ([`tinycua-nr/workdir/report.md:27-53`](../experiment-2/tinycua-nr/workdir/report.md#L27-L53), [`tinycua-nr/workdir/report.md:158-159`](../experiment-2/tinycua-nr/workdir/report.md#L158-L159)).
- **[D] Both-off:** The report is structurally complete but compares older Llama 3.1, Mixtral 8x7B, and Command R+, so it misses every bundled reference model. It also presents many uncited estimates as facts ([`tinycua-nd-nr/workdir/report.md:7-51`](../experiment-2/tinycua-nd-nr/workdir/report.md#L7-L51)).

### Interpretation

**[D]** Both individual-role cells pass while both-off fails in this fixture, but through different artifacts and evaluator-sensitive names. The Reviewer-on, Digester-off cell scored five points higher and ran 2,515 seconds longer than both-off while enforcing a requirement not present in `TASK.md`. **[I]** This association does not establish that review caused the added evaluator coverage or improved factual research quality.

## Experiment 3 case study: animated analog clock

The task requires one self-contained `clock.html`, current-time-derived hands, scheduled repeated updates, and clockwise movement ([`experiment-3/workdir/TASK.md:5-19`](../../experiment-fixtures/experiments-list/experiment-3/workdir/TASK.md#L5-L19)). The evaluator freezes browser time, captures Canvas/SVG geometry, advances time, and requires all nine categories ([`experiment-3/eval/check.py:24-94`](../../experiment-fixtures/experiments-list/experiment-3/eval/check.py#L24-L94), [`experiment-3/eval/check.py:248-297`](../../experiment-fixtures/experiments-list/experiment-3/eval/check.py#L248-L297)).

| Configuration | Score / pass | Runtime | Artifact | Decisive evaluator result |
|---|---|---:|---|---|
| `tinycua` | 5/9, fail | [324.75 s](../experiment-3/tinycua/result.json#L6-L17) | 237-line `clock.html` | Loads, surface, two nominal angle matches, and self-contained pass; hour and all movement checks fail ([`result.json:20-96`](../experiment-3/tinycua/result.json#L20-L96)). |
| `tinycua-nd` | 0/9, fail | [301.08 s](../experiment-3/tinycua-nd/result.json#L6-L17) | `clock.html/clock.html` | Required path is a directory; all checks fail ([`result.json:20-96`](../experiment-3/tinycua-nd/result.json#L20-L96)). |
| `tinycua-nr` | 0/9, fail | [196.10 s](../experiment-3/tinycua-nr/result.json#L6-L17) | `clock.html/clock.html` | Same directory-path failure ([`result.json:20-96`](../experiment-3/tinycua-nr/result.json#L20-L96)). |
| `tinycua-nd-nr` | 3/9, fail | [131.30 s](../experiment-3/tinycua-nd-nr/result.json#L6-L17) | 179-line `clock.html` | Loads, surface, self-contained pass; no hand or movement check passes ([`result.json:20-96`](../experiment-3/tinycua-nd-nr/result.json#L20-L96)). |

### False verification in the full-role cell

**[D]** Full TinyCUA computes `currentHandStates` inside the animation loop but then draws all hands from the initial `handStates` constant, so the rendered hands never update ([`tinycua/workdir/clock.html:156-217`](../experiment-3/tinycua/workdir/clock.html#L156-L217)). The Reviewer nevertheless approved it as having a smooth `requestAnimationFrame` update and satisfying all root criteria ([`tinycua/stdout.log:247-255`](../experiment-3/tinycua/stdout.log#L247-L255)). The deterministic browser evaluator then failed every movement category ([`tinycua/result.json:55-74`](../experiment-3/tinycua/result.json#L55-L74)).

**[D]** The two initial-angle points do not prove that the styled second and minute hands were correct. The evaluator's permissive `has_angle` helper accepts any center-originating segment at the requested angle, allowing TinyCUA's reversed second and minute geometries to cross-match each other's expected categories ([`experiment-3/eval/check.py:188-218`](../../experiment-fixtures/experiments-list/experiment-3/eval/check.py#L188-L218)).

**[I]** The Reviewer checked for the presence of time formulas and an animation loop but did not verify that updated state reached the draw calls. This is a concrete semantic false positive.

### Other artifact failures

- **[D]** No-Digester and no-Reviewer both explicitly reported the output as `/workspace/clock.html/clock.html`, not the required file path ([`tinycua-nd/stdout.log:94`](../experiment-3/tinycua-nd/stdout.log#L94), [`tinycua-nr/stdout.log:94`](../experiment-3/tinycua-nr/stdout.log#L94)). The no-Digester artifact also passes degree values to trigonometric functions expecting radians and references a global `secondAngle` rather than its first parameter ([`tinycua-nd/workdir/clock.html/clock.html:27-57`](../experiment-3/tinycua-nd/workdir/clock.html/clock.html#L27-L57), [`tinycua-nd/workdir/clock.html/clock.html:79-104`](../experiment-3/tinycua-nd/workdir/clock.html/clock.html#L79-L104)).
- **[D]** Both-off calculates three rotations but never passes them to `drawHand`; every hand is drawn with rotation zero. It also initializes `handThickness` from itself, which raises before hand drawing completes ([`tinycua-nd-nr/workdir/clock.html:49-69`](../experiment-3/tinycua-nd-nr/workdir/clock.html#L49-L69), [`tinycua-nd-nr/workdir/clock.html:129-166`](../experiment-3/tinycua-nd-nr/workdir/clock.html#L129-L166)).

### Interpretation

**[D]** Full TinyCUA earned the highest score, but no cell produced a working clock. The Reviewer did not catch a direct data-flow defect or the wrong-path artifact in no-Digester. **[I]** Experiment 3 provides no evidence that either role is sufficient for coding correctness; it instead shows the need for evaluator-equivalent browser execution before approval.

## Experiment 4 case study: Notion-like Python/SQLite app

The required public workflow is start through `PORT=8765 sh start.sh`, create/edit/delete selected text blocks through accessible controls, and retain data across reload and restart ([`experiment-4/workdir/TASK.md:5-29`](../../experiment-fixtures/experiments-list/experiment-4/workdir/TASK.md#L5-L29)). The evaluator copies the submission, starts it from that copy, drives the browser by accessible roles, inspects SQLite, and restarts the process ([`experiment-4/eval/check.py:266-341`](../../experiment-fixtures/experiments-list/experiment-4/eval/check.py#L266-L341)).

| Configuration | Score / pass | Runtime | Artifact | Decisive evaluator result |
|---|---|---:|---|---|
| `tinycua` | 1/9, fail | [929.91 s](../experiment-4/tinycua/result.json#L6-L17) | Flask/SQLite app | `start.sh` exists but exits 1; every runtime workflow check fails ([`result.json:20-96`](../experiment-4/tinycua/result.json#L20-L96)). |
| `tinycua-nd` | 3/9, fail | [769.23 s](../experiment-4/tinycua-nd/result.json#L6-L17) | Self-generating Flask app | App and Python process start; browser finds no visible accessible text field ([`result.json:20-96`](../experiment-4/tinycua-nd/result.json#L20-L96)). |
| `tinycua-nr` | 1/9, fail | [1,374.20 s](../experiment-4/tinycua-nr/result.json#L6-L17) | FastAPI/SQLite app | `start.sh` exits 2; all runtime workflow checks fail ([`result.json:20-96`](../experiment-4/tinycua-nr/result.json#L20-L96)). |
| `tinycua-nd-nr` | 1/9, fail | [269.64 s](../experiment-4/tinycua-nd-nr/result.json#L6-L17) | Flask-SQLAlchemy app | `start.sh` exits 127; all runtime workflow checks fail ([`result.json:20-96`](../experiment-4/tinycua-nd-nr/result.json#L20-L96)). |

### Full-role portability failure

**[D]** The full-role `start.sh` hard-codes `/workspace/venv`, `/workspace/requirements.txt`, and `/workspace/app.py`, while the evaluator deliberately copies the submission to another workspace before launch ([`tinycua/workdir/start.sh:13-28`](../experiment-4/tinycua/workdir/start.sh#L13-L28), [`experiment-4/eval/check.py:266-285`](../../experiment-fixtures/experiments-list/experiment-4/eval/check.py#L266-L285)). The final `app.py` also contains literal `\n` tokens between decorators and functions and drops the `blocks` table during initialization ([`tinycua/workdir/app.py:20-46`](../experiment-4/tinycua/workdir/app.py#L20-L46), [`tinycua/workdir/app.py:115-130`](../experiment-4/tinycua/workdir/app.py#L115-L130)). **[I]** These are independent startup and persistence blockers. The retained evaluator output gives exit code 1 but not enough child-process stderr to assign the immediate exit to only one of them.

**[D]** Six visible Reviewer payloads approved the full app, including a "Testing and Verification" approval claiming reload and restart persistence ([`tinycua/stdout.log:386-415`](../experiment-4/tinycua/stdout.log#L386-L415)). The evaluator could not start it. **[I]** Verification occurred in the original workspace assumptions rather than the deliverable's execution contract.

### No-Digester partial startup

**[D]** This was the only cell to expose a root page backed by Python. Its UI starts with an add button and keeps its only textarea inside a hidden editor overlay, so it does not provide the initially visible textbox expected by the public workflow ([`tinycua-nd/workdir/start.sh:92-121`](../experiment-4/tinycua-nd/workdir/start.sh#L92-L121)). More seriously, `start.sh` deletes the SQLite database on every invocation, contradicting restart persistence ([`tinycua-nd/workdir/start.sh:21-33`](../experiment-4/tinycua-nd/workdir/start.sh#L21-L33)). The Reviewer approved startup as preserving data and later approved the composed outcome after claimed API-level checks; the retained server log does not preserve a successful POST ([`tinycua-nd/stdout.log:142-175`](../experiment-4/tinycua-nd/stdout.log#L142-L175), [`tinycua-nd/stdout.log:317-368`](../experiment-4/tinycua-nd/stdout.log#L317-L368), [`tinycua-nd/workdir/server.log:11-48`](../experiment-4/tinycua-nd/workdir/server.log#L11-L48)).

### Remaining entrypoints

- **[D]** No-Reviewer also hard-codes `/workspace` for its database message, module import path, and app launch ([`tinycua-nr/workdir/start.sh:13-45`](../experiment-4/tinycua-nr/workdir/start.sh#L13-L45)).
- **[D]** Both-off invokes `uv pip install` without a system or virtual environment target, then relies on bare `python` and `flask`; the evaluator reports command-not-found exit 127 ([`tinycua-nd-nr/workdir/start.sh:1-16`](../experiment-4/tinycua-nd-nr/workdir/start.sh#L1-L16), [`tinycua-nd-nr/result.json:27-81`](../experiment-4/tinycua-nd-nr/result.json#L27-L81)).

### Interpretation

**[D]** No-Digester scored two points above the other cells only because it started and had a Python process. No role configuration completed any browser CRUD or persistence category. **[I]** The dominant failure is deliverable-level integration testing, not missing architecture or code volume. Reviewer value cannot be claimed when its strongest approvals contradict the evaluator's first executable check.

## Experiment 5 case study: neural-network study guide

The task asks for readable Markdown explaining six concepts, at least one code block, and a practical schedule or exercise; a linked table of contents is encouraged but optional ([`experiment-5/workdir/TASK.md:8-13`](../../experiment-fixtures/experiments-list/experiment-5/workdir/TASK.md#L8-L13)).

| Configuration | Score / pass | Runtime | Artifact | Only failed categories |
|---|---|---:|---|---|
| `tinycua` | 13/14, pass | [320.76 s](../experiment-5/tinycua/result.json#L6-L16) | 667 lines | Table of contents ([`result.json:41-46`](../experiment-5/tinycua/result.json#L41-L46)). |
| `tinycua-nd` | 13/14, pass | [1,642.91 s](../experiment-5/tinycua-nd/result.json#L6-L16) | 3,185 lines | Unique normalized headings ([`result.json:48-53`](../experiment-5/tinycua-nd/result.json#L48-L53)). |
| `tinycua-nr` | 13/14, pass | [774.45 s](../experiment-5/tinycua-nr/result.json#L6-L16) | 490 lines | Table of contents ([`result.json:41-46`](../experiment-5/tinycua-nr/result.json#L41-L46)). |
| `tinycua-nd-nr` | 12/14, pass | [581.08 s](../experiment-5/tinycua-nd-nr/result.json#L6-L16) | 3,083 lines | Table of contents and unique headings ([`result.json:41-53`](../experiment-5/tinycua-nd-nr/result.json#L41-L53)). |

### Concision and duplication

- **[D] Full:** The guide is compact and organized, but its TOC links "5. Positional Encoding" to `#6-positional-encoding`, causing the evaluator miss ([`tinycua/workdir/study-guide.md:1-15`](../experiment-5/tinycua/workdir/study-guide.md#L1-L15)). It also contains a technical code defect: the forward pass stores sigmoid output in `self.a1`, but the backward derivative uses `self.z1 * (1 - self.z1)` ([`tinycua/workdir/study-guide.md:63-86`](../experiment-5/tinycua/workdir/study-guide.md#L63-L86)).
- **[D] No-Digester:** The guide expands to 3,185 logical lines and repeats generic headings such as `### Table of Contents` five times and `#### Architecture` multiple times ([`tinycua-nd/workdir/study-guide.md:430-451`](../experiment-5/tinycua-nd/workdir/study-guide.md#L430-L451), [`tinycua-nd/workdir/study-guide.md:1335-1356`](../experiment-5/tinycua-nd/workdir/study-guide.md#L1335-L1356), [`tinycua-nd/workdir/study-guide.md:1805-1818`](../experiment-5/tinycua-nd/workdir/study-guide.md#L1805-L1818)). The deterministic evaluator catches duplicate normalized headings but otherwise gives full content credit.
- **[D] No-Reviewer:** This is the shortest guide and has the highest BLEU and ROUGE-L values among TinyCUA cells, though those lexical metrics are not pass gates ([`tinycua-nr/result.json:119-129`](../experiment-5/tinycua-nr/result.json#L119-L129)). Its heading is `## [Table of Contents](#table-of-contents)`, which does not match the evaluator's regex requiring literal `Table of Contents` or `Contents`; no TOC block is detected ([`tinycua-nr/workdir/study-guide.md:1-20`](../experiment-5/tinycua-nr/workdir/study-guide.md#L1-L20), [`experiment-5/eval/check.py:118-123`](../../experiment-fixtures/experiments-list/experiment-5/eval/check.py#L118-L123)).
- **[D] Both-off:** The artifact is several study guides concatenated together, including new H1 titles and repeated TOCs at lines 563 and 992 ([`tinycua-nd-nr/workdir/study-guide.md:550-578`](../experiment-5/tinycua-nd-nr/workdir/study-guide.md#L550-L578), [`tinycua-nd-nr/workdir/study-guide.md:988-1007`](../experiment-5/tinycua-nd-nr/workdir/study-guide.md#L988-L1007)). It still passes all required topic checks.

### Reviewer instability on large artifacts

**[D]** The no-Digester Reviewer made 17 passes and logged 85 tool-result events. It alternated between approving the complete file and claiming that only its first section or title existed ([`tinycua-nd/stdout.log:488-562`](../experiment-5/tinycua-nd/stdout.log#L488-L562)). Large reads were persisted with only previews in the immediate context ([`tinycua-nd/stdout.log:480`](../experiment-5/tinycua-nd/stdout.log#L480)). **[I]** Partial previews and the 3,185-line artifact coincided with contradictory judgments; the logs do not isolate which factor caused them.

### Interpretation

**[D]** All four cells satisfy the evaluator's required content gate. Full and no-Reviewer are far more concise than both Digester-disabled cells. Reviewer presence does not separate pass status: with Digester on, both cells score 13; with Digester off, Reviewer-on scores 13 and Reviewer-off scores 12. **[I]** This fixture provides the clearest descriptive support for digestion as context/structure compression and the clearest warning that review without stable artifact access can amplify work rather than improve the document.

## Cross-experiment artifact assessment

| Dimension | Digester-associated observation | Reviewer-associated observation |
|---|---|---|
| Required-path compliance | No consistent pattern: Digester-on no-Reviewer still produced a `clock.html` directory in experiment 3. | No consistent protection: no-Digester Reviewer also accepted the directory path. |
| Concision | Digester-enabled research artifacts were shorter in both experiments 2 and 5. | Reviewer-disabled experiment 5 was the shortest guide; Reviewer-enabled no-Digester was the longest. |
| Structural/evaluator coverage | Digester-on cells passed experiment 2 with and without Reviewer. | Reviewer-on no-Digester achieved the highest experiment-2 score, partly through evaluator-sensitive reference names and an extra chapter. |
| Executable verification | Digester did not prevent coding failures. | Reviewer approved non-moving clock code and non-portable startup scripts. |
| Runtime | One Digester invocation per nontrivial enabled cell. | Reviewer loops added 30 and 50 invocations across the two enabled configurations. |

**[I]** The observed roles solve different problems: Digester is a bounded context transformation, while Reviewer is a potentially recursive control loop. Treating them as symmetric binary features obscures their very different risk and cost profiles.

## Validity caveats

### One trial and stochastic sampling

**[D]** Every pair has exactly one trial, no retries, and no configured seed; temperature and top-p are also unset ([`run_metadata.json:754-764`](../run_metadata.json#L754-L764)). **[I]** A single divergent task decomposition can dominate a cell, as seen in the 20-pass experiment-2 no-Digester loop. There are no confidence intervals, variance estimates, or pass-at-k comparisons.

### Mixed result-generation revisions

**[D]** All five full TinyCUA cells were preserved from result-generation revision `81eb2977...`; all three ablation variants use `7b0d6f40...` ([`run_metadata.json:833-853`](../run_metadata.json#L833-L853)). The campaign records two runner migrations that explicitly preserved earlier full TinyCUA pairs while changing fixture-scoped evaluator images and evaluator volume mounts ([`run_metadata.json:766-830`](../run_metadata.json#L766-L830)).

**[I]** This is not a strict same-runner 2x2 factorial. The candidate TinyCUA image is held constant, but result-generation/evaluator orchestration revision is confounded with the full-role condition. Pairwise differences should be treated as descriptive until all four cells are rerun under one revision.

### Incomplete token telemetry and partial artifact views

**[D]** The text logs expose token usage for top-level nodes such as QueryAnalyst, Worker, ResultAggregation, and Response, but not complete per-invocation usage for Digester, TaskExecutor, or Reviewer. For example, experiment 5 no-Digester records aggregation usage after 17 Reviewer passes but no Reviewer token totals ([`tinycua-nd/stdout.log:582-601`](../experiment-5/tinycua-nd/stdout.log#L582-L601)).

**[D]** Large tool outputs are stored separately and represented by truncated previews in the main log ([`tinycua-nd/stdout.log:480`](../experiment-5/tinycua-nd/stdout.log#L480)). **[I]** Runtime and tool-call counts are measurable, but complete token cost is not. "Incomplete token" here is a telemetry limitation; it does not by itself prove model generation was cut off. Partial tool views coincided with contradictory Reviewer judgments, but the logs do not establish a sole cause.

### Evaluator scope and score comparability

- **[D]** Experiment 2 rewards exact hidden reference names and lexical reference coverage, not source truth. It can fail above threshold because model relevancy is critical.
- **[D]** Experiments 3 and 4 use strong executable gates, and all four cells fail them.
- **[D]** Experiment 5's topic checks are presence-based, so duplicated or technically flawed educational content can pass.
- **[I]** Raw point differences across experiments do not measure one common quality construct. Pass/fail and artifact inspection are more interpretable than summed score.

## Conclusion

**[D]** The campaign does not identify a universally superior role configuration. Full, no-Digester, and no-Reviewer tie on pass count; both-off loses one additional research fixture. Full TinyCUA leads experiment 3's partial score, no-Digester leads experiments 2 and 4, and all three single-role/full variants tie in experiment 5.

**[I]** The most defensible operational reading is:

1. Do not claim either role as a default quality improvement from this campaign.
2. Replace routine Reviewer approval with a mandatory task-appropriate final check against the exported artifact; invoke review only to diagnose failed evidence.
3. Rerun all four variants under one result-generation revision with multiple fixed seeds and semantic-quality checks before making a default-role or performance claim.

Until that rerun, these results support hypotheses about context compression, review-loop failure modes, and role interaction. They do not support a practical quality claim for either role.
