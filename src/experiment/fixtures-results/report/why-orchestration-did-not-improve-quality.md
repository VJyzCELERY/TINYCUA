# Why TinyCUA Orchestration Did Not Improve Quality

[Report index](README.md) | [Evaluator validity](evaluator-validity-and-artifact-quality.md) | [Reviewer limitations](reviewer-verification-limitations.md) | [TinyCUA ablation](tinycua-ablation.md) | [Full-harness comparison](new-harness-comparison.md)

## Direct answer

TinyCUA's task decomposition and review did not produce a demonstrated practical benefit in this campaign because they mostly added **role transitions, local checks, and repeated passes over shared artifacts**, not independent knowledge or an enforced end-to-end correctness oracle.

The architecture did perform more work. The missing link was converting that work into a better final artifact.

The most likely mechanisms are:

1. generated tasks were coverage-oriented work items, not precise executable contracts;
2. leaves were intentionally reviewed locally, while most failures were cross-task integration or semantic failures;
3. planner, executor, and reviewer used the same underlying model/client, so role labels did not create independent judgment;
4. verification was model-selected and prompt-enforced rather than deterministically required;
5. evidence was bounded and could become stale after later shared-workspace edits;
6. small, tightly coupled tasks were decomposed even when one coherent implementation would have been easier to reason about; and
7. every task paid orchestration cost even when earlier work had already produced the artifact.

These are source- and trace-supported explanations, not isolated causal effect estimates. The campaign has a Reviewer ablation, but no clean “same TinyCUA with task decomposition off” cell.

## What the experiment establishes

### Practical outcome

| Observation | Evidence |
|---|---|
| Full TinyCUA and no-Reviewer TinyCUA each passed 3/5 fixtures. | `tinycua-ablation.md:17-24,56-78` |
| With Digester enabled, turning Reviewer on changed scores by -1, +5, 0, and 0 across experiments 2-5. | `tinycua-ablation.md:67-78` |
| Every TinyCUA role configuration failed both executable coding fixtures. | `tinycua-ablation.md:19-24,147-203` |
| Full TinyCUA's Reviewer approved a non-moving clock. | `experiment-3/tinycua/stdout.log:247-255`; `experiment-3/tinycua/result.json:55-74` |
| Full TinyCUA's Reviewer approved an app that failed its first startup gate. | `experiment-4/tinycua/stdout.log:386-415`; `experiment-4/tinycua/result.json:20-96` |
| Full TinyCUA was slowest among the four complete harnesses on every nontrivial fixture. | `new-harness-comparison.md:35-59` |

The practical comparison is therefore negative: no consistent quality gain appears, while latency and internal activity increase.

### What is not established

- The campaign does not isolate task decomposition from every other TinyCUA behavior.
- OpenCode is a useful whole-harness baseline, not a clean decomposition ablation.
- One unseeded trial per pair cannot estimate variance or stable effect size.
- Deterministic scores do not fully measure semantic artifact quality; see [Evaluator Validity and Actual Artifact Quality](evaluator-validity-and-artifact-quality.md).

The correct conclusion is not “decomposition can never help.” It is narrower:

> This implementation of decomposition and review did not demonstrate a net quality benefit on these tasks under these conditions.

## Intended pipeline versus effective pipeline

### Intended

```text
understand request
  -> decompose work
  -> execute one bounded task
  -> independently verify it
  -> integrate verified children
  -> verify the root outcome
```

### Effective in the failed cases

```text
same model interprets request
  -> same model generates topical tasks
  -> same model edits one shared artifact
  -> same model reviews local prose/tool summaries
  -> later tasks edit the same artifact
  -> same model performs another prompted root check
  -> external evaluator finds behavior or portability failure
```

The architecture has a parent verification gate in its prompts. The problem is not the total absence of a final review stage. The problem is that the gate remains another LLM judgment with optional, self-selected checks rather than a separately enforced acceptance test.

## Mechanism 1: decomposition improved coverage, not contracts

The TaskExecutor is given an active generated task and told to execute only that task (`src/tinycua/tinycua/loops/task_nodes.py:127-146`). The Reviewer likewise judges only the active task outcome (`src/tinycua/tinycua/loops/node_guidance.py:60-77`). For non-root leaves, root acceptance criteria are explicitly advisory rather than gates (`src/tinycua/tinycua/loops/task_nodes.py:1105-1122`).

