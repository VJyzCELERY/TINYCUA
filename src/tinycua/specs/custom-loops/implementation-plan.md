# Implementation: Agent + Loop Integration (M2)

Implement integrated custom loop strategies, agent factory/configuration, system prompts, concrete agent definitions, and agent-to-agent calling tools for all seven architecture agents. Custom loops extend `tinycua_sdk.agent.loop.BaseLoop` and are attached to SDK agents via `Agent(loop=...)`. Standard single-input/single-output agents use SDK `BaseLoop` directly. Each internal agent is configured through its own `AgentConfig` dataclass, enabling future MainLoop metadata overrides without code changes.

## Context

- **Spec Reference**: `src/tinycua/specs/custom-loops/spec.md`
- **Design Reference**: `src/tinycua/specs/custom-loops/design.md`
- **Priority**: P1
- **Estimated Effort**: L

## Environment Pre-requisites

### Configuration

- [ ] **None** — this feature has no configuration dependencies. Tests use mock SDK `Agent` and `BaseLoop`; no live model endpoint required.

### Running Services

- [ ] **None** — no external services needed. All tests run with mocks.

### Data / Fixtures

- [ ] **None** — no data or fixtures needed. Mock LLM responses are provided inline in tests.

### Access / Permissions

- [ ] **None** — no special access required.

### Developer Tooling

- [ ] **Runtime**: Python 3.12+
- [ ] **Package manager**: uv
- [ ] **None** — no special tooling required beyond the workspace standard.

---

## Success Criteria — Integration Tests (TDD First)

Define the integration tests that prove the feature works. These are written FIRST — before any implementation code. The implementation is only complete when these tests pass.

### Phase 1: SDK Integration Foundation

```python
# Test file: tests/integration/test_agent_factory.py
"""Integration tests for agent factory and config registry."""


def test_create_all_agents_returns_seven_configured_sdk_agents():
    """Factory produces exactly one configured Agent per architecture agent."""
    agents = create_all_agents()
    assert len(agents) == 7
    agent_names = {a.name for a in agents.values()}
    assert agent_names == {
        "query-analyst",
        "information-digester",
        "task-analyzer",
        "task-assessor",
        "task-executor",
        "result-reviewer",
        "primary-agent",
    }
    # Every agent is an SDK Agent (not a wrapper)
    from tinycua_sdk.agent import Agent
    for agent in agents.values():
        assert isinstance(agent, Agent)


def test_each_agent_config_is_overridable():
    """Each agent config dataclass accepts overrides without modifying defaults."""
    from tinycua.agents.configs import QueryAnalystConfig

    config = QueryAnalystConfig(
        classification_labels=["mode_a", "mode_b", "mode_c"],
        extra_tools=[FakeTool()],
        metadata={"custom": "value"},
    )
    assert config.classification_labels == ["mode_a", "mode_b", "mode_c"]
    assert len(config.extra_tools) == 1
    assert config.metadata["custom"] == "value"


def test_agent_factory_accepts_config_overrides():
    """Factory creates agents from custom config objects."""
    custom_config = QueryAnalystConfig(
        name="custom-qa",
        model_override=FakeModel(),
        classification_labels=["x", "y"],
    )
    agent = create_agent(AgentKind.QUERY_ANALYST, config=custom_config)
    assert agent.name == "custom-qa"
    assert agent.config.loop is not None  # ClassificationLoop


def test_agent_config_preserves_metadata_for_mainloop():
    """Agent config metadata is stored and retrievable for future MainLoop propagation."""
    config = InformationDigesterConfig(
        metadata={"mainloop": {"max_iterations": 5, "tool_allowlist": ["search"]}},
    )
    assert config.metadata["mainloop"]["max_iterations"] == 5
    assert config.metadata["mainloop"]["tool_allowlist"] == ["search"]
```

### Phase 2: Classification Loop

