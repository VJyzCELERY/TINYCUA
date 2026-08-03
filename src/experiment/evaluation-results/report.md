# Experiment Results Report

This report summarizes five agent-harness experiments comparing `opencode`, `hermes`, `openclaw`, and `tinycua`.

Judge verdicts are centralized under [`judges_verdict/`](judges_verdict/). Each experiment directory contains:

- `verdict.md` — cross-harness judge verdict.
- `mapping.json` — anonymous submission mapping and judge metadata.

The source per-experiment verdict directories under `opencode/experiment-N/cross_verdict/` additionally retain `raw_output.txt`, `raw_stderr.txt`, and `judge_model_snapshot.txt` for audit. Per-harness run logs and workdirs live under `{harness}/experiment-N/run_logs/` and `{harness}/experiment-N/workdir/`.

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

The cross-submission judge was a **hermes-judge container** running model **`openai/gpt-5.5`** with variant **`high`**, via the `openai-codex` provider at `https://chatgpt.com/backend-api/codex`. The judge container is a persistent Hermes Agent instance configured separately from the evaluated harnesses; its model and provider are snapshotted into each verdict directory's `mapping.json` for audit.

Submissions were anonymized during judging:

| Submission | Harness |
|---|---|
| A | opencode |
| B | hermes |
| C | openclaw |
| D | tinycua |

This anonymization reduces direct name bias, but the judge harness is still hermes. That should be disclosed as a validity limitation because hermes is also one of the evaluated systems.

## Experiment Tasks

| Experiment | Task type | Prompt summary |
|---:|---|---|
| 1 | Conversational | Respond to `Hello there`. |
| 2 | Research report | Search current frontier LLMs and write `report.md`. |
| 3 | Small code artifact | Build a single-file animated analog clock HTML app. |
| 4 | Complex code artifact | Build a Notion-like app using Python backend, web UI, and SQLite. |
| 5 | Study documentation | Research neural networks and transformers and write comprehensive markdown learning docs. |

## Judge Score Summary

Task types are reported separately because coding correctness, research quality,
and conversational quality are not commensurate.

### Conversation outcome

| Harness | Exp1 |
|---|---:|
| opencode | 4.8 |
| tinycua | 4.8 |
| hermes | 4.6 |
| openclaw | 2.8 |

### Research outcomes

| Harness | Exp2 | Exp5 |
|---|---:|---:|
| opencode | 3.2 | 3.6 |
| tinycua | 4.6 | 3.2 |
| hermes | 4.2 | 4.4 |
| openclaw | 2.6 | 1.6 |

### Coding outcomes

| Harness | Exp3 | Exp4 |
|---|---:|---:|
| opencode | 4.4 | 2.0 |
| tinycua | 3.2 | 1.8 |
| hermes | 1.8 | 1.6 |
| openclaw | 3.4 | 1.6 |

TinyCUA tied opencode on the conversation task and led Experiment 2, while
opencode led both historical code-artifact judgments. These task-specific
results are not combined into an overall rank.

## Per-Experiment Findings

### Experiment 1: Greeting

All of opencode, hermes, and tinycua answered the simple greeting appropriately. opencode (A) and tinycua (D) tied at 4.8 — both concise and friendly, with only modest stdout logging noise. hermes (B) scored 4.6: the final answer was good but the submission was significantly noisier due to extensive initialization output. openclaw (C) scored 2.8, the weakest, because it overcomplicated a simple greeting with an unnecessary identity/persona setup exercise and had heavily cluttered plugin/debug logs.

### Experiment 2: Frontier LLM Report

All harnesses produced a `report.md`, but sourcing and currency differed sharply. tinycua (D) ranked highest at 4.6 — the most complete, sourced, current, and useful report, with model rankings, benchmark discussion, recommendations, pricing, and source links. It was penalized only for a serious cost-calculation arithmetic error. hermes (B) scored 4.2: substantial and well organized but less verifiable and prone to unsupported or overconfident claims. opencode (A) scored 3.2: readable and structured but with questionable model names (e.g. "GPT-o4"), dubious context-window claims, and weak benchmark figures. openclaw (C) scored 2.6: organized but explicitly stale (late-2024 knowledge), missing current model families and benchmarks.

### Experiment 3: Analog Clock HTML App

opencode (A) produced the strongest single-file clock at 4.4 — functional, visually polished, with correct hand movement, despite flawed hour-marker placement. openclaw (C) ranked second at 3.4: mostly functional and animated, but missing visible markers and with some alignment issues. tinycua (D) scored 3.2: a complete canvas-based approach, but the hands rotated the wrong direction (counterclockwise due to negative angles) and the file contained unused/conflicting DOM hand elements. hermes (B) scored 1.8 — worst because a JavaScript runtime error (`clock.querySelector('.center-dot')` against a nonexistent element) prevented the animation from starting, breaking the core requested behavior.

