# Full-Harness Comparison on Controlled Experiments 1-5

[Report index](README.md) | [Fixture vs prototype](fixture-vs-prototype-attribution.md) | [TinyCUA ablations](tinycua-ablation.md) | [Historical comparison](historical-comparison.md) | [Experiment harness](../../README.md)

## Scope

This report compares the full configurations of TinyCUA, Hermes, OpenCode, and OpenClaw. It does not include the TinyCUA no-digestion or no-review ablations.

Evidence labels:

- **[D] Direct evidence:** recorded metadata, evaluator output, logs, or submitted artifacts.
- **[I] Inference:** an interpretation of direct evidence, stated more cautiously than an observed fact.

The campaign used the same `qwen3.5-9b` model endpoint for all four harnesses. Harness versions were OpenCode 1.18.4, Hermes 0.16.0, OpenClaw 2026.7.1-2, and TinyCUA at commit `89d2402e5dd6626390e9c5e09b52a21898e0cf2c`. Temperature, top-p, and seed were unset. Each pair had one trial, no retries, and sequential execution. [D] `src/experiment/template-results/run_metadata.json:731-764`

That controls the base model but not the complete agent environment. The harnesses supplied different system prompts, orchestration, tool adapters, permission modes, and thinking settings. OpenClaw alone is explicitly recorded with `EXPERIMENT_OPENCLAW_THINKING=off`; the metadata does not establish one shared thinking mode across harnesses. [D] `src/experiment/template-results/run_metadata.json:737-752` The campaign documentation also describes OpenCode's permission bypass, Hermes's `--yolo` mode, and OpenClaw's full profile; it notes that SearXNG backoff persists between sequential invocations. [D] `src/experiment/README.md:235-253` The findings therefore compare complete harness behavior, not isolated prompting algorithms.

## Results At A Glance

`P` means the evaluator passed the submission; `F` means it failed. Raw scores are only comparable within the same experiment because the denominators and checks differ.

| Experiment | TinyCUA | Hermes | OpenCode | OpenClaw |
|---|---:|---:|---:|---:|
| 1. Exact greeting | 1/1 P | 1/1 P | 1/1 P | 1/1 P |
| 2. Frontier LLM report | 19/32 P | 16/32 F | 17/32 F | 17/32 F |
| 3. Analog clock | 5/9 F | 9/9 P | 3/9 F | 3/9 F |
| 4. Notion-like app | 1/9 F | 1/9 F | 1/9 F | 3/9 F |
| 5. Neural-network guide | 13/14 P | 14/14 P | 13/14 P | 2/14 F |
| Passed fixtures | 3/5 | 3/5 | 2/5 | 1/5 |

The source of each score and pass state is the checked-in aggregate. [D] `src/experiment/template-results/outcomes.json:2-235`

The headline is not that one harness won. TinyCUA and Hermes each passed three fixtures, but on different work: TinyCUA alone passed the evaluator's unusual research relevancy gate, while Hermes alone rendered an evaluator-correct clock. OpenCode produced substantial artifacts but missed critical hidden or deployment constraints. OpenClaw was the only app submission that actually started after export, yet it failed the initial browser workflow and produced no study guide after a length-truncated turn. [I]

## Runtime

The following values are prompt-to-finish seconds, before evaluator scoring, from each pair's `result.json`.

| Experiment | TinyCUA | Hermes | OpenCode | OpenClaw | Fastest |
|---|---:|---:|---:|---:|---|
| 1 | 8.59 | 14.88 | 7.08 | 11.27 | OpenCode |
| 2 | 252.69 | 85.28 | 106.02 | 90.60 | Hermes |
| 3 | 324.75 | 72.74 | 103.17 | 47.15 | OpenClaw |
| 4 | 929.91 | 137.30 | 518.96 | 231.83 | Hermes |
| 5 | 320.76 | 181.94 | 108.43 | 101.28 | OpenClaw |

[D] Experiment 1 runtime fields: `src/experiment/template-results/experiment-1/tinycua/result.json:6-8`, `src/experiment/template-results/experiment-1/hermes/result.json:6-8`, `src/experiment/template-results/experiment-1/opencode/result.json:6-8`, `src/experiment/template-results/experiment-1/openclaw/result.json:6-8`

[D] Experiment 2 runtime fields: `src/experiment/template-results/experiment-2/tinycua/result.json:6-8`, `src/experiment/template-results/experiment-2/hermes/result.json:6-8`, `src/experiment/template-results/experiment-2/opencode/result.json:6-8`, `src/experiment/template-results/experiment-2/openclaw/result.json:6-8`

