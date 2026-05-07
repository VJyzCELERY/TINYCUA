# Implementation: Stage 13 — Create Examples

Write new, stateless, runnable examples demonstrating the refactored SDK API.

## Context

- **Spec Reference**: spec.md — 7 example files, stateless, new API only
- **Design Reference**: design.md — detailed example code, YAML config, custom loop
- **Priority**: P1
- **Estimated Effort**: M

## Proposed Changes

### Examples Directory

#### [NEW] docs/examples/01_basic_agent.py

- **[Description]**: Basic agent with LLMModel construction and simple run()
- **[Rationale]**: Entry-point example; shows minimal SDK usage

#### [NEW] docs/examples/02_tools.py

- **[Description]**: Agent with @tool decorator, add_tools(), and tool invocation
- **[Rationale]**: Demonstrates tool integration in the refactored API

#### [NEW] docs/examples/03_skills.py

- **[Description]**: Agent with Skill.load() and add_skills()
- **[Rationale]**: Shows skill-based instructions and YAML frontmatter loading

#### [NEW] docs/examples/04_config_file.py

- **[Description]**: Agent.from_config() with YAML-based agent definition
- **[Rationale]**: Demonstrates configuration-driven agent creation

#### [NEW] docs/examples/agent.yaml

- **[Description]**: YAML config file used by 04_config_file.py
- **[Rationale]**: Provides a realistic config example for consumers

#### [NEW] docs/examples/05_streaming.py

- **[Description]**: Streaming response with stream=True and async iteration
- **[Rationale]**: Shows how to consume streaming LLM output

#### [NEW] docs/examples/06_sub_agents.py

- **[Description]**: Agent composition and sub-agent delegation
- **[Rationale]**: Demonstrates multi-agent patterns with coordinator/researcher/writer

#### [NEW] docs/examples/07_custom_loop.py

- **[Description]**: Custom ReAct loop extending BaseLoop
- **[Rationale]**: Shows consumers how to build their own loop logic; no built-in ReactLoop

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| docs/examples/ | New | 7 example scripts + 1 YAML config |

## Data Model Changes

None. Examples are documentation only.

## API Changes

None. Examples consume existing public API.

## Verification Plan

### Automated Tests

- [ ] All examples are importable (no SyntaxError, no NameError)
- [ ] Examples do not import deleted modules or singletons

### Manual Verification

- [ ] Run each example with `python docs/examples/XX_*.py` (requires LLM server for some)
- [ ] Verify all examples use new API (LLMModel, add_tools(), Skill.load(), etc.)

## Rollout Strategy

1. **Phase 1** (Create examples): Write all 7 .py files and agent.yaml
2. **Phase 2** (Verify): Run import checks and syntax validation
3. **Phase 3** (Document): Ensure examples are discoverable in docs/

## Dependencies

### Internal Dependencies

- [ ] Depends on Stage 11 (Agent refactoring)
- [ ] Depends on Stage 12 (Config refactoring)
- [ ] Blocks Stage 14 (integration tests based on examples)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SDK API not yet stable from Stage 11/12 | Medium | Verify imports against actual refactored SDK before finalizing |
| Examples fail to run due to missing LLM server | Low | Examples are documentation; add comments about server requirement |

---

*Generated from spec.md and design.md*
*Last updated: 2026-04-29*
