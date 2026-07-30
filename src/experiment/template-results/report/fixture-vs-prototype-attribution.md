# Fixture Change Versus TinyCUA Prototype Change

[Report index](README.md) | [TinyCUA ablations](tinycua-ablation.md) | [New-harness comparison](new-harness-comparison.md) | [Historical comparison](historical-comparison.md)

## Question

When an old and new TinyCUA result differ, how much of the difference comes from:

1. the new fixture and its narrower or stricter task contract;
2. the newer TinyCUA prototype and its planning/review behavior;
3. the new evaluator measuring different properties; or
4. one-run stochastic and environmental variation?

The checked-in experiments do not form a clean causal ablation because all four layers changed together. This report therefore uses **observational attribution**, not causal effect estimates.

Confidence labels:

- **HIGH:** directly demonstrated or repeated in suitable cross-harness controls.
- **MODERATE:** supported by multiple traces but with unresolved alternatives.
- **LOW:** a one-run association.
- **NOT IDENTIFIED:** the existing data cannot separate the candidate causes.

## Short answer for Experiment 4

**The narrower Experiment 4 application is primarily associated with the fixture change, not a TinyCUA-only change.**

The old prompt was one open sentence asking for a Notion-like Python/web/SQLite app (`src/experiment/evaluation-results/tinycua/experiment-4/run_logs/prompt.txt:1`). The new fixture specifies one block CRUD workflow, a portable `start.sh`, accessibility, reload/restart persistence, and explicitly says not to add authentication, accounts, sharing, or unrelated collaboration (`src/experiment/experiment-fixtures/experiments-list/experiment-4/workdir/TASK.md:5-29`).

All four harnesses produced much smaller new applications:

| Harness | Historical text inventory | New text inventory | Change |
|---|---:|---:|---:|
| TinyCUA | 3,134 lines | 541 lines | -82.7% |
| Hermes | 3,943 | 638 | -83.8% |
| OpenCode | 2,025 | 324 | -84.0% |
| OpenClaw | 3,915 | 911 | -76.7% |
| Non-TinyCUA aggregate | 9,883 | 1,873 | -81.0% |

TinyCUA contracts by almost the same proportion as the three imperfect controls. The scope collapse is therefore a **HIGH-confidence shared fixture association**.

The prototype still appears to reinforce the contraction:

- Historical TinyCUA reached 40 retained task nodes and reported 16 root children; new TinyCUA used one root plus seven flat children.
- Model requests fell from 1,422 to 137.
- The newer planning guidance explicitly allows an adequate high-level plan to remain unsplit.

Those are **MODERATE-confidence prototype-associated mechanisms**, but their independent contribution cannot be quantified because the fixture itself supplies the finite seven-part problem.

The new evaluator is a third, separate effect. It copies the submission, runs `sh start.sh`, drives the public browser workflow, inspects SQLite, and restarts the app (`src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:93-145,266-341`). That changes what is measured; it does not explain why every harness generated a smaller app.

## Attribution method

### 1. Separate generation from measurement

- **Generation effect:** changes visible in plans, logs, files, task trees, and artifact scope before evaluation.
- **Measurement effect:** changes in score or ranking caused by a different judge, hidden gate, executable test, or cascading evaluator dependency.

For example, Experiment 4's smaller files are a generation observation. A score of 1/9 is primarily a failure-frontier observation: once startup fails, CRUD and persistence cannot be exercised as independent checks.

### 2. Use other harnesses as pattern controls

Hermes, OpenCode, and OpenClaw also changed versions and behavior, so they are not causal controls. They are still useful for asking:

> Did the same fixture change produce the same directional artifact change across unrelated harnesses?

A shared direction and similar magnitude support a common fixture association. A TinyCUA-only residual supports a candidate prototype-specific association.

### 3. Require a TinyCUA mechanism

A candidate prototype attribution should have corresponding TinyCUA evidence such as:

- different planning guidance;
- a smaller or flatter task tree;
- fewer model requests;
- changed executor/reviewer scheduling; or
- a different stopping rule.

Artifact length alone is insufficient.

### 4. Keep environment and stochastic residuals unassigned

The campaign has one unseeded trial per pair, no retries, and sequential execution (`src/experiment/template-results/run_metadata.json:754-764`). Search-service backoff persists between invocations (`src/experiment/README.md:243-248`). An unexplained residual is not automatically a TinyCUA effect.