### Experiment 4: Notion-like App

All four submissions failed to produce a working application. opencode (A) ranked highest at 2.0 — the most directly aligned with the requested Notion-like app, with a recognizable sidebar/editor UI, page/block CRUD intent, SQLite models, and documentation, though the backend was not runnable (missing imports/definitions, unbound SQLAlchemy sessions, invalid `create_all`). tinycua (D) scored 1.8: the most modern stack (FastAPI + sqlmodel + React/Vite) and some useful backend/frontend components, but the shipped frontend was mostly the default Vite starter, the Notion-specific components were not integrated, and API/frontend request fields mismatched. hermes (B) and openclaw (C) both scored 1.6 — nonfunctional scaffolds with severe correctness issues: hermes' implementation was extremely broken, duplicated, and internally inconsistent; openclaw's ambitious FastAPI scaffold had truncated models and syntactically invalid files (JavaScript beginning with Python triple-quoted strings).

### Experiment 5: Neural Networks and Transformers Study Docs

hermes (B) ranked highest at 4.4 — the cleanest, most coherent, and most useful study guide, with broad coverage and relatively few correctness issues. opencode (A) scored 3.6: solid and readable but weaker due to more broken pseudo-code and technical inaccuracies (incorrect RNN state handling, broken Transformer/PyTorch snippets). tinycua (D) scored 3.2: extremely comprehensive in volume — a single 188KB markdown file covering fundamentals through future architectures — but heavily duplicated, poorly edited, internally repetitive, with malformed markdown/LaTeX and many factual/technical errors. openclaw (C) scored 1.6, the weakest: its workdir was empty and stdout contained mostly runtime/tool logs plus a partial markdown-like response, so it failed to provide a clean comprehensive study document.

## TinyCUA Strengths

### 1. Broad coverage on open-ended tasks

TinyCUA tends to expand broad requests into explicit work units. This helped it produce extensive, well-sourced artifacts: it won Experiment 2 outright on completeness and sourcing, and in Experiment 5 it produced a single 188KB comprehensive study guide covering fundamentals, architectures, training, attention, transformer variants, applications, implementation, and future directions.

### 2. Structured decomposition

TinyCUA's architecture routes larger tasks through Query Analyst, Information Digester, Worker, Task Creation, Task Analyzer, Task Assessor, Task Executor, Result Reviewer, aggregation, and final response. This makes its work process observable and explainable.

TinyCUA's important behavioral difference is that it turns analysis from an optional model behavior into a required harness behavior. In ordinary single-session harnesses, the LLM may choose to analyze, plan, or use a todo list, but this depends on the model's generated behavior. In Worker Mode, TinyCUA requires pre-execution analysis through Query Analyst, Information Digester, Task Creation, Task Analyzer, and Task Assessor before Task Executor begins work.

### 3. Consistent task-list creation

Many agent harnesses include todo/task-list tools, but using them is usually optional. In these runs, opencode used its `task` subagent tool once in Experiment 4 and did not use it in Experiments 1, 2, 3, or 5. hermes exposed a `todo` toolset and invoked it once in Experiment 4; it was not visibly invoked in the other experiments. openclaw showed no visible todo/task-list usage in any experiment.

TinyCUA is different in Worker Mode: task-list creation is mandatory. For every Worker Mode experiment (Experiments 2–5), TinyCUA initialized and decomposed a task tree before execution.

| Harness | Exp1 | Exp2 | Exp3 | Exp4 | Exp5 | Pattern |
|---|---:|---:|---:|---:|---:|---|
| opencode `task` subagent calls | 0 | 0 | 0 | 1 | 0 | Optional; used only for complex app task. |
| hermes `todo` tool calls | 0 | 0 | 0 | 1 | 0 | Todo toolset available, used once for app task. |
| openclaw todo/task-list usage | 0 | 0 | 0 | 0 | 0 | No visible todo usage. |
| tinycua `task_init` calls | 0 | 1 | 1 | 1 | 1 | Mandatory in Worker Mode. |
| tinycua `task_decompose` calls | 0 | 2 | 2 | 12 | 3 | Mandatory decomposition workflow. |

This suggests that TinyCUA makes task-list planning a consistent agent behavior rather than an optional tool-use choice.

