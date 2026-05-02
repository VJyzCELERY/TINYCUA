# Stage 1: Core Value Objects — Specification

## Objective
Implement the three pure value objects that have no I/O dependencies: `LanguageModel`, `Tool`, and `Skill`.

These objects are immutable configuration containers. They do not make network calls, do not depend on each other, and can be instantiated and tested in complete isolation.

## Guiding Principles
All stages adhere to the principles defined in [`ROADMAP.md#principles`](../../docs/ROADMAP.md#principles).

## References
- [`goals/getting-started/01_language_model_definition.py`](../goals/getting-started/01_language_model_definition.py)
- [`goals/intermediate/01_tool_creation.py`](../goals/intermediate/01_tool_creation.py)
- [`goals/intermediate/02_skills_creation.py`](../goals/intermediate/02_skills_creation.py)

## Requirements

### R-1.1: LanguageModel (rename from LLMModel)

**Rename** the existing `LLMModel` class to `LanguageModel` in `agent/llm_model.py`.

**Required fields with defaults:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `str` | `"openai-compatible"` | Provider identifier. |
| `model_name` | `str` | `"gpt-4o-mini"` | Model identifier string. |
| `base_url` | `str \| None` | `None` | Custom endpoint URL (e.g., LM Studio). |
| `api_key` | `SecretStr` | `SecretStr("")` | API key, supports env-var substitution. |
| `temperature` | `float` | `1.0` | Sampling temperature. |
| `max_tokens` | `int \| None` | `None` | Max output tokens. |
| `top_p` | `float` | `1.0` | Nucleus sampling. |
| `frequency_penalty` | `float` | `0.0` | Frequency penalty. |
| `presence_penalty` | `float` | `0.0` | Presence penalty. |
| `stop` | `str \| list[str] \| None` | `None` | Stop sequences. |
| `seed` | `int \| None` | `None` | Determinism seed. |
| `response_format` | `dict \| None` | `None` | Structured output schema. |
| `tool_choice` | `str \| dict \| None` | `None` | Tool selection control. |
| `logprobs` | `bool` | `False` | Return logprobs. |
| `top_logprobs` | `int \| None` | `None` | Number of top logprobs. |
| `user` | `str \| None` | `None` | End-user identifier. |
| `system_prompt` | `str` | `"You are a helpful assistant."` | Default system prompt. |
| `strip_thinking` | `bool` | `False` | Strip reasoning tags from responses. |
| `max_context` | `int` | `128_000` | Context window size hint. |

**Serialization methods:**
- `to_dict() -> dict[str, Any]` — plain dict. Optional fields with `None` should be excluded.
- `to_json() -> str` — JSON string.
- `from_dict(data: dict) -> LanguageModel` — classmethod constructor.
- `from_json(data: str) -> LanguageModel` — classmethod constructor.

**Env-var substitution:**
- When `api_key` is passed as a string containing `${VAR_NAME}`, resolve it from `os.environ` before wrapping in `SecretStr`.
- If the env var is not set, keep the literal string.

**Immutability:**
- Frozen Pydantic model (`ConfigDict(frozen=True)`).

### R-1.2: Tool / @tool

**`Tool` class:**
- `name: str`
- `description: str`
- `parameters: dict` — JSON Schema object
- `_callable: Callable | None` — underlying function
- `dependencies: list[str] = []` — optional package dependencies metadata

**Methods:**
- `to_config() -> dict` — returns OpenAI function-calling schema:
  ```python
  {
      "type": "function",
      "function": {
          "name": self.name,
          "description": self.description,
          "parameters": self.parameters,
      }
  }
  ```
- `invoke(**kwargs) -> Any` — calls `_callable` with kwargs. Raises `RuntimeError` if `_callable` is None.

**`@tool` decorator:**
- Applied to a function.
- Inspects function signature using `inspect.signature()`.
- Parses docstring for parameter descriptions (Google-style `Args:` section).
- Generates JSON Schema `properties` and `required` arrays.
- Wraps function in a `Tool` instance.
- The decorated function name becomes `Tool.name`.
- The function docstring (first line) becomes `Tool.description`.
- Supports `@tool(dependencies=["requests"])` syntax.

**Supported type mappings:**
- `str` → `"string"`
- `int` / `float` → `"number"`
- `bool` → `"boolean"`
- `list[T]` → `"array"` with `items`
- `dict` → `"object"`
- `Any` / unannotated → omitted (allows any)

### R-1.3: Skill

**Fields:**
- `name: str`
- `description: str`
- `instructions: str`
- `metadata: dict = {}`

**Methods:**
- `to_dict() -> dict`
- `from_dict(data: dict) -> Skill` — classmethod

**`SkillRegistry`:**
- `register(skill: Skill) -> None`
- `list_skills() -> list[Skill]`
- `get(name: str) -> Skill | None`
- Duplicate name registration overwrites previous entry.

## Success Criteria

Each success criterion must be validated by running the specified target file(s).

Format: [ ] Success Criteria Description - Target File(s) - Expected Output - How to validate

- [ ] LanguageModel Creation and Access - tests/integration/goals/test_gs_01_language_model_definition.py - PASS - `print('PASS')`
  Description: All creation patterns from the goal script work.

- [ ] LanguageModel Serialization Round-Trip - N/A - PASS - `print('PASS')`
  Description: `to_dict` / `from_dict` round-trip preserves all data.

- [ ] @tool Schema Generation - tests/integration/goals/test_int_01_tool_creation.py - PASS - `print('PASS')`
  Description: `@tool` decorator produces correct OpenAI function schema.

- [ ] Tool.invoke Works - tests/integration/goals/test_int_01_tool_creation.py - PASS - `print('PASS')`
  Description: Calling `tool.invoke()` executes the underlying function.

- [ ] SkillRegistry Operations - N/A - PASS - `print('PASS')`
  Description: Register, list, and lookup skills.

- [ ] Integration Tests Pass - tests/integration/goals/test_gs_01_language_model_definition.py, tests/integration/goals/test_int_01_tool_creation.py, tests/integration/goals/test_int_02_skills_creation.py - 3 passed, 0 failed - pytest -v

## Integration Test Files
- `tests/integration/goals/test_gs_01_language_model_definition.py`
- `tests/integration/goals/test_int_01_tool_creation.py`
- `tests/integration/goals/test_int_02_skills_creation.py`