## Cross-harness breadth changes

Logical lines are counted with `str.splitlines()`. Experiment 4 inventories include generated text source/configuration/documentation and exclude fixture seeds, lockfiles, databases, logs, virtual environments, temporary tool output, and harness identity/state files.

| Experiment | TinyCUA | Hermes | OpenCode | OpenClaw | Non-TinyCUA aggregate |
|---|---:|---:|---:|---:|---:|
| 2, frontier report | 368 -> 97 (-73.6%) | 267 -> 175 (-34.5%) | 123 -> 239 (+94.3%) | 114 -> 176 (+54.4%) | 504 -> 590 (+17.1%) |
| 3, clock | 240 -> 237 (-1.3%) | 171 -> 137 (-19.9%) | 182 -> 139 (-23.6%) | 210 -> 129 (-38.6%) | 563 -> 405 (-28.1%) |
| 4, app text inventory | 3,134 -> 541 (-82.7%) | 3,943 -> 638 (-83.8%) | 2,025 -> 324 (-84.0%) | 3,915 -> 911 (-76.7%) | 9,883 -> 1,873 (-81.0%) |
| 5, study guide | 4,978 -> 667 (-86.6%) | 579 -> 1,236 (+113.5%) | 710 -> 669 (-5.8%) | no artifact -> no artifact | 1,289 -> 1,905 (+47.8%), Hermes/OpenCode only |

The table separates two patterns:

1. **Experiment 4 is a shared contraction.** Every harness shrinks by 77-84%.
2. **Experiments 2 and 5 are not shared contractions.** The non-TinyCUA aggregates grow by 17.1% and 47.8%. Hermes in Experiment 2 and OpenCode in Experiment 5 contract in the same direction as TinyCUA, but neither approaches TinyCUA's magnitude.

## What changed in the TinyCUA prototype

Historical TinyCUA is pinned at `f1b0193f` (`src/experiment/evaluation-results/SNAPSHOT.md:13-20`). The controlled campaign records TinyCUA source `89d2402e5dd6626390e9c5e09b52a21898e0cf2c` (`src/experiment/template-results/run_metadata.json:731-735`). This is a bundled source change, not one isolated planning toggle.

### Recursive planning was retained

The new source can still decompose any unfinished parent through `TaskStateStore.decompose_task()` (`src/tinycua/tinycua/models/task.py:374-416`). Reviewer-triggered local replanning also remains available and intentionally has no hard cap (`src/tinycua/tinycua/loops/worker_runtime.py:62-185`).

The new flat trees therefore do **not** result from deleting recursive planning.

### Planning guidance became more tolerant of coarse granularity

The newer guidance, introduced and refined around commits `b1d13f2b`, `ac1e5ce7`, and `71d0dadb`, says:

- split only when useful;
- no fixed depth or task count is required;
- size or further decomposability is not itself a defect; and
- an adequate task should remain unchanged.

Direct source: `src/tinycua/tinycua/loops/task_nodes.py:59-111`.

Historical source already allowed an adequate task to remain unchanged (`f1b0193f:src/tinycua/tinycua/loops/task_nodes.py:59-70`). The newer policy strengthens that allowance and permits a flat acceptance-shaped plan to be judged sufficient when `TASK.md` already supplies a closed checklist.

### Executor sibling ownership became stricter; no-change behavior became explicit

Historical source already assigned the active task and allowed reporting incidentally completed siblings (`f1b0193f:src/tinycua/tinycua/loops/task_nodes.py:137-157`). The newer executor guidance prohibits intentional sibling work and adds explicit verification of an already-existing outcome rather than recreation (`src/tinycua/tinycua/loops/task_nodes.py:127-146`).

The lifecycle runtime also separates action, commit, and termination and tells a node to stop after its successful commit (`src/tinycua/tinycua/loops/tinycua_loop.py:578-633,712-819`).

These instructions tighten assignment boundaries and termination, although Experiment 5 shows that the model can still over-complete a broad first leaf.

### Digestion now prioritizes referenced workspace constraints

Both snapshots run Information Digester before Worker (`src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stderr.txt:4-9`; `src/experiment/template-results/experiment-4/tinycua/stderr.log:12-20`). The newer guidance prioritizes explicitly referenced workspace files and commits structured constraints (`src/tinycua/tinycua/loops/information_digester.py:21-51`; `src/tinycua/tinycua/tools/digest_information.py:20-60`). In Experiment 4, the digest records block persistence, accessible controls, and no authentication/sharing (`src/experiment/template-results/experiment-4/tinycua/stdout.log:19-30`).

