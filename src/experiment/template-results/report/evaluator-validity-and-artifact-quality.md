# Evaluator Validity and Actual Artifact Quality

[Report index](README.md) | [Why orchestration did not improve quality](why-orchestration-did-not-improve-quality.md) | [Harness specialties](harness-specialties.md) | [Reviewer limitations](reviewer-verification-limitations.md) | [New-harness comparison](new-harness-comparison.md)

## Central question

Can the deterministic evaluator justify this statement?

> A higher score means a higher-quality artifact.

**No.** Determinism means the same input produces the same score. It does not mean that the score measures the intended quality construct.

The controlled scores are best interpreted as **counts of fixture-specific acceptance signals**, not general quality, correctness, research currency, pedagogy, or usefulness.

## Reliability versus validity

- **Reliability/determinism:** repeated evaluation of the same artifact yields the same output.
- **Construct validity:** the output actually measures the quality being claimed.

An evaluator can be perfectly deterministic and still reward the wrong thing. Experiment 2 can reliably count hidden model-name strings without verifying research. Experiment 5 can reliably count topic words and code fences without checking whether the explanation or code is correct.

## Per-fixture validity

| Fixture | What a high score supports | What it does not support | Are partial scores quality-ordered? |
|---|---|---|---|
| 1, exact reply | The expected literal response pattern was detected. | Conversational quality, absence of extra output, reasoning quality. | Only as a narrow 0/1 compliance signal. |
| 2, frontier report | Structural, lexical, URL-presence, bundled-name, and integrity predicates. | Currency, factual correctness, source authority, claim-source entailment, arithmetic, coherence. | **No.** One point may mean an arbitrary H2, URL string, or hidden name. |
| 3, clock | At 9/9, Chromium observed expected hand geometry and same-hand motion in four frozen-time cases. | Visual polish, accessibility, numeral placement, general animation correctness. | Perfect/non-perfect is useful; partial ordering is weak because geometry checks overlap and cascade. |
| 4, app | At 9 functional points, one evaluator-defined startup/CRUD/reload/SQLite/restart workflow passed; two extra static signals record Python compilation and Ruff lint. | General product quality, Notion-like UX, robust modeling, security, maintainability. | Partial ordering is weak because startup and browser categories are dependent failure frontiers; static points do not prove a workflow. |
| 5, guide | Markdown structure, topic-word presence, code fences, plan words, and integrity. | Factual explanations, mathematical correctness, runnable code, pedagogy, coherence. | **No.** More predicates do not imply a better guide. |

Evaluator sources:

- Experiment 1: `src/experiment/experiment-fixtures/experiments-list/experiment-1/eval/run.sh:4-13`
- Experiment 2: `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py:139-211`
- Experiment 3: `src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:188-218,221-296`
- Experiment 4: `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:134-233,266-336`
- Experiment 5: `src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:124-170`

## Experiment 2: the score does not verify updated research

### What is scored

The 32 points include:

- file/title/chapter/table structure;
- raw URL count;
- family and comparison keywords;
- capability/cost/latency/context/safety words;
- methodology/reproducibility/contamination words;
- one critical hidden-model relevance gate;
- twelve exact hidden model-name checks;
- lexical reference coverage; and
- task integrity.

The critical hidden list is in `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/evidence.json:2-15`. The checker does not validate source authority, publication date, or claim support.

### Visible versus hidden results

| Harness | Prompt-visible checks | Hidden/reference checks | Integrity | Total |
|---|---:|---:|---:|---:|
| TinyCUA | 16/17 | 2/14 | 1/1 | 19/32 |
| Hermes | 15/17 | 0/14 | 1/1 | 16/32 |
| OpenCode | 16/17 | 0/14 | 1/1 | 17/32 |
| OpenClaw | 16/17 | 0/14 | 1/1 | 17/32 |

TinyCUA's two extra hidden points come from `model_relevancy` plus the `Claude Fable 5` category (`src/experiment/template-results/experiment-2/tinycua/result.json:139-187`). OpenCode's current real models receive no hidden points because they are outside the bundled list (`src/experiment/template-results/experiment-2/opencode/result.json:139-235`).

The score therefore rewards hidden vocabulary intersection rather than general currentness.