```python
# Test file: tests/integration/test_classification_loop.py
"""Integration tests for ClassificationLoop and Query Analyst agent."""


@pytest.mark.asyncio
async def test_classification_tool_outputs_correct_label():
    """The classify(index) tool returns the label mapped to the given index."""
    labels = ["primary_agent", "worker", "uncertain"]
    tool = ClassificationTool(labels=labels)

    # Agent-selected indices produce corresponding labels
    result = await tool.execute(mode_index=0)
    assert result == "primary_agent"

    result = await tool.execute(mode_index=1)
    assert result == "worker"

    result = await tool.execute(mode_index=2)
    assert result == "uncertain"


@pytest.mark.asyncio
async def test_classification_tool_rejects_invalid_index():
    """Tool rejects out-of-range indices with a clear error."""
    tool = ClassificationTool(labels=["a", "b"])
    with pytest.raises(ValueError, match="index 5 out of range"):
        await tool.execute(mode_index=5)


@pytest.mark.asyncio
async def test_classification_loop_primary_agent_path():
    """Query Analyst with ClassificationLoop produces primary_agent decision end-to-end.

    End-to-end: Agent receives a simple query, SDK loop runs (1+ iterations),
    Agent uses the classify tool to pick index 0, tool returns "primary_agent",
    SchemaValidator parses the output into ContextEnhancedQuery + ModeDecision.
    """
    agent = create_agent(
        AgentKind.QUERY_ANALYST,
        config=QueryAnalystConfig(
            classification_labels=["primary_agent", "worker", "uncertain"],
        ),
    )
    # Mock LLM returns a structured response referencing classify(mode_index=0)
    mock_client = MockLLMClient(response={"reasoning": "simple query", "mode_index": 0})
    result = await agent.run(query="What is 2+2?")
    assert result.mode_decision["mode"] == "primary_agent"
    assert result.context_enhanced_query is not None


@pytest.mark.asyncio
async def test_classification_loop_worker_mode():
    """Query Analyst produces worker ModeDecision for complex multi-step queries.

    End-to-end: Agent receives a complex query requiring decomposition,
    uses classify tool to pick index 1, tool returns "worker".
    """
    agent = create_agent(
        AgentKind.QUERY_ANALYST,
        config=QueryAnalystConfig(
            classification_labels=["primary_agent", "worker", "uncertain"],
        ),
    )
    mock_client = MockLLMClient(
        response={"reasoning": "multi-step task", "mode_index": 1}
    )
    result = await agent.run(query="Research X, build Y, deploy Z on AWS with CI/CD")
    assert result.mode_decision["mode"] == "worker"


@pytest.mark.asyncio
async def test_classification_loop_uncertain_mode():
    """Query Analyst produces uncertain ModeDecision when confidence is low.

    End-to-end: Agent cannot confidently classify, uses classify tool
    with index 2, tool returns "uncertain". uncertain_next_action is set.
    """
    agent = create_agent(
        AgentKind.QUERY_ANALYST,
        config=QueryAnalystConfig(
            classification_labels=["primary_agent", "worker", "uncertain"],
        ),
    )
    mock_client = MockLLMClient(
        response={"reasoning": "ambiguous query", "mode_index": 2}
    )
    result = await agent.run(query="?")
    assert result.mode_decision["mode"] == "uncertain"
    assert result.mode_decision["uncertain_next_action"] is not None


@pytest.mark.asyncio
async def test_classification_loop_no_forced_single_pass():
    """ClassificationLoop uses SDK BaseLoop default iteration behavior,
    not max_iterations=1 or a single-pass restriction."""
    loop = ClassificationLoop()
    assert loop.max_iterations is None  # inherits SDK default, not forced to 1


@pytest.mark.asyncio
async def test_anti_laziness_safeguards():
    """Primary_agent rationale must explain why worker is not needed;
    worker rationale must explain decomposition benefit."""
    agent = create_agent(AgentKind.QUERY_ANALYST)
    mock_client = MockLLMClient(
        response={"reasoning": "simple math", "mode_index": 0}
    )
    result = await agent.run(query="1+1")
    # The rationale field must contain more than a trivial dismissal
    assert len(result.mode_decision.get("reasoning", "")) > 20
```

### Phase 3: Exploration Loop

```python
# Test file: tests/integration/test_exploration_loop.py
"""Integration tests for ExplorationLoop and Information Digester agent."""


@pytest.mark.asyncio
async def test_exploration_loop_multi_iteration_retrieval():
    """Information Digester makes multiple tool-calling iterations end-to-end.

    End-to-end: Agent receives CEQ, invokes retrieval tool, SDK BaseLoop
    iterates for tool calls, agent decides if gaps remain, produces
    DigestedInformation with context_summary and key_points.
    """
    agent = create_agent(
        AgentKind.INFORMATION_DIGESTER,
        config=InformationDigesterConfig(extra_tools=[mock_retrieval_tool]),
    )
    # Mock: first LLM call requests retrieval, second call returns structured output
    mock_client = MockLLMClient(
        responses=[
            MockToolUse(tool="enhanced_context_retrieval", result={"docs": [...]}),
            MockTextResponse(
                content=json.dumps({
                    "context_summary": "Found relevant docs",
                    "key_points": ["point 1", "point 2"],
                    "known_gaps": [],
                })
            ),
        ]
    )
    result = await agent.run(
        query=json.dumps({"query": "research topic", "enhanced_context": {}})
    )
    assert result["context_summary"] is not None
    assert len(result["key_points"]) > 0


@pytest.mark.asyncio
async def test_exploration_stops_on_llm_sufficiency():
    """Agent stops retrieval when LLM judges context sufficient."""
    agent = create_agent(AgentKind.INFORMATION_DIGESTER)
    mock_client = MockLLMClient(
        responses=[
            MockToolUse(tool="enhanced_context_retrieval", result={"docs": [...]}),
            MockTextResponse(
                content=json.dumps({
                    "context_summary": "Sufficient context gathered",
                    "key_points": ["p1"],
                    "known_gaps": [],
                })
            ),
        ]
    )
    result = await agent.run(query=json.dumps({"query": "topic"}))
    assert result["known_gaps"] == []
    # Verify loop did not exceed BaseLoop.max_iterations
    assert mock_client.llm_call_count <= 5


@pytest.mark.asyncio
async def test_exploration_empty_results_produces_known_gaps():
    """When retrieval returns nothing, DigestedInformation records gaps."""
    agent = create_agent(AgentKind.INFORMATION_DIGESTER)
    mock_client = MockLLMClient(
        responses=[
            MockToolUse(tool="enhanced_context_retrieval", result={}),
            MockTextResponse(
                content=json.dumps({
                    "context_summary": "No relevant context found",
                    "key_points": [],
                    "known_gaps": ["missing: topic background", "missing: prior work"],
                })
            ),
        ]
    )
    result = await agent.run(query=json.dumps({"query": "unknown_topic"}))
    assert len(result["known_gaps"]) > 0


@pytest.mark.asyncio
async def test_exploration_loop_honors_max_iterations_hard_cap():
    """BaseLoop.max_iterations prevents infinite retrieval loops."""
    loop = ExplorationLoop(max_iterations=2)
    assert loop.max_iterations == 2
```

