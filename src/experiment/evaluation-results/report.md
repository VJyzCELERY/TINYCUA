# Experiment Results Report

This report summarizes five agent-harness experiments comparing `opencode`, `hermes`, `openclaw`, and `tinycua`.

Judge verdicts are centralized under [`judges_verdict/`](judges_verdict/). Each experiment directory contains:

- `verdict.md` — cross-harness judge verdict.
- `mapping.json` — anonymous submission mapping and judge metadata.

## Evaluation Setup

All evaluated harnesses used the same local inference model:

| Setting | Value |
|---|---|
| Model | Qwen3.5 9B (`qwen3.5-9b`) |
| Provider/API | OpenAI-compatible local server via LM Studio |
| Context length | 262,144 tokens |
| GPU offload | 32 layers |
| CPU threads / thread pool | 9 |
| Evaluation batch size | 2048 |
| Physical batch size | 512 |
| Max concurrent requests | 4 |
| Thinking | Enabled |
| Temperature | 0.6 |
| Context overflow | Rolling window |
| Top-K | 20 |
| Top-P | 0.95 |
| Min-P | 0 |
| Repeat penalty | 1.1 |
| Presence penalty | 1 |
| Flash Attention | Enabled |
| Unified KV cache | Enabled |
| KV cache quantization | K: Q8_0, V: Q8_0 |
| KV cache GPU offload | Enabled |
| Keep model in memory | Enabled |
| mmap | Enabled |
| Structured output | Disabled |

The cross-submission judge was an **opencode agent** running model **`openai/gpt-5.5`** with variant **`high`**.

Submissions were anonymized during judging:

| Submission | Harness |
|---|---|
| A | opencode |
| B | hermes |
| C | openclaw |
| D | tinycua |

This anonymization reduces direct name bias, but the judge harness is still opencode. That should be disclosed as a validity limitation because opencode is also one of the evaluated systems.

## Experiment Tasks

| Experiment | Task type | Prompt summary |
|---:|---|---|
| 1 | Conversational | Respond to `Hello there`. |
| 2 | Research report | Search current frontier LLMs and write `report.md`. |
| 3 | Small code artifact | Build a single-file animated analog clock HTML app. |
| 4 | Complex code artifact | Build a Notion-like app using Python backend, web UI, and SQLite. |
| 5 | Study documentation | Research neural networks and transformers and write comprehensive markdown learning docs. |

## Judge Score Summary

| Harness | Exp1 | Exp2 | Exp3 | Exp4 | Exp5 | Average |
|---|---:|---:|---:|---:|---:|---:|
| opencode | 4.2 | 2.8 | 4.2 | 2.4 | 4.2 | **3.56** |
| tinycua | 3.8 | 3.0 | 3.6 | 2.2 | 4.0 | **3.32** |
| hermes | 4.0 | 3.8 | 2.0 | 2.2 | 3.8 | **3.16** |
| openclaw | 2.8 | 3.6 | 2.6 | 2.2 | 4.4 | **3.12** |

Ranking by average score:

1. opencode — 3.56
2. tinycua — 3.32
3. hermes — 3.16
4. openclaw — 3.12

## Per-Experiment Findings

### Experiment 1: Greeting

All harnesses handled the simple greeting, but outputs were noisy because harness logs were visible. opencode ranked highest; tinycua was third due duplicated/internal routing output.

### Experiment 2: Frontier LLM Report

All harnesses produced a `report.md`, but the judge flagged weak sourcing and likely unsupported claims across all submissions. Hermes ranked highest because its report was broad and organized. TinyCUA produced a substantial report but was penalized for repetition and weaker direct comparative focus.

### Experiment 3: Analog Clock HTML App

opencode produced the strongest single-file clock. TinyCUA ranked second: it produced a working simple canvas-based clock, but the judge found issues with immediate rendering, hand angles, and polish. Hermes and openclaw missed core animation/hand behavior.

### Experiment 4: Notion-like App

All submissions failed to produce a working application. opencode was marginally strongest at 2.4/5, but every harness had severe integration, dependency, or runtime issues. TinyCUA produced a modular FastAPI/SQLAlchemy-style backend plus a polished single-file frontend, but backend/frontend wiring was broken and imports failed due missing dependencies.

