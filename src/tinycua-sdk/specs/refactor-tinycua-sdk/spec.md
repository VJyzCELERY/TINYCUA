# SDK Stateless Refactor — Specification

## Overview

Refactor `tinycua_sdk` into a **stateless, runnable framework** for building and executing AI agents. The SDK provides building blocks (Agent, Tool, Skill, Config) without managing runtime state, persistence, sessions, memory, or infrastructure.

## Goals

1. **Stateless SDK**: No stores, no singletons, no database connections, no file I/O, no HTTP clients.
2. **Runnable out of the box**: Create an agent in one line and execute it immediately.
3. **Configuration-driven**: Support programmatic and YAML/JSON config-based agent creation.
4. **Consumer owns state**: Sessions, memory, storage, remote backends, and registries live in the consumer codebase.

## Non-Goals

- Session management or message history persistence.
- Memory storage, snapshots, embeddings, or retrieval.
- User profiling, personality modeling, or communication analysis.
- Database schemas, migrations, connection pools, or CRUD utilities.
- CLI, REPL, or command-line interfaces.
- HTTP clients for remote backend communication.
- Singleton registries or global caches.

## Requirements

### R1 — Agent Execution

The SDK must provide a fully runnable `Agent` class.

```python
agent = Agent(
    llm_model=LLMModel(base_url="...", model_name="...", system_prompt="..."),
    instructions="Answer questions concisely.",
)
response = await agent.run("What is quantum computing?")
```

**R1.1** `Agent` must accept `llm_model`, `instructions`, `tools`, `skills`, `policy`, `backend`, `sub_agents`, `max_depth`, `loop`, and `strip_thinking`.

**R1.2** `Agent.run(query, messages, instructions, stream, trace, verbose)` must return `str` when `stream=False`, or `AsyncIterator[str]` when `stream=True`.

**R1.3** `Agent.add_tools(tool_or_list)` must accept a single `Tool` or a `list[Tool]`.

**R1.4** `Agent.add_skills(skill_or_list)` must accept a single `Skill` or a `list[Skill]`.

**R1.5** `Agent.from_config(path_or_dict)` must support YAML/JSON config loading.

**R1.6** `Agent.to_config()` must return a serialization-friendly dict.

### R2 — LLM Model Configuration

`LLMModel` is a pure Pydantic value object describing the LLM endpoint.

**R2.1** Fields: `provider`, `model_name`, `base_url`, `api_key`, `max_context`, `temperature`, `system_prompt`.

**R2.2** `system_prompt` lives on `LLMModel` because different models interpret prompts differently.

**R2.3** `LLMModel` must not perform I/O, database lookups, or have `.save()` / `.load()` methods.

### R3 — Tool Framework

**R3.1** `@tool` decorator must convert a function into a `Tool` dataclass instance.

**R3.2** `Tool` must support `to_config()`, `to_bundle()`, and `invoke(**kwargs)`.

**R3.3** The SDK must not provide tool storage, backends, ORM models, or singleton registries.

**R3.4** Memory-dependent tools (remember, recall, etc.) are out of scope and removed.

### R4 — Skill Framework

**R4.1** `Skill` is a Pydantic/dataclass value object with fields: `name`, `description`, `category`, `instructions`, `tools`, `dependencies`, `source`, `metadata`, `is_active`, `version`.

**R4.2** `Skill.from_markdown(text)` must parse a skill definition from a Markdown string. The consumer decides how to obtain the string (file read, DB query, inline, etc.).

**R4.3** `SkillRegistry` must be non-singleton, instantiated explicitly by the consumer. No filesystem I/O.

**R4.4** The SDK must not provide skill storage backends, ORM models, or directory scanners.

### R5 — Configuration System

**R5.1** `AgentConfig`, `SDKConfig`, `LLMModel`, `BackendConfig` must support `from_dict()` / `to_dict()` for stateless deserialization.

**R5.2** `SDKConfig` contains only: `llm`, `loop`, `skills`, `backend_url`.

**R5.3** `AgentConfig` contains: `name`, `instructions`, `llm_model`, `tools`, `skills`, `policy`, `backend`, `sub_agents`, `max_depth`, `loop`, `strip_thinking`.

### R6 — Removed Modules

The following modules must be deleted entirely:
- `session/` — session management is consumer concern
- `memory/` — memory management is consumer concern
- `modeling/` — user profiling is consumer concern
- `storage/` — persistence is consumer concern
- `clients/` — HTTP clients are consumer concern
- `cli/` — CLI is a separate consumer package
- `core/registry.py` — ToolRegistry singleton is global state
- `tools/memory.py` — MemoryBackend is stateful
- `tools/memory_tools.py` — depends on memory module
- `skills/backend.py` — SkillBackend is stateful

## API Surface

### Public Exports

```python
# tinycua_sdk/__init__.py
from tinycua_sdk.agent.agent import Agent
from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.llm_model import LLMModel
from tinycua_sdk.agent.backend_kind import BackendConfig, BackendKind
from tinycua_sdk.tools.decorators import tool, Tool
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.core.config import SDKConfig

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentPolicy",
    "LLMModel",
    "BackendConfig",
    "BackendKind",
    "tool",
    "Tool",
    "Skill",
    "SDKConfig",
]
```