### Phase 4: Direct SDK BaseLoop Agent Configurations

```python
# Test file: tests/integration/test_base_loop_agents.py
"""Integration tests for Task Analyzer, Task Assessor, Task Executor, Primary Agent."""


@pytest.mark.asyncio
async def test_task_analyzer_produces_valid_task_tree():
    """Task Analyzer using SDK BaseLoop produces a Task tree end-to-end.

    End-to-end: Agent receives DigestedInformation, uses optional tools,
    produces a Task tree with root and child_tasks.
    """
    agent = create_agent(AgentKind.TASK_ANALYZER)
    mock_client = MockLLMClient(
        response=json.dumps({
            "task_id": "root-1",
            "description": "Research topic X",
            "child_tasks": [
                {"task_id": "leaf-1", "description": "Search for papers"},
                {"task_id": "leaf-2", "description": "Summarize findings"},
            ],
        })
    )
    result = await agent.run(query=json.dumps({"key_points": ["research X"]}))
    assert result["task_id"] == "root-1"
    assert len(result["child_tasks"]) == 2


@pytest.mark.asyncio
async def test_task_assessor_selects_decomposition_tasks():
    """Task Assessor using SDK BaseLoop selects tasks for decomposition end-to-end."""
    agent = create_agent(AgentKind.TASK_ASSESSOR)
    mock_client = MockLLMClient(response=json.dumps({"task_ids": ["leaf-1", "leaf-3"]}))
    result = await agent.run(
        query=json.dumps({"task_tree": {...}, "worker_config": {...}})
    )
    assert result["task_ids"] == ["leaf-1", "leaf-3"]


@pytest.mark.asyncio
async def test_task_executor_uses_native_tools():
    """Task Executor uses configured native benchmark tools via SDK BaseLoop."""
    agent = create_agent(
        AgentKind.TASK_EXECUTOR,
        config=TaskExecutorConfig(native_tools=[mock_benchmark_tool]),
    )
    mock_client = MockLLMClient(
        responses=[
            MockToolUse(tool="run_benchmark", result={"score": 0.95}),
            MockTextResponse(
                content=json.dumps({"task_id": "t1", "status": "success", "data": {}})
            ),
        ]
    )
    result = await agent.run(query=json.dumps({"task_id": "t1"}))
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_primary_agent_synthesizes_final_response():
    """Primary Agent synthesizes final response from context/worker results."""
    agent = create_agent(AgentKind.PRIMARY_AGENT)
    mock_client = MockLLMClient(
        response=json.dumps({"response": "Here is your answer", "citations": []})
    )
    result = await agent.run(
        query=json.dumps({"context_enhanced_query": {...}})
    )
    assert "response" in result


@pytest.mark.asyncio
async def test_no_custom_linear_loop_exists():
    """Verify no LinearAgentLoop or SimpleLoop wrapper was introduced."""
    from tinycua.loops import __all__ as loop_exports
    assert "LinearAgentLoop" not in loop_exports
    assert "SimpleLoop" not in loop_exports
```

### Phase 5: Hybrid Review Loop

