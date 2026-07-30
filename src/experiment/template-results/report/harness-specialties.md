# Harness Specialties Supported by the Controlled Evaluations

[Report index](README.md) | [Evaluator validity](evaluator-validity-and-artifact-quality.md) | [Why orchestration did not improve quality](why-orchestration-did-not-improve-quality.md) | [Reviewer limitations](reviewer-verification-limitations.md) | [New-harness comparison](new-harness-comparison.md) | [TinyCUA ablations](tinycua-ablation.md) | [Fixture vs prototype](fixture-vs-prototype-attribution.md)

## Question

Do the controlled evaluations provide evidence that any harness is especially good at a particular kind of work?

The answer is **yes for narrow observed capabilities**, but not for universal harness quality. Each harness ran once per fixture without a seed or retry. Harness prompts, tools, permissions, and thinking settings differ (`src/experiment/template-results/run_metadata.json:731-764`).

Evidence labels:

- **[D] Direct:** recorded in logs, artifacts, deterministic results, or evaluator source.
- **[I] Inference:** a bounded interpretation of direct evidence.
- **Measured specialty:** directly distinguished by an evaluator category or failure frontier.
- **Observed specialty:** supported by logs/artifacts but not independently scored.
- **Not established:** plausible but unsupported by this campaign.

## Result overview

| Harness | Experiment 2 | Experiment 3 | Experiment 4 | Experiment 5 | Narrowest defensible profile |
|---|---:|---:|---:|---:|---|
| TinyCUA | 19/32 pass | 5/9 fail | 1/9 fail | 13/14 pass | Compact checklist coverage; weak executable and semantic verification. |
| Hermes | 16/32 fail | 9/9 pass | 1/9 fail | 14/14 pass | Strong direct clock implementation; broad but technically weak documentation. |
| OpenCode | 17/32 fail | 3/9 fail | 1/9 fail | 13/14 pass | Strongest observed direct web-acquisition loop; unreliable factual synthesis. |
| OpenClaw | 17/32 fail | 3/9 fail | 3/9 fail | 2/14 fail | Best exported startup portability in Experiment 4; weakest completion reliability. |

Source: `src/experiment/template-results/outcomes.json` and each pair's `result.json`.

This table does not create an overall rank. The fixtures measure different constructs, and Experiment 2 includes hidden lexical gates.

## Specialty summary

| Candidate specialty | Best-supported harness | Confidence | What the evidence proves |
|---|---|---|---|
| Direct internet acquisition | OpenCode | Moderate | It recovered from empty search output, queried SearXNG directly, and fetched several pages successfully. |
| Hidden-evaluator vocabulary alignment | TinyCUA | High for this run | It alone mentioned a bundled reference model and therefore passed Experiment 2's critical gate. |
| Concise checklist synthesis | TinyCUA | Moderate | Its 97-line report covered all non-optional visible requirements and produced a complete compact artifact. |
| Conventional clock implementation | Hermes | High | It alone passed all nine browser-observed clock categories. |
| Exported application startup | OpenClaw | High | All full harnesses had `start.sh`; OpenClaw alone also passed application-start and Python-process checks. |
| Long-form structural breadth | Hermes | High for Experiment 5 | It produced the longest guide and alone passed all 14 structural categories; static technical quality was worse. |
| Local API/tool-loop verification | OpenCode | Moderate | It repeatedly launched and exercised APIs, though it missed exported-path behavior. |

## Experiment 2: internet acquisition versus synthesis

### What the evaluator actually rewards

The visible task requires a fixed report structure, at least three model families, URLs, six comparison dimensions, and benchmark limitations (`src/experiment/experiment-fixtures/experiments-list/experiment-2/workdir/TASK.md:10-31`).

The evaluator adds fourteen hidden/reference checks:

- one critical `model_relevancy` gate;
- twelve exact bundled model-name checks; and
- one lexical reference-coverage check.

Those names live in evaluator-only evidence (`src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/evidence.json:2-14`). In `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py`, `model_relevancy` is declared critical at lines 13-18, tolerant matching is defined at lines 59-80 and 190, critical failure is enforced at lines 116-119, and the literal/BLEU reference checks are at lines 191-205.

### Visible versus hidden score