## Current research-artifact audit

The reports were manually checked against their claims, citations, and a representative set of external sources. None is publication-ready.

### TinyCUA: highest score, not best-established research

#### Supported/current elements

TinyCUA's BenchLM-derived claims about Claude Mythos 5, Opus 5, Fable 5, Grok 4.5, and MiniMax M3 are supported by current BenchLM pages and Anthropic's first-party announcement (`src/experiment/template-results/experiment-2/tinycua/workdir/report.md:24,29,41,45,51,74`).

#### Quality problems

- It presents Gemini 1.5 and Llama 3.1-3.3 as frontier families despite its own current source listing newer alternatives (`report.md:5,18-19,31-45`).
- The Meta/Llama section substitutes Grok and MiniMax evidence for Llama capability, cost, context, and evaluation evidence (`report.md:39-45`).
- It frames BenchLM, Artificial Analysis, and Klu as independent support even where the exact claim originates only from BenchLM (`report.md:49-58,74-76`).
- Generic leaderboard links do not substantiate several specific methodology claims (`report.md:64-72`).

Paths above are under `src/experiment/template-results/experiment-2/tinycua/workdir/`.

**Conclusion:** TinyCUA is concise and structurally compliant, but its 19/32 is not evidence of superior factual coherence.

### OpenCode: most current retrieval, unreliable synthesis

OpenCode has the strongest live acquisition trail. It fetched the current BenchLM open-weight page, leading to genuinely current model names and the correct top-three open-weight ranking (`src/experiment/template-results/experiment-2/opencode/stdout.log:37-54`; `workdir/report.md:13-20,160-162`).

The resulting report still contains major errors:

- MiniMax M3's one-million-token context is misreported as one million parameters (`report.md:13`).
- Llama 3.1 405B is incorrectly called a 405B MoE with 17B active parameters (`report.md:17`).
- Mistral Small 4 is assigned the wrong active-parameter count (`report.md:20`).
- Llama 4 Scout context is internally contradicted (`report.md:29,89,147,197,227`).
- Hardware/monthly cost figures and universal benchmark-effect ranges are unsourced (`report.md:17,27,95,102,110,117,152,181-192`).

Paths above are under `src/experiment/template-results/experiment-2/opencode/workdir/`.

**Conclusion:** OpenCode's search loop produced more current tokens and names, but not reliably updated research. Retrieval recency did not translate into claim discipline.

### Hermes: broad fallback synthesis with severe numerical errors

Hermes searches actively but cannot extract source pages and falls back to model knowledge (`src/experiment/template-results/experiment-2/hermes/stdout.log:81-220,241-315,365-423`).

Its report is explicitly 2024-2025 and contains:

- malformed or thousand-fold price/unit errors (`workdir/report.md:17-18,35-38`);
- implausible uncited latency values (`report.md:26,43-45`);
- benchmark values conflicting with the named current leaderboard (`report.md:17-20,76-81`);
- incorrect Qwen context (`report.md:21,30,148`);
- chronology and unsupported safety claims (`report.md:61,88`); and
- no qualifying literal source URLs, matching its zero citation point.

**Conclusion:** source existence does not make the attached claims supported. Hermes is the weakest research report in this static audit.

### OpenClaw: stronger first-party citation intent, stale and inaccurate

OpenClaw's configured search integration is unavailable, and it writes largely from model knowledge (`src/experiment/template-results/experiment-2/openclaw/stdout.log:8-18`; `stderr.log:10-25,296-297`).

Its report uses several first-party links, but remains centered on 2023-2024 models and contains:

- Llama architecture/license conflation (`workdir/report.md:18,29`);
- Mixtral active-parameter/context errors (`report.md:22,29-30`);
- Qwen license/context errors (`report.md:23,34,52`);
- unsupported safety and contamination percentages (`report.md:82,109,131-146`); and
- recommendations obsolete for July 2026 (`report.md:155-173`).

Two cited Gemini/Qwen URLs returned 404 during the audit.

**Conclusion:** a readable fallback report and first-party-looking URLs do not establish currentness or correctness.

## Research-quality conclusion