### Experiment 5: Neural Networks and Transformers Study Docs

openclaw ranked highest for balance of clarity and correctness. TinyCUA produced the broadest output: many markdown documents covering fundamentals, history, training, attention, transformer variants, applications, implementation, future directions, and resources. The judge penalized TinyCUA for fragmentation, repetition, and technical issues in formulas/examples.

## TinyCUA Strengths

### 1. Broad coverage on open-ended tasks

TinyCUA tends to expand broad requests into explicit work units. This helped it produce extensive artifacts, especially in Experiment 5, where it generated 22 markdown files and covered many topic areas.

### 2. Structured decomposition

TinyCUA's architecture routes larger tasks through Query Analyst, Information Digester, Worker, Task Creation, Task Analyzer, Task Executor, Result Reviewer, aggregation, and final response. This makes its work process observable and explainable.

TinyCUA's important behavioral difference is that it turns analysis from an optional model behavior into a required harness behavior. In ordinary single-session harnesses, the LLM may choose to analyze, plan, or use a todo list, but this depends on the model's generated behavior. In Worker Mode, TinyCUA requires pre-execution analysis through Query Analyst, Information Digester, Task Creation, Task Analyzer, and Task Assessor before Task Executor begins work.

### 3. Consistent task-list creation

Many agent harnesses include todo/task-list tools, but using them is usually optional. In these runs, opencode only used `todowrite` in Experiment 4 and did not use it in Experiments 1, 2, 3, or 5. Hermes exposed a `todo` toolset, but the logs only show the toolset being available, not used for task execution. OpenClaw showed no visible todo/task-list usage.

TinyCUA is different in Worker Mode: task-list creation is mandatory. For every Worker Mode experiment (Experiments 2–5), TinyCUA initialized and decomposed a task tree before execution.

| Harness | Exp1 | Exp2 | Exp3 | Exp4 | Exp5 | Pattern |
|---|---:|---:|---:|---:|---:|---|
| opencode `todowrite` calls | 0 | 0 | 0 | 2 | 0 | Optional; used only for complex app task. |
| hermes todo calls | 0 | 0 | 0 | 0 | 0 | Todo toolset available, not visibly invoked. |
| openclaw todo/task-list usage | 0 | 0 | 0 | 0 | 0 | No visible todo usage. |
| tinycua `task_init` calls | 0 | 1 | 1 | 1 | 1 | Mandatory in Worker Mode. |
| tinycua `task_decompose` calls | 0 | 3 | 1 | 2 | 3 | Mandatory decomposition workflow. |

This suggests that TinyCUA makes task-list planning a consistent agent behavior rather than an optional tool-use choice.

This distinction matters because todo tools alone do not guarantee structured execution. In opencode Experiment 4, the agent created a todo list at the start but updated it only near the end, marking several items complete in bulk. The todo list helped express intent, but it did not enforce task-by-task execution. TinyCUA's task tree is part of the runtime control loop, so task state must be initialized, decomposed, executed, result-updated, and reviewed before progression.

### 4. Competitive quality

TinyCUA ranked second overall by average judge score. It did not beat opencode, but it stayed competitive across task categories.

### 5. Self-supervising behavior

TinyCUA's strongest architectural effect is that it makes the LLM behave less like a single-shot session and more like a supervised workflow. Instead of relying on one continuous generation that eventually stops when the model decides the task is complete, TinyCUA repeatedly re-prompts specialized roles around persistent task state.

The Result Reviewer is the key mechanism. It forces task outputs through an explicit review step before they are accepted, retried, or replanned. This makes self-review systematic rather than optional.

This means TinyCUA can make smaller or local LLMs behave more systematically by externalizing analysis, planning, and review into the agent runtime instead of relying on the model to voluntarily perform them in a single session.

## TinyCUA Weaknesses

### 1. High and variable runtime cost

TinyCUA was much slower than the other harnesses on non-trivial tasks.

| Experiment | TinyCUA duration |
|---:|---:|
| 1 | 5.1s |
| 2 | 1127.9s |
| 3 | 311.8s |
| 4 | 1985.0s |
| 5 | 4456.9s |