[D] Experiment 3 runtime fields: `src/experiment/template-results/experiment-3/tinycua/result.json:6-8`, `src/experiment/template-results/experiment-3/hermes/result.json:6-8`, `src/experiment/template-results/experiment-3/opencode/result.json:6-8`, `src/experiment/template-results/experiment-3/openclaw/result.json:6-8`

[D] Experiment 4 runtime fields: `src/experiment/template-results/experiment-4/tinycua/result.json:6-8`, `src/experiment/template-results/experiment-4/hermes/result.json:6-8`, `src/experiment/template-results/experiment-4/opencode/result.json:6-8`, `src/experiment/template-results/experiment-4/openclaw/result.json:6-8`

[D] Experiment 5 runtime fields: `src/experiment/template-results/experiment-5/tinycua/result.json:6-8`, `src/experiment/template-results/experiment-5/hermes/result.json:6-8`, `src/experiment/template-results/experiment-5/opencode/result.json:6-8`, `src/experiment/template-results/experiment-5/openclaw/result.json:6-8`

TinyCUA was the slowest harness on every nontrivial fixture: 3.0x the fastest time on experiment 2, 6.9x on experiment 3, 6.8x on experiment 4, and 3.2x on experiment 5. [D] `src/experiment/template-results/experiment-2/tinycua/result.json:6-16`, `src/experiment/template-results/experiment-3/tinycua/result.json:6-16`, `src/experiment/template-results/experiment-4/tinycua/result.json:6-16`, `src/experiment/template-results/experiment-5/tinycua/result.json:6-16`

This is separate from new-versus-old TinyCUA duration. The earlier campaign recorded TinyCUA at 5.4, 1,135.0, 584.7, 8,394.9, and 3,004.3 seconds across experiments 1-5. [D] `src/experiment/evaluation-results/report.md:175-196` The new full TinyCUA durations are smaller by ratios of approximately 4.5x, 1.8x, 9.0x, and 9.4x on experiments 2-5. Because prompts, acceptance criteria, runner behavior, and work scope changed, those ratios are not an isolated optimization estimate. TinyCUA is substantially less slow relative to its old snapshot while remaining the slowest current harness on substantial work. [I]

## Artifact Volume

Line, word, and byte counts were computed with `wc -l -w -c` over the checked-in primary artifacts. They measure output volume, not correctness.

| Experiment 2 report | Lines | Words | Bytes |
|---|---:|---:|---:|
| TinyCUA | 97 | 1,181 | 10,691 |
| Hermes | 174 | 1,830 | 13,772 |
| OpenCode | 239 | 2,374 | 18,442 |
| OpenClaw | 176 | 1,674 | 12,332 |

[D] `src/experiment/template-results/experiment-2/tinycua/workdir/report.md:1-97`, `src/experiment/template-results/experiment-2/hermes/workdir/report.md:1-175`, `src/experiment/template-results/experiment-2/opencode/workdir/report.md:1-239`, `src/experiment/template-results/experiment-2/openclaw/workdir/report.md:1-176`

| Experiment 3 clock | Lines | Words | Bytes |
|---|---:|---:|---:|
| TinyCUA | 237 | 892 | 8,473 |
| Hermes | 137 | 506 | 4,054 |
| OpenCode | 139 | 417 | 4,658 |
| OpenClaw | 129 | 431 | 4,016 |

[D] `src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:1-237`, `src/experiment/template-results/experiment-3/hermes/workdir/clock.html:1-137`, `src/experiment/template-results/experiment-3/opencode/workdir/clock.html:1-139`, `src/experiment/template-results/experiment-3/openclaw/workdir/clock.html:1-129`

| Experiment 5 guide | Lines | Words | Bytes |
|---|---:|---:|---:|
| TinyCUA | 667 | 3,077 | 25,281 |
| Hermes | 1,236 | 4,473 | 42,001 |
| OpenCode | 669 | 2,825 | 24,624 |
| OpenClaw | 0 | 0 | 0 |

[D] `src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:1-667`, `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:1-1236`, `src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:1-669`; OpenClaw's exported workspace has no `study-guide.md`, as confirmed by `src/experiment/template-results/experiment-5/openclaw/result.json:20-25`.