This distinction matters because todo tools alone do not guarantee structured execution. In opencode Experiment 4, the agent delegated the whole build to a single `task` subagent that returned a claimed-complete result in one shot. The todo/subagent helped express intent, but it did not enforce task-by-task execution. TinyCUA's task tree is part of the runtime control loop, so task state must be initialized, decomposed, executed, result-updated, and reviewed before progression.

In other words, a todo that is written once and updated at the end (or never) is a record of intent, not a control mechanism; it cannot guide step-by-step execution because nothing in the runtime depends on its intermediate state. TinyCUA's task tree guides execution because progression is gated on task state, not merely recorded by it.

This is also why TinyCUA is slow on a small language model. Keeping the task tree as a real control loop means the runtime must ensure the model actually updates task state at each step. A small language model often fails to do this — it skips `task_result_update`, mis-reports paths, or exits a node without finalizing state — which triggers retries and verification loops. The same failure mode is visible in the other harnesses' todo usage (the model creates a todo but does not maintain it), but those harnesses do not enforce it, so they finish fast at the cost of unstructured execution. TinyCUA enforces it, so it stays structured at the cost of retries and latency. The trade-off is deliberate: structure on a small language model costs runtime because the harness must compensate for the model's weak state discipline.

### 4. Competitive quality

TinyCUA tied opencode on Experiment 1 and beat both hermes and openclaw on
Experiment 2. On the separate coding tasks, it did not beat opencode. No single
cross-task average is reported.

### 5. Self-supervising behavior

TinyCUA's strongest architectural effect is that it makes the LLM behave less like a single-shot session and more like a supervised workflow. Instead of relying on one continuous generation that eventually stops when the model decides the task is complete, TinyCUA repeatedly re-prompts specialized roles around persistent task state.

The Result Reviewer is the key mechanism. It forces task outputs through an explicit review step before they are accepted, retried, or replanned. This makes self-review systematic rather than optional.

Across all five experiments, the Task Executor and Result Reviewer together account for 1,928 of 2,033 LLM calls (94.8%). In Experiment 5 alone they account for 375 of 394 calls (95.2%). The remaining 5% is split across the planning and aggregation nodes (Query Analyst, Digester, Worker, Task Create, Task Analyzer, Task Assessor, Result Aggregation, Response).

This means TinyCUA can make smaller or local LLMs behave more systematically by externalizing analysis, planning, and review into the agent runtime instead of relying on the model to voluntarily perform them in a single session.

## TinyCUA Weaknesses

### 1. High and variable runtime cost

TinyCUA was much slower than the other harnesses on non-trivial tasks.

| Experiment | TinyCUA duration |
|---:|---:|
| 1 | 5.4s |
| 2 | 1135.0s |
| 3 | 584.7s |
| 4 | 8394.9s |
| 5 | 3004.3s |

The full runtime comparison shows that TinyCUA was consistently slower than the other harnesses, especially on broad research/documentation tasks and on the complex app task.

| Harness | Exp1 | Exp2 | Exp3 | Exp4 | Exp5 |
|---|---:|---:|---:|---:|---:|
| opencode | 1.5s | 42.9s | 70.9s | 254.0s | 85.4s |
| hermes | 5.5s | 99.1s | 31.8s | 1170.0s | 106.1s |
| openclaw | 7.1s | 145.9s | 86.3s | 639.6s | 110.8s |
| tinycua | 5.4s | 1135.0s | 584.7s | 8394.9s | 3004.3s |

Compared with the fastest non-TinyCUA harness per experiment, TinyCUA was about 3.6× slower on the greeting task, 11.5× slower on the LLM report task, 18.4× slower on the clock app, 33.1× slower on the Notion-like app, and 35.2× slower on the neural-network documentation task.

The better explanation is not simply "TinyCUA runs many planning loops." In Experiments 2–5, the early loop shape was similar: one `task_init` and a small number of `task_decompose` calls. Runtime instead tracked how large the task tree became and how many executor/reviewer cycles followed.

| Experiment | Early task-tree growth observed in logs | Task executor starts | Result reviewer starts | Duration |
|---:|---|---:|---:|---:|
| 3 | about 7 tasks | 12 | 12 | 584.7s |
| 2 | about 9+ tasks | 14 | 14 | 1135.0s |
| 4 | about 12+ tasks | 77 | 75 | 8394.9s |
| 5 | about 14+ tasks | 25 | 25 | 3004.3s |

Interpretation:

> TinyCUA runtime depends heavily on early task-tree granularity. When initial task analysis expands a request into many subtasks, each leaf tends to incur executor and reviewer work, increasing latency and token usage.