```python
# Test file: tests/integration/test_hybrid_review_loop.py
"""Integration tests for HybridReviewLoop and Result Reviewer agent."""


@pytest.mark.asyncio
async def test_hybrid_review_accepts_valid_result():
    """Result Reviewer accepts a valid TaskResult end-to-end.

    End-to-end: Phase 1 deterministic checks pass, Phase 2 SDK Agent.run()
    conducts semantic review, returns accepted with context_updates.
    """
    agent = create_agent(AgentKind.RESULT_REVIEWER)
    mock_client = MockLLMClient(
        response=json.dumps({
            "status": "accepted",
            "reason": "Output meets all success criteria",
            "context_updates": {
                "completed_tasks": ["t1"],
                "relevant_context": "Task t1 produced useful artifact A",
            },
        })
    )
    result = await agent.run(
        query=json.dumps({
            "task_id": "t1",
            "task_result": {"status": "success", "data": {}},
            "execution_log": [],
        })
    )
    assert result["status"] == "accepted"
    assert "context_updates" in result


@pytest.mark.asyncio
async def test_hybrid_review_retry_status():
    """Result Reviewer returns retry with instructions."""
    agent = create_agent(AgentKind.RESULT_REVIEWER)
    mock_client = MockLLMClient(
        response=json.dumps({
            "status": "retry",
            "reason": "Output partially correct, needs refinement",
            "retry_instructions": "Re-run with stricter accuracy threshold",
        })
    )
    result = await agent.run(
        query=json.dumps({"task_id": "t1", "task_result": {}, "execution_log": []})
    )
    assert result["status"] == "retry"
    assert "retry_instructions" in result


@pytest.mark.asyncio
async def test_hybrid_review_replan_status():
    """Result Reviewer returns replan with rationale."""
    agent = create_agent(AgentKind.RESULT_REVIEWER)
    mock_client = MockLLMClient(
        response=json.dumps({
            "status": "replan",
            "reason": "Task decomposition was insufficient",
            "rationale": "Leaf task requires further sub-decomposition",
        })
    )
    result = await agent.run(
        query=json.dumps({"task_id": "t1", "task_result": {}, "execution_log": []})
    )
    assert result["status"] == "replan"
    assert "rationale" in result


@pytest.mark.asyncio
async def test_hybrid_review_escalate_user():
    """Result Reviewer escalates to user with clear explanation."""
    agent = create_agent(AgentKind.RESULT_REVIEWER)
    mock_client = MockLLMClient(
        response=json.dumps({
            "status": "escalate_user",
            "reason": "Ambiguous success criteria",
            "user_explanation": "Cannot determine if the output satisfies the task.",
        })
    )
    result = await agent.run(
        query=json.dumps({"task_id": "t1", "task_result": {}, "execution_log": []})
    )
    assert result["status"] == "escalate_user"
    assert len(result["user_explanation"]) > 0


@pytest.mark.asyncio
async def test_deterministic_failure_overrides_llm():
    """When Phase 1 deterministic rules fail, Phase 2 (LLM) is skipped entirely."""
    failing_rule = DeterministicRule(
        name="SchemaValidity",
        check=lambda t, r, e: DeterministicRuleResult(
            passed=False, reason="Missing required field", severity="escalate"
        ),
    )
    agent = create_agent(
        AgentKind.RESULT_REVIEWER,
        config=ResultReviewerConfig(deterministic_rules=[failing_rule]),
    )
    # Phase 1 fails → Phase 2 skipped even if LLM would accept
    result = await agent.run(
        query=json.dumps({"task_id": "t1", "task_result": {}, "execution_log": []})
    )
    assert result["status"] == "escalate_user"
    assert "Missing required field" in result["reason"]


@pytest.mark.asyncio
async def test_pluggable_deterministic_rules():
    """Different rule sets produce different deterministic outcomes without subclassing."""
    rules_a = [
        DeterministicRule(name="CheckA", check=lambda t, r, e: DeterministicRuleResult(passed=True)),
        DeterministicRule(name="CheckB", check=lambda t, r, e: DeterministicRuleResult(passed=False, reason="fail", severity="replan")),
    ]
    loop = HybridReviewLoop(deterministic_rules=rules_a)
    # CheckB fails → loop should return replan decision before reaching LLM
    assert len(loop._deterministic_rules) == 2
```

### Phase 6: Agent-to-Agent Tools, Integration & Documentation

