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

## Dependencies
- Depends on: Stage 0 (cleanup), Stage 1 (`LanguageModel` must exist).
- Feeds into: Stages 3–9 (all execution stages depend on a working `Agent` constructor).
