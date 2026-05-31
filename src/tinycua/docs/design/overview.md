# Design Overview

> **File:** `docs/design/overview.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **See also:** [`../architecture/overview.md`](../architecture/overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Design Thesis

TinyCUA agents are **wrapper classes** that compose (not extend) an SDK `Agent` internally.
Loops are low-level execution strategies; wrappers handle high-level concerns.
This separation ensures:

- Loops stay testable at the SDK level (mock `Agent`, mock `LLMClient`)
- Wrappers stay testable at the integration level (mock LLM responses through the composed agent)
- Each agent's tools, config, and state are self-documenting
- Future `MainLoop` can customize internal agents without touching loop internals

---

## Project Structure

```
src/tinycua/tinycua/
├── config/                           # AgentKind enum, TINYCUA_DEFAULT_MODEL, config dataclasses
│   ├── types.py                        # AgentKind, TINYCUA_DEFAULT_MODEL
│   └── agents.py                       # AgentConfigBase + 7 per-agent config dataclasses
├── constants/                        # Pre-configured tool sets per agent
│   └── tools.py                        # *_BASE_TOOLS for all 7 agents
├── loops/                            # Execution loop strategies
│   ├── react_agent.py                  # ReActAgentLoop (used by 4 simple agents)
│   ├── query_analyst_loop.py           # QueryAnalystLoop (classification)
│   ├── information_digestion_loop.py   # InformationDigestionLoop (iterative retrieval)
│   ├── result_review_loop.py           # ResultReviewLoop (two-phase review)
│   ├── schema_validator.py             # Output validation + retry
│   ├── main_loop.py                    # FUTURE (M6)
│   └── errors.py                       # LoopError hierarchy
├── agents/                           # Agent wrapper classes
│   ├── base.py                         # BaseAgentWrapper[S] abstract class
│   ├── factory.py                      # create_agent(), create_all_agents()
│   ├── prompts.py                      # System prompts for all 7 agents
│   ├── query_analyst.py                # QueryAnalyst
│   ├── information_digester.py         # InformationDigester
│   ├── task_analyzer.py                # TaskAnalyzer
│   ├── task_assessor.py                # TaskAssessor
│   ├── task_executor.py                # TaskExecutor
│   ├── result_reviewer.py              # ResultReviewer
│   ├── primary_agent.py                # PrimaryAgent
│   └── tinycua_agent.py                # FUTURE (M6): TinyCUA external wrapper
├── tools/                            # Agent-to-agent calling tools
│   └── agent_calls.py                  # call_query_analyst(), etc.
├── state/                            # M1 state objects + StateInformation
│   ├── information.py                  # StateInformation ABC + 7 subclasses
│   ├── state_store.py                  # FUTURE (M6)
│   └── ...                             # Existing M1 types
└── __init__.py
```

Directories removed by this design:
- `agent/` — superseded by `agents/`
- `orchestration/` — contents moved to `loops/`, `agents/`, and `state/`

---

## Layer Separation: Wrapper vs Loop

| Concern | Managed By | Examples |
|---------|-----------|----------|
| LLM orchestration | SDK `BaseLoop` | Tool calling, message construction, streaming |
| Tool execution | SDK `ToolExecutor` | Invoke tools, normalize results |
| Domain control flow | Custom loop | Gap evaluation, two-phase review, classification |
| Input preparation | Wrapper `run()` | Building prompt messages from domain objects |
| Output parsing | Wrapper `run()` | Parsing raw LLM output into typed M1 objects |
| Context management | Wrapper `self.state` | Storing last result, session state, tool results |
| Persistence hooks | Wrapper `save_state()` / `restore_state()` | Delegating to SQLite/filesystem stores |
| Logging / verbosity | Wrapper class | Per-agent log level, progress callbacks |
| Config override | Agent config dataclass | Classification labels, deterministic rules |

---

## Tool Sources Pattern

Every agent's composed SDK `Agent` receives tools from exactly two sources:

```python
# _build_agent() inside wrapper class:
self.agent = Agent(
    ...
    tools=[*QUERY_ANALYST_BASE_TOOLS, *self.config.extra_tools],
    loop=QueryAnalystLoop(),
)
```

| Source | Location | Purpose |
|--------|----------|---------|
| `*_BASE_TOOLS` | `tinycua.constants.tools` | Pre-configured tool set (module-level constant) |
| `config.extra_tools` | Agent config dataclass | Externally injected tools — **empty by default** |

Seven `*_BASE_TOOLS` constants exist (see [`constants/tools.py`](#constants-toolspy)):

| Constant | Contents |
|----------|----------|
| `QUERY_ANALYST_BASE_TOOLS` | `[ClassificationTool(labels=["primary_agent", "worker", "uncertain"])]` |
| `INFORMATION_DIGESTER_BASE_TOOLS` | `[enhanced_context_retrieval]` |
| `TASK_ANALYZER_BASE_TOOLS` | `[]` |
| `TASK_ASSESSOR_BASE_TOOLS` | `[]` |
| `TASK_EXECUTOR_BASE_TOOLS` | `[*native_benchmark_tools]` |
| `RESULT_REVIEWER_BASE_TOOLS` | `[]` |
| `PRIMARY_AGENT_BASE_TOOLS` | `[]` |

---

## Agent Loop Mapping

| Agent | Loop | Extends | Custom Behavior |
|-------|------|---------|-----------------|
| QueryAnalyst | `QueryAnalystLoop` | SDK `BaseLoop` | Classification control flow |
| InformationDigester | `InformationDigestionLoop` | SDK `BaseLoop` | Iterative retrieval + gap evaluation |
| TaskAnalyzer | `ReActAgentLoop` | SDK `BaseLoop` | (none — shared ReAct) |
| TaskAssessor | `ReActAgentLoop` | SDK `BaseLoop` | (none — shared ReAct) |
| TaskExecutor | `ReActAgentLoop` | SDK `BaseLoop` | (none — shared ReAct) |
| ResultReviewer | `ResultReviewLoop` | SDK `BaseLoop` | Two-phase: deterministic rules + LLM review |
| PrimaryAgent | `ReActAgentLoop` | SDK `BaseLoop` | (none — shared ReAct) |
| TinyCUA (future) | `MainLoop` | SDK `BaseLoop` | Full orchestration flow |

---

## Default Model Configuration

```python
TINYCUA_DEFAULT_MODEL = LanguageModel(
    provider="openai-chat-completions",
    model_name="qwen/qwen3.5-4b",
    base_url="http://localhost:1234/v1",
)
```

Defined in `tinycua.config.types`. Use the canonical SDK provider identifier
`openai-chat-completions` — do not use the alias `openai`.

---

## Related

- [`loop-strategies.md`](loop-strategies.md) — Detailed loop designs
- [`base-agent-wrapper.md`](base-agent-wrapper.md) — Wrapper base class and state
- Per-agent design docs for each wrapper class
- [`../architecture/overview.md`](../architecture/overview.md) — Conceptual architecture
- [`../../specs/custom-loops/spec.md`](../../specs/custom-loops/spec.md) — Feature specification
- [`../../specs/custom-loops/design.md`](../../specs/custom-loops/design.md) — Condensed design document
