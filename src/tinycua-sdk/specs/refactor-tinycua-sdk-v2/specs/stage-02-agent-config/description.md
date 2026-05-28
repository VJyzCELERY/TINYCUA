# Stage 2: Agent Configuration & Creation — Description

## Purpose
Enable `Agent` instantiation with the constructor. The agent can be configured with all parameters (name, instructions, model, tools, skills, policy, metadata) but cannot yet execute. This stage establishes the config model and public API surface.

## What You'll Find Here
- **`spec.md`** — Requirements for `AgentPolicy`, `AgentConfig`, and the `Agent` constructor signature. Includes 7 success criteria covering minimal creation, named agents, policy settings, metadata, dynamic composition, config serialization, and integration tests.
- **`design.md`** — Implementation plan: collapsing `AgentDefinition` into `AgentConfig`, property proxies on `Agent`, and the constructor flow.

## What This Stage Does NOT Do
- It does not provide LLM execution or streaming — those come in Stages 3 and 5.
- It does not implement directory loading or file serialization — that's Stage 6.

## How to Use These Files
1. Read `spec.md` for the full list of requirements.
2. Use `design.md` as an implementation reference, but write tests first.
3. Verify the constructor is clean — no backward-compatibility validation or dead parameter references.

## Targets (Test Scenarios)
This stage includes 7 atomic test scenarios in `targets/`:
- **01_minimal_agent.py** — Create a minimal Agent with no arguments
- **02_named_agent.py** — Create a named agent with custom instructions and model
- **03_agent_with_policy.py** — Create an agent with custom policy settings
- **04_agent_with_metadata.py** — Create an agent with consumer-defined metadata
Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

> **Important:** These targets are **MUST-HAVE** requirements for this stage. However, you should write additional integration tests during development as needed. The targets represent the minimum coverage; you may add more tests to ensure robustness.

## Dependencies
- Depends on: Stage 0 (cleanup), Stage 1 (`LanguageModel` must exist).
- Feeds into: Stages 3–9 (all execution stages depend on a working `Agent` constructor).
