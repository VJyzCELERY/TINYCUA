# Feature Specification: TINYCUA SDK Cookbook

**Status**: Draft
**Created**: 2026-05-28
**Last Updated**: 2026-05-28
**Subproject(s) Affected**: tinycua-sdk

---

## Problem Statement

- **Goals**: Provide a comprehensive, linearly-structured cookbook of Markdown guides with inline code snippets that teaches developers how to use all capabilities of tinycua-sdk, from basic first steps through advanced patterns.
- **Gaps**: The SDK's README.md covers only the file-attachment feature set (Phases 1–6). There is no documentation for agent creation, configuration, tools, skills, streaming, providers, security, execution loops, error handling, or the canonical event system. New developers have no guided on-ramp; advanced users have no reference for deeper features.
- **Non-Goals**: This spec does NOT cover API reference docs (auto-generated from docstrings), tutorial videos, or interactive playgrounds. It does NOT cover documentation for other subprojects (tinycua, tinycua-backend, tinycua-finetune). Cookbook examples are conceptual illustrations, not integration tests.
- **Constraints**: All cookbook pages must be valid Markdown files stored under `src/tinycua-sdk/docs/cookbook/`. Code snippets must use `python` fenced code blocks. The cookbook must assume Python 3.12+ and the dependencies declared in tinycua-sdk's `pyproject.toml`.

---

## User Scenarios & Testing

### Primary Scenario

A developer new to TINYCUA opens the cookbook, reads through pages in order as defined by `index.md`, copies code snippets, runs them locally, and progressively builds understanding from "Hello World" agent to advanced patterns like custom loops and approval workflows.

An experienced developer already using the SDK needs to reference a specific capability (e.g., streaming events, tool-result files, custom providers). They navigate to the relevant page, find a self-contained example, and copy it without needing to read preceding pages.

### Acceptance Scenarios

1. **Given** a clean Python environment with tinycua-sdk installed, **When** the reader follows the installation-and-setup page, **Then** they have a working environment with an API key configured.
2. **Given** the environment from scenario 1, **When** the reader copies the code from the your-first-agent page, **Then** the agent runs and returns a response from the configured LLM.
3. **Given** any cookbook page, **When** the reader copies a code snippet, **Then** the snippet imports only from `tinycua_sdk`, its submodules, or standard library modules listed at the top of that page.
4. **Given** all onboarding through execution-and-reference pages read in index.md order, **When** the reader finishes the cookbook, **Then** they understand all public capabilities of tinycua-sdk and can choose the right approach for their use case.

### Edge Cases

- What happens when a reader has no GPU or local LLM? The cookbook must show both local (LM Studio) and remote (OpenAI) provider configurations so either path works.
- What happens when a code snippet references a file that doesn't exist on the reader's machine? Snippets must use placeholder paths like `"path/to/your/file.png"` or generate example data inline.
- What happens with Windows vs Linux path separators? All file path examples must use forward slashes and `pathlib.Path` where possible.

---

## Requirements

### Functional Requirements

- **FR-001**: The cookbook MUST consist of multiple Markdown files under `src/tinycua-sdk/docs/cookbook/`, organized into phase-named subdirectories (e.g., `onboarding/`, `core-concepts/`). Files use descriptive hyphenated names; the linear reading order is defined by the `index.md`.
- **FR-002**: Each cookbook page MUST contain a title, brief concept overview, and at least one complete, runnable code example using fenced ````python` blocks.
- **FR-003**: Every code snippet MUST include all necessary imports at the top of the snippet or document them in the page's prerequisites section.
- **FR-004**: Provider examples MUST show patterns for both local endpoints (LM Studio at `http://localhost:1234/v1`) and remote endpoints (OpenAI API at `https://api.openai.com/v1`).
- **FR-005**: The cookbook MUST cover the following capability areas, organized into six phase folders:
  - **onboarding/** — Installation & Setup, Your First Agent, Agent Configuration
  - **core-concepts/** — Language Models & Providers, Streaming Responses, File Attachments, Multimodal Content
  - **agent-extensions/** — Creating Tools, Skills & Skill Registry, Tool Permissions & Approval
  - **advanced-file-handling/** — Streaming File Uploads, Upload Cache & Persistence, Tool Results with Files
  - **provider-deep-dives/** — Chat Completions Provider, Responses Provider, Custom Providers
  - **execution-and-reference/** — Custom Execution Loops, Canonical Stream Events, Error Handling
- **FR-006**: Each page MUST be self-contained enough that an experienced developer can read it in isolation (all imports and prerequisites stated).
- **FR-007**: The cookbook root (`docs/cookbook/`) MUST contain an `index.md` that serves as a table of contents with brief descriptions of each page.
- **FR-008**: Code snippets MUST NOT hardcode real API keys, file paths to real user data, or secrets. Use environment variables and placeholder paths.
- **FR-009**: Pages that build on concepts from earlier pages MUST include a "Prerequisites" section linking to the relevant prior pages.

### Key Entities

- **Cookbook Page**: A single Markdown file covering one capability area. Contains a title, prerequisites section, concept overview, code example(s), and common pitfalls or next steps.
- **Index Page**: The `index.md` file serving as the cookbook's root. Lists all pages in reading order with brief descriptions and links.

---

## Success Criteria

- [ ] **Reader can build first agent within 5 minutes**: The installation-and-setup and your-first-agent pages get from zero to a working agent calling an LLM.
- [ ] **All public API surfaces documented**: Every class and function in `tinycua_sdk.__all__` appears in at least one cookbook page.
- [ ] **Linear reading path complete**: Reading all 19 pages in index.md order introduces no forward references (concepts are explained before they are used).
- [ ] **Code snippets are self-contained**: Every snippet can be copied, pasted, and run (after setting environment variables) without modification.
- [ ] **Both provider patterns shown**: For provider-related features, both local (LM Studio) and remote (OpenAI) configuration patterns are demonstrated.
- [ ] **No secrets in examples**: All API keys and credentials are read from environment variables or shown as `"$API_KEY"` placeholders.

---

## Testing Plan

### Automated Tests

- Structural validation tests at `src/tinycua-sdk/tests/test_cookbook_structure.py` will verify file existence, naming conventions, index completeness, Python snippet syntax/runtime validity, page structure compliance, provider pattern coverage, and secret detection.

### Integration Tests

- Verify all code snippets against the current tinycua-sdk API by running them in a test environment.
- Verify the linear reading experience: a reviewer reads all 19 pages in index.md order and confirms no concept is used before it is introduced.
- Verify self-containment: a reviewer jumps to a random page, reads only that page, and confirms they can follow and run the example.
- Verify cross-page links (prerequisites sections, index links) are not broken.
- Confirm all files follow the naming convention of descriptive hyphenated lowercase names (e.g., `installation-and-setup.md`), with no numeric prefixes.
- Confirm `index.md` lists every page and the list matches the filesystem.
- Confirm no Markdown linting errors.

---

## Open Questions

1. **Topic ordering and completeness**
   - **Owner**: @christopher-sebastian
   - **Target**: 2026-05-28
   - **Status**: Decided
   - **Resolution**: The 19-page outline in FR-005 covers all 13 public exports plus provider internals, loop customization, events, and error handling. This is comprehensive without being exhaustive (API reference depth is out of scope).

## Review Checklist

- [x] No implementation details (no code, framework, or architecture choices)
- [x] All mandatory sections completed
- [x] No `[NEEDS CLARIFICATION]` markers remain
- [x] Requirements are testable and unambiguous
- [x] Scope is clearly bounded with explicit non-goals
- [x] Success criteria are measurable