The better explanation is not simply “TinyCUA runs many planning loops.” In Experiments 2–5, the early loop shape was similar: about three task-analysis starts and two assessor starts. Runtime instead tracked how large the task tree became and how many executor/reviewer cycles followed.

| Experiment | Early task-tree growth observed in logs | Task executor starts | Result reviewer starts | Duration |
|---:|---|---:|---:|---:|
| 3 | about 7 tasks | 8 | 8 | 311.8s |
| 2 | about 9+ tasks | 14 | 14 | 1127.9s |
| 4 | about 8 → 12+ tasks | 18 | 14 | 1985.0s |
| 5 | about 13 → 18+ tasks | 23 | 23 | 4456.9s |

Interpretation:

> TinyCUA runtime depends heavily on early task-tree granularity. When initial task analysis expands a request into many subtasks, each leaf tends to incur executor and reviewer work, increasing latency and token usage.

Experiment 4 needs an additional qualification: its runtime was amplified by prototype retry and verification-tooling weaknesses, not only by task-tree size. The detailed failure mode is discussed in the verification-gate analysis below.

### 2. Decomposition does not guarantee correctness

Experiment 4 is the clearest failure case. TinyCUA decomposed the app into backend, database, auth, pages, users, and frontend pieces, but the final product was still not runnable. The task tree improved coverage, not integration correctness.

### 3. Overproduction and fragmentation

Experiment 5 shows TinyCUA's tendency to produce many separate files. This improved breadth but reduced cohesion: the judge noted lack of a clear master guide/index, repetition, and inconsistent correctness.

### 4. Prototype verification is still weak

TinyCUA is more consistent at self-review than the other harnesses, but the current prototype's verification system is not yet strong enough. The Result Reviewer often checks local task claims, such as whether a file exists or whether a command ran, but this does not guarantee that all accepted tasks integrate into a working final system.

Experiment 4 demonstrates this limitation: TinyCUA performed repeated review and revision, but the final app still failed integration-level correctness checks.

### 5. Experiment 4 runtime and verification-gate analysis

Experiment 4 should not be interpreted only as evidence that TinyCUA's architecture is inherently slow. The logs show that a large part of the slowdown came from prototype implementation weaknesses in task-state enforcement, path handling, shell execution, and review-decision control.

TinyCUA reported 18 TaskExecutor starts but only 14 ResultReviewer starts. This mismatch is explainable from the logs: four TaskExecutor sessions never produced a successful `task_result_update`, so there was no task result for the ResultReviewer to review. Those sessions ended with retry exhaustion and the runtime warning:

> `TaskExecutor must call task_result_update with an outcome report before finishing. Task state cannot be inferred from prose.`

Therefore, the extra executor calls were not normal task work. They were failed executor sessions where the runtime repeatedly tried to force the executor to satisfy the task-state contract.

| Area | Observed behavior | Interpretation |
|---|---|---|
| Frontend-backend integration | Multiple TaskExecutor sessions reached 25 model/tool-call attempts without `task_result_update`. | Runtime overhead came from contract/retry failure, not only decomposition. |
| Final parent verification | Executor attempted integration fixes and verification, then also reached retry exhaustion before a later executor produced a result. | Parent-level verification lacked a deterministic bounded recipe. |
| ResultReviewer | Repeated `needs_revision` / `rejected` decisions were sometimes overwritten by later `approved` decisions in the same review session. | Review decisions were not treated as single authoritative outcomes. |

The logs also show a path-normalization problem. For example, the TaskExecutor successfully wrote authentication files under the experiment workspace:

- `/workspace/experiment-4/backend/api/auth/auth.py`
- `/workspace/experiment-4/backend/api/auth/__init__.py`

However, the ResultReviewer initially checked absolute paths outside that workspace:

- `/backend/api/auth/auth.py`
- `/backend/api/auth/__init__.py`

Those checks reported the files as missing, causing rejection or revision decisions. Later, when the reviewer used `/workspace/experiment-4/...` or relative paths, it found the files and approved the task. The same pattern appeared earlier for backend API files: the executor wrote files under `/workspace/experiment-4/backend/api/...`, while the reviewer checked `/backend/api/...` and reported them missing.