| Harness | Prompt-visible checks | Hidden/reference checks | Task integrity | Total |
|---|---:|---:|---:|---:|
| TinyCUA | 16/17 | 2/14 | 1/1 | 19/32 |
| Hermes | 15/17 | 0/14 | 1/1 | 16/32 |
| OpenCode | 16/17 | 0/14 | 1/1 | 17/32 |
| OpenClaw | 16/17 | 0/14 | 1/1 | 17/32 |

The 17 visible checks include the optional extra-chapter bonus. Excluding that optional point, TinyCUA, OpenCode, and OpenClaw satisfy all 16 required visible checks. Hermes misses literal URL citation.

**[D]** TinyCUA passes because `Claude Fable 5` supplies the critical hidden relevance match. It misses eleven of twelve reference names and the lexical reference-coverage point (`src/experiment/template-results/experiment-2/tinycua/result.json:139-255`).

**[I]** TinyCUA's pass is evidence of successful evaluator-vocabulary alignment and checklist synthesis. It is not proof of generally superior research.

### Information acquisition

#### OpenCode: strongest observed acquisition loop

**[D]** OpenCode reacts to empty SearXNG output by querying the API directly, obtains search results, and successfully fetches BenchLM plus additional pages (`src/experiment/template-results/experiment-2/opencode/stdout.log:12-53`; runtime activity in `src/experiment/template-results/experiment-2/opencode/stderr.log:39-103`).

Its final report contains detailed deployment concerns such as evidence confidence, licensing, hardware cost, quantization, and operational trade-offs (`src/experiment/template-results/experiment-2/opencode/workdir/report.md:5-77,149-164`). Static source audit also finds serious errors, including confusing context length with parameter count, incorrectly describing Llama 3.1 405B as MoE, and adding unsourced deployment costs (`evaluator-validity-and-artifact-quality.md#opencode-most-current-retrieval-unreliable-synthesis`).

**[I]** This is the strongest evidence for “good at acquiring information from the internet” in this campaign. It is not evidence of reliable research synthesis: current retrieval and factual accuracy diverged.

#### TinyCUA: functional but smaller acquisition loop

**[D]** Full TinyCUA successfully performs three SearXNG searches during report execution (`src/experiment/template-results/experiment-2/tinycua/stderr.log:81-85`; tool results at `src/experiment/template-results/experiment-2/tinycua/stdout.log:122-126`). Its concise report cites multiple current-looking aggregation sources and uniquely intersects the hidden reference vocabulary.

The report is not fully coherent: its Meta/Llama discussion uses Grok and MiniMax evidence, attaching evidence from other families to the Llama section (`src/experiment/template-results/experiment-2/tinycua/workdir/report.md:39-45`).

**[I]** TinyCUA is better described as effective at **compressing research into a required structure** than as the strongest internet gatherer.

#### Hermes: search with extraction limitations

**[D]** Hermes actively searches and obtains useful initial links, but later searches are empty and `web_extract` repeatedly reports that its SearXNG backend is search-only (`src/experiment/template-results/experiment-2/hermes/stdout.log:81-220,241-315,365-423`). It falls back to model knowledge.

Its report is broad and has coherent benchmark caveats, but it centers 2024-2025 model families and contains unsupported exact values. Its source section names domains without literal URL schemes (`src/experiment/template-results/experiment-2/hermes/workdir/report.md:5-31,92-129,166-173`).

**[I]** Hermes demonstrates resilient fallback synthesis, not superior live acquisition.

#### OpenClaw: productive fallback despite unavailable search

**[D]** OpenClaw warns that its configured SearXNG provider/plugin is unavailable. Web-search calls fail and direct fetches return 404 pages (`src/experiment/template-results/experiment-2/openclaw/stdout.log:8-18`; `src/experiment/template-results/experiment-2/openclaw/stderr.log:10-25,296-297`).

It still produces a readable report from model knowledge, but it is explicitly centered on 2023-2024 models (`src/experiment/template-results/experiment-2/openclaw/workdir/report.md:3-23`).

**[I]** OpenClaw shows fallback completion under tool failure, but this run provides negative evidence for its configured internet-acquisition path.

### Experiment 2 conclusion

- **Best observed web acquisition:** OpenCode.
- **Best hidden-evaluator alignment:** TinyCUA.
- **Broadest conventional fallback synthesis:** Hermes.
- **Most resilient artifact completion despite broken search:** OpenClaw.
- **Factually reliable report:** none; all four contain material unsupported, stale, or false claims.

## Experiment 3: why Hermes alone succeeds