Experiment 4 has no comparable single artifact because each harness chose a different application layout. A `du -sb` count over the four exported `src/experiment/template-results/experiment-4/<harness>/workdir/` directories gave 149,512 bytes for TinyCUA, 30,180 for Hermes, 53,082 for OpenCode, and 82,457 for OpenClaw. These totals include databases, harness state, fixture files, and auxiliary files, so they are inventory measurements only. TinyCUA's largest workspace still scored 1/9; OpenClaw's smaller, launchable but workflow-incomplete app scored 3/9. [D] `src/experiment/template-results/experiment-4/tinycua/result.json:18-96`, `src/experiment/template-results/experiment-4/openclaw/result.json:18-96`

## Experiment 1: Exact Greeting

All four harnesses returned the required exact `Hello Reply` and passed the only check. [D] `src/experiment/template-results/experiment-1/tinycua/result.json:18-33`, `src/experiment/template-results/experiment-1/hermes/result.json:18-33`, `src/experiment/template-results/experiment-1/opencode/result.json:18-33`, `src/experiment/template-results/experiment-1/openclaw/result.json:18-33`

OpenCode was fastest at 7.08 seconds; Hermes was slowest at 14.88 seconds. The fixture establishes that each harness can obey a constrained conversational response, but one exact string gives no evidence about planning, tool use, coding, or factual reliability. [I]

## Experiment 2: Research Under A Hidden Relevancy Gate

### What the evaluator measured

The visible task requested a current frontier-model report with fixed headings, a model table, at least three model families and source URLs, six comparison dimensions, and benchmark limitations. The evaluator additionally treated `model_relevancy` as critical and required at least one exact model name from an evaluator-only corpus. A submission could exceed the 12-point threshold and still fail this gate. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py:13-28`, `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py:59-80`, `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py:139-210`

The bundled corpus names GPT-5.5, several GPT-5.6 variants, Claude Fable 5, Claude Opus 4.8, Claude Sonnet 5, Kimi K3, GLM 5.2, Gemini 3.5, and Gemini 3.6 Flash. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/evidence.json:2-21` None of the reports achieved the evaluator's 8.0 BLEU-1 reference-coverage bonus, and TinyCUA named only one of the twelve exact reference models. [D] `src/experiment/template-results/experiment-2/tinycua/result.json:139-235`

### TinyCUA

TinyCUA created a separate `research_scope.md`, decomposed the deliverable, searched for current sources, wrote the report, and repeatedly routed sections through Result Reviewer checks. [D] `src/experiment/template-results/experiment-2/tinycua/stdout.log:30-106`, `src/experiment/template-results/experiment-2/tinycua/stdout.log:108-143`, `src/experiment/template-results/experiment-2/tinycua/stdout.log:145-226`

Its compact report covered the requested dimensions and cited multiple URLs. Crucially, it named `Claude Fable 5`, which matched the hidden corpus and satisfied the critical gate; that one exact match made its 19/32 score a pass. [D] `src/experiment/template-results/experiment-2/tinycua/workdir/report.md:13-29`, `src/experiment/template-results/experiment-2/tinycua/result.json:139-187`, `src/experiment/template-results/experiment-2/tinycua/result.json:245-255`

The pass should not be read as broad current-model coverage. The report omitted eleven of twelve reference models, mixed purported 2026 Claude names with Gemini 1.5 and Llama 3.x families, and relied heavily on third-party leaderboard summaries. [D] `src/experiment/template-results/experiment-2/tinycua/workdir/report.md:17-45` TinyCUA best aligned with the evaluator's hidden vocabulary, but the deterministic score does not establish that its factual claims were the most accurate. [I]

### Hermes

Hermes produced a structured 174-line report with the widest conventional cross-provider model-family comparison: GPT, Claude, Gemini, Llama, Qwen, and Mistral. Its benchmark-interpretation section directly discussed task alignment, prompt sensitivity, tool integration, saturation, reproducibility, and contamination. [D] `src/experiment/template-results/experiment-2/hermes/workdir/report.md:5-31`, `src/experiment/template-results/experiment-2/hermes/workdir/report.md:92-129`

Its search behavior was active but constrained. Initial searches returned useful benchmark links, later model-specific searches returned no results, and URL extraction failed because Hermes's configured SearXNG backend was search-only. [D] `src/experiment/template-results/experiment-2/hermes/stdout.log:74-162`, `src/experiment/template-results/experiment-2/hermes/stdout.log:224-290`, `src/experiment/template-results/experiment-2/hermes/stdout.log:241-256`