This carries the fixture's stronger scope into planning; digestion itself was not newly introduced.

## Experiment 4 attribution in detail

### Shared fixture effect: HIGH

Historical plans expanded the open Notion analogy into broad product features:

- TinyCUA introduced JWT authentication, React/Vite, Tailwind, TipTap, migrations, and broad schemas.
- Hermes' todo included users, comments, and search.
- OpenCode requested separate frontend/backend and authentication if possible.
- OpenClaw advertised JWT authentication, workspaces, hierarchy, comments, and search.

Representative evidence:

- `src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stdout.txt:96-115,15689-15707`
- `src/experiment/evaluation-results/hermes/experiment-4/run_logs/stdout.txt:45-87`
- `src/experiment/evaluation-results/opencode/experiment-4/run_logs/stdout.txt:2-8`
- `src/experiment/evaluation-results/openclaw/experiment-4/run_logs/stdout.txt:207-227,548-559`

The new contract removes those features explicitly. New harness behavior converges on compact CRUD applications:

- TinyCUA: seven tasks for setup, `start.sh`, SQLite, Flask API, UI, integration, and testing (`src/experiment/template-results/experiment-4/tinycua/stderr.log:27-44`).
- Hermes: SQLite, Flask API, frontend, and `start.sh` (`src/experiment/template-results/experiment-4/hermes/stdout.log:79-113`).
- OpenCode: reads `TASK.md`, restates no auth/sharing, and chooses one Flask/SQLite/HTML app (`src/experiment/template-results/experiment-4/opencode/stdout.log:9-12`).
- OpenClaw: produces a compact pages/blocks Flask app without auth/collaboration (`src/experiment/template-results/experiment-4/openclaw/stdout.log:341-395`).

Because unrelated harnesses narrow by nearly the same amount, the fixture change is the strongest observed association with **what** the app includes.

### Prototype reinforcement: MODERATE

Historical Experiment 4 reached 40 retained task nodes and reported 16 direct root children. Controlled Experiment 4 had eight total nodes: root plus seven children. Model requests fell from 1,422 to 137 and duration from 8,394.9 to 929.9 seconds.

Evidence:

