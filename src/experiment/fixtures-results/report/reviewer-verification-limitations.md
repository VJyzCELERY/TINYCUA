# Why TinyCUA Review Approval Does Not Guarantee Integration Correctness

[Report index](README.md) | [Why orchestration did not improve quality](why-orchestration-did-not-improve-quality.md) | [Evaluator validity](evaluator-validity-and-artifact-quality.md) | [Harness specialties](harness-specialties.md) | [TinyCUA ablations](tinycua-ablation.md) | [New-harness comparison](new-harness-comparison.md) | [Fixture vs prototype](fixture-vs-prototype-attribution.md)

## Question

In theory, a Result Reviewer should catch an artifact that does not work. Why did TinyCUA's Reviewer approve the failed clock, failed Notion-like app, and broken study-guide link?

The controlled evidence supports this answer:

> TinyCUA's Reviewer is a probabilistic, active-task-scoped critic operating inside the same mutable construction environment as the Executor. It can inspect and test, but no deterministic rule requires an evaluator-equivalent clean integration test before approval. The external evaluator runs the exported artifact in a separate environment and therefore observes defects that shared-state review can miss.

The Reviewer catches some real defects and causes revisions, but this campaign does not demonstrate a net final-quality benefit. Its approval means something closer to **“sufficient evidence for this active task”** than **“the final exported system works from a clean start.”**

Evidence labels:

- **[D] Direct:** source, log, artifact, or evaluator evidence.
- **[I] Inference:** bounded interpretation.
- **Proven:** architecture or chronology is directly recorded.
- **Strongly supported:** multiple observations fit one mechanism, but a missing command/output prevents strict proof.
- **Not supported:** the proposed mechanism conflicts with recorded evidence.

## What the Reviewer actually does

### It can independently inspect and execute

**[D]** Reviewer tool scope includes task inspection, file inspection, and guarded shell execution (`src/tinycua/tinycua/config/tool_scopes.py:196-212`). Logs separately show actual Reviewer use of shell/file/decision tools (`src/experiment/template-results/experiment-3/tinycua/stdout.log:172-178`) and web-search/fetch tools (`src/experiment/template-results/experiment-2/tinycua-nd/stdout.log:198-204,312-325`).

The Reviewer therefore is not merely a language-only summary stage.

### Independent behavioral testing is optional

**[D]** The runtime accepts approval without a mandatory `task_inspect` or test command; a unit test explicitly permits approval without inspection (`src/tinycua/tests/unit/test_result_reviewer_inspect_protocol.py:32-44`).

No deterministic rule requires:

- a browser run for visual work;
- a clean process restart for an application;
- installation from exported dependency manifests;
- launch from a relocated copy;
- a global duplicate-heading scan; or
- execution of documentation code examples.

The LLM chooses which evidence is sufficient.

### Review is scoped to the active task

**[D]** The decision tool prevents a Reviewer from deciding a task other than the active task (`src/tinycua/tinycua/tools/task_tools.py:839-848`). Task prompts distinguish active-task criteria from the root goal and instruct the Reviewer to judge the active assignment (`src/tinycua/tinycua/loops/task_nodes.py:1116-1122`).

This supports focused review, but it creates an integration risk:

- one backend task can be locally correct while the frontend calls it incorrectly;
- one document section can be complete while the full document is duplicated;
- one startup task can look correct while final edits later make the application unlaunchable.

### Parent integration review exists as guidance, not an enforced oracle

**[D]** Current source gives parent executors and Reviewers a child-verification gate and tells them to verify composed behavior (`src/tinycua/tinycua/loops/task_nodes.py:834-860,1018-1029`).

That gate remains a prompt obligation. The runtime does not require a particular integration command or evidence artifact before accepting the decision.

### Reviewer evidence is bounded

**[D]** Node configuration disables ordinary chat history and bounds the context supplied to executors/reviewers (`src/tinycua/tinycua/config/node_config.py:324-328`). Reviewer evidence contains task state, the executor outcome, roadmap context, and a bounded set of recent tool outcomes (`src/tinycua/tinycua/loops/task_nodes.py:1052-1133`).

Important earlier failures or full command output can disappear unless explicitly preserved in task state, files, or logs.

## The environment boundary

### Executor and Reviewer share construction state: proven

**[D]** One TinyCUA agent container mounts one workspace volume at `/workspace` for the pair (`src/experiment/run_template_experiment.py:519-556,2212-2245`). TinyCUA nodes bind tools to the same configured workspace, and shell subprocesses execute there (`src/tinycua/tinycua/loops/tinycua_loop.py:455-466`; `src/tinycua/tinycua/agent/tools/native/shell.py:398-410`).