```python
# Test file: tests/integration/test_agent_calling_tools.py
"""Integration tests for agent-to-agent calling tools."""


@pytest.mark.asyncio
async def test_call_query_analyst_delegates_to_configured_agent():
    """call_query_analyst Tool invokes the configured Query Analyst Agent.run()."""
    internal_agents = create_all_agents()
    tool = call_query_analyst(internal_agents)
    mock_client = MockLLMClient(response=json.dumps({"mode_index": 0}))
    result = await tool.execute(
        user_query="Simple question",
        chat_history=[],
        session_context={},
    )
    assert "context_enhanced_query" in result
    assert "mode_decision" in result


@pytest.mark.asyncio
async def test_agent_calling_tool_respects_target_loop():
    """Agent-calling tools pass through the target agent's configured loop."""
    # Set custom labels on Query Analyst config
    config = QueryAnalystConfig(classification_labels=["direct", "team"])
    agent = create_agent(AgentKind.QUERY_ANALYST, config=config)
    agents = {AgentKind.QUERY_ANALYST: agent}
    tool = call_query_analyst(agents)
    # The tool must call agent.run(), not bypass the loop
    mock_client = MockLLMClient(response=json.dumps({"mode_index": 0}))
    result = await tool.execute(user_query="test", chat_history=[], session_context={})
    assert result["mode_decision"]["mode"] == "direct"


@pytest.mark.asyncio
async def test_all_call_tools_exist_as_sdk_tools():
    """All seven agent-calling tools are SDK Tool objects."""
    from tinycua.tools.agent_calls import (
        call_query_analyst,
        call_information_digester,
        call_task_analyzer,
        call_task_assessor,
        call_task_executor,
        call_result_reviewer,
        call_primary_agent,
    )
    from tinycua_sdk.tools.decorators import Tool as SdkTool

    agents = create_all_agents()
    tools = [
        call_query_analyst(agents),
        call_information_digester(agents),
        call_task_analyzer(agents),
        call_task_assessor(agents),
        call_task_executor(agents),
        call_result_reviewer(agents),
        call_primary_agent(agents),
    ]
    assert len(tools) == 7
    for tool in tools:
        assert isinstance(tool, SdkTool), f"{tool} is not an SDK Tool"


@pytest.mark.asyncio
async def test_custom_loops_attached_via_agent_not_wrapping():
    """Custom loops are configured as Agent(loop=...) not as agent wrappers."""
    agent = create_agent(AgentKind.QUERY_ANALYST)
    # The loop is a property on Agent.config, not an outer wrapper
    assert agent.config.loop is not None
    assert not hasattr(agent.config.loop, "agent")  # Loop does not own Agent


@pytest.mark.asyncio
async def test_agent_factory_output_fits_mainloop_metadata():
    """Agent factory output can be placed under Agent(metadata={...}) 
    for MainLoop consumption without changing internal agent APIs."""
    agents = create_all_agents()
    assert len(agents) == 7
    # Verify it can be stored in metadata as expected by MainLoop contract
    metadata = {"tinycua": {"internal_agents": agents}}
    assert len(metadata["tinycua"]["internal_agents"]) == 7
```

### Key Test Scenarios

- [ ] **Scenario 1 (Classification end-to-end)**: Query Analyst configured with `ClassificationLoop` and `ClassificationTool` makes classification decisions via index-based tool for all three modes (primary_agent, worker, uncertain). The classification labels are configurable in `QueryAnalystConfig`.
- [ ] **Scenario 2 (Exploration end-to-end)**: Information Digester configured with `ExplorationLoop` performs multi-iteration retrieval, stops on LLM-judged sufficiency with `BaseLoop.max_iterations` hard cap, and produces `DigestedInformation` with gaps on empty results.
- [ ] **Scenario 3 (Standard agents end-to-end)**: Task Analyzer, Task Assessor, Task Executor, and Primary Agent all use SDK `BaseLoop` directly (no custom loop class), produce schema-valid outputs, and support optional tools.
- [ ] **Scenario 4 (Hybrid Review end-to-end)**: Result Reviewer produces all four statuses (accepted/retry/replan/escalate_user), deterministic failures skip LLM phase, and pluggable rule sets work without subclassing.
- [ ] **Scenario 5 (Agent-to-agent calling)**: All seven `call_*` SDK `Tool` objects delegate through configured `Agent.run()`, respecting target agent loops and config.
- [ ] **Scenario 6 (Agent config overrides)**: Each agent's `AgentConfig` dataclass accepts per-field overrides (classification_labels, extra_tools, deterministic_rules, native_tools, model_override, metadata) and the factory produces agents reflecting those overrides.
- [ ] **Edge case (Invalid tool index)**: `ClassificationTool` rejects out-of-range indices with clear error.
- [ ] **Edge case (Empty retrieval)**: Exploration loop produces `DigestedInformation` with `known_gaps` when retrieval returns nothing.

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] Unit tests for each loop type — construction, error handling, edge cases, fallbacks (see Testing Plan in spec.md for full matrix)
- [ ] Unit tests for SchemaValidator — valid output passes, invalid output fails with descriptive error, nested structure validation
- [ ] Unit tests for AgentFactory/config registry — each architecture agent constructed with expected name, instructions, tools, output validator, and loop value
- [ ] Unit tests for model configuration — verify default TinyCUA agents use provider `openai-chat-completions`, model `qwen/qwen3.5-4b`, base URL `http://localhost:1234/v1`
- [ ] Unit tests for system prompts — verify definitions include role, input contract, output schema, constraints, and guardrails
- [ ] Unit tests for ClassificationTool — valid indices return correct labels, invalid indices raise error
- [ ] Unit tests for agent config dataclasses — each config class accepts overrides, defaults remain unchanged
- [ ] Existing test suite — confirm no regressions: `cd src/tinycua && uv run pytest`

### Manual Verification

- [ ] Verify `tinycua-sdk` dependency is available and properly configured in `src/tinycua/pyproject.toml`
- [ ] Verify no `tinycua/loops/base.py` with custom `LoopBase`, `LLMBackend`, or `ToolDef` classes exists
- [ ] Verify no `tinycua/loops/linear.py` with `LinearAgentLoop` or `SimpleLoop` wrapper exists
- [ ] Verify all custom loops extend `tinycua_sdk.agent.loop.BaseLoop`
- [ ] Verify architecture docs listed in spec "Future Architecture Documentation Sync" are updated during implementation

