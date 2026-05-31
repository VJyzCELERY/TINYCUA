# Prompt Contracts

> **File:** `docs/design/constants/prompts.md`
> **Package:** `tinycua.constants.prompts`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## Overview

System prompt strings for all seven internal agents plus the TinyCUA main prompt.
Each prompt includes role, input contract, output schema, constraints, and guardrails.
Prompts are module-level string constants, NOT embedded in orchestrator or loop code.

---

## Prompt Constants

| Constant | Agent | Loop | Key Elements |
|----------|-------|------|-------------|
| `QUERY_ANALYST_PROMPT` | QueryAnalyst | QueryAnalystLoop | Role: fast classification. Input: `user_query`, `chat_history`, `session_context`. Output: `ContextEnhancedQuery` + `ModeDecision`. Scoring: task complexity, context dependency, safety/risk. Guardrails: anti-laziness rationales. Tool: `classify(mode_index=N)`. |
| `INFORMATION_DIGESTER_PROMPT` | InformationDigester | InformationDigestionLoop | Role: precision retrieval. Input: `ContextEnhancedQuery`. Output: `DigestedInformation`. Strategy: identify gaps → retrieve → evaluate → repeat or stop. Guardrails: stop on sufficiency; record `known_gaps` on empty results. |
| `TASK_ANALYZER_PROMPT` | TaskAnalyzer | ReActAgentLoop | Role: task decomposition. Input: `DigestedInformation`. Output: `Task` tree with root + child_tasks. Constraints: each leaf has required fields; `child_tasks: None` = leaf. |
| `TASK_ASSESSOR_PROMPT` | TaskAssessor | ReActAgentLoop | Role: decomposition selection. Input: `Task` tree + `WorkerConfig`. Output: `list[task_id]`. Guardrails: only select tasks too complex for direct execution. |
| `TASK_EXECUTOR_PROMPT` | TaskExecutor | ReActAgentLoop | Role: task execution. Input: `Task`. Output: `TaskResult`. Tools: native benchmarks as available. Guardrails: execute as specified, report issues. |
| `RESULT_REVIEWER_PROMPT` | ResultReviewer | ResultReviewLoop | Role: result review. Input: `task`, `task_result`, `execution_log`. Output: `ReviewerDecision`. Statuses: accepted/retry/replan/escalate_user. Guardrails: LLM handles semantics; deterministic phase handles schema. |
| `PRIMARY_AGENT_PROMPT` | PrimaryAgent | ReActAgentLoop | Role: final synthesis. Input: `ContextEnhancedQuery` or `WorkerResult`. Output: final response + optional citations. Guardrails: self-contained response. |
| `TINYCUA_MAIN_PROMPT` | TinyCUA | MainLoop | Role: orchestration. Input: user query. Flow: classify → route to primary/worker/uncertain → delegate via agent-calling tools → synthesize response. |

---

## Prompt Governance

- Prompts live in `tinycua/constants/prompts.py` — not embedded in orchestrator `__init__` or loop `run()`

- To change a prompt, edit the constant. No code changes needed in orchestrator or loop classes
- Prompts are derived from architecture docs (`src/tinycua/docs/architecture/`)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Prompts as constants | `tinycua/constants/prompts.py` | Single place to find/edit prompts; not scattered across orchestrator classes |
| Own package | `tinycua.constants` | Separates prompts from tools and config; each constant type has its own module |
