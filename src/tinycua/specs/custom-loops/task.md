# Tasks: Agent + Loop Integration (M2)

Implementation tasks for Agent + Loop Integration (M2). Check off items as completed.

## TDD Phase — Phase 1: SDK Foundation (Tests First)

- [ ] Write integration tests: agent factory creates all seven agents <!-- id: 1 -->
- [ ] Write integration tests: each agent config dataclass accepts overrides <!-- id: 2 -->
- [ ] Write integration tests: factory accepts config overrides per agent <!-- id: 3 -->
- [ ] Write integration tests: agent config preserves metadata for MainLoop <!-- id: 4 -->
- [ ] Write unit tests: SchemaValidator accepts/rejects valid/invalid output <!-- id: 5 -->
- [ ] Write unit tests: ClassificationTool maps index to label, rejects invalid index <!-- id: 6 -->
- [ ] Write unit tests: error hierarchy instantiable with correct types <!-- id: 7 -->
- [ ] Write unit tests: model config uses correct provider/model/base_url defaults <!-- id: 8 -->
- [ ] Run integration tests — expect RED (no implementation yet) <!-- id: 9 -->

## Implementation Phase — Phase 1: SDK Foundation

- [ ] Verify `tinycua-sdk` dependency in `src/tinycua/pyproject.toml` <!-- id: 10 -->
- [ ] Create `tinycua/loops/errors.py` with `LoopError`, `LoopTransientError`, `LoopPermanentError`, `LoopOutputValidationError` <!-- id: 11 -->
- [ ] Create `tinycua/loops/schema_validator.py` wrapping SDK `Agent.run()` with validation and retry <!-- id: 12 -->
- [ ] Create `tinycua/loops/__init__.py` re-exporting SDK types + custom loop types + errors <!-- id: 13 -->
  - [ ] Re-export `BaseLoop`, `Agent`, `LanguageModel`, `Tool` from SDK
  - [ ] Re-export `LoopType` enum (`SDK_BASE`, `CLASSIFICATION`, `EXPLORATION`, `HYBRID_REVIEW`)
- [ ] Create `tinycua/agents/configs.py` with `AgentConfigBase` and all seven agent config dataclasses <!-- id: 14 -->
  - [ ] `QueryAnalystConfig` — `classification_labels: list[str]`
  - [ ] `InformationDigesterConfig` — `max_iterations_override: int | None`
  - [ ] `TaskAnalyzerConfig`
  - [ ] `TaskAssessorConfig`
  - [ ] `TaskExecutorConfig` — `native_tools: list[Tool]`
  - [ ] `ResultReviewerConfig` — `deterministic_rules: list[DeterministicRule]`
  - [ ] `PrimaryAgentConfig`
- [ ] Define `TINYCUA_DEFAULT_MODEL` as `LanguageModel(provider="openai-chat-completions", model_name="qwen/qwen3.5-4b", base_url="http://localhost:1234/v1")` <!-- id: 15 -->
- [ ] Define `AgentKind` enum with all seven architecture agent identifiers <!-- id: 16 -->
- [ ] Define MainLoop metadata contract keys (`internal_agents`, `state_store`, `artifact_store`, `default_session_id`, `orchestration`) <!-- id: 17 -->
- [ ] Run integration tests — expect partially GREEN (Phase 1 foundation tests pass) <!-- id: 18 -->

## TDD Phase — Phase 2: Classification Loop (Tests First)

- [ ] Write integration tests: classify tool outputs correct label for each index <!-- id: 19 -->
- [ ] Write integration tests: classification end-to-end — primary_agent path <!-- id: 20 -->
- [ ] Write integration tests: classification end-to-end — worker path <!-- id: 21 -->
- [ ] Write integration tests: classification end-to-end — uncertain path <!-- id: 22 -->
- [ ] Write integration tests: no forced `max_iterations=1` <!-- id: 23 -->
- [ ] Write integration tests: anti-laziness safeguards (meaningful rationale) <!-- id: 24 -->
- [ ] Write unit tests: ClassificationLoop construction, invalid config, edge cases <!-- id: 25 -->
- [ ] Write unit tests: all three modes reachable depending on mock input <!-- id: 26 -->
- [ ] Run integration tests — expect RED (Phase 2 tests only) <!-- id: 27 -->

