# Agent Rules

This document defines the core principles and general rules for AI agents working in any project built from this template.

---

## Core Principles

### 1. Simplicity First

If the solution feels complex, it is. Break it down.

- Prefer simple solutions over clever ones
- Inline single-use helpers instead of extracting them
- Avoid premature abstraction
- Question every layer of indirection
- If you can't explain it simply, it's too complex

### 2. Test-First

Write failing tests before implementation. No exceptions.

- Unit tests must exist for all new logic
- Integration tests for workflows and APIs
- Tests validate the spec, not just the code
- Coverage is a side effect, not the goal

### 3. Question the Spec

During review, challenge assumptions. Specs can be wrong.

- Does the spec make sense?
- Are there gaps or contradictions?
- Is the proposed solution minimal?
- Flag spec issues early — do not blindly implement

### 4. No Overengineering

Flag unnecessary complexity, premature optimization, and gold-plating.

- Implement only what is in the spec
- Avoid "flexibility" that is not needed yet
- Simple code is maintainable code
- Do not add features not requested

---

## General Agent Rules

- **Responsible Use**: AI agents must be used to assist, not replace, developer judgment.
- **Document AI Contributions**: Clearly indicate which parts of the codebase were AI-assisted.
- **Task Scoping**: Define specific, bounded tasks for AI agents. Avoid open-ended instructions.
- **Review All Output**: All AI-generated code must be reviewed by a human before merging.
- **Follow Project Standards**: AI agents must produce code that passes `make lint`, `make test`, and `make complexity` before output is considered complete.
- **No Secrets in Output**: AI must never generate code that contains hardcoded secrets, credentials, or API keys.

---

## Agent Behavior During Code Generation

- Read the relevant spec file before generating code
- Generate the minimum code that satisfies the spec
- Include docstrings for all functions and classes
- Include corresponding tests alongside generated code
- Follow naming conventions in `docs/project_rules/naming_conventions.md`
- Follow coding standards in `docs/project_rules/coding_standards.md`

---

## References

- `docs/agents/workflow.md` — development commands and commit guidelines
- `docs/agents/style.md` — code style enforcement rules
- `docs/agents/testing.md` — test organization and naming
- `docs/agents/code_review.md` — review standards and severity levels
- `docs/project_rules/coding_standards.md` — full coding standards
- `docs/project_rules/cognitive_complexity.md` — complexity limits