The evaluator freezes time, executes scheduled callbacks, intercepts rendered Canvas/SVG geometry, and checks exact hand positions and clockwise changes. Every category is critical (`src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:12-94,221-295`).

### Hermes: correct direct geometry

**[D]** Hermes rereads time every frame, includes fractional minute/hour progress, converts clock angles from twelve o'clock with `angle - Math.PI / 2`, and recursively schedules `requestAnimationFrame` (`src/experiment/template-results/experiment-3/hermes/workdir/clock.html:33-39,90-134`). It passes all nine categories (`src/experiment/template-results/experiment-3/hermes/result.json:18-97`).

Hermes performs a browser check, but the retained check only establishes that the page loads and has the expected title (`src/experiment/template-results/experiment-3/hermes/stderr.log:250-266`). The external evaluator—not Hermes' self-report—proves correct movement.

**[I]** Hermes' specialty here is not a more sophisticated planning system. It generated a compact conventional implementation whose state flow, coordinate baseline, and animation loop were all correct.

### Why the other implementations fail

| Harness | Root implementation defect | Evaluator consequence |
|---|---|---|
| TinyCUA | Computes fresh `currentHandStates` but draws stale outer `handStates`; orientation is reversed (`workdir/clock.html:72-110,156-217`). | Hour and all movement checks fail. Two initial points may be permissive cross-matches. |
| OpenCode | Draws from a downward baseline while applying angles defined for an upward baseline (`workdir/clock.html:79-133`). | 180-degree offset; all hand/movement checks fail. |
| OpenClaw | Omits the 90-degree clock-axis offset and schedules only one callback (`workdir/clock.html:84-126`). | Wrong initial geometry and no continuing movement. |

Paths are under `src/experiment/template-results/experiment-3/<harness>/`.

**[I]** Experiment 3 supports a narrow conclusion: direct, conventional code outperformed more elaborate or narrated implementations. It does not establish that Hermes is generally better at coding.

## Experiment 4: is OpenClaw's 3/9 genuinely better?

### Yes for startup portability

**[D]** All four full harnesses pass `start_script`. OpenClaw alone also passes:

1. `application_starts`, meaning the application responds after export; and
2. `python_backend`, meaning the process group contains Python.

That makes OpenClaw the only full harness to clear all three startup layers.

Evidence: `src/experiment/template-results/experiment-4/openclaw/result.json:20-39`.

Its relative-path startup script genuinely launches in the evaluator's copied workspace (`src/experiment/template-results/experiment-4/openclaw/workdir/start.sh:6-18`).

Full TinyCUA clears only script existence. It has independent fatal defects:

- hard-coded construction paths (`src/experiment/template-results/experiment-4/tinycua/workdir/start.sh:13-28`);
- invalid literal `\n` tokens in Python (`src/experiment/template-results/experiment-4/tinycua/workdir/app.py:115-130`); and
- destructive table recreation on startup (`src/experiment/template-results/experiment-4/tinycua/workdir/app.py:20-46,138-141`).

OpenClaw's extra points are therefore not evaluator noise.

### No for end-user functionality

**[D]** All OpenClaw CRUD and persistence categories fail. Its editor and page-title textbox are hidden initially, while the empty-page state renders text without a page-creation control (`src/experiment/template-results/experiment-4/openclaw/workdir/app/templates/index.html:10-23`; `src/experiment/template-results/experiment-4/openclaw/workdir/app/static/js/app.js:29-48`).

The frontend also never calls page creation, confuses block indexes with database IDs, and does not persist textarea edits (`src/experiment/template-results/experiment-4/openclaw/workdir/app/static/js/app.js:119-180`; backend endpoints at `src/experiment/template-results/experiment-4/openclaw/workdir/app/app.py:45-62,124-213`).

The three points are correlated startup layers, not three working user features.

### Experiment 4 conclusion

> OpenClaw is demonstrably better at exported startup portability than full TinyCUA. Its 3/9 does not establish a better Notion-like product: both score zero on CRUD and persistence.

TinyCUA contains more intended UI/backend behavior and locally recorded API activity, but final exported code that cannot start is not a usable alternative. The evaluator appropriately prioritizes the public executable boundary.

## Experiment 5: why Hermes scores 14/14 and TinyCUA 13/14

### The measured difference is one TOC link

**[D]** Hermes' table-of-contents links target existing normalized headings (`src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:7-19`; `src/experiment/template-results/experiment-5/hermes/result.json:41-53`).