The artifact then fell back to 2024-2025 models and several unsupported or internally inconsistent numerical claims. It listed source domains without literal `http://` or `https://` URLs in its source section, so the evaluator denied the URL point; more importantly, it named none of the bundled models and failed the critical relevancy gate despite scoring 16, above the nominal threshold. [D] `src/experiment/template-results/experiment-2/hermes/workdir/report.md:5-22`, `src/experiment/template-results/experiment-2/hermes/workdir/report.md:166-173`, `src/experiment/template-results/experiment-2/hermes/result.json:62-67`, `src/experiment/template-results/experiment-2/hermes/result.json:139-257`

### OpenCode

OpenCode produced the longest report and used direct shell searches, SearXNG API calls, and web fetches before writing. [D] `src/experiment/template-results/experiment-2/opencode/stderr.log:39-103` It focused heavily on open-weight July 2026 candidates, evidence confidence intervals, licenses, hardware costs, quantization, and deployment trade-offs. [D] `src/experiment/template-results/experiment-2/opencode/workdir/report.md:5-36`, `src/experiment/template-results/experiment-2/opencode/workdir/report.md:40-77`, `src/experiment/template-results/experiment-2/opencode/workdir/report.md:149-164`

This was substantial research behavior, but it did not intersect the evaluator's exact model list. OpenCode scored every visible structural and methodology category except the optional extra chapter, then failed `model_relevancy`; its 17/32 therefore failed overall. [D] `src/experiment/template-results/experiment-2/opencode/result.json:20-143`, `src/experiment/template-results/experiment-2/opencode/result.json:245-258` Length and operational detail did not compensate for a critical hidden lexical constraint. [I]

### OpenClaw

OpenClaw started with an explicit warning that its configured SearXNG search provider and plugin were unavailable. [D] `src/experiment/template-results/experiment-2/openclaw/stdout.log:8-18` It attempted command and web-fetch fallbacks, including a fetch that returned a 404 page. [D] `src/experiment/template-results/experiment-2/openclaw/stdout.log:108-145`, `src/experiment/template-results/experiment-2/openclaw/stderr.log:10-25`

It still produced a coherent 176-line report, but the content centered on 2023-2024 Llama 3, GPT-4o, Claude 3, Gemini 1.5, Mixtral, and Qwen2.5. [D] `src/experiment/template-results/experiment-2/openclaw/workdir/report.md:3-23` It passed visible structure, URLs, topic coverage, and methodology checks, scored 17/32, and failed only because no bundled model satisfied the critical relevancy category. [D] `src/experiment/template-results/experiment-2/openclaw/result.json:20-143`, `src/experiment/template-results/experiment-2/openclaw/result.json:245-258`

### Interpretation

TinyCUA's research workflow was the only one to land on an evaluator-recognized current name, but the pass hinged on one lexical hit. Hermes was broader on conventional closed models, OpenCode was deeper on open-weight deployment, and OpenClaw remained productive despite a broken primary search integration. [I] The experiment is useful for instruction following and search adaptation, but its pass/fail result is unusually sensitive to a hidden synthetic model list and should not be treated as a general research-quality ranking. [I]

## Experiment 3: Browser-Observed Clock Behavior

### What the evaluator measured

The evaluator replaced browser time with fixed timestamps, intercepted Canvas paths, collected SVG lines, controlled scheduled callbacks, and checked rendered hand angles at four times. Every category was critical. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:12-23`, `src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:24-94`, `src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:221-295`

This is a stronger behavioral test than searching source text for `Date` or `requestAnimationFrame`: it checks what Chromium actually draws.

### Hermes

Hermes passed 9/9 with the shortest successful implementation. It reads current seconds, minutes, and hours inside every draw, subtracts `PI/2` to align zero with twelve o'clock, and schedules the next frame. [D] `src/experiment/template-results/experiment-3/hermes/workdir/clock.html:90-134`, `src/experiment/template-results/experiment-3/hermes/result.json:18-97`

The implementation is simple rather than exhaustive, which helped here. One limitation remains outside the scored cases: the hour hand uses integer hours without a minute offset, so it steps by hour instead of moving continuously. [D] `src/experiment/template-results/experiment-3/hermes/workdir/clock.html:118-125` Hermes is evaluator-correct, not a claim of perfect analog-clock fidelity. [I]

### TinyCUA

TinyCUA created the largest clock file and repeatedly approved it as correct. Its executor and reviewer explicitly claimed current-time derivation, clockwise positive angles, and complete acceptance-criteria compliance. [D] `src/experiment/template-results/experiment-3/tinycua/stdout.log:227-257`

The artifact contradicts that review. `animate()` computes fresh `currentHandStates` but never uses it; all three rendered hands continue using the one-time outer `handStates` object. [D] `src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:109-140`, `src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:156-217` It also converts angles with `PI/2 - angle` while drawing through `cos`/`sin`, reversing the intended clock direction. [D] `src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:72-106`

The 5/9 result passed load, surface, self-containment, and nominal second/minute initial angles, but failed the hour angle and all motion checks. [D] `src/experiment/template-results/experiment-3/tinycua/result.json:18-98` The evaluator's `has_angle` function accepts any center-originating line at the expected angle rather than identifying hands by style. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:188-218` At 03:20:10, TinyCUA's reversed minute geometry is near the evaluator's expected second angle and its reversed second geometry is near the expected minute angle. The two initial hand points are therefore likely cross-matches, not evidence that those specific hands were correct. [I]

