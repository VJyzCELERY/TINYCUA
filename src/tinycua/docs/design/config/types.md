# Config Types

> **File:** `docs/design/config/types.md`
> **Package:** `tinycua.config.types`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## `AgentKind` Enum

Identifies each of the seven architecture agents plus the external TinyCUA agent:

```python
from enum import Enum

class AgentKind(str, Enum):
    QUERY_ANALYST = "query-analyst"
    INFORMATION_DIGESTER = "information-digester"
    TASK_ANALYZER = "task-analyzer"
    TASK_ASSESSOR = "task-assessor"
    TASK_EXECUTOR = "task-executor"
    RESULT_REVIEWER = "result-reviewer"
    PRIMARY_AGENT = "primary-agent"
    TINYCUA = "tinycua"
```

Used by `create_agent(AgentKind, ...)` and `create_all_agents()` in the factory.

---

## `TINYCUA_DEFAULT_MODEL`

```python
from tinycua_sdk.agent.llm_model import LanguageModel

TINYCUA_DEFAULT_MODEL = LanguageModel(
    provider="openai-chat-completions",
    model_name="qwen/qwen3.5-4b",
    base_url="http://localhost:1234/v1",
)
```

All agent configs default to this model. Use the canonical SDK provider identifier
`openai-chat-completions` — do NOT use the alias `openai`. Individual agents
can override via their config dataclass.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| `TINYCUA_DEFAULT_MODEL` in `config/types` | Central constant | Single source of truth for the default model; all agents reference it |
| Provider `openai-chat-completions` | Not alias `openai` | SDK's `openai` alias resolves to the Responses API, not the intended chat-completions endpoint |
| `AgentKind.TINYCUA` | Enum member even though wrapper is in `agents/` | Consistent registry lookup; factory can return either internal or external agents |