## Implementation Phase — Phase 2: Classification Loop

- [ ] Implement `ClassificationTool` — configurable label list, `execute(mode_index: int) -> str` <!-- id: 28 -->
- [ ] Implement `tinycua/loops/classification.py` — `ClassificationLoop` extends `BaseLoop` <!-- id: 29 -->
  - [ ] Constructor: no `max_iterations=1` override; uses SDK default behavior
  - [ ] `run()` delegates to `BaseLoop.run()` with classification prompt
  - [ ] `SchemaValidator` validates output against `ContextEnhancedQuery` + `ModeDecision` schema
- [ ] Write `QUERY_ANALYST_PROMPT` in `tinycua/agents/prompts.py` <!-- id: 30 -->
  - [ ] Include role, input contract (`user_query`, `chat_history`, `session_context`), output schema (scoring dimensions, mode selection via `classify` tool index), guardrails (anti-laziness: rationale required)
- [ ] Configure Query Analyst in factory: `Agent(loop=ClassificationLoop(), tools=[ClassificationTool], ...)` <!-- id: 31 -->
  - [ ] Factory reads `classification_labels` from `QueryAnalystConfig` to configure `ClassificationTool`
- [ ] Run integration tests — expect GREEN (Phase 2 tests pass) <!-- id: 32 -->
- [ ] Write and run unit tests for ClassificationLoop (mock Agent) — expect GREEN <!-- id: 33 -->

## TDD Phase — Phase 3: Exploration Loop (Tests First)

- [ ] Write integration tests: multi-iteration retrieval end-to-end <!-- id: 34 -->
- [ ] Write integration tests: stops on LLM-judged sufficiency <!-- id: 35 -->
- [ ] Write integration tests: empty results produce known_gaps <!-- id: 36 -->
- [ ] Write integration tests: honors `BaseLoop.max_iterations` hard cap <!-- id: 37 -->
- [ ] Write unit tests: ExplorationLoop construction, sufficiency parsing, error edge cases <!-- id: 38 -->
- [ ] Run integration tests — expect RED (Phase 3 tests only) <!-- id: 39 -->

## Implementation Phase — Phase 3: Exploration Loop

- [ ] Implement `tinycua/loops/exploration.py` — `ExplorationLoop` extends `BaseLoop` <!-- id: 40 -->
  - [ ] `__init__` accepts optional `max_iterations` override (passed to `BaseLoop`)
  - [ ] `run()` adds gap-evaluation after each SDK `BaseLoop` iteration
  - [ ] Stop on LLM-judged sufficiency OR `max_iterations` hit
  - [ ] `SchemaValidator` validates output against `DigestedInformation` schema
- [ ] Define Enhanced Context Retrieval as an SDK `Tool` contract (stub/mock acceptable for tests) <!-- id: 41 -->
- [ ] Write `INFORMATION_DIGESTER_PROMPT` in `tinycua/agents/prompts.py` <!-- id: 42 -->
  - [ ] Include role, input contract (`ContextEnhancedQuery`), retrieval strategy, gap-identification, output schema, stop-condition guardrails
- [ ] Configure Information Digester in factory: `Agent(loop=ExplorationLoop(), tools=[retrieval_tool], ...)` <!-- id: 43 -->
  - [ ] Factory reads `max_iterations_override` from `InformationDigesterConfig`
- [ ] Run integration tests — expect GREEN (Phase 3 tests pass) <!-- id: 44 -->
- [ ] Write and run unit tests for ExplorationLoop (mock Agent) — expect GREEN <!-- id: 45 -->

## TDD Phase — Phase 4: Direct SDK BaseLoop Agents (Tests First)

- [ ] Write integration tests: Task Analyzer produces valid Task tree end-to-end <!-- id: 46 -->
- [ ] Write integration tests: Task Assessor selects decomposition tasks end-to-end <!-- id: 47 -->
- [ ] Write integration tests: Task Executor uses native tools end-to-end <!-- id: 48 -->
- [ ] Write integration tests: Primary Agent synthesizes final response end-to-end <!-- id: 49 -->
- [ ] Write integration tests: no custom `LinearAgentLoop` or `SimpleLoop` exists <!-- id: 50 -->
- [ ] Write unit tests: each agent config produces agent with correct name, loop=None (BaseLoop default) <!-- id: 51 -->
- [ ] Run integration tests — expect RED (Phase 4 tests only) <!-- id: 52 -->