### Performance Considerations

- [ ] ClassificationLoop: single structured output, minimal overhead over SDK `BaseLoop`
- [ ] ExplorationLoop: bounded by `BaseLoop.max_iterations` (default 5) — no unbounded retrieval
- [ ] HybridReviewLoop: deterministic phase is O(n_rules); LLM phase is a single `BaseLoop.run()` call
- [ ] Agent factory: all seven agents constructable in O(1) with no network calls

## Proposed Changes

### tinycua/loops/ — Custom Loop Strategies

#### [NEW] `tinycua/loops/__init__.py`

- **Description**: Re-exports all loop types (`ClassificationLoop`, `ExplorationLoop`, `HybridReviewLoop`), `SchemaValidator`, `DeterministicRule`, `DeterministicRuleResult`, `LoopType`, error hierarchy, and re-exported SDK types (`BaseLoop`, `Agent`, `LanguageModel`, `Tool`).
- **Dependencies**: SDK modules (`BaseLoop`, `Agent`, etc.)

#### [NEW] `tinycua/loops/errors.py`

- **Description**: Thin error hierarchy wrapping SDK exceptions: `LoopError`, `LoopTransientError`, `LoopPermanentError`, `LoopOutputValidationError`.
- **Rationale**: Give callers typed exceptions without leaking SDK internals.

#### [NEW] `tinycua/loops/schema_validator.py`

- **Description**: Wraps SDK `Agent.run()` with output validation and retry. Takes a `validation_fn` and `max_validation_retries`. On validation failure, retries Agent with error context in the prompt.
- **Rationale**: Centralizes output schema enforcement without custom LLM calling.

#### [NEW] `tinycua/loops/classification.py`

- **Description**: `ClassificationLoop` extends SDK `BaseLoop`. Uses SDK default iteration behavior (no forced `max_iterations=1`). Provides the `ClassificationTool` as a configurable tool: the tool accepts a `mode_index` and returns the label at that index from a configurable list. The agent uses this tool to emit a structured classification verdict. `SchemaValidator` validates the output into `ContextEnhancedQuery` + `ModeDecision`.
- **Dependencies**: SDK `BaseLoop`, `SchemaValidator`, `ClassificationTool`.

#### [NEW] `tinycua/loops/exploration.py`

- **Description**: `ExplorationLoop` extends SDK `BaseLoop`, adding gap-evaluation between SDK iterations. Overrides `run()` to: (1) let SDK `BaseLoop` handle tool-calling iteration, (2) after each iteration check if LLM output indicates gaps are addressed, (3) stop on sufficiency OR `max_iterations` hard cap.
- **Dependencies**: SDK `BaseLoop`, `SchemaValidator`.

#### [NEW] `tinycua/loops/hybrid_review.py`

- **Description**: `HybridReviewLoop` extends SDK `BaseLoop` with two-phase execution. Constructor accepts `deterministic_rules: list[DeterministicRule]`. Phase 1 evaluates all rules; if any fail with `escalate` or `replan`, returns immediately. Phase 2 delegates to SDK `BaseLoop` behavior for LLM semantic review.
- **Dependencies**: SDK `BaseLoop`, `DeterministicRule`, `DeterministicRuleResult`.

### tinycua/agents/ — Agent Factory and Configuration

#### [NEW] `tinycua/agents/__init__.py`

- **Description**: Re-exports `AgentKind`, `AgentConfigSpec`, `create_agent`, `create_all_agents`, and all agent config dataclasses.

#### [NEW] `tinycua/agents/configs.py`

- **Description**: Agent config dataclasses for all seven architecture agents. Each class extends a common base. Fields include agent-specific knobs and an `extra_tools` list for MainLoop-injected tools. Classification labels are configurable here. Examples:
  - `QueryAnalystConfig` — name, model_override, instructions_override, classification_labels, extra_tools, metadata
  - `InformationDigesterConfig` — name, model_override, instructions_override, extra_tools, max_iterations_override, metadata
  - `TaskAnalyzerConfig` — name, model_override, instructions_override, extra_tools, metadata
  - `TaskAssessorConfig` — name, model_override, instructions_override, extra_tools, metadata
  - `TaskExecutorConfig` — name, model_override, instructions_override, native_tools, extra_tools, metadata
  - `ResultReviewerConfig` — name, model_override, instructions_override, deterministic_rules, extra_tools, metadata
  - `PrimaryAgentConfig` — name, model_override, instructions_override, extra_tools, metadata
- **Rationale**: Each agent's configurable parameters are explicit, typed, and overridable from MainLoop metadata later.

#### [NEW] `tinycua/agents/prompts.py`

