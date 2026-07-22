# Reviewer Ablation Evidence (trace-based / retrospective)

## Methodology

This is a **trace-based / retrospective ablation**, not a re-execution ablation. Each reviewer verdict, its cited cause, the executor re-entry it triggered, and the LLM-call cost of that cycle are already in the TinyCUA stdout. We aggregate them per run.

**Stated assumption**: removing the reviewer means *auto-accept the executor's first recorded task_result*. The retrospective analysis measures what would have shipped, and what cost would not have been paid, in that counterfactual.

**Bounded scope**: the analysis does not capture second-order effects (a no-reviewer executor knowing no one is watching might behave differently). Validation against one true re-execution on the simple coding task is left for future compute budget.

## Reviewer cost across all experiments

| Exp | Reviewer LLM calls | Reviewer tokens | Out-of-reviewer tokens | Reviewer share |
|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 2,997 | 0.0% |
| 2 | 106 | 981,065 | 532,120 | 64.8% |
| 3 | 73 | 480,845 | 250,432 | 65.8% |
| 4 | 651 | 7,633,320 | 8,482,087 | 47.4% |
| 5 | 218 | 2,319,436 | 2,322,395 | 50.0% |

## Reviewer verdict outcomes

| Exp | approved | needs_revision | rejected | replan | Revision-triggering total |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 0 | 0 | 0 | 0 |
| 2 | 8 | 11 | 1 | 0 | 12 |
| 3 | 9 | 5 | 0 | 0 | 5 |
| 4 | 41 | 54 | 3 | 1 | 58 |
| 5 | 15 | 21 | 0 | 0 | 21 |

## Reviewer-cited causes (anchored catalog)

Causes are matched by anchored regex on the assistant text preceding each `task_review_decision` call. Non-matching verdicts are recorded as `unclassified` and preserved verbatim in `run_summary.json` for manual review — never silently guessed.

| Cause | Count across experiments 1-5 |
|---|---:|
| unclassified | 145 |
| syntax_error | 7 |
| database_failed | 7 |
| exit_code | 5 |
| module_not_found | 3 |
| missing_import | 1 |
| type_error | 1 |

## False approvals (reviewer approved then admitted broken)

Detected by scanning reviewer cited_causes for verdicts whose following reviewer text or later verdicts on the same task reversed the approval (`should NOT have approved`, `wrong`, `broken`). Manual citation, not an automatic flag — these are the strongest defect evidence in the trace.

| Exp | seq | task | note |
|---:|---:|---|---|
| 4 | 14130 | `f148f911` | reviewer admitted approval was wrong |

## Cross-harness verification presence

OpenCode and OpenClaw stdouts are NOT parsed by this tool; they are read by hand and cited by line number. The grammars differ too much to share a parser, and the question being answered is qualitative: does the harness's orchestrator emit any review/verify event at all?

| Exp | OpenCode parent events | Orchestrator tool_use tools | Verification tool_use present? |
|---:|---|---|---|
| 1 | 2 reasoning, 1 step_finish, 1 step_start, 2 text | (none) | no |
| 2 | 14 reasoning, 7 step_finish, 7 step_start, 2 text, 6 tool, 6 tool_use | webfetch, webfetch, bash, bash, bash, write | no |
| 3 | 6 reasoning, 3 step_finish, 3 step_start, 2 text, 2 tool, 2 tool_use | write, bash | no |
| 4 | 4 reasoning, 2 step_finish, 2 step_start, 4 text, 1 tool, 1 tool_use | task | no |
| 5 | 4 reasoning, 2 step_finish, 2 step_start, 4 text, 1 tool, 1 tool_use | write | no |

OpenCode's parent orchestrator (the only layer whose events reach stdout) emits zero post-write verification tool calls across every experiment. On experiment-4 (complex coding) the parent:

- emits a single `tool_use` event, named `task` (the delegation);
- its post-delegation reasoning reads verbatim: `"The task agent has successfully created the complete Notion-like application, so I should summarize what was built"` (`src/experiment/evaluation-results/opencode/experiment-4/run_logs/stdout.txt`, line ~5);
- the delegated subagent's `task_result` summary is accepted as ground truth and re-summarized to the user;
- the subagent's internal session (`ses_10a389239ffeyO7DTE8bvb08Sq`) is not persisted anywhere under `experiment-4/`; we cannot know whether it self-verified internally. The orchestrator verifiably did not.

Compare with TinyCUA experiment-4 in this report (75 reviewer starts, 99 review decisions, 58 revision-triggering verdicts, 12 rework cycles on the SQLite task alone). The architectural claim — **absence of an explicit review step in the orchestrator correlates with acceptance of lower-verified output** — is observable directly from the OpenCode parent's event-type inventory.