That division is useful only when each leaf has a sufficiently precise contract and the composition is mechanically checkable. The controlled tasks often did not have that shape:

- **Clock:** correctness depends on one continuous time→angle→render→schedule data flow.
- **Application:** correctness depends on the public entrypoint, process, browser controls, API, database, reload, and restart working as one path.
- **Research report:** quality depends on each consequential claim being entailed by a current source, not merely on covering assigned sections.
- **Study guide:** quality depends on equations, tensor shapes, interfaces, and examples remaining coherent across sections.

The generated roadmap could distribute topics such as styling, animation, persistence, or model families. It did not turn those topics into machine-enforced interfaces. Completing every topic therefore did not imply completing the root behavior.

### Observed consequence

TinyCUA's clock contained the expected ingredients—time formulas, hand drawing, and an animation loop—but fresh state never reached the draw calls (`experiment-3/tinycua/workdir/clock.html:156-217`). The Reviewer approved the ingredients while Chromium found no motion (`tinycua-ablation.md:158-165`).

The plan covered the parts; it did not prove the connection between them.

## Mechanism 2: the work was often too coupled to benefit from decomposition

Decomposition has value when subproblems can be completed and verified independently. These fixtures were mostly small deliverables with high coupling:

| Fixture | Dominant correctness boundary | Why task splitting has limited leverage |
|---|---|---|
| 2 | claim ↔ current source | Section ownership does not validate claims. |
| 3 | one render loop | Splitting geometry, styling, and animation creates handoff risk inside a small file. |
| 4 | one exported user journey | Backend/frontend/startup/persistence are only valuable when composed. |
| 5 | one coherent teaching sequence | Independent section generation permits contradictions and broken interfaces. |

Hermes passed the clock with a 137-line direct implementation while TinyCUA's 237-line decomposed/reviewed implementation failed (`new-harness-comparison.md:74-81,148-174`). This does not prove that short code always wins. It shows that this task did not require enough independent work to repay decomposition overhead.

## Mechanism 3: roles were not independent sources of judgment

All complete harnesses used the same `qwen3.5-9b` endpoint in the campaign (`run_metadata.json:731-764`). Inside TinyCUA, node configurations are derived by replacing policies on one base configuration; `create_node_config` preserves the inherited `llm_client` while changing tools, messages, retry settings, and metadata (`src/tinycua/tinycua/config/node_config.py:230-267,324-337`).

The planner, executor, and reviewer therefore had different instructions and context views, but not independently trained expertise or an external oracle.

This matters because model errors are correlated:

- a generated task can encode the model's original misunderstanding;
- the executor follows that generated interpretation;
- the reviewer sees the same task description and can accept evidence consistent with the same misunderstanding.

Experiment 2 no-Digester shows this feedback loop directly. The Reviewer invented a requirement for three URLs **per model family**, repeatedly rejected work against that nonexistent rule, and eventually approved a compromise (`tinycua-ablation.md:107-112`). Repetition increased confidence and runtime, not alignment with the actual task.

Different role names did not guarantee different failure modes.

## Mechanism 4: verification was requested, not enforced

The Reviewer prompt is strong: inspect artifacts, runtime-check behavior, source external claims, and distrust executor claims (`src/tinycua/tinycua/loops/node_guidance.py:60-77`). Its tool guidance says to prefer a focused runtime check and allows exact current evidence to substitute for rerunning explicitly requested verification (`node_guidance.py:81-107`). The review tool scope describes shell inspection as optional (`src/tinycua/tinycua/config/tool_scopes.py:196-212`).

What the runtime enforces is that the Reviewer records a decision and rationale. It does not enforce fixture-specific evidence such as:

- load the clock in Chromium at frozen times;
- copy the app to a clean directory and run `PORT=... sh start.sh`;
- execute every educational code block; or
- verify every numerical research claim against a cited source.

The parent gate similarly instructs the Executor and Reviewer to validate composed behavior in a fresh context (`src/tinycua/tinycua/loops/task_nodes.py:834-860,1018-1030`). It does not itself launch a clean environment or execute a required command.

### Observed consequence

- The clock review inferred animation from source structure instead of observing motion.
- The app review approved startup and persistence in the construction environment, while the exported copy failed immediately.
- The research review accepted generic leaderboard links and semantically mismatched evidence.
- The guide review accepted many code blocks that are statically non-runnable.

The Reviewer checked plausibility. The external evaluator checked selected behavior. Those are not equivalent.

## Mechanism 5: review was local while failures were global