## Implementation Phase — Phase 4: Direct SDK BaseLoop Agents

- [ ] Write `TASK_ANALYZER_PROMPT`, `TASK_ASSESSOR_PROMPT`, `TASK_EXECUTOR_PROMPT`, `PRIMARY_AGENT_PROMPT` in `tinycua/agents/prompts.py` <!-- id: 53 -->
  - [ ] Each prompt: role, input contract, output schema, constraints, guardrails
- [ ] Configure Task Analyzer in factory: `Agent(loop=None, instructions=TASK_ANALYZER_PROMPT, ...)` (omits custom loop) <!-- id: 54 -->
- [ ] Configure Task Assessor in factory: `Agent(loop=None, ...)` <!-- id: 55 -->
- [ ] Configure Task Executor in factory: `Agent(loop=None, tools=native_tools, ...)` <!-- id: 56 -->
  - [ ] Factory merges `TaskExecutorConfig.native_tools` and `extra_tools`
- [ ] Configure Primary Agent in factory: `Agent(loop=None, ...)` <!-- id: 57 -->
- [ ] Run integration tests — expect GREEN (Phase 4 tests pass) <!-- id: 58 -->
- [ ] Write and run unit tests for agent configs + factory — expect GREEN <!-- id: 59 -->

## TDD Phase — Phase 5: Hybrid Review Loop (Tests First)

- [ ] Write integration tests: accepted status with context_updates <!-- id: 60 -->
- [ ] Write integration tests: retry status with retry_instructions <!-- id: 61 -->
- [ ] Write integration tests: replan status with rationale <!-- id: 62 -->
- [ ] Write integration tests: escalate_user with user_explanation <!-- id: 63 -->
- [ ] Write integration tests: deterministic failure skips LLM phase entirely <!-- id: 64 -->
- [ ] Write integration tests: pluggable rule sets without subclassing <!-- id: 65 -->
- [ ] Write unit tests: HybridReviewLoop construction, rule evaluation, edge cases <!-- id: 66 -->
- [ ] Run integration tests — expect RED (Phase 5 tests only) <!-- id: 67 -->

## Implementation Phase — Phase 5: Hybrid Review Loop

- [ ] Define `DeterministicRule` and `DeterministicRuleResult` dataclasses <!-- id: 68 -->
- [ ] Define default deterministic rules (`SchemaValidity`, `RequiredFields`) <!-- id: 69 -->
- [ ] Implement `tinycua/loops/hybrid_review.py` — `HybridReviewLoop` extends `BaseLoop` <!-- id: 70 -->
  - [ ] `__init__` accepts `deterministic_rules: list[DeterministicRule]`
  - [ ] Phase 1: evaluate all rules; fail with `escalate`/`replan` → return immediately
  - [ ] Phase 2: delegate to SDK `BaseLoop` behavior for LLM semantic review
  - [ ] Output schema: `ReviewerDecision` with `status`, `reason`, optional `context_updates`/`retry_instructions`/`rationale`/`user_explanation`
- [ ] Write `RESULT_REVIEWER_PROMPT` in `tinycua/agents/prompts.py` <!-- id: 71 -->
  - [ ] Include role, input contract (task, task_result, execution_log), review criteria, decision output schema, guardrails
- [ ] Configure Result Reviewer in factory: `Agent(loop=HybridReviewLoop(deterministic_rules=config.deterministic_rules), ...)` <!-- id: 72 -->
  - [ ] Factory reads `deterministic_rules` from `ResultReviewerConfig`
- [ ] Run integration tests — expect GREEN (Phase 5 tests pass) <!-- id: 73 -->
- [ ] Write and run unit tests for HybridReviewLoop (mock Agent) — expect GREEN <!-- id: 74 -->

## TDD Phase — Phase 6: Agent-to-Agent Tools & Documentation (Tests First)

- [ ] Write integration tests: `call_query_analyst` delegates to configured agent <!-- id: 75 -->
- [ ] Write integration tests: agent-calling tool respects target agent loop/config <!-- id: 76 -->
- [ ] Write integration tests: all seven call tools exist as SDK `Tool` objects <!-- id: 77 -->
- [ ] Write integration tests: custom loops attached via `Agent(loop=...)` not wrapping agents <!-- id: 78 -->
- [ ] Write integration tests: agent factory output fits MainLoop metadata contract <!-- id: 79 -->
- [ ] Run integration tests — expect RED (Phase 6 tests only) <!-- id: 80 -->