This is the clearest failure of TinyCUA's review architecture in the campaign: multiple review passes verified source-level intent but did not execute the deterministic behavior that mattered. [I]

### OpenCode

OpenCode recalculates time every frame and schedules correctly, but it draws each hand downward from the center before applying an angle measured as if the unrotated hand pointed upward. [D] `src/experiment/template-results/experiment-3/opencode/workdir/clock.html:79-133` The resulting 180-degree geometry error caused every initial and movement hand check to fail; only load, surface, and self-containment passed. [D] `src/experiment/template-results/experiment-3/opencode/result.json:18-99`

### OpenClaw

OpenClaw computes conventional degree values but maps them with `cos` and `sin` from the positive x-axis without the required 90-degree offset. It also schedules `updateClock` only once; the callback does not schedule another frame. [D] `src/experiment/template-results/experiment-3/openclaw/workdir/clock.html:84-126` Like OpenCode, it scored 3/9 for load, surface, and self-containment while failing all hand geometry and motion checks. [D] `src/experiment/template-results/experiment-3/openclaw/result.json:18-99`

### Interpretation

Hermes won by implementing the conventional geometry directly. TinyCUA spent 4.5x as long as Hermes, wrote 1.7x as many logical lines, and still allowed a stale-state bug through explicit review. OpenCode and OpenClaw both had plausible source structure but coordinate-system mistakes. [I] The experiment demonstrates why browser-observed behavior is more discriminating than artifact size, code narration, or self-reported verification.

## Experiment 4: Exported Application And Persistence

### What the evaluator measured

The task required `PORT=8765 sh start.sh`, a foreground Python backend, durable SQLite, and an accessible browser workflow for creating, selecting, editing, deleting, reloading, and restarting blocks. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-4/workdir/TASK.md:5-29`

The evaluator copied each submission to a new directory, invoked `sh start.sh` with a random port, inspected the process group for Python, drove the public UI by accessible roles and labels, searched SQLite files for browser-created text, then restarted the app. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:22-39`, `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:93-145`, `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:148-233`, `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:266-336`

All four submissions failed. The differences are in how early they failed.

### TinyCUA

TinyCUA scored only for having `start.sh`; the script exited before serving a page. [D] `src/experiment/template-results/experiment-4/tinycua/result.json:18-98`

The submission contains three independent blockers:

- `start.sh` hard-codes `/workspace` for the virtual environment, requirements, and app instead of resolving its exported directory. [D] `src/experiment/template-results/experiment-4/tinycua/workdir/start.sh:13-28`
- `app.py` contains literal `\n` tokens between decorators and function definitions, which are invalid Python source. [D] `src/experiment/template-results/experiment-4/tinycua/workdir/app.py:115-130`
- Even if startup were repaired, `init_db()` drops the `blocks` table every invocation, directly defeating restart persistence. [D] `src/experiment/template-results/experiment-4/tinycua/workdir/app.py:20-46`, `src/experiment/template-results/experiment-4/tinycua/workdir/app.py:138-141`

TinyCUA's reviewer nevertheless described the database as preserving data and approved the startup design. [D] `src/experiment/template-results/experiment-4/tinycua/stdout.log:119-155`, `src/experiment/template-results/experiment-4/tinycua/stdout.log:183-214` The 929.91-second run produced the largest workspace but did not clear the first executable gate. [I]

### Hermes