| Dimension | Best-supported observation |
|---|---|
| Most current model shortlist | OpenCode |
| Most compact structural compliance | TinyCUA |
| Strongest first-party citation intent | OpenClaw |
| Broad conventional fallback synthesis | Hermes |
| Factually reliable publication-ready report | **None** |

OpenCode's stronger web acquisition does not prove better research. TinyCUA's higher score does not prove better factual quality. No report reliably connects every consequential claim to a current supporting source.

## Experiment 5: 14/14 does not mean a better study guide

### What creates the score difference

Hermes receives the table-of-contents point. TinyCUA and OpenCode each lose that one point:

- Hermes: `src/experiment/template-results/experiment-5/hermes/result.json:41-46,119`
- TinyCUA: `src/experiment/template-results/experiment-5/tinycua/result.json:41-46,119`
- OpenCode: `src/experiment/template-results/experiment-5/opencode/result.json:41-46,119`

Both 13/14 guides pass every substantive lexical category. The one-point difference is structural, not semantic.

### Static technical-quality audit

| Dimension | TinyCUA | Hermes | OpenCode |
|---|---|---|---|
| Conceptual prose | Focused and generally clear, with false statements | Adequate introduction, overwhelmed by errors | Best conceptual progression, with misleading claims |
| Mathematics | Core attention/sinusoidal formulas mostly sound | Multiple incorrect positional/tensor formulas | Core formulas mostly sound; some bad claims |
| Code | Non-runnable mixed NumPy/PyTorch pseudocode | Pervasively non-runnable and shape-incoherent | Non-runnable with undefined variables/interfaces |
| Organization | Manageable length; broken TOC link | Valid TOC but severe overextension/duplication | Good sequence; broken TOC link |
| Practical plan | Strongest detailed schedule/capstones | Actionable but bloated | Focused and usable |
| Static overall band | Comparable to OpenCode | Lower | Comparable to TinyCUA |

### TinyCUA: useful outline, unsafe implementation guide

Strengths include clear backpropagation/gradient-descent prose, standard attention equations, succinct encoder/decoder roles, and a detailed 12-week plan (`src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:21-48,102-188,340-421,595-663`).

Material defects include:

- nonexistent `np.sigmoid`, incompatible target reshape, wrong sigmoid derivative, and a non-updating training loop (`study-guide.md:66-98`);
- wrong attention tensor-axis handling (`study-guide.md:192-218`);
- incorrect claim that the original Transformer uses learned positional embeddings (`study-guide.md:261-271`);
- reversed/invalid mask examples (`study-guide.md:325-335,450-466`);
- invalid encoder self-assignments and missing normalization (`study-guide.md:359-403`); and
- a “complete” model mixing undefined NumPy/PyTorch components (`study-guide.md:492-590`).

### Hermes: structurally perfect, technically worse

Hermes has a valid TOC and actionable final schedule (`src/experiment/template-results/experiment-5/hermes/workdir/study-guide.md:7-15,1139-1201`).

Its larger guide contains more severe defects:

- duplicated broken backpropagation implementations (`study-guide.md:127-243`);
- invalid momentum/Adam abstractions (`study-guide.md:245-298`);
- nonexistent `np.softmax`, wrong transposes, and incoherent attention backward logic (`study-guide.md:344-395`);
- invalid positional encoding and normalization (`study-guide.md:412-523`);
- encoder/decoder/cross-attention code with unsupported arguments, undefined variables, and incompatible shapes (`study-guide.md:561-637,788-817`); and
- a purported practical model that cannot consume its data or update parameters (`study-guide.md:822-1135`).

### OpenCode: similar quality band to TinyCUA

OpenCode has the best high-level progression and a focused plan (`src/experiment/template-results/experiment-5/opencode/workdir/study-guide.md:37-203,538-570`).

Its code remains unusable:

- undefined forward values and misleading complexity claims (`study-guide.md:72-81,149-197`);
- invalid multi-head attention interfaces and variables (`study-guide.md:225-256,346-369`);
- undefined positional dimensions and decoder memory (`study-guide.md:270-285,401-457`);
- invalid masking and cross-attention shapes (`study-guide.md:460-512`); and
- broken exercises with uncached or undefined activations (`study-guide.md:574-632`).

### OpenClaw