TinyCUA intentionally reviews one active task at a time. Pending task information can be passed forward, but the Reviewer must not review or modify those tasks (`src/tinycua/tinycua/loops/task_nodes.py:968-1033`). Parent tasks are revisited after children complete (`src/tinycua/tinycua/models/task.py:1381-1408`).

That is a reasonable control-flow design, but it creates a long interval in which individually accepted work can be invalidated by later shared-workspace changes.

The campaign's dominant failures were root-level properties:

- current state actually reaches rendering;
- output exists at the exact required path;
- shell script is portable under `sh`;
- database survives startup and restart;
- browser controls expose the required workflow;
- evidence supports the report's actual claims; and
- code examples agree across guide sections.

A local approval cannot establish those properties before the composed artifact exists. The final prompted root pass did not recover them reliably.

## Mechanism 6: evidence was bounded and could become stale

The Reviewer receives the executor's outcome report plus a bounded rendering of up to the last 16 executor tool outcomes. The rendering records fields such as success, exit code, invocation, error, and an audit path; earlier tool results may be omitted (`src/tinycua/tinycua/loops/task_nodes.py:1051-1082`).

This is useful context control, but it is not proof that:

- a successful command tested the final file version;
- a server response came from the intended newly launched process;
- a later task did not overwrite an approved artifact;
- a database result survives clean export; or
- a cited page entails the nearby claim.

There is no automatic file-hash/evidence invalidation relationship in the review path. Validity after later edits is delegated to the parent LLM gate.

Large artifacts make the problem worse. In experiment 5 no-Digester, the Reviewer alternated between approving a 3,185-line guide and claiming that it contained only a title or first section while large reads were represented by previews (`tinycua-ablation.md:216-229`). Repeated review over partial views became unstable rather than more accurate.

The environment-specific risks and the evidence limits are detailed in [Reviewer Verification and Environment Limitations](reviewer-verification-limitations.md).

## Mechanism 7: shared mutable state weakened task boundaries

Executors and reviewers operate against the same configured workspace (`src/tinycua/tinycua/config/session_config.py:40-68`; `src/tinycua/tinycua/loops/task_nodes.py:821-877`). Task separation is logical, not filesystem or process isolation.

This permits useful incremental work, but also means:

- later tasks can alter files accepted by earlier reviews;
- old processes can survive and answer checks;
- package/database state can leak between passes;
- two nominal tasks can both own the same document or application file; and
- acceptance evidence can describe an earlier workspace state.

The architecture asks the final parent pass to detect these conditions. It does not prevent them.

For experiment 4, this distinction is decisive: local checks in the construction workspace did not establish behavior in the evaluator's copied workspace. TinyCUA, Hermes, and OpenCode all failed startup after export despite producing substantial implementations (`new-harness-comparison.md:176-220`).

## Mechanism 8: decomposition sometimes became repeated no-op verification

The Executor policy acknowledges that active work may incidentally satisfy pending outcomes and says that an already-existing outcome should be verified as a no-change success (`src/tinycua/tinycua/loops/task_nodes.py:127-146`).

That is necessary for a shared workspace, but it weakens the cost model:

1. an early task can create most or all of a deliverable;
2. later topical tasks inspect the same artifact;
3. each task still produces an executor result;
4. review-enabled runs add a Reviewer invocation after each pass; and
5. parent tasks add further integration passes.

The controlled traces show this multiplication. Full TinyCUA used 6, 8, 8, and 8 Executor/Reviewer pairs in experiments 2-5; no-Digester used 20, 6, 7, and 17 (`tinycua-ablation.md:88-98`). More passes did not correspond to more independent acceptance evidence.

## Why the Reviewer specifically failed

The Reviewer was not idle. It rejected, replanned, inspected, and approved. Its failure was a mismatch between **review method** and **defect type**.

| Defect type | What review appeared to use | What was required |
|---|---|---|
| Stale clock state | Presence of formulas and animation loop | Browser-observed motion from final draw calls |
| Exported app startup | Local paths/process observations | Clean-copy `sh start.sh` execution |
| Restart persistence | Schema/API reasoning or local checks | Create marker, stop, restart, retrieve marker |
| Research truth | URLs and plausible prose | Claim-level source entailment and date checks |
| Guide correctness | Topic coverage and code-like structure | Equation/shape audit and executable snippets |

Review created another language-model pass over representations of the work. It did not create the missing oracle.

