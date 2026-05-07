# TINYCUA SDK Stateless Refactor — Roadmap

## Overview

This roadmap breaks the SDK refactor into **incremental, testable stages**. Each stage has its own folder under `specs/refactor-tinycua-sdk/` containing a focused specification.

## Principles

1. **Test-driven**: Each implementation stage is preceded by tests that define the target behavior.
2. **Incremental**: Stages build on each other. Earlier stages must pass before later stages begin.
3. **No regressions**: Each stage leaves the codebase in a working (test-passing) state.

---

## Stage Summary

| Stage | Code | Title | Description |
|-------|------|-------|-------------|
| 1 | `01` | Remove Legacy Tests & Examples | Delete all obsolete tests and examples for deleted modules |
| 2 | `02` | New Unit Tests | Write unit tests for the new stateless SDK API (they will fail initially) |
| 3 | `03` | Remove Session & Utils | Delete `session/` package and `utils/session.py` |
| 4 | `04` | Remove Storage | Delete `storage/` package |
| 5 | `05` | Remove Memory | Delete `memory/` package |
| 6 | `06` | Remove Modeling | Delete `modeling/` package |
| 7 | `07` | Remove CLI & Clients | Delete `cli/` and `clients/` packages |
| 8 | `08` | Remove Core Registry | Delete `core/registry.py` (ToolRegistry singleton) |
| 9 | `09` | Refactor Tools Framework | Remove `tools/memory.py`, `tools/memory_tools.py`, flatten `tools/` |
| 10 | `10` | Refactor Skills Framework | Delete `skills/backend.py`, add `Skill.load()`, make `SkillRegistry` non-singleton |
| 11 | `11` | Refactor Agent | Introduce `LLMModel`, `BackendConfig`, remove old params from `Agent` |
| 12 | `12` | Refactor Core Config | Update `SDKConfig` to framework-only concerns |
| 13 | `13` | Create Examples | Write new stateless, runnable examples |
| 14 | `14` | Create Integration Tests | Write integration tests based on working examples |

---

## Stage Dependencies

```
01-remove-legacy-tests-examples
    |
    v
02-new-unit-tests
    |
    +---> 03-remove-session
    +---> 04-remove-storage
    +---> 05-remove-memory
    +---> 06-remove-modeling
    +---> 07-remove-cli-clients
    +---> 08-remove-core-registry
    +---> 09-refactor-tools
    +---> 10-refactor-skills
    +---> 11-refactor-agent
    +---> 12-refactor-config
    |
    v
13-create-examples
    |
    v
14-create-integration-tests
```

Stages 3-12 can be done in parallel where there are no code dependencies, but the test suite (stage 2) must be in place first.

---

## Exit Criteria

After all stages complete:

- [ ] All deleted modules are gone (session, memory, modeling, storage, cli, clients, registry singleton)
- [ ] New unit tests pass
- [ ] New integration tests pass
- [ ] Examples are runnable and stateless
- [ ] `Agent` is fully usable out of the box
- [ ] No singletons, no stores, no persistence logic in SDK
- [ ] Documentation is updated

---

## Files

| File | Purpose |
|------|---------|
| `refactor-target.md` | Master analysis document with all findings and recommendations |
| `ROADMAP.md` | This file — overall stage plan |
| `01-remove-legacy-tests-examples/spec.md` | What to delete and why |
| `02-new-unit-tests/spec.md` | New test structure and success criteria |
| `03-remove-session/spec.md` | Session module removal details |
| `04-remove-storage/spec.md` | Storage module removal details |
| `05-remove-memory/spec.md` | Memory module removal details |
| `06-remove-modeling/spec.md` | Modeling module removal details |
| `07-remove-cli-clients/spec.md` | CLI and clients removal details |
| `08-remove-core-registry/spec.md` | Registry singleton removal details |
| `09-refactor-tools/spec.md` | Tools framework refactor details |
| `10-refactor-skills/spec.md` | Skills framework refactor details |
| `11-refactor-agent/spec.md` | Agent refactor details |
| `12-refactor-config/spec.md` | Core config refactor details |
| `13-create-examples/spec.md` | Example requirements |
| `14-create-integration-tests/spec.md` | Integration test requirements |