Executor and Reviewer can therefore share:

- files modified by earlier tasks;
- virtual environments and installed packages;
- SQLite databases and migration state;
- generated helper files;
- fixed ports;
- background or still-running child processes; and
- server code loaded before later source edits.

This is what “construction-environment pollution” means in this report. It is shared mutable state, not necessarily an implementation bug by itself.

### Nodes have fresh conversation state but not a clean machine

**[D]** TinyCUA creates node sessions while retaining common configuration, task state, and workspace access (`src/tinycua/tinycua/loops/node.py:302-342`). Fresh LLM context does not reset processes, packages, databases, files, or ports.

### The evaluator is isolated: proven

**[D]** The evaluator runs in a separate `docker run` container with the candidate volume mounted read-only at `/submission` (`src/experiment/run_template_experiment.py:645-681,2095-2118`). Experiment 4 then copies that tree into evaluator-owned storage before launch (`src/experiment/experiment-fixtures/experiments-list/experiment-4/eval/check.py:266-285`).

The evaluator does not inherit the agent's running process, construction venv, installed system packages, fixed-port state, or in-memory application code.

This boundary is intentional: it tests whether the **exported artifact** is self-sufficient.

## Controlled Experiment 4: full TinyCUA chronology

### 1. Initial implementation is reviewed mostly by reading files

The first tasks create project files, then write `start.sh`, `app.py`, and `templates/index.html` (`src/experiment/template-results/experiment-4/tinycua/stdout.log:85-138`). The following Reviewer lists and reads files and approves without a runtime shell check (`src/experiment/template-results/experiment-4/tinycua/stdout.log:140-165`).

### 2. Later tasks mutate persistence and integration

The storage task edits `app.py`. The final `init_db()` drops and recreates `blocks`, so every genuine restart destroys retained data (`src/experiment/template-results/experiment-4/tinycua/workdir/app.py:20-46`). Backend and UI tasks continue editing the same files (`src/experiment/template-results/experiment-4/tinycua/stdout.log:167-255`).

The “Integration and Start Script Finalization” task reads files and reports success without a shell/browser action (`src/experiment/template-results/experiment-4/tinycua/stdout.log:270-282`).

### 3. Testing occurs in the construction environment

The testing Executor performs many shell actions (`src/experiment/template-results/experiment-4/tinycua/stdout.log:293-361`). `start.sh` uses the construction-specific paths `/workspace/venv`, `/workspace/requirements.txt`, and `/workspace/app.py` (`src/experiment/template-results/experiment-4/tinycua/workdir/start.sh:13-28`).

The retained application log records:

- dependencies already present in the construction venv;
- one Flask startup on fixed port 8765;
- direct API create/edit/delete requests; and
- no second Flask startup.

Evidence: `src/experiment/template-results/experiment-4/tinycua/workdir/logs/app.log:1-41`.

These checks prove that one construction-environment process handled direct API traffic. They do not prove that final exported files launch cleanly or that the browser workflow works.

### 4. Final source changes occur after the retained launch

After the long shell sequence, the Executor reads and edits `app.py` again, then performs more shell actions (`src/experiment/template-results/experiment-4/tinycua/stdout.log:363-381`). The final exported source contains literal `\n` tokens between decorators and function definitions, making it invalid Python (`src/experiment/template-results/experiment-4/tinycua/workdir/app.py:115-130`).

The next Reviewer performs no shell/browser call. It accepts Executor claims through task inspection and decisions (`src/experiment/template-results/experiment-4/tinycua/stdout.log:383-394`). The root Executor/Reviewer again inspect and approve without a clean launch (`src/experiment/template-results/experiment-4/tinycua/stdout.log:396-425`).

### 5. Fresh evaluation fails immediately

After export, the evaluator's independent launch exits 1 and every browser operation is refused (`src/experiment/template-results/experiment-4/tinycua/stderr.log:605-631`; `src/experiment/template-results/experiment-4/tinycua/result.json:20-98`).

The final artifact has at least three independent blockers:

1. construction-specific absolute paths;
2. invalid Python syntax; and
3. destructive table initialization.

Evaluator child stderr is not retained, so the exact first blocker is not identifiable.

### Was a stale server tested?

**Strongly supported, not proven.**

Supporting evidence:

- one server startup is retained;
- later checks continue after source mutation;
- no second startup appears despite claims of kill/restart;
- final source cannot launch; and
- late Reviewer approvals contain no independent shell/browser evidence.