Experiment 4 needs an additional qualification: its runtime was amplified by prototype retry and verification-tooling weaknesses, not only by task-tree size. The detailed failure mode is discussed in the verification-gate analysis below.

#### Token usage

TinyCUA's runtime cost is matched by its token cost. Token usage was measured with `count_tokens.py`, which parses `[node] usage: input_tokens=N output_tokens=N total_tokens=N` lines from TinyCUA's `stdout.txt` files.

| Experiment | LLM calls | Input | Output | Combined |
|---:|---:|---:|---:|---:|
| 1 | 2 | 2,731 | 266 | 2,997 |
| 2 | 183 | 1,453,014 | 60,171 | 1,513,185 |
| 3 | 123 | 695,302 | 35,975 | 731,277 |
| 4 | 1,331 | 15,694,617 | 420,790 | 16,115,407 |
| 5 | 394 | 4,494,222 | 147,609 | 4,641,831 |
| **Total** | **2,033** | **22,339,886** | **664,811** | **23,004,697** |

Per-node breakdown, sorted by combined tokens descending:

| Node | Calls | Input | Output | Combined | % of total |
|---|---:|---:|---:|---:|---:|
| result_reviewer | 1,048 | 11,153,063 | 261,603 | 11,414,666 | 49.6% |
| task_executor | 880 | 10,807,968 | 366,119 | 11,174,087 | 48.6% |
| task_analyzer | 51 | 252,714 | 18,832 | 271,546 | 1.2% |
| task_assessor | 28 | 74,939 | 11,522 | 86,461 | 0.4% |
| result_aggregation | 4 | 18,181 | 737 | 18,918 | 0.1% |
| response | 5 | 13,831 | 2,702 | 16,533 | 0.1% |
| digester | 4 | 8,352 | 478 | 8,830 | 0.0% |
| query_analyst | 5 | 4,232 | 1,130 | 5,362 | 0.0% |
| worker | 4 | 3,395 | 965 | 4,360 | 0.0% |
| task_create | 4 | 3,211 | 723 | 3,934 | 0.0% |
| **Total** | **2,033** | **22,339,886** | **664,811** | **23,004,697** | 100% |

Top-2 nodes per experiment (the only nodes that matter for non-trivial tasks):

| Exp | Reviewer calls | Reviewer combined | Executor calls | Executor combined | Reviewer share of exp |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 | — (trivial, no worker mode) |
| 2 | 106 | 981,065 | 59 | 465,814 | 64.8% |
| 3 | 73 | 480,845 | 38 | 219,264 | 65.8% |
| 4 | 651 | 7,633,320 | 626 | 8,226,225 | 47.4% |
| 5 | 218 | 2,319,436 | 157 | 2,262,784 | 50.0% |

Three observations:

1. **The Result Reviewer is the single largest token consumer at 49.6% of total**, narrowly ahead of the Task Executor (48.6%). Together they account for 98.2% of all tokens. Every other node combined is under 2%.
2. **The review loop is input-bound, not output-bound.** Input-to-output ratio is about 33:1 overall. The reviewer reads a lot (full task context plus prior review history) and writes a little (a verdict). The dominant cost is re-sending context on every review call, not generating prose.
3. **Planning nodes are negligible.** `task_analyzer`, `task_assessor`, `query_analyst`, `digester`, `worker`, and `task_create` together are about 1.8% of tokens. The decomposition/planning phase is cheap; the executor↔reviewer loop is where tokens burn. In the lighter experiments (2, 3), the reviewer out-spends the executor roughly 2:1 because each review call re-sends the full task context. Experiment 4 is the crossover where the executor edges ahead, because 626 executor sessions each re-send growing workspace state.

Full per-experiment per-node breakdown can be regenerated with:

```bash
uv run python count_tokens.py evaluation-results/tinycua/experiment-*/run_logs/stdout.txt
```

### 2. Decomposition does not guarantee correctness

Experiment 4 is the clearest failure case. TinyCUA decomposed the app into backend, database, auth, pages, users, and frontend pieces (12 `task_decompose` calls, 77 executor starts, 75 reviewer starts), but the final product was still not runnable. The task tree improved coverage, not integration correctness.

### 3. Overproduction and fragmentation

Experiment 5 shows TinyCUA's tendency to overproduce. It consolidated the output into a single 188KB markdown file, but the judge still flagged heavy duplication, poor editing, internal repetition, and malformed markdown/LaTeX. Breadth-without-cohesion persists even when the file count is low: the problem is not how many files are produced, but that the review loop does not enforce editorial consolidation.

