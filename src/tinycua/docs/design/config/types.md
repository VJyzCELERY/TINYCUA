# Config Types

> **File:** `docs/design/config/types.md`
> **Package:** `tinycua.config.types`
> **Last Updated:** 2026-05-31
> **Status:** Draft

---

## `AgentKind` Enum

Identifies each of the eight architecture agents plus the external TinyCUA agent:

```text
AgentKind (str, Enum)
    · QUERY_ANALYST = "query-analyst"
    · INFORMATION_DIGESTER = "information-digester"
    · TASK_CREATOR = "task-creator"
    · TASK_ANALYZER = "task-analyzer"
    · TASK_ASSESSOR = "task-assessor"
    · TASK_EXECUTOR = "task-executor"
    · RESULT_REVIEWER = "result-reviewer"
    · PRIMARY_AGENT = "primary-agent"
    · TINYCUA = "tinycua"
```

Used by `create_agent_node(AgentKind, ...)` and `create_all_agent_nodes()` in the factory.

---

## `TINYCUA_DEFAULT_MODEL`

```text
TINYCUA_DEFAULT_MODEL → LanguageModel with:
    · provider: str = "openai-chat-completions"
    · model_name: str = "qwen/qwen3.5-4b"
    · base_url: str = "http://localhost:1234/v1"
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
| `AgentKind.TINYCUA` | Enum member even though AgentGraph is in `orchestration/` | Consistent registry lookup |


---


---


---

## See also

Next : [Per-Agent Config Dataclasses](agents.md)


## Related

- [Per-agent config dataclasses using AgentKind](agents.md)
- [BaseAgentNode — agents are looked up by AgentKind](../agent_node/base.md)