The exact `run_shell` command bodies and complete outputs are omitted from the compact stdout log, so it is still possible that another unretained process was launched. The report should not state stale-process reuse as proven fact.

### Causal chain

1. Executor launches and tests within `/workspace`.
2. Installed dependencies, database state, and a running process remain available.
3. Later tasks edit source after the retained process has loaded code.
4. Reviewer accepts task reports/file inspection without a clean restart.
5. Root integration approval remains prompt-driven.
6. Export contains only files, not the successful in-memory process or construction environment.
7. Isolated evaluation launches final files and fails.

This is the strongest example of environment-assisted false confidence.

## Controlled Experiment 4: `tinycua-nd`

This run shows one real Reviewer-caused correction and the same integration limitation.

### Genuine correction

**[D]** The Reviewer notices that the API still uses the old `texts` table after the schema changes to pages/blocks (`src/experiment/template-results/experiment-4/tinycua-nd/stdout.log:172-183`). Executor revisions add pages/blocks behavior, and later reviews inspect the corrected schema/API (`src/experiment/template-results/experiment-4/tinycua-nd/stdout.log:185-243`).

This is a real cross-file consistency improvement caused by review.

### Misfocused runtime diagnosis

The Reviewer later claims nullable SQLite foreign keys will reject `NULL` and runs multiple shell checks (`src/experiment/template-results/experiment-4/tinycua-nd/stdout.log:314-343`). SQLite permits nullable foreign keys, so the diagnosis is incorrect.

The retained `server.log` shows only failed POST requests against an older `page_id NOT NULL` schema and a database-lock failure (`src/experiment/template-results/experiment-4/tinycua-nd/workdir/server.log:11-48`). Final `start.sh` declares nullable `page_id`, proving the retained process/database predates the final script (`workdir/start.sh:44-53`).

Later Reviewer text claims successful API checks (`src/experiment/template-results/experiment-4/tinycua-nd/stdout.log:345-384`), but the retained log does not prove a successful POST. Another unretained process is possible.

### Final integration defects

The fresh evaluator starts the app and detects Python, proving this artifact is more portable than full TinyCUA. It then fails every browser CRUD/persistence category (`src/experiment/template-results/experiment-4/tinycua-nd/result.json:27-81`).

The exported defects are direct:

- the only textarea is inside a hidden overlay, so no text field is initially visible (`workdir/start.sh:92-124`); and
- every invocation deletes `.database/app.db`, making restart persistence impossible (`workdir/start.sh:21-33`).

The Reviewer focused on API behavior rather than the required visible browser flow and clean restart.

## Experiment 3: a semantic verification failure

Environment isolation is not the main problem in the full clock run.

**[D]** The final artifact calculates `currentHandStates` but draws the initial `handStates`, so hands remain static (`src/experiment/template-results/experiment-3/tinycua/workdir/clock.html:156-217`). Executor and Reviewer narrate formulas and source structure and approve (`src/experiment/template-results/experiment-3/tinycua/stdout.log:227-257`).

The external browser evaluator loads the same artifact and fails every movement category (`src/experiment/template-results/experiment-3/tinycua/result.json:55-74`).

**[I]** The Reviewer checked the presence of an animation loop and time formulas, not the data flow from fresh state to drawing. This is a semantic source-review false positive, not construction-environment pollution.

The `tinycua-nd` clock demonstrates a path-contract variation: it browser-tests `/workspace/clock.html/index.html`, while the required output is a root file named `clock.html`. Reviewer inspection of the nested page cannot establish exported-path compliance (`src/experiment/template-results/experiment-3/tinycua-nd/stdout.log:182-265`; `src/experiment/template-results/experiment-3/tinycua-nd/result.json:20-81`).

## Experiment 5: global-document integration failure

No process contamination is needed to explain the guide defects.

### Full TinyCUA

The Reviewer claims all TOC links work, but “5. Positional Encoding” points to `#6-positional-encoding` while the heading is section 5 (`src/experiment/template-results/experiment-5/tinycua/stdout.log:102-107`; `src/experiment/template-results/experiment-5/tinycua/workdir/study-guide.md:3-11,255-257`; `src/experiment/template-results/experiment-5/tinycua/result.json:41-46`).

This is direct structural review failure.

### `tinycua-nd`