### 4. Prototype verification is still weak

TinyCUA is more consistent at self-review than the other harnesses, but the current prototype's verification system is not yet strong enough. The Result Reviewer often checks local task claims, such as whether a file exists or whether a command ran, but this does not guarantee that all accepted tasks integrate into a working final system.

Experiment 4 demonstrates this limitation: TinyCUA performed 77 executor starts and 75 reviewer starts, but the final app still failed integration-level correctness checks. Experiment 5 shows the same gap from a different angle: the reviewer verified file integrity (0 tab characters, 0 literal `\uXXXX` sequences, 44 section headers) but did not catch the duplicated sections, malformed equations, and factual errors that the cross-harness judge flagged.

### 5. Experiment 4 runtime and verification-gate analysis

Experiment 4 should not be interpreted only as evidence that TinyCUA's architecture is inherently slow. The logs show that a large part of the slowdown came from prototype implementation weaknesses in task-state enforcement, path handling, shell execution, and review-decision control.

TinyCUA reported 77 TaskExecutor starts but only 75 ResultReviewer starts. This mismatch is explainable from the logs: executor sessions that never produced a successful `task_result_update` had no task result for the ResultReviewer to review, and the runtime retried the executor until the task-state contract was satisfied.

Therefore, the extra executor calls were not normal task work. They were failed or repeated executor sessions where the runtime repeatedly tried to force the executor to satisfy the task-state contract.

| Area | Observed behavior | Interpretation |
|---|---|---|
| Frontend-backend integration | Multiple TaskExecutor sessions ran long without `task_result_update`. | Runtime overhead came from contract/retry failure, not only decomposition. |
| Final parent verification | Executor attempted integration fixes and verification repeatedly before producing a result. | Parent-level verification lacked a deterministic bounded recipe. |
| ResultReviewer | 75 review sessions for 77 executor sessions, with repeated `needs_revision` / `approved` cycles. | Review decisions were not always treated as single authoritative outcomes. |

Experiment 4's runtime cost was not caused only by TinyCUA's architecture. The architecture created more checkpoints, but the largest overhead came from prototype implementation weaknesses: retry exhaustion when executor nodes failed to update task state, non-canonical workspace paths, shell-context mismatch, and review decisions that could be repeated or overwritten. These are prototype-level issues in the current verification tooling, not inherent architectural limits.

Recommended implementation improvements:

- enforce one canonical workspace root for all tools and reviewer checks;
- normalize task-reported paths before verification;
- make `task_review_decision` single-final per review session, or require explicit supersession metadata;
- replace ad hoc shell checks with deterministic verifier helpers such as `file_exists(path)`, `python_import(module, cwd, venv)`, and `command_ok(command, cwd)`;
- fail fast when TaskExecutor does not call `task_result_update` instead of allowing long retry loops;
- add bounded parent-task verification recipes for app tasks: dependency install, import check, backend startup check, and frontend/API route consistency check.

In short, Experiment 4 shows that TinyCUA's verification gate is promising but immature. The prototype can detect local false claims, but weak tooling caused false negatives, repeated decisions, and excessive runtime (8394.9s, 1,331 LLM calls, 16.1M combined tokens). The next improvement should focus less on reducing decomposition and more on making verification deterministic, path-aware, and bounded.

## Interpretation

The results do not support the claim that TinyCUA is globally better than existing harnesses. They support a narrower claim:

> TinyCUA demonstrates competitive task quality and stronger decomposition-driven coverage on broad tasks, but this comes with substantial runtime and token overhead. Its performance depends strongly on early task-tree granularity, and decomposition alone does not ensure executable correctness.

TinyCUA should be presented as a trade-off:

- **Benefit:** explicit decomposition, broader coverage, observable orchestration.
- **Benefit:** more systematic self-supervision through task execution and Result Reviewer loops.
- **Cost:** high latency, high token usage (23M combined tokens across 5 experiments, 98% in the executor↔reviewer loop), and risk of fragmented or over-expanded outputs.
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
- The judge was a hermes-judge container using GPT-5.5 high. Submissions were anonymized during judging, so the judge did not know which harness produced each output. This reduces direct harness-name bias, but the evaluator still ran through the hermes harness, so evaluator-harness effects remain a limitation (hermes is also one of the evaluated systems).
- Some tasks, especially Experiment 4, are much more complex than others and dominate qualitative interpretation.
- Runtime is affected by task complexity, local model responsiveness, tool calls, and TinyCUA's task-tree growth.
- The judge scores combine qualitative and tested evidence; they should be treated as comparative signals, not absolute ground truth.