TinyCUA links “5. Positional Encoding” to `#6-positional-encoding` while its actual heading is `## 5. Positional Encoding` (`src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:3-11,255`; `src/experiment/template-results/experiment-5/tinycua/result.json:41-47`).

Both pass every substantive lexical category.

### Hermes is broader and statically less correct

**[D]** Hermes writes 1,236 lines versus TinyCUA's 667. It covers more fundamentals, optimizer material, implementation detail, exercises, resources, and quick-reference material (`src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:19-581,822-1236`).

The evaluator checks headings, required terms, code fences, and a practical plan. It does not execute code examples or evaluate factual/pedagogical quality (`src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:124-176`).

All three submitted guides contain code defects:

- TinyCUA uses nonexistent `np.sigmoid` and applies a sigmoid derivative to `z1` instead of the activation (`src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:50-98`).
- Hermes contains duplicated broken backpropagation, invalid optimizer abstractions, nonexistent `np.softmax`, incoherent attention shapes, invalid positional encoding/normalization, and a model that cannot update parameters (`src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:127-298,344-637,822-1135`).
- OpenCode has a stronger conceptual progression but undefined values, invalid multi-head interfaces, broken masks, and non-runnable exercises (`src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:72-81,225-285,346-512,574-632`).

### Experiment 5 conclusion

> Hermes is measurably broader and has the only valid table of contents. Static technical inspection reverses the deterministic ordering: TinyCUA and OpenCode occupy a similar quality band, both above Hermes. None is safe as an implementation guide without correction.

## Harness profiles

### TinyCUA

**Observed capabilities**

- Complete long-form artifact production.
- High visible-requirement coverage.
- Compact checklist-shaped synthesis.

**Supported weaknesses**

- Slowest full harness on every nontrivial fixture.
- Review frequently validates source intent instead of exported behavior.
- Integration defects survive repeated per-task approval.

**Not established**

- Superior internet gathering.
- Superior factual coherence.
- Superior executable correctness.

### Hermes

**Observed capabilities**

- Only fully correct clock in the controlled evaluator.
- Broadest and only structurally perfect Experiment 5 guide, though technically worse in static audit.
- Fastest on Experiments 2 and 4.
- Productive fallback synthesis when extraction fails.

**Supported weaknesses**

- After extraction failed, Hermes fell back to model knowledge and its report contained stale/unsupported claims; this run does not isolate extraction failure as their cause.
- Bash-specific startup fails the required `sh start.sh` interface.
- Long documentation includes unchecked code defects.

**Not established**

- General coding superiority.
- General semantic-document quality superiority.

### OpenCode

**Observed capabilities**

- Strongest observed direct search/fetch adaptation.
- Detailed deployment and operational coverage.
- Extensive local shell/API verification.

**Supported weaknesses**

- Local testing remains coupled to `/workspace` assumptions.
- Coordinate-system mistake defeats the clock.
- Research detail does not guarantee factual discipline.

**Not established**

- Highest factual accuracy.
- Portable application delivery.

### OpenClaw

**Observed capabilities**

- Only full-harness Experiment 4 app that starts after export.
- Can synthesize a report despite unavailable search.
- Fast on several tasks.

**Supported weaknesses**

- Broken configured search integration.
- Incomplete animation scheduling.
- No usable empty-state workflow in the app.
- Experiment 5 terminates for output length without creating an artifact.

**Not established**

- Better Notion-like functionality from its 3/9 score.
- Reliable long-form completion.

## Limits

- One unseeded trial per harness/fixture; no variance estimates.
- Different tool adapters and permission modes.
- OpenClaw alone has thinking explicitly disabled (`src/experiment/template-results/run_metadata.json:737-752`).
- Search backoff persists across sequential runs (`src/experiment/README.md:243-248`).
- No controlled semantic cross-verdict or learner study exists; the current semantic assessment is a sampled static audit.
- Experiment 2's hidden corpus measures lexical intersection, not research truth.
- Experiment 5's structural evaluator does not measure code correctness or pedagogy.

## Bottom line

The campaign supports narrow capabilities rather than a universal winner. OpenCode shows the strongest live acquisition loop but unreliable synthesis. TinyCUA shows compact checklist coverage and hidden-vocabulary alignment but no demonstrated quality benefit from decomposition/review. Hermes shows the best clock implementation but the weakest submitted guide in static technical inspection. OpenClaw shows the best exported startup portability without a working user flow. None is generally superior.