No current `study-guide.md` exists. Its 2/14 consists of task integrity plus vacuous heading uniqueness, not content quality (`src/experiment/template-results/experiment-5/openclaw/result.json:20-53,111-131`).

## Study-guide conclusion

The deterministic score ordering is misleading:

> **Static quality audit: TinyCUA ≈ OpenCode > Hermes; deterministic total: Hermes 14 > TinyCUA/OpenCode 13.**

TinyCUA's guide is not reliably correct, but it is materially more usable than Hermes' larger 14/14 artifact. OpenCode and TinyCUA occupy a similar quality band for different reasons. A semantic judge or executable code audit is required before ranking learner value.

## Coding evaluators: stronger but still narrow

### Experiment 3

A perfect 9/9 is meaningful evidence that expected hand geometry and scheduled movement were observed in four frozen-time cases. Re-evaluation records each candidate's surface and normalized length, then requires the same candidate to move from its base angle to the expected later angle; this removes prior cross-hand false positives (`src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:188-286`). Partial scores remain failure frontiers rather than visual-quality ratings, and numeral placement remains intentionally unscored.

### Experiment 4

A perfect 9/9 functional score would support one end-to-end workflow. Python compilation and Ruff lint add two non-critical static signals, so the displayed total is now out of 11; they do not make a non-running app functionally better. Functional partial scores are failure frontiers, not independent quality increments:

- all four browser categories share one create→edit→delete→reload execution path;
- SQLite/restart checks depend on that path producing marker text; and
- startup failure mechanically prevents every later category.

Sources: `src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:175-233,291-297,329-334`.

OpenClaw's 4/11 includes three functional startup checks and one compilation check, while TinyCUA's 1/11 is script existence only. This proves deeper startup progress, not a four-point product-quality advantage.

## Required interpretation language

Use:

> Deterministic score is the count of fixture-specific acceptance signals observed. It is not a general artifact-quality rating.

Per fixture:

- **Experiment 2:** “Satisfied N of 32 structural, lexical, URL-presence, bundled-model, and integrity checks; currency and factual correctness were not verified.”
- **Experiment 3:** “Chromium observed/did not observe expected same-hand geometry and scheduling at four frozen timestamps; numeral placement and general visual quality were not assessed.”
- **Experiment 4:** “Reached this evaluator-defined startup/CRUD/persistence failure frontier; Python compilation and Ruff lint are static signals, and general application quality was not rated.”
- **Experiment 5:** “Satisfied N of 14 Markdown and topic-presence checks; explanation and code correctness were not tested.”

Avoid:

- “quality score”;
- “correctness score” for Experiments 2 or 5;
- normalized “quality percentage”;
- cross-fixture score sums as quality rankings; and
- claiming one harness is better solely from a one-point structural difference.

## What would measure actual quality

### Research

- verify every URL resolves;
- record source publication dates;
- require claim-level citations;
- check claim-source entailment;
- prefer first-party/model-card evidence;
- validate architecture, pricing, context, license, and benchmarks;
- penalize contradiction and unsupported numbers; and
- freeze an explicit as-of date.

### Study guides

- parse and execute code blocks in declared environments;
- validate equations and tensor shapes;
- check contradictions and repeated major sections;
- independently score pedagogical progression and clarity;
- require uncertainty/citation markers for non-consensus claims; and
- optionally run a blinded expert or learner study.

### Applications

- preserve clean exported execution;
- test multiple CRUD sequences and records;
- use accessibility-independent and accessibility-aware probes;
- inspect actual database causality, not only marker presence; and
- report failure frontiers instead of additive quality totals.

## Limits

- The semantic audits are static and sampled; code blocks were not executed.
- Live research sources are dynamic and reflect the audit date.
- Some inaccessible or script-heavy sources could not be fully checked.
- No learner study or controlled semantic judge exists for the current campaign.
- One artifact per harness cannot establish stable harness-level semantic quality.

## Bottom line

The evaluator can deterministically report whether its predicates passed. It cannot generally say that a higher score means better quality. TinyCUA's 19/32 research score is not evidence of more factual research than OpenCode's 17/32, and Hermes' 14/14 study-guide score is not evidence of a better guide than TinyCUA/OpenCode at 13/14. Manual artifact inspection reverses the latter ordering and finds no publication-ready research report.
