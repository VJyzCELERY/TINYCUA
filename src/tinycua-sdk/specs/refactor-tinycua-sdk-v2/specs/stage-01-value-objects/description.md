# Stage 1: Core Value Objects — Description

## Purpose
Implement the three pure value objects that have no I/O dependencies: `LanguageModel`, `Tool` (with `@tool` decorator), and `Skill`. These are immutable configuration containers that can be instantiated, serialized, and tested in complete isolation.

## What You'll Find Here
- **`spec.md`** — Detailed requirements for each object's fields, methods, and behavior. Includes 6 success criteria covering creation, serialization round-trips, schema generation, invocation, registry operations, and integration tests.
- **`design.md`** — Full class implementations with code: `LanguageModel` (renamed from `LLMModel` with all OpenAI-compatible params), `Tool`/`@tool` decorator (with type mapping and docstring parsing), `Skill`, and `SkillRegistry`.

## What This Stage Does NOT Do
- It does not implement agent execution — that's Stage 3.
- It does not handle streaming, permissions, or directory loading — those are later stages.
- It does not connect to any LLM provider — these objects are pure data.

## How to Use These Files
1. Read `spec.md` to understand the exact API contract each object must satisfy.
2. Implement using `design.md` as a reference, but write integration tests first (per the Tests First principle).
3. Verify each success criterion before moving on — these objects are foundational; bugs here cascade into every later stage.

## Targets (Test Scenarios)
This stage includes 9 atomic test scenarios in `targets/`:
- **01_minimal_creation.py** — Create minimal LanguageModel with defaults
- **02_full_configuration.py** — Create LanguageModel with all OpenAI-compatible params
- **03_serialization_roundtrip.py** — Verify to_dict/from_dict round-trip preserves data
- **04_json_export_import.py** — Verify to_json/from_json round-trip
- **05_tool_schema_generation.py** — Verify @tool generates correct OpenAI schema
- **06_tool_invoke.py** — Verify @tool-decorated function can be invoked
- **07_manual_tool_construction.py** — Verify manual Tool construction works
- **08_skill_creation.py** — Verify Skill creation, to_dict, from_dict
- **09_skill_registry.py** — Verify SkillRegistry register, list, get

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

## Dependencies
- Depends on: Stage 0 (cleanup must be complete so we can rename `LLMModel` to `LanguageModel`).
- Feeds into: Stages 2–9 (all other stages depend on these value objects).
