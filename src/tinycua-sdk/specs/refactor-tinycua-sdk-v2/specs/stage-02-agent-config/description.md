# Stage 2: Agent Configuration & Creation — Description

## Purpose
Enable `Agent` instantiation with the v2 constructor shape. The agent can be configured with all parameters (name, instructions, model, tools, skills, policy, metadata) but cannot yet execute. This stage establishes the config model and public API surface.

## What You'll Find Here
- **`spec.md`** — Requirements for `AgentPolicy`, `AgentConfig`, and the `Agent` constructor signature. Includes 8 success criteria covering minimal creation, named agents, policy settings, metadata, obsolete parameter rejection, dynamic composition, config serialization, and integration tests.
- **`design.md`** — Implementation plan: collapsing `AgentDefinition` into `AgentConfig`, property proxies on `Agent`, obsolete parameter rejection logic, and the new constructor flow.

## What This Stage Does NOT Do
- It does not implement `agent.run()` or LLM calling — that's Stage 3.
- It does not handle serialization to JSON/YAML files — that's Stage 6.
- It does not wire up tools or skills for execution — only storage and access.

## How to Use These Files
1. Read `spec.md` to understand the exact constructor signature and config shape.
2. Implement using `design.md`, but write integration tests first.
3. Verify obsolete parameter rejection carefully — this is the primary migration signal for consumers upgrading from v1.

## Targets (Test Scenarios)
This stage includes 7 atomic test scenarios in `targets/`:
- **01_minimal_agent.py** — Create a minimal Agent with no arguments
- **02_named_agent.py** — Create a named agent with custom instructions and model
- **03_agent_with_policy.py** — Create an agent with custom policy settings
- **04_agent_with_metadata.py** — Create an agent with consumer-defined metadata
- **05_obsolete_params_rejected.py** — Verify obsolete parameters raise TypeError
- **06_dynamic_composition.py** — Verify tools and skills can be added after creation
- **07_to_config.py** — Verify to_config() captures all fields

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

> **Important:** These targets are **MUST-HAVE** requirements for this stage. However, you should write additional integration tests during development as needed. The targets represent the minimum coverage; you may add more tests to ensure robustness.

## Dependencies
- Depends on: Stage 0 (cleanup), Stage 1 (`LanguageModel` must exist).
- Feeds into: Stages 3–9 (all execution stages depend on a working `Agent` constructor).