This means some Experiment 4 review failures were caused by weak verification tooling and inconsistent workspace path handling, not necessarily by the executor failing to create files.

A similar issue appeared with shell environment handling. Some reviewer checks used `source`, but the shell execution context behaved like `/bin/sh`, producing `exit_code=127`. The reviewer then interpreted dependency imports such as `ModuleNotFoundError: No module named 'fastapi'` as evidence that dependencies were missing, even though part of the issue was inconsistent activation or command context.

These details change the interpretation of TinyCUA's slowness:

> Experiment 4's runtime cost was not caused only by TinyCUA's architecture. The architecture created more checkpoints, but the largest overhead came from prototype implementation weaknesses: retry exhaustion when executor nodes failed to update task state, non-canonical workspace paths, shell-context mismatch, and review decisions that could be repeated or overwritten.

The architectural idea remains useful: task execution is explicit, reviewed, and observable. The problem is that the current prototype needs stronger deterministic gates before those reviews can reliably improve final correctness.

Recommended implementation improvements:

- enforce one canonical workspace root for all tools and reviewer checks;
- normalize task-reported paths before verification;
- make `task_review_decision` single-final per review session, or require explicit supersession metadata;
- replace ad hoc shell checks with deterministic verifier helpers such as `file_exists(path)`, `python_import(module, cwd, venv)`, and `command_ok(command, cwd)`;
- fail fast when TaskExecutor does not call `task_result_update` instead of allowing long retry loops;
- add bounded parent-task verification recipes for app tasks: dependency install, import check, backend startup check, and frontend/API route consistency check.

In short, Experiment 4 shows that TinyCUA's verification gate is promising but immature. The prototype can detect local false claims, but weak tooling caused false negatives, repeated decisions, and excessive runtime. The next improvement should focus less on reducing decomposition and more on making verification deterministic, path-aware, and bounded.

## Interpretation

The results do not support the claim that TinyCUA is globally better than existing harnesses. They support a narrower claim:

> TinyCUA demonstrates competitive task quality and stronger decomposition-driven coverage on broad tasks, but this comes with substantial runtime overhead. Its performance depends strongly on early task-tree granularity, and decomposition alone does not ensure executable correctness.

TinyCUA should be presented as a trade-off:

- **Benefit:** explicit decomposition, broader coverage, observable orchestration.
- **Benefit:** more systematic self-supervision through task execution and Result Reviewer loops.
- **Cost:** high latency, token overhead, and risk of fragmented or over-expanded outputs.
- **Open problem:** improve verification so decomposition increases integrated correctness rather than only breadth.

A promising improvement is not necessarily reducing task granularity. Fine-grained tasks improve observability and coverage. The more important improvement is upgrading verification.

TinyCUA should strengthen the Result Reviewer with:

- deterministic checks for file existence, imports, syntax, dependency installation, and command exit codes;
- task-type-specific verification recipes;
- integration gates that verify groups of related tasks together;
- final end-to-end acceptance checks before aggregation;
- stricter evidence requirements before marking a task as accepted.

This would preserve TinyCUA's main strength — decomposition-driven self-supervision — while reducing the risk that locally accepted tasks fail as an integrated deliverable.

In short:

> TinyCUA can make an LLM more self-supervising by wrapping it in a persistent task/review loop. However, because the current system is still a prototype, its tools and verification gates are not strong enough to guarantee integrated correctness. The next step is to make the Result Reviewer more deterministic and more integration-aware.

## Limitations

- Only five tasks were evaluated.
- The judge was an opencode agent using GPT-5.5 high. Submissions were anonymized during judging, so the judge did not know which harness produced each output. This reduces direct harness-name bias, but the evaluator still ran through the opencode harness, so evaluator-harness effects remain a limitation.
- Some tasks, especially Experiment 4, are much more complex than others and dominate qualitative interpretation.
- Runtime is affected by task complexity, local model responsiveness, tool calls, and TinyCUA's task-tree growth.
- The judge scores combine qualitative and tested evidence; they should be treated as comparative signals, not absolute ground truth.