Hermes also scored only for the script's existence. The evaluator deliberately invokes `sh start.sh`, but the script uses Bash-only `${BASH_SOURCE[0]}`, `&>`, and `source`; it fails before launching Python under a POSIX shell. [D] `src/experiment/template-results/experiment-4/hermes/workdir/start.sh:1-18`, `src/experiment/template-results/experiment-4/hermes/result.json:18-98`

The backend also hard-codes `/workspace/data.db`, so relocation and durable data ownership would remain fragile after fixing the shell syntax. [D] `src/experiment/template-results/experiment-4/hermes/workdir/app.py:4-16` Hermes built the app quickly but did not test the exact documented `sh start.sh` interface. [I]

### OpenCode

OpenCode spent substantial effort repeatedly starting the app in `/workspace`, exercising CRUD endpoints with `curl`, inspecting SQLite, and restarting its development server. [D] `src/experiment/template-results/experiment-4/opencode/stderr.log:78-141`, `src/experiment/template-results/experiment-4/opencode/stderr.log:191-226`, `src/experiment/template-results/experiment-4/opencode/stderr.log:299-345`

The final app still fixes its database at `/workspace/workspace.db`. [D] `src/experiment/template-results/experiment-4/opencode/workdir/app.py:1-14` The exported evaluator copy runs elsewhere, and `start.sh` exited with code 1 before the root page appeared. [D] `src/experiment/template-results/experiment-4/opencode/result.json:18-98` OpenCode's API-focused local checks validated behavior in the construction directory but missed portability through the required public entrypoint. [I]

### OpenClaw

OpenClaw was the only harness to clear startup and process checks: the exported root responded and the process group contained Python. It scored 3/9. [D] `src/experiment/template-results/experiment-4/openclaw/result.json:18-39`

Its initial browser state has no usable path into the editor. The editor, page-title textbox, and Add Block button are inside a hidden `<main>`. When there are no pages, JavaScript renders only `Create a new page to get started`; it creates no page button or form. [D] `src/experiment/template-results/experiment-4/openclaw/workdir/app/templates/index.html:10-23`, `src/experiment/template-results/experiment-4/openclaw/workdir/app/static/js/app.js:29-48` The evaluator therefore found no visible accessible textbox and could not establish retained text for subsequent checks. [D] `src/experiment/template-results/experiment-4/openclaw/stderr.log:17-22`

There are deeper workflow defects behind that first failure. The backend exposes page creation, but the frontend never calls it. Rendered blocks use array indexes where the API expects database IDs, newly added blocks omit even that index, and text input only resizes the textarea without sending an update request. [D] `src/experiment/template-results/experiment-4/openclaw/workdir/app/app.py:45-62`, `src/experiment/template-results/experiment-4/openclaw/workdir/app/app.py:124-183`, `src/experiment/template-results/experiment-4/openclaw/workdir/app/static/js/app.js:119-180`

### Interpretation

Experiment 4 is the strongest end-to-end discriminator in the set. Three polished-looking submissions failed before a browser could connect because they assumed the construction path or shell. OpenClaw alone produced a relocatable, launchable app, but it failed the first empty-state interaction and would still have failed edit/delete persistence. [I] Testing APIs inside `/workspace` was not equivalent to testing the required exported product through `sh start.sh` and the rendered UI.

## Experiment 5: Study-Guide Thoroughness And Truncation

### What the evaluator measured