### Agent

```python
class Agent:
    def __init__(
        self,
        name: str = "assistant",
        instructions: str = "",
        llm_model: LLMModel = LLMModel(),
        tools: list[Tool] | None = None,
        skills: list[str] | None = None,
        policy: AgentPolicy | None = None,
        backend: BackendConfig | None = None,
        sub_agents: list[Agent] | None = None,
        max_depth: int = 3,
        loop: Any = None,
        strip_thinking: bool | list[str] | None = None,
    ) -> None: ...

    def add_tools(self, tools: Tool | list[Tool]) -> None: ...
    def add_skills(self, skills: Skill | list[Skill]) -> None: ...

    def to_config(self) -> dict[str, Any]: ...
    @classmethod
    def from_config(cls, config: str | Path | dict[str, Any]) -> Agent: ...

    async def run(
        self,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        instructions: str | None = None,
        stream: bool = False,
        trace: bool = False,
        verbose: bool = False,
    ) -> str | AsyncIterator[str]: ...
```

### LLMModel

```python
class LLMModel(BaseModel):
    provider: str = "openai-compatible"
    model_name: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: SecretStr = SecretStr("")
    max_context: int = 128_000
    temperature: float = 1.0
    system_prompt: str = "You are a helpful assistant."
```

### Tool

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    _fn: Callable | None
    _source: str | None
    _external_dependencies: list[str]
    _tool_dependencies: list[dict[str, Any]]
    _version: str | None

    def to_config(self) -> dict[str, Any]: ...
    def to_bundle(self) -> dict[str, Any]: ...
    def invoke(self, **kwargs: Any) -> Any: ...
```

### Skill

```python
@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    version: str = "1.0.0"

    @classmethod
    def from_markdown(cls, text: str) -> Skill:
        """Parse skill from Markdown text."""
        ...
```

## Examples

### Basic Agent
```python
from tinycua_sdk import Agent, LLMModel, tool

@tool
def search(query: str) -> str:
    return f"Results for {query}"

agent = Agent(
    llm_model=LLMModel(
        base_url="http://localhost:1234/v1",
        model_name="qwen3.5-9b",
        system_prompt="You are a research assistant.",
    ),
    instructions="Answer questions concisely using available tools.",
)
agent.add_tools(search)

response = await agent.run("What is quantum computing?")
print(response)
```

### Config-Based Agent
```python
# agent.yaml
name: researcher
instructions: Answer questions concisely using available tools.
llm_model:
  provider: openai-compatible
  model_name: qwen3.5-9b
  base_url: http://localhost:1234/v1
  system_prompt: You are a research assistant.
tools:
  - search
  - summarize

# main.py
agent = Agent.from_config("agent.yaml")
response = await agent.run("Explain quantum computing")
```

### Streaming
```python
async for chunk in await agent.run("Tell me a story", stream=True):
    print(chunk, end="")
```

### With Skills (Programmatic)
```python
from tinycua_sdk import Agent, LLMModel, Skill

coder = Skill(
    name="coder",
    instructions="Write clean, efficient code.",
    tools=["read_file", "write_file"],
)

agent = Agent(llm_model=LLMModel())
agent.add_skills(coder)
```

### With Skills (From Markdown)
```python
from tinycua_sdk import Agent, LLMModel, Skill

# Consumer decides how to obtain the markdown text
skill_md = """
---
name: coder
category: development
tools:
  - read_file
  - write_file
---

# Coder

## Description
Write clean, efficient code.

## Instructions
When asked to write code, plan first, then implement.
"""

coder = Skill.from_markdown(skill_md)
agent = Agent(llm_model=LLMModel())
agent.add_skills(coder)
```

### With Skills (Consumer loads from file)
```python
from tinycua_sdk import Agent, LLMModel, Skill

# Consumer handles filesystem access
with open("./skills/coder.md") as f:
    coder = Skill.from_markdown(f.read())

agent = Agent(llm_model=LLMModel())
agent.add_skills(coder)
```

## Acceptance Criteria

- [ ] All modules in "Removed Modules" list are deleted.
- [ ] `Agent` is fully runnable with `run()`, `add_tools()`, `add_skills()`, `from_config()`.
- [ ] `Agent` constructor does not accept `system_prompt`, `session_id`, `short_term_memory`, `long_term_memory`, `planning_prompt`, `model`, `provider`, `base_url`, `api_key`, `mode`, `backend_url`.
- [ ] `LLMModel` contains `system_prompt` and is a pure value object.
- [ ] `ToolRegistry` singleton is deleted.
- [ ] `SkillRegistry` is non-singleton.
- [ ] `SDKConfig` contains only `llm`, `loop`, `skills`, `backend_url`.
- [ ] All config classes support `from_dict()` / `to_dict()`.
- [ ] Examples in `docs/examples/` are stateless and runnable.
- [ ] `pytest` suite passes after deleting obsolete tests.