The Reviewer detects missing Transformer material and causes it to be added (`src/experiment/template-results/experiment-5/tinycua-nd/stdout.log:171-300`). That is a local content change, not proof of a better final guide: the resulting artifact remains duplicated and technically flawed. A later complaint about a missing study plan does not produce a demonstrated correction because the plan already exists and subsequent tools only inspect it (`src/experiment/template-results/experiment-5/tinycua-nd/workdir/study-guide.md:359`; `src/experiment/template-results/experiment-5/tinycua-nd/stdout.log:440-495`).

It also shows context instability: the same 3,185-logical-line file is approved, then described as only one section, then only a title, then approved again (`src/experiment/template-results/experiment-5/tinycua-nd/stdout.log:475-562`). Full outputs are persisted and offset reads remain possible, so the file itself was not truncated; the immediate preview/context was bounded.

Repeated per-task appends create duplicate headings. The evaluator deducts `unique_headings` but still passes the guide because that point is not critical (`src/experiment/template-results/experiment-5/tinycua-nd/result.json:48-53`).

**[I]** Active-task review can improve missing local content while failing to enforce global editorial coherence.

## Where review demonstrably changes artifacts

| Run | Reviewer finding | Downstream change | Bounded effect |
|---|---|---|---|
| Experiment 2, `tinycua-nd` | Evidence/source coverage repeatedly judged insufficient. | Supplementary URLs and explicit limitations are added; citation check passes. | Improved source-count coverage, though based on an invented per-family requirement. |
| Experiment 4, `tinycua-nd` | API still references obsolete schema/table. | Executor revises pages/blocks schema and routes. | Real cross-file consistency correction. |
| Experiment 5, `tinycua-nd` | Transformer sections missing or off-scope. | Transformer material is added and later verified. | Real content-completeness correction. |

The observed corrections involve file-visible, task-local defects. They demonstrate activity, not net user benefit: final pass count does not improve consistently and serious defects remain. This campaign does not establish conditions that reliably predict Reviewer effectiveness.

## Why integration between tasks escapes

### 1. Local correctness does not compose automatically

Each leaf can be approved against its own report while assumptions diverge across siblings. Integration requires retesting the composed artifact, not summing approvals.

### 2. The final integration gate is probabilistic

Parent/root guidance requests integration verification, but no runtime rule maps task type to a mandatory executable check.

### 3. Review and execution share mutable construction state

A server, venv, package, database, or generated file created by one task can satisfy later checks even when the exported artifact cannot reproduce that state.

### 4. Final edits can invalidate earlier evidence

Earlier successful checks are not automatically invalidated when another task edits the same file. The final `app.py` mutation after the retained server launch is the clearest example.

### 5. Review evidence is compressed

Outcome reports and recent tool metadata can omit full command output or earlier failures. The Reviewer may evaluate the Executor's interpretation rather than raw evidence.

### 6. Export is a separate trust boundary

The evaluator tests only retained files under a new path and process. Runtime state that made construction tests pass is deliberately absent.

## What approval would need to mean

The smallest robust change is not another LLM Reviewer. It is one mandatory, task-appropriate acceptance command executed after all final mutations and from a clean context.

For web applications:

1. export or copy final files to a fresh path;
2. install only from retained manifests;
3. choose a fresh port;
4. run exact `PORT=<port> sh start.sh`;
5. require a Python child process;
6. drive create/select/edit/delete through visible accessible controls;
7. reload and inspect SQLite;
8. stop the process group;
9. restart from final files; and
10. recheck retained/deleted state.

For clocks:

- freeze time;
- inspect rendered geometry;
- advance scheduled callbacks; and
- verify clockwise changes.

For large documents:

- scan global heading uniqueness;
- validate every TOC target;
- detect repeated major sections; and
- execute or lint code examples when correctness matters.

Only after that evidence succeeds should Reviewer approval represent integration correctness.

## Limits

- The compact logs omit literal shell command bodies and many full outputs.
- Stale-process reuse in full Experiment 4 is strongly supported but not proven.
- The immediate evaluator startup error does not identify which independent blocker fired first.
- Current source describes the present Reviewer contract; the campaign source is pinned at `89d2402e`, and no later TinyCUA source changes are included in these report commits.
- One unseeded trial cannot estimate false-approval rates.

## Bottom line

TinyCUA's Reviewer does real work and sometimes corrects local defects, but this campaign shows no net final-quality benefit. Independent behavioral verification is optional, decisions are active-task scoped, integration gates are prompt-level obligations, and testing occurs inside the Executor's shared mutable construction environment. The isolated evaluator tests a stronger claim: that final exported files work from a clean launch. Experiment 4 demonstrates the gap most clearly; Experiments 3 and 5 show that semantic and global-structure failures remain even without environment contamination.