- **Description**: System prompt strings for all seven architecture agents (`QUERY_ANALYST_PROMPT`, `INFORMATION_DIGESTER_PROMPT`, `TASK_ANALYZER_PROMPT`, `TASK_ASSESSOR_PROMPT`, `TASK_EXECUTOR_PROMPT`, `RESULT_REVIEWER_PROMPT`, `PRIMARY_AGENT_PROMPT`). Derived from architecture docs (`src/tinycua/docs/architecture/`). Each prompt includes role, input contract, output schema, constraints, and guardrails.
- **Rationale**: Prompts are owned by the agent config layer, not embedded in loops.

#### [NEW] `tinycua/agents/factory.py`

- **Description**: `AgentFactory` / `create_agent(AgentKind, config=None)` creates a configured SDK `Agent`. Accepts optional config override dataclass. `create_all_agents(config_overrides: dict[AgentKind, AgentConfig] | None)` creates all seven. Attaches custom loops through `Agent(loop=...)` and omits `loop` for direct `BaseLoop` agents. Uses `TINYCUA_DEFAULT_MODEL` unless config specifies `model_override`. Merges config `extra_tools` into agent's tool list.
- **Dependencies**: SDK `Agent`, `BaseLoop`, `LanguageModel`, `configs.py`, `prompts.py`, custom loop types.

### tinycua/tools/ — Agent-to-Agent Calling Tools

#### [NEW] `tinycua/tools/agent_calls.py`

- **Description**: Seven SDK `Tool` objects: `call_query_analyst`, `call_information_digester`, `call_task_analyzer`, `call_task_assessor`, `call_task_executor`, `call_result_reviewer`, `call_primary_agent`. Each is a factory: `call_query_analyst(internal_agents: dict[AgentKind, Agent]) -> Tool`. The tool's execute method calls `target_agent.run(...)`, validates the output schema, and returns the normalized output.
- **Dependencies**: SDK `Tool`, `Agent`; `tinycua.agents` (`AgentKind`, configs).

### tinycua/ — Module Registration

#### [MODIFY] `tinycua/__init__.py`

- **Description**: Re-export `tinycua.loops` and `tinycua.agents` submodules if appropriate. No breaking changes.
- **Rationale**: Make loop types and agent factory discoverable from the package root.

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `tinycua/loops/` | New | Custom loop strategies extending `tinycua_sdk.agent.loop.BaseLoop`; no custom `base.py` or `linear.py` |
| `tinycua/agents/` | New | Agent factory/registry, config dataclasses, system prompt definitions |
| `tinycua/tools/agent_calls.py` | New | Seven agent-to-agent SDK `Tool` wrappers |
| `tinycua/orchestration/main_loop.py` | Future | MainLoop external TINYCUA loop; consumes M2 internal agent registry (deferred) |
| `tinycua/state/` | Unchanged | Loops consume M1 state objects as input/output |
| `tinycua/__init__.py` | Modify | Re-export loop and agent modules |
| `tinycua_sdk` | No changes | Used as-is; custom loops extend SDK classes, do not modify SDK |
| Architecture docs | Modify (impl phase) | Update to reflect direct `BaseLoop` usage, rename legacy loop type references |
| SDK cookbook (`custom-execution-loops.md`) | Modify (impl phase) | Correct examples to show `Agent(loop=CustomLoop(...))` |

## Data Model Changes

### Agent Config Dataclasses

```python
@dataclass
class AgentConfigBase:
    """Base configuration shared by all TinyCUA internal agents."""
    name: str
    instructions: str
    model: LanguageModel = field(default_factory=lambda: TINYCUA_DEFAULT_MODEL)
    extra_tools: list[Tool] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QueryAnalystConfig(AgentConfigBase):
    """Configuration for the Query Analyst (Classification Loop)."""
    name: str = "query-analyst"
    instructions: str = QUERY_ANALYST_PROMPT
    classification_labels: list[str] = field(
        default_factory=lambda: ["primary_agent", "worker", "uncertain"]
    )


@dataclass
class InformationDigesterConfig(AgentConfigBase):
    """Configuration for the Information Digester (Exploration Loop)."""
    name: str = "information-digester"
    instructions: str = INFORMATION_DIGESTER_PROMPT
    max_iterations_override: int | None = None


@dataclass
class TaskAnalyzerConfig(AgentConfigBase):
    """Configuration for the Task Analyzer (SDK BaseLoop)."""
    name: str = "task-analyzer"
    instructions: str = TASK_ANALYZER_PROMPT


@dataclass
class TaskAssessorConfig(AgentConfigBase):
    """Configuration for the Task Assessor (SDK BaseLoop)."""
    name: str = "task-assessor"
    instructions: str = TASK_ASSESSOR_PROMPT


@dataclass
class TaskExecutorConfig(AgentConfigBase):
    """Configuration for the Task Executor (SDK BaseLoop)."""
    name: str = "task-executor"
    instructions: str = TASK_EXECUTOR_PROMPT
    native_tools: list[Tool] = field(default_factory=list)


@dataclass
class ResultReviewerConfig(AgentConfigBase):
    """Configuration for the Result Reviewer (Hybrid Review Loop)."""
    name: str = "result-reviewer"
    instructions: str = RESULT_REVIEWER_PROMPT
    deterministic_rules: list[DeterministicRule] = field(
        default_factory=lambda: [DEFAULT_SCHEMA_RULE, DEFAULT_FIELDS_RULE]
    )


@dataclass
class PrimaryAgentConfig(AgentConfigBase):
    """Configuration for the Primary Agent (SDK BaseLoop)."""
    name: str = "primary-agent"
    instructions: str = PRIMARY_AGENT_PROMPT
```