## Why OpenCode remained competitive without TinyCUA's task tree

OpenCode is not evidence that unstructured work is universally superior. It is evidence that, for these fixtures, a simpler continuous tool loop was enough to reach similar final outcomes:

- both OpenCode and TinyCUA satisfied 16/17 visible Experiment 2 checks;
- both failed the clock and application fixtures;
- both scored 13/14 on the study-guide structure evaluator;
- static guide quality places them in a similar band; and
- neither produced a publication-ready research report.

OpenCode also failed in important ways: coordinate geometry, exported-path assumptions, unsupported research claims, and broken educational code. TinyCUA's additional stages did not remove those general model weaknesses.

The difference is cost: TinyCUA was slower on every nontrivial fixture. Internal observability is not counted as a TinyCUA advantage here because OpenCode already exposes its activity through its TUI and logs. The campaign therefore shows extra orchestration without demonstrated extra user value.

## Per-fixture causal diagnosis

### Experiment 2: decomposition organized the report but did not ground claims

TinyCUA produced a compact report and covered the visible structure. Its hidden pass came from one exact `Claude Fable 5` match, not broad evidence quality. The factual audit found mismatched family evidence, stale model families, and generic sources reused for exact claims.

**Why planning/review did not help:** tasks could allocate sections and source collection, but no stage enforced claim→source entailment or an as-of-date standard.

### Experiment 3: decomposition obscured one small end-to-end data flow

The implementation computed fresh hand state but rendered stale initial state. Reviewer approval described intended architecture rather than observed pixels.

**Why planning/review did not help:** the task's essential property was one integrated loop. More topical checkpoints did not replace one frozen-time browser check.

### Experiment 4: decomposition built parts before proving the public boundary

TinyCUA generated the largest workspace and reviewed database, startup, and testing work separately. The final export still contained hard-coded paths, invalid Python text, and destructive database initialization.

**Why planning/review did not help:** integration was the product. The cheapest decisive check—copy, start through the exact command, then perform one browser CRUD/restart path—was not enforced before approval.

### Experiment 5: decomposition increased coverage but not semantic verification

TinyCUA covered every substantive lexical category and produced a manageable plan. Static inspection still found nonexistent APIs, tensor-axis errors, wrong derivatives, invalid masks, and incompatible code sections.

**Why planning/review did not help:** topic-complete sections were accepted without executing code or checking mathematical interfaces across sections.

## Architectural conclusion

The failed assumption was:

> More structured intermediate work plus another model pass should monotonically improve final quality.

The campaign instead supports:

> Intermediate structure helps only when task boundaries match real interfaces and approval depends on evidence that directly measures the root behavior.

TinyCUA had orchestration controls, but its quality gates remained semantic instructions to the same model over mutable shared state. That improved process structure without reliably improving outcome correctness.

## Smallest corrective direction

Do not add more roles. Replace routine per-task review with one mandatory acceptance path that tests the final deliverable from a clean state.

1. **Do not decompose by default.** Keep one executor for small single-artifact tasks. Decompose only when children have independent artifacts or explicit input/output contracts.
2. **Run the public contract first and last.** For applications, test the exact exported startup and one end-to-end user journey. For the clock, run frozen-time browser geometry. For documents, run claim/code validation appropriate to the artifact.
3. **Invoke review on failed evidence, not after every task.** Give the Reviewer the failed command/output and final artifact version.
4. **Bind evidence to artifact state.** At minimum, record the final file hash or exported snapshot used by the check.
5. **Fail closed at the root.** If required acceptance evidence is absent or fails, do not allow an LLM approval to substitute for it.

This is a smaller architecture than the current repeated review loop and directly targets the observed failures.

## Limits

- Mechanisms are inferred from source and traces; only the Reviewer and Digester have direct 2x2 cells.
- One trial per pair prevents statistical causal claims.
- Full-harness differences include prompts, tools, permissions, and thinking settings.
- Artifact semantic audits are static and sampled.
- The campaign does not include a clean final-gate-only TinyCUA baseline.

## Bottom line

TinyCUA did more planning and reviewing, but the added work was not independent and did not enforce the properties the final artifacts actually needed. Local, same-model review over shared mutable state approved plausible structure; external checks exposed stale state, path portability, startup, persistence, factual grounding, and code-correctness failures. Until a controlled rerun shows a quality gain, task decomposition and routine Reviewer passes should be treated as overhead rather than demonstrated benefits.
