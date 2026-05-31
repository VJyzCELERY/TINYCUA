# Primary Agent

> **File:** `docs/design/primary-agent.md`
> **Last Updated:** 2026-05-31
> **Status:** Draft
> **Architecture reference:** [`../architecture/primary-agent.md`](../architecture/primary-agent.md)
> **See also:** [`overview.md`](overview.md), [`loop-strategies.md`](loop-strategies.md), [`base-agent-wrapper.md`](base-agent-wrapper.md)

---

## Role

The Primary Agent synthesizes the final user-facing response from either a direct
`ContextEnhancedQuery` (Primary Agent mode) or a `WorkerResult` (Worker mode).

---

## Wrapper Class

**File:** `tinycua/agents/primary_agent.py`

```python
from tinycua_sdk.agent import Agent
from tinycua.agents.base import BaseAgentWrapper
from tinycua.config.agents import PrimaryAgentConfig
from tinycua.constants.tools import PRIMARY_AGENT_BASE_TOOLS
from tinycua.loops.react_agent import ReActAgentLoop
from tinycua.loops.schema_validator import SchemaValidator
from tinycua.state.information import PrimaryAgentState


class PrimaryAgent(BaseAgentWrapper[PrimaryAgentState]):
    """Final synthesis agent — ReActAgentLoop."""

    state: PrimaryAgentState

    def __init__(self, config: PrimaryAgentConfig):
        super().__init__(config, state_factory=PrimaryAgentState)
        self._build_agent()

    def _build_agent(self):
        self.agent = Agent(
            name=self.config.name,
            instructions=self.config.instructions,
            llm_model=self.config.model,
            tools=[*PRIMARY_AGENT_BASE_TOOLS, *self.config.extra_tools],
            loop=ReActAgentLoop(),
        )

    async def run(self, input_data: dict) -> dict:
        """input_data is either a ContextEnhancedQuery or a WorkerResult."""
        self.state.last_query = {"input": input_data}
        raw = await self.agent.run(query=json.dumps(input_data))
        result = SchemaValidator(validation_fn=validate_final_response).validate(raw)
        self.state.final_response = result
        self.state.citations = result.get("citations", [])
        self.state.last_result = result
        return result
```

---

## Config

**File:** `tinycua/config/agents.py`

```python
@dataclass
class PrimaryAgentConfig(AgentConfigBase):
    name: str = "primary-agent"
    instructions: str = PRIMARY_AGENT_PROMPT
```

---

## State

**File:** `tinycua/state/information.py`

```python
@dataclass
class PrimaryAgentState(StateInformation):
    final_response: dict[str, Any] = field(default_factory=dict)
    citations: list[str] = field(default_factory=list)
```

---

## Loop

`ReActAgentLoop` — shared loop. See [`loop-strategies.md`](loop-strategies.md#reactagentloop).

---

## Tools

**File:** `tinycua/constants/tools.py`

```python
PRIMARY_AGENT_BASE_TOOLS: list[Tool] = []
```

No inherent tools. Formatting and verification tools can be injected via `config.extra_tools`.

---

## Prompt Contract

**File:** `tinycua/agents/prompts.py`

The prompt must include:
- **Role**: Final synthesis agent — produce a polished, user-facing response
- **Input contract**: `ContextEnhancedQuery` (primary mode) or `WorkerResult` (worker mode)
- **Output schema**: Final response with optional `citations`
- **Guardrails**: Response must be self-contained; cite sources where applicable

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No custom loop | `ReActAgentLoop` | Synthesis is a single input → single output task |
| Flexible input | Accepts CEQ or WorkerResult | Both modes converge on the same synthesis pipeline |