- Historical retained-tree expansion: `src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stderr.txt:11-167,6472-6480`
- Historical direct-child report: `src/experiment/evaluation-results/tinycua/experiment-4/run_logs/stdout.txt:15689-15707`
- New decomposition: `src/experiment/template-results/experiment-4/tinycua/stderr.log:22-44`
- Request/runtime analysis: [historical comparison](historical-comparison.md#process-count-and-task-tree-granularity)

The coarse-granularity-tolerant planner accepted the fixture-shaped seven-task plan without recursive refinement. That is consistent with reinforcing the fixture's narrow scope and shorter runtime. Comparable contractions occur in non-TinyCUA harnesses, so a TinyCUA-specific update is not necessary for the cross-harness pattern; its contribution within TinyCUA remains unidentified.

### Evaluator effect: HIGH, but separate

The old semantic judge found every Experiment 4 app nonfunctional while still discussing visible architecture and product intent (`src/experiment/evaluation-results/judges_verdict/experiment_4/verdict.md:3-56`).

The new evaluator identifies the deepest executable stage reached:

| Harness/cell | Failure frontier |
|---|---|
| Full TinyCUA | `start.sh` exists; startup fails. |
| Hermes | `start.sh` exists; startup fails. |
| OpenCode | `start.sh` exists; startup fails. |
| OpenClaw | Startup and Python process pass; initial accessible block workflow fails. |
| `tinycua-nd` | Startup and Python process pass; initial accessible text field fails. |

The new measurement is stricter on the specified startup/browser/persistence workflow and more operational. It does not show that narrowing caused failure: all old apps were already judged nonfunctional, and the new failures arise from concrete startup, accessibility, and persistence defects.

### Experiment 4 conclusion

> **Shared fixture-associated breadth change; prototype-consistent process change; evaluator-driven visibility of failures.**

The fixture change is the strongest observed association with the shared product-scope contraction. The newer TinyCUA policy is consistent with accepting one flat decomposition and performing fewer cycles. The executable evaluator makes portability and public-workflow defects more visible. Independent causal contributions are not identified.

## Experiment 2 attribution

### Fixture effect: HIGH for structure, not length

The new fixture mandates an exact title, five ordered H2 chapters, one table schema, three model families, three URLs, six dimensions, and benchmark caveats (`src/experiment/experiment-fixtures/experiments-list/experiment-2/workdir/TASK.md:10-31`). All four new harnesses converge on that chapter structure.

But artifact length does not share one direction:

- TinyCUA shrinks 73.6%.
- Hermes shrinks 34.5%.
- OpenCode grows 94.3%.
- OpenClaw grows 54.4%.

The fixture standardized structure and supplied a coverage floor. It did not generally make reports shorter.

### Candidate prototype association: MODERATE

TinyCUA's requests fall from 203 to 57 and visible child tasks from seven to five. The first substantial executor writes the complete report; later Evidence, Benchmark Interpretation, Conclusion, and final tasks mostly verify existing content (`src/experiment/template-results/experiment-2/tinycua/stdout.log:108-226`).

This TinyCUA-specific process coincides with a particularly short checklist-shaped report. Planning remains confounded with the new finite task and one generated trajectory.

### Evaluator effect: HIGH

Experiment 2's pass/fail hinges on a critical exact-name check against an evaluator-only synthetic model list (`src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/check.py:13-28,122-211`; `src/experiment/experiment-fixtures/experiments-list/experiment-2/eval/evidence.json:2-14`). TinyCUA passes because it happens to mention `Claude Fable 5`; three substantial control reports exceed the numeric threshold but fail that gate.

That is a measurement/ranking effect, not evidence that TinyCUA generated the broadly best research.

## Experiment 3 attribution

### Fixture effect: HIGH for the target contract

The old task requested a simple animated analog clock. The new fixture fixes the filename, rendering surface, time derivation, repeated scheduling, clockwise direction, and dependency rules (`src/experiment/experiment-fixtures/experiments-list/experiment-3/workdir/TASK.md:5-19`). Hermes and OpenCode switch from `analog-clock.html` to the required `clock.html`, and all three non-TinyCUA implementations become shorter.

TinyCUA remains nearly the same size: 240 to 237 lines. There is no general TinyCUA scope contraction in this task.

### Prototype-versus-generation effect: NOT IDENTIFIED

New full TinyCUA is static because it computes fresh state but draws stale state. Historical TinyCUA rendered but moved in the wrong direction. New Hermes moves from a historical runtime crash to 9/9.

Those differences could arise from harness changes, fixture interaction, or generation variance. The single trials do not isolate a TinyCUA prototype effect.

### Evaluator effect: HIGH

The new evaluator freezes time and inspects rendered geometry and movement (`src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:24-94,221-297`). It exposes defects that source narration and Reviewer approval miss. Its permissive segment matcher can cross-match lines, so TinyCUA's 5/9 still overstates styled-hand correctness (`src/experiment/experiment-fixtures/experiments-list/experiment-3/eval/check.py:188-218`).

## Experiment 5 attribution

### Fixture effect: HIGH for the stopping boundary

The old request asked for comprehensive study documentation without a ceiling. The new task names six concepts, one code block, and one practical plan (`src/experiment/experiment-fixtures/experiments-list/experiment-5/workdir/TASK.md:8-13`). That gives every harness a finite minimum, but no length maximum.

### Uniform fixture-only explanation: rejected descriptively

- TinyCUA contracts from 4,978 to 667 lines (-86.6%).
- Hermes expands from 579 to 1,236 (+113.5%).
- OpenCode remains near stable at 710 to 669 (-5.8%).

The fixture alone cannot explain one common volume shift.

### Candidate TinyCUA process association: MODERATE

New TinyCUA's seven tasks mirror the finite checklist. The first task is nominally Markdown structure but writes the entire 667-line guide; the next six executors mostly verify that their sections already exist (`src/experiment/template-results/experiment-5/tinycua/stdout.log:88-249`).

This behavior conflicts with the executor's instruction not to implement pending sibling outcomes (`src/tinycua/tinycua/loops/task_nodes.py:127-146`). The runtime nevertheless continues through unfinished leaves, and the same guidance tells later executors to verify an already-existing outcome. The result is one broad write followed by no-op checks.

Requests fall from 427 to 65, duration from 3,004.3 to 320.8 seconds, and visible child tasks from fourteen to seven. Those are strong TinyCUA-specific associations, but the historical TinyCUA trial was also pathologically repetitive and the new prompt is finite.

### Evaluator effect: HIGH

The new evaluator checks headings, literal topic terms, code fences, and a practical plan but does not execute examples or assess factual quality (`src/experiment/experiment-fixtures/experiments-list/experiment-5/eval/check.py:108-177`). It can pass duplicated or technically defective guides.

The score therefore does not answer whether TinyCUA's smaller guide or Hermes' larger guide is pedagogically better.

## Attribution matrix

| Observed change | Fixture association | TinyCUA prototype association | Evaluator association | Best reading |
|---|---|---|---|---|
| Experiment 4 app breadth collapse | **HIGH:** all four shrink 77-84%. | **MODERATE reinforcement:** flat accepted plan and fewer cycles. | Not relevant to file breadth. | Predominantly shared fixture scope. |
| Experiment 4 failure visibility | Narrow workflow defines exact behavior. | Reviewer still approves blockers. | **HIGH:** copied-workspace startup/browser/restart checks. | Measurement exposes real integration defects. |
| Experiment 2 exact structure | **HIGH:** every harness follows fixed chapters. | Flat plan maps to chapters. | Hidden critical model-name gate. | Shared structure; TinyCUA-specific concision. |
| Experiment 2 TinyCUA contraction | Controls collectively grow 17.1%. | **MODERATE candidate:** fewer requests and no-op later tasks. | Not relevant to length; highly relevant to pass. | Not a general fixture-length effect. |
| Experiment 3 correctness reversal | New task states behavioral requirements. | **NOT IDENTIFIED:** distinct one-run bugs. | **HIGH:** dynamic evaluator observes movement. | Generation plus stronger measurement. |
| Experiment 5 TinyCUA contraction | Finite checklist supplies a stopping boundary. | **MODERATE candidate:** first-task overcompletion and fewer expansion cycles. | Structural score ignores semantic quality. | Fixture and prototype are both candidate associations; their interaction is **NOT IDENTIFIED**. |
| New TinyCUA lower durations | Narrow scope can reduce work. | Fewer requests and accepted shallow plans coincide. | Evaluator runs after measured generation time. | Exact contribution is **NOT IDENTIFIED**. |

## What the current data cannot identify

- A percentage of any change attributable to fixture, TinyCUA prototype, evaluator, or environment.
- A causal TinyCUA prototype effect on speed, correctness, or detail.
- Whether adaptive planning itself caused fewer requests or merely responded to narrower tasks.
- Whether the same output would recur across seeds.
- Causal main or interaction effects for Digester and Reviewer.
- Which TinyCUA component produced Experiment 2's hidden lexical match.
- Old/new token reduction because specialized-node telemetry is incomplete in the new logs.
- Cross-era quality rankings from incompatible old semantic and new deterministic scores.

## Experiment needed for causal separation

Use one model snapshot, seed policy, tool surface, timeout, and evaluator, then run a 2x2 design:

| | Historical fixture/prompt | Controlled fixture/TASK.md |
|---|---|---|
| Historical TinyCUA prototype | old prototype + old fixture | old prototype + new fixture |
| New TinyCUA prototype | new prototype + old fixture | new prototype + new fixture |

For each cell:

1. run multiple fixed seeds;
2. retain complete per-node token/tool/decision telemetry;
3. measure artifact breadth before evaluation;
4. run both the executable deterministic evaluator and one frozen semantic rubric; and
5. compare failure frontiers rather than only raw totals.

That design would separate the fixture main effect, prototype main effect, and their interaction. The checked-in old/new snapshots cannot.

## Bottom line

Experiment 4's narrower code has its strongest observed association with the narrower fixture: every harness contracts by nearly the same proportion and removes the same broad product features. The newer TinyCUA prototype is consistent with that response through one flat, high-level decomposition and far fewer processing cycles, but its independent contribution is not identifiable.

Experiments 2 and 5 differ: TinyCUA contracts dramatically while both control aggregates grow; the same-direction individual controls contract much less. Those results support a TinyCUA-specific association with adaptive planning, fewer revision cycles, and first-task overcompletion. Evaluator changes explain many score and ranking reversals, but not the generated artifact breadth itself.