The evaluator awards one point each for file/title/section structure, a valid optional table of contents, unique headings, six literal topic terms, a fenced code example, a practical plan, and untouched `TASK.md`. Passing requires 9/14 plus three critical structural categories. It computes BLEU and ROUGE metrics but does not use them for pass/fail, execute code examples, or judge factual accuracy. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:13-20`, `src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:108-177`

### Hermes

Hermes produced by far the most expansive guide: 1,236 lines and 42,001 bytes. It covered neural-network components, activation and loss functions, backpropagation, optimizers, self-attention, positional encoding, normalization, encoder/decoder implementations, six practical exercises, a schedule, resources, and a concept checklist. [D] `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:19-302`, `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:302-581`, `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:822-1236`

Its web-search adapter returned zero results for several queries, so Hermes explicitly proceeded from model knowledge. [D] `src/experiment/template-results/experiment-5/hermes/stderr.log:108-137`, `src/experiment/template-results/experiment-5/hermes/stderr.log:172-223` Despite that, it was the only harness to satisfy all 14 structural checks. [D] `src/experiment/template-results/experiment-5/hermes/result.json:18-130`

The 14/14 score is structural, not a correctness certificate. Examples use nonexistent `np.softmax`, invalid transpose axes, undefined variables such as `x`, `ax`, `causal_mask`, and helper functions that are never supplied. [D] `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:344-395`, `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:426-435`, `src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:969-1005` Hermes was most thorough in topic and exercise volume, but that volume also carried the most unchecked pseudo-code. [I]

### TinyCUA

TinyCUA produced a 667-line guide after decomposing each required topic into reviewed subtasks. [D] `src/experiment/template-results/experiment-5/tinycua/stdout.log:31-106`, `src/experiment/template-results/experiment-5/tinycua/stdout.log:109-214` The guide includes mathematical explanations, implementation sketches, alternatives such as RoPE, encoder/decoder sections, a 12-week plan, daily exercises, resources, and capstone ideas. [D] `src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:21-338`, `src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:340-667`

It scored 13/14 and passed. The only evaluator failure was a broken table-of-contents target: the `5. Positional Encoding` link points to `#6-positional-encoding`. [D] `src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:3-11`, `src/experiment/template-results/experiment-5/tinycua/result.json:41-47` Review did not catch that small structural defect or code issues such as nonexistent `np.sigmoid` and a sigmoid derivative applied to `z1` rather than the activation. [D] `src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:50-98`

### OpenCode

OpenCode read the task, successfully ran two focused searches, and wrote its 669-line guide in one large write. [D] `src/experiment/template-results/experiment-5/opencode/stdout.log:8-23` It covered the requested material with a comparatively concise 10-week plan and linked external reading. [D] `src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:26-201`, `src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:201-536`, `src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:538-669`

It also scored 13/14 and passed, losing the same table-of-contents category because `5. Practical Study Plan` links to `#6-practical-study-plan`. [D] `src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:7-22`, `src/experiment/template-results/experiment-5/opencode/result.json:41-47` Its examples are not generally runnable either; for example, one attention block applies softmax to `attn_weights` before assigning it. [D] `src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:225-257`

### OpenClaw

OpenClaw produced no guide. The harness reported an incomplete turn with `stopReason=length`, then stated that the agent could not generate a response. [D] `src/experiment/template-results/experiment-5/openclaw/stderr.log:10`, `src/experiment/template-results/experiment-5/openclaw/stdout.log:108-120` The unavailable SearXNG plugin warning was also present, although the fatal event here was output-length truncation after one tool call. [D] `src/experiment/template-results/experiment-5/openclaw/stderr.log:10`, `src/experiment/template-results/experiment-5/openclaw/stdout.log:8-18`

The 2/14 score came from the untouched task file and vacuously unique empty heading set; `guide_exists` and every substantive content category failed. [D] `src/experiment/template-results/experiment-5/openclaw/result.json:18-132`

### Interpretation

Hermes was the most thorough writer and the only perfect structural scorer. TinyCUA and OpenCode delivered roughly half as many lines while covering every required topic. OpenClaw's failure was harness-level completion reliability rather than a low-quality submitted guide because no guide reached the workspace. [I]

All three passing guides contain code defects that the evaluator never executes. The experiment therefore supports claims about coverage, organization, and completion, but not that Hermes's 14/14 is semantically superior to the two 13/14 guides. [I]

## Cross-Harness Behavior

### TinyCUA

TinyCUA most visibly externalized planning and review and produced complete long-form deliverables, but every substantial run was the slowest. Only TinyCUA happened to include one name from the hidden experiment-2 model list in this unseeded trial; the data does not identify which orchestration component produced that match. [D] `src/experiment/template-results/experiment-2/tinycua/result.json:139-187`, `src/experiment/template-results/run_metadata.json:754-764` More importantly, Result Reviewer often checked whether source text appeared to satisfy a requirement rather than running the decisive behavior: it approved stale clock state, invalid startup code, destructive database initialization, and broken guide anchors. [D] `src/experiment/template-results/experiment-3/tinycua/stdout.log:227-257`, `src/experiment/template-results/experiment-4/tinycua/stdout.log:119-214`, `src/experiment/template-results/experiment-5/tinycua/result.json:41-47`

The architecture supplies systematic review, but this campaign shows that review quality depends on the verification surface. Repeated self-review without an independent executable oracle can repeat the same mistaken premise. [I]

### Hermes

Hermes was fastest on experiments 2 and 4, produced the only passing clock, and wrote the most comprehensive study guide. Its direct, conventional clock code outperformed more elaborate implementations. Conversely, it did not honor the exact POSIX startup interface in experiment 4, its research became stale when extraction failed, and its long guide accumulated many non-runnable examples. [I]

