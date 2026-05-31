# Information Digester

> **File:** `docs/design/information-digester.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/information-digestion.md`](../architecture/information-digestion.md), [`../architecture/context-retrieval.md`](../architecture/context-retrieval.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Information Digester performs iterative Enhanced Context Retrieval to produce
`DigestedInformation` — a focused, de-noised context summary with key points and
identified gaps.

---

## Wrapper Class

**File:** `tinycua/agents/information_digester.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import InformationDigesterConfig
from tinycua.constants.tools import INFORMATION_DIGESTER_BASE_TOOLS
from tinycua.loops.information_digestion_loop import InformationDigestionLoop
from tinycua.loops.schema_validator import SchemaValidator
from tinycua.state.information import InformationDigesterState


class InformationDigester(BaseAgentWrapper[InformationDigesterState]):
    """Information digestion agent — InformationDigestionLoop."""

    state: InformationDigesterState

    def __init__(self, config: InformationDigesterConfig):
        super().__init__(config, state_factory=InformationDigesterState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*INFORMATION_DIGESTER_BASE_TOOLS, *self.config.extra_tools],
            loop=InformationDigestionLoop(
                max_iterations=config.max_iterations_override,
            ),
        )

    async def run(self, context_enhanced_query: dict) -> dict:
        self.state.last_query = {"context_enhanced_query": context_enhanced_query}
        raw = await self.agent.run(query=json.dumps(context_enhanced_query))
        result = SchemaValidator(validation_fn=validate_digested_information).validate(raw)
        self.state.digested_information = DigestedInformation(**result)
        self.state.last_result = result
        return result
```

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class InformationDigesterConfig(AgentConfigBase):
    name: str = "information-digester"
    instructions: str = INFORMATION_DIGESTER_PROMPT
    max_iterations_override: int | None = None  # None → use BaseLoop default (5)
```

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class InformationDigesterState(StateInformation):
    digested_information: DigestedInformation | None = None
    retrieval_iterations: int = 0
```

---

## Loop

`InformationDigestionLoop` — extends SDK `BaseLoop` with iterative gap evaluation.
See [`loop-strategies.md`](loop-strategies.md#informationdigestionloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
INFORMATION_DIGESTER_BASE_TOOLS: list[Tool] = [
    enhanced_context_retrieval,
]
```

The retrieval tool is defined as an SDK `Tool` contract. Full native implementation
belongs to the Tools milestone; a stub/mock is acceptable for early tests.

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Precision retrieval agent — identify gaps, retrieve, evaluate, stop or continue
- **Input contract**: `ContextEnhancedQuery`
- **Output schema**: `DigestedInformation` with `context_summary`, `key_points`, optional `advisory_instructions`, `constraints`, `known_gaps`
- **Retrieval strategy**: Use `enhanced_context_retrieval` tool to search session context
- **Stop-condition guardrails**: Judge whether identified gaps are addressed; stop when sufficient or retrieval returns no new info
- **Gap handling**: When retrieval returns nothing, explicitly list `known_gaps`

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stop on sufficiency + hard cap | LLM-judged + `BaseLoop.max_iterations` | Context awareness + safety against infinite loops |
| Retrieval tool as contract | SDK `Tool` contract, native impl deferred | Tool infrastructure belongs to Tools milestone |
| Max iterations configurable | `config.max_iterations_override` | Different deployments may want different limits |
