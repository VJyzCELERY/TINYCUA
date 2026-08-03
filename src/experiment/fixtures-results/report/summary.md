# Interim Paper Summary

This document condenses the controlled-template experiment into paper-ready language. Detailed evidence and source references remain in the linked reports.

[Full report index](README.md) | [Evaluator validity](evaluator-validity-and-artifact-quality.md) | [Why orchestration did not improve quality](why-orchestration-did-not-improve-quality.md) | [Full-harness comparison](new-harness-comparison.md) | [TinyCUA ablation](tinycua-ablation.md)

## Study scope

The controlled campaign compared TinyCUA, Hermes, OpenCode, and OpenClaw on five tasks: an exact-response task, a current-model research report, an animated analog clock, a Python/SQLite browser application, and a neural-network study guide. All harnesses used the same `qwen3.5-9b` model endpoint, but retained their own prompts, tools, permissions, and orchestration. Each harness-task pair was run once without a fixed seed or retry, so the results are descriptive rather than statistical effect estimates.

TinyCUA was also evaluated in a 2x2 role ablation: full TinyCUA, no Information Digester, no Result Reviewer, and neither role.

Post-campaign evaluator-only re-evaluation updates the published artifact scores without rerunning agents. Experiment 3 now follows the same rendered hand across frozen-time samples, removing prior cross-hand false positives; Experiment 4 displays 11 categories, with Python compilation and Ruff lint recorded as non-critical static signals beside its nine functional checks. Original execution evaluations remain preserved in each `result.json`.

## Reproducibility anchor

The TinyCUA implementation evaluated in this campaign is anchored to the annotated Git tag `prototype-stable-2026-07-30`, which resolves to commit `404ee446916caf76db3cc870987e4a8cfaaaea5f`. The tag identifies the stable prototype snapshot before later Reviewer falsification work.

Campaign metadata records `89d2402e5dd6626390e9c5e09b52a21898e0cf2c` as the result-generation and TinyCUA source commit. That commit descends from `prototype-stable-2026-07-30`; the intervening commits add or revise experiment infrastructure without changing `src/tinycua`. The `src/tinycua` directory has the identical Git tree object `a0787d7ec7714c3569fa6217ea941ed902ca92df` at both references.

Therefore:

- cite `prototype-stable-2026-07-30` as the evaluated TinyCUA prototype version; and
- use commit `89d2402e5dd6626390e9c5e09b52a21898e0cf2c` when reproducing the exact controlled runner, fixtures, and evaluator configuration.

Paper-ready provenance statement:

> The TinyCUA results were produced using the prototype snapshot tagged `prototype-stable-2026-07-30` (`404ee446`). The controlled campaign ran at commit `89d2402e`, whose TinyCUA source tree is identical to the tagged prototype while adding the experiment harness and fixtures required for reproduction.

## Main results

| Harness | Passed fixtures | Total runtime | Distinctive observed result |
|---|---:|---:|---|
| TinyCUA | 3/5 | 30.61 min | Passed the research evaluator through one hidden model-name match; failed both executable coding tasks. |
| Hermes | 3/5 | 8.20 min | Produced the only fully correct clock; its structurally perfect guide contained severe technical errors. |
| OpenCode | 2/5 | 14.06 min | Demonstrated the strongest live web-acquisition loop but produced unsupported claims and missed executable integration constraints. |
| OpenClaw | 1/5 | 8.04 min | Produced the only application that started after export, but no CRUD workflow worked and no study guide was created. |

TinyCUA was the slowest full harness on every nontrivial fixture. Relative to the fastest harness in each task, it was approximately 3.0 times slower on the research report, 6.9 times slower on the clock, 6.8 times slower on the application, and 3.2 times slower on the study guide.

The TinyCUA role ablation produced no stable winner:

| Configuration | Passed fixtures | Passed nontrivial fixtures |
|---|---:|---:|
| Full TinyCUA | 3/5 | 2/4 |
| No Digester | 3/5 | 2/4 |
| No Reviewer | 3/5 | 2/4 |
| Neither role | 2/5 | 1/4 |

Reviewer-on versus Reviewer-off score differences changed direction across tasks. Full TinyCUA and no-Reviewer TinyCUA had the same pass count, while review-enabled runs sometimes expanded into long revision loops. These observations do not demonstrate a consistent final-quality benefit from routine review.

## Evaluator interpretation

The deterministic totals should be interpreted as counts of fixture-specific acceptance signals, not general quality scores.