## Implementation Phase — Phase 6: Agent-to-Agent Tools & Documentation

- [ ] Implement `call_query_analyst(internal_agents) -> Tool` in `tinycua/tools/agent_calls.py` <!-- id: 81 -->
- [ ] Implement `call_information_digester(internal_agents) -> Tool` <!-- id: 82 -->
- [ ] Implement `call_task_analyzer(internal_agents) -> Tool` <!-- id: 83 -->
- [ ] Implement `call_task_assessor(internal_agents) -> Tool` <!-- id: 84 -->
- [ ] Implement `call_task_executor(internal_agents) -> Tool` <!-- id: 85 -->
- [ ] Implement `call_result_reviewer(internal_agents) -> Tool` <!-- id: 86 -->
- [ ] Implement `call_primary_agent(internal_agents) -> Tool` <!-- id: 87 -->
- [ ] Each tool: loads target agent from registry, calls `target_agent.run(...)`, validates output schema, returns normalized output <!-- id: 88 -->
- [ ] Run integration tests — expect GREEN (Phase 6 tests pass) <!-- id: 89 -->
- [ ] Wirite and run unit tests for agent-calling tools — expect GREEN <!-- id: 90 -->

## Testing Phase — Full Suite

- [ ] Run all integration tests — expect GREEN (all phases pass) <!-- id: 91 -->
- [ ] Run all unit tests — expect GREEN <!-- id: 92 -->
- [ ] Run full test suite: `cd src/tinycua && uv run pytest` <!-- id: 93 -->
- [ ] Verify test coverage >85% for `tinycua/loops/` module <!-- id: 94 -->
- [ ] Verify no regressions in existing tests <!-- id: 95 -->

## Verification Phase

- [ ] Verify no `tinycua/loops/base.py` with custom `LoopBase`, `LLMBackend`, or `ToolDef` classes <!-- id: 96 -->
- [ ] Verify no `tinycua/loops/linear.py` with `LinearAgentLoop` or `SimpleLoop` wrapper <!-- id: 97 -->
- [ ] Verify all custom loops extend `tinycua_sdk.agent.loop.BaseLoop` <!-- id: 98 -->
- [ ] Verify all custom loops do NOT define custom LLM backend protocols or tool-calling infrastructure <!-- id: 99 -->
- [ ] Verify `TINYCUA_DEFAULT_MODEL` uses provider `openai-chat-completions`, not alias `openai` <!-- id: 100 -->
- [ ] Verify `ClassificationTool` is configurable — changing `classification_labels` in config changes tool behavior without prompt edits <!-- id: 101 -->
- [ ] Verify each agent config dataclass accepts overrides without modifying defaults <!-- id: 102 -->
- [ ] Verify factory output can be nested under `Agent(metadata={"tinycua": {"internal_agents": ...}})` without changing agent APIs <!-- id: 103 -->

## Documentation Phase

- [ ] Add docstrings and usage examples for all loop types <!-- id: 104 -->
- [ ] Update SDK custom execution loops cookbook: correct `Agent(loop=CustomLoop(...))` examples <!-- id: 105 -->
  - [ ] Fix `src/tinycua-sdk/docs/cookbook/execution-and-reference/custom-execution-loops.md`
- [ ] Sync architecture docs (per spec "Future Architecture Documentation Sync"): <!-- id: 106 -->
  - [ ] `overview.md` — update Agent Loop Types table
  - [ ] `task-analysis.md` — clarify SDK `BaseLoop` direct usage
  - [ ] `task-assessor.md` — clarify SDK `BaseLoop` direct usage
  - [ ] Any references to "Linear"/"Simple"/"input→output" loop — normalize to "SDK BaseLoop"
- [ ] Update module `__init__.py` re-exports for discoverability <!-- id: 107 -->

## Review and Merge

- [ ] Create pull request (or push to existing PR #67) <!-- id: 108 -->
- [ ] Address review feedback <!-- id: 109 -->
- [ ] Merge to base branch <!-- id: 110 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-31*
