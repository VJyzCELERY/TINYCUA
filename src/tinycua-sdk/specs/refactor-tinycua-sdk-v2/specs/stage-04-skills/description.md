# Stage 4: Skills & Composition — Description

## Purpose
Inject skill instructions into the agent's system prompt and enable agents to use both tools and skills simultaneously. Skills are metadata-only — they provide context but never auto-resolve tools. This stage enhances the execution loop from Stage 3 with multi-skill prompt composition.

## What You'll Find Here
- **`spec.md`** — Requirements for skill prompt injection (single concatenated system message), combined tools+skills usage, and dynamic `add_skills()`. Includes 5 success criteria covering single/multiple skills, dynamic addition, combined usage, and integration tests.
- **`design.md`** — Implementation of `_build_system_message()` with skill block formatting (`[skill_name]\ninstructions`), design decisions on single vs multiple system messages, and the metadata-only philosophy.

## What This Stage Does NOT Do
- It does not implement tool auto-resolution from skills — that is explicitly out of scope.
- It does not handle loading skills from directories — that's Stage 6.
- It does not add new fields to `Skill` — only prompt injection behavior.

## How to Use These Files
1. Read `spec.md` to understand the exact system prompt format and constraints.
2. Implement using `design.md` — this is a small behavioral change to `BaseLoop._build_system_message()`.
3. Verify with integration tests that the LLM actually receives combined skill instructions (use mock client inspection).

## Targets (Test Scenarios)
This stage includes 4 atomic test scenarios in `targets/`:
- **01_single_skill.py** — Verify agent with one skill includes its instructions
- **02_multiple_skills.py** — Verify multiple skills inject instructions in registration order
- **03_dynamic_add_skills.py** — Verify skills added after creation work on next run
- **04_combined_tools_and_skills.py** — Verify agent with both tools and skills works

Each target has an accompanying `_expected-output.txt` file showing the expected output when the target passes. These targets can be directly converted into integration tests.

> **Important:** These targets are **MUST-HAVE** requirements for this stage. However, you should write additional integration tests during development as needed. The targets represent the minimum coverage; you may add more tests to ensure robustness.

## Dependencies
- Depends on: Stages 0–3 (execution loop must exist).
- Feeds into: Stage 6 (directory loading builds on this stage's prompt injection).