- The research evaluator primarily checks structure, keywords, URL presence, and hidden model-name strings. It does not validate publication dates, source authority, factual correctness, or whether a citation supports its associated claim.
- The study-guide evaluator checks Markdown structure, topic words, code fences, and the presence of a practical plan. It does not validate equations, tensor shapes, API usage, or whether examples execute.
- The clock and application evaluators provide stronger behavioral evidence because they execute the artifacts. Clock checks now follow one rendered hand across time; the app's two static compilation/lint points do not alter its nine-category functional gate. Their partial scores still represent dependent failure frontiers rather than equal increments of product quality.

This distinction changes the interpretation of the ranking. TinyCUA's 19/32 research score does not establish better research than OpenCode's 17/32. Hermes' 14/14 study-guide score also does not establish a better guide than the 13/14 TinyCUA and OpenCode artifacts.

## Actual artifact quality

### Research report

No submitted report was publication-ready.

- OpenCode retrieved the most current model shortlist, but its report confused context length with parameter count, mischaracterized model architectures, contradicted itself on context limits, and included unsupported deployment costs.
- TinyCUA produced the most compact structurally compliant report, but mixed current and stale model families, attached evidence from unrelated model families to its Llama discussion, and reused generic leaderboard links for specific claims.
- Hermes relied heavily on fallback model knowledge and contained severe pricing, latency, context, benchmark, and chronology errors.
- OpenClaw showed stronger first-party citation intent but remained stale and contained architecture, license, context, and unsupported-percentage errors.

TinyCUA's research pass was caused by one exact match with the evaluator's hidden synthetic model list, not by verified factual superiority.

### Study guide

Static technical inspection produced a different ordering from the deterministic score:

> **TinyCUA approximately equals OpenCode, and both are better than Hermes; none is safe as an implementation guide without correction.**

TinyCUA and OpenCode both provided useful conceptual progression and practical study plans, but their code examples contained nonexistent APIs, undefined variables, invalid tensor operations, and incompatible interfaces. Hermes covered more material and had a valid table of contents, but accumulated substantially more severe mathematical, shape, API, and runtime defects. Its one-point deterministic advantage was purely structural.

### Executable tasks

Hermes produced the only working clock. TinyCUA's reviewed clock calculated fresh hand state but rendered stale initial state, so every movement check failed despite internal approval.

All four applications failed the required end-to-end workflow. TinyCUA's exported application failed to start because it contained hard-coded construction paths and invalid final Python source; its database initialization also destroyed persistence. OpenClaw progressed furthest by starting successfully after export, but its initial interface offered no usable route to create the first page or block.

## TinyCUA interpretation

The controlled campaign does not demonstrate a practical quality advantage from TinyCUA's task decomposition or Result Reviewer. The architecture performed more intermediate work, but that work did not reliably improve the final artifact.

The observed failure mechanisms were:

1. generated tasks divided work by topic rather than by independently testable contracts;
2. leaf review was local while the decisive failures occurred at integration boundaries;
3. planner, executor, and reviewer used the same underlying model, allowing correlated misunderstandings;
4. behavioral and semantic verification was requested through prompts rather than deterministically required;
5. executor and reviewer shared mutable files, packages, databases, ports, and possible running processes;
6. bounded evidence could describe an earlier artifact state after later tasks changed the files; and
7. small, tightly coupled deliverables paid repeated orchestration cost without gaining independent verification.

The Reviewer did identify some local defects and cause revisions. However, activity is not equivalent to net benefit: it also invented requirements, issued contradictory judgments on large artifacts, and approved final results that failed external execution. In this campaign, Reviewer approval was closer to a task-local plausibility judgment than an independent correctness certificate.

## Paper-ready conclusion

In this single-trial controlled comparison, TinyCUA's explicit task decomposition and review stages did not produce a demonstrated improvement in final artifact quality over simpler agent loops. TinyCUA tied Hermes on fixture pass count, remained the slowest harness on every nontrivial task, and failed both executable coding fixtures. Its only unique pass depended on a hidden lexical research criterion that did not measure factual reliability. Manual inspection further showed that deterministic structural scores could disagree with semantic quality, most clearly when Hermes' 14/14 study guide was technically worse than the 13/14 TinyCUA and OpenCode guides. The results therefore support a negative interim finding: additional orchestration increased process activity and latency, but did not reliably convert into better factual, semantic, or executable outcomes.

## Limitations

- Each harness-task pair was run once without a fixed seed, preventing variance estimates or statistical significance claims.
- Harnesses shared a model endpoint but differed in prompts, tools, permissions, and thinking settings.
- Full TinyCUA and its ablations were preserved under different result-generation revisions.
- Search availability changed during sequential execution.
- Research and study-guide quality conclusions rely on sampled manual inspection rather than a blinded expert or learner study.
- The five fixtures do not establish performance on all task types.