Hermes's strength in this sample was rapid, broad construction from model knowledge. Its weakness was limited validation of exact deployment contracts and generated code details. [I]

### OpenCode

OpenCode showed the clearest direct tool loop: search or inspect, write, then use shell/API checks. It produced the longest research report and spent the second-most time on the app. Yet it had no equivalent independent behavioral review: the report missed a hidden critical vocabulary, the clock had a coordinate-origin error, and extensive app API tests missed exported-path startup. [I]

Its work was often operationally detailed, but verification was too close to the environment and assumptions used during construction. [I]

### OpenClaw

OpenClaw was fastest on experiments 3 and 5 and was the only app submission to start after export. It also had the weakest completion record: only the greeting passed, web search was misconfigured, clock geometry was wrong, the app had no initial workflow, and experiment 5 ended on a length-truncated turn without an artifact. [D] `src/experiment/template-results/experiment-2/openclaw/stdout.log:8-18`, `src/experiment/template-results/experiment-4/openclaw/result.json:18-96`, `src/experiment/template-results/experiment-5/openclaw/stderr.log:10`

Its experiment-4 startup result shows useful portability, but tool availability and long-output completion were material harness risks in this campaign. [I]

## Evidence Limits

- **One unseeded trial:** Each pair ran once with no seed and no retries, so no pass-rate variance or statistical ranking is available. [D] `src/experiment/template-results/run_metadata.json:754-764`
- **Unequal tools:** The model was shared, but tool implementations were not. OpenClaw's configured SearXNG plugin was unavailable, Hermes could search but not extract through its SearXNG backend, and OpenCode and TinyCUA had working search paths in the observed runs. [D] `src/experiment/template-results/experiment-2/openclaw/stdout.log:8-18`, `src/experiment/template-results/experiment-2/hermes/stdout.log:241-256`, `src/experiment/template-results/experiment-2/opencode/stderr.log:39-96`, `src/experiment/template-results/experiment-2/tinycua/stdout.log:108-130`
- **Sequential external conditions:** Agents ran sequentially, and the shared search service intentionally preserves upstream backoff between invocations. Search freshness and availability may therefore differ by run order. [D] `src/experiment/template-results/run_metadata.json:242-244`, `src/experiment/README.md:243-248`
- **Different evaluator strength:** Experiments 3 and 4 execute browser behavior; experiments 2 and 5 primarily check structure and lexical coverage. A point has different semantic weight across fixtures. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:221-295`, `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:175-233`, `src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:124-176`
- **Hidden-corpus sensitivity:** Experiment 2's pass depends on exact evaluator-only model names. TinyCUA's single matching name passed the critical gate while three otherwise substantial reports failed it. [D] `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/evidence.json:2-14`, `src/experiment/template-results/experiment-2/tinycua/result.json:139-187`
- **Resumed campaign:** The campaign was resumed through runner migrations, and the metadata stamps full TinyCUA pairs with an older result-generation revision than the other full harness pairs. The checked-in aggregate treats them as compatible, but the exact effect of those preserved revisions cannot be inferred from artifacts alone. [D] `src/experiment/template-results/run_metadata.json:766-830`, `src/experiment/template-results/run_metadata.json:833-868`
- **Volume is not quality:** Line and byte counts describe artifact size. The largest clock failed, the largest app workspace never started, and the largest guide passed lexical checks while containing invalid examples.
- **No semantic judge used here:** Conclusions come from deterministic evaluator outcomes plus manual artifact/log inspection. They should not be generalized beyond these five tasks or this model/harness snapshot.

## Conclusion

No full harness dominated the campaign. TinyCUA and Hermes tied on fixture passes but succeeded for different reasons. TinyCUA most visibly externalized workflow decomposition and happened to match the hidden experiment-2 model list; Hermes was strongest at concise working clock code and broad documentation. OpenCode produced substantial, tool-driven artifacts but missed critical hidden and relocation assumptions. OpenClaw demonstrated the best exported startup behavior yet suffered the most severe tool and completion failures. [I]

The most defensible cross-experiment result is about verification, not raw score: executable, externally controlled checks exposed defects that source inspection and self-review repeatedly missed. Future comparisons should add seeded repeated trials, equalize tool surfaces, execute documentation code samples, and preserve the exported-entrypoint browser test as the standard for application work. [I]