### ClassificationTool

```python
@dataclass
class ClassificationTool:
    """Tool that maps an agent-selected index to a classification label.
    
    The agent calls classify(mode_index=N) and the tool returns
    the label at that index from a configurable list. The list is
    set at construction, not by the agent during execution.
    """
    labels: list[str]

    async def execute(self, mode_index: int) -> str:
        if 0 <= mode_index < len(self.labels):
            return self.labels[mode_index]
        raise ValueError(
            f"Classification index {mode_index} out of range "
            f"[0..{len(self.labels) - 1}]. Valid labels: {self.labels}"
        )
```

## API Changes

### New Public API

| Symbol | Location | Description |
|--------|----------|-------------|
| `ClassificationLoop` | `tinycua.loops.classification` | Custom loop for Query Analyst classification |
| `ExplorationLoop` | `tinycua.loops.exploration` | Custom loop for Information Digester retrieval |
| `HybridReviewLoop` | `tinycua.loops.hybrid_review` | Custom loop for Result Reviewer two-phase review |
| `SchemaValidator` | `tinycua.loops.schema_validator` | Output validation with SDK Agent retry |
| `DeterministicRule` | `tinycua.loops.hybrid_review` | Pluggable deterministic check for Hybrid Review |
| `DeterministicRuleResult` | `tinycua.loops.hybrid_review` | Result of a deterministic check |
| `LoopType` | `tinycua.loops` | Enum of loop strategy identifiers |
| `LoopError` et al. | `tinycua.loops.errors` | Error hierarchy (transient, permanent, validation) |
| `AgentKind` | `tinycua.agents.configs` | Enum of architecture agent types |
| `create_agent()` | `tinycua.agents.factory` | Factory: create one configured SDK Agent |
| `create_all_agents()` | `tinycua.agents.factory` | Factory: create all seven configured SDK Agents |
| Agent config dataclasses | `tinycua.agents.configs` | Per-agent configuration with overridable fields |
| `call_query_analyst()` et al. | `tinycua.tools.agent_calls` | Agent-to-agent SDK Tool factories |

### No Modified Endpoints

All new surface area. No existing APIs are broken.

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `tinycua-sdk` | >=0.1.0 (workspace) | `BaseLoop`, `Agent`, `LLMClient`, `LanguageModel`, `Tool`, `ToolExecutor` |

### Internal Dependencies

- [ ] Depends on M1 state types (`tinycua.state`) — consumed as input/output, not modified
- [ ] Depends on architecture docs for prompt content (`src/tinycua/docs/architecture/`)
- [ ] Blocks future milestones: M4 (sessions), M5 (worker orchestration), M6 (MainLoop executable)

### Agent Config → MainLoop Forward Compatibility

The `AgentConfig` dataclasses include a `metadata: dict[str, Any]` field. Future MainLoop can:
1. Read config defaults from `create_all_agents()`
2. Override individual agent config fields (e.g., `classification_labels`, `deterministic_rules`, `extra_tools`) from its own metadata
3. Store overrides under `agent.config.metadata["tinycua"]`
4. Inject extra tools or model overrides per-agent without modifying factory code

This propagation mechanism (MainLoop → internal agent config) is a future MainLoop concern; M2 ensures configs are structured to accept it.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM output parsing failures with real models | High | SchemaValidator retries via SDK Agent with error context. Lower retry threshold surfaces failures early. |
| Exploration loop infinite retrieval | Medium | SDK's `BaseLoop.max_iterations` provides configurable hard cap. Default 5. |
| Hybrid Review deterministic/LLM conflict | Low | Deterministic checks win — if they fail, Phase 2 (SDK Agent) is skipped. |
| Direct SDK BaseLoop misused for branching agents | Low | Documented per agent. AgentKind enum + factory prevents misconfiguration. |
| SDK version incompatibility | Medium | `tinycua` depends on `tinycua-sdk>=0.1.0` via workspace. SDK breaking changes require coordinated updates. |
| Classification labels changes require prompt edits | Medium | ClassificationTool decouples labels from prompts. The tool owns the label list; the agent only picks an index. Changing labels only requires changing `classification_labels` in `QueryAnalystConfig` — no prompt rewrite needed. |
| Agent config explosion (too many dataclasses) | Low | Seven config classes match the seven architecture agents. Each exposes only overridable knobs that MainLoop will realistically change. Avoid premature abstraction. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-31*
