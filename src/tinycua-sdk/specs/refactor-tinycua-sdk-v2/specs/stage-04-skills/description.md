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

## Dependencies
- Depends on: Stages 0–3 (execution loop must exist).
- Feeds into: Stage 6 (directory loading builds on this stage's prompt injection).
