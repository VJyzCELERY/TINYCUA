# Implementation: TINYCUA SDK Cookbook

Provide a comprehensive, linearly-structured cookbook of 19 Markdown guides organized into six phase folders under `src/tinycua-sdk/docs/cookbook/`. Each page teaches a specific SDK capability with self-contained, runnable code examples supporting both local (LM Studio) and remote (OpenAI) provider patterns.

## Context

- **Spec Reference**: [spec.md](./spec.md)
- **Design Reference**: [design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: L (19 pages across 6 phases + index + README update + validation)

## Environment Pre-requisites

**N/A** — This feature has no configuration, services, data, or access dependencies.

### Developer Tooling

- [ ] **Runtime**: Python 3.12+
- [ ] **Package manager**: uv (already configured in `src/tinycua-sdk/pyproject.toml`)
- [ ] **Linting**: markdownlint or equivalent (for validation script)

---

## Success Criteria — Integration Tests (TDD First)

The tests prove that the cookbook meets all structural and content requirements. They are written FIRST — before any cookbook page content. Implementation is only complete when these tests pass.

The validation suite consists of a single Python script at `src/tinycua-sdk/tests/test_cookbook_structure.py`.

```python
# Test file: src/tinycua-sdk/tests/test_cookbook_structure.py
"""Structural validation tests for the SDK cookbook.

These tests verify that all cookbook files exist, follow naming conventions,
have valid links, contain valid Python snippets, and avoid hardcoded secrets.
"""

import ast
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

import pytest

COOKBOOK_ROOT = Path(__file__).resolve().parent.parent / "docs" / "cookbook"

EXPECTED_PAGES: dict[str, list[str]] = {
    "onboarding": [
        "installation-and-setup.md",
        "your-first-agent.md",
        "agent-configuration.md",
    ],
    "core-concepts": [
        "language-models-and-providers.md",
        "streaming-responses.md",
        "file-attachments.md",
        "multimodal-content.md",
    ],
    "agent-extensions": [
        "creating-tools.md",
        "skills-and-skill-registry.md",
        "tool-permissions-and-approval.md",
    ],
    "advanced-file-handling": [
        "streaming-file-uploads.md",
        "upload-cache-and-persistence.md",
        "tool-results-with-files.md",
    ],
    "provider-deep-dives": [
        "chat-completions-provider.md",
        "responses-provider.md",
        "custom-providers.md",
    ],
    "execution-and-reference": [
        "custom-execution-loops.md",
        "canonical-stream-events.md",
        "error-handling.md",
    ],
}

TOTAL_PAGES = sum(len(pages) for pages in EXPECTED_PAGES.values())

def _find_project_root(start: Path) -> Path:
    for parent in start.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("Could not find project root (no pyproject.toml found in ancestors)")


_PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
_TMP_DIR = _PROJECT_ROOT / "tmp"
_IMPORT_PATTERN = re.compile(r"^\s*(import |from \w)", re.MULTILINE)


def extract_python_blocks(md_content: str) -> list[tuple[int, str]]:
    """Extract ```python ... ``` blocks with their starting line numbers."""
    blocks = []
    in_block = False
    buf: list[str] = []
    start_line = 0
    for i, line in enumerate(md_content.splitlines(), 1):
        if line.strip().startswith("```python") and not in_block:
            in_block = True
            start_line = i
            continue
        if line.strip() == "```" and in_block:
            in_block = False
            blocks.append((start_line, "\n".join(buf)))
            buf = []
            continue
        if in_block:
            buf.append(line)
    return blocks


def test_all_pages_exist():
    """All 19 expected pages must exist in their phase folders."""
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            assert page_path.is_file(), f"Page missing: {page_path}"


SECRET_PATTERNS = [
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), "OpenAI API key pattern"),
    (re.compile(r'api_key\s*=\s*"[^$"]{8,}"'), "Hardcoded non-placeholder API key"),
    (re.compile(r'Bearer\s+[a-zA-Z0-9\-_=]{20,}'), "Hardcoded Bearer token"),
]


def test_no_hardcoded_secrets():
    """No page should contain hardcoded API keys, tokens, or secrets."""
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue
            content = page_path.read_text(encoding="utf-8")
            for pattern, desc in SECRET_PATTERNS:
                match = pattern.search(content)
                assert match is None, (
                    f"Potential secret in {phase}/{page}: "
                    f"matched '{desc}' near: ...{match.group()[:40]}..."
                )


def test_standalone_snippets_run_without_errors():
    """Every standalone snippet (with its own imports) must execute cleanly."""
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    snippet_index = 0

    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue
            content = page_path.read_text(encoding="utf-8")
            for start_line, code in extract_python_blocks(content):
                if code.strip() in ("", "..."):
                    continue
                first_code_lines = [
                    l for l in code.splitlines()
                    if l.strip() and not l.strip().startswith("#")
                ]
                if not first_code_lines:
                    continue
                if not _IMPORT_PATTERN.match(first_code_lines[0]):
                    continue

                snippet_index += 1
                tmp_file = _TMP_DIR / f"_cookbook_snippet_{snippet_index}.py"
                try:
                    tmp_file.write_text(code, encoding="utf-8")
                    result = subprocess.run(
                        ["uv", "run", "python", str(tmp_file)],
                        cwd=str(_PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    assert result.returncode == 0, (
                        f"Standalone snippet in {phase}/{page} "
                        f"(line {start_line}) exited with code {result.returncode}.\n"
                        f"--- stdout ---\n{result.stdout[-2000:]}\n"
                        f"--- stderr ---\n{result.stderr[-2000:]}"
                    )
                finally:
                    if tmp_file.exists():
                        tmp_file.unlink()
```

**Design Note — LLM-calling snippets**: The `test_standalone_snippets_run_without_errors` test only executes code blocks that start with an `import`/`from` statement (line 163 filter). To avoid timeouts and auth failures, standalone import-headed snippets must stop at object construction/configuration — they must not call `agent.run()`, `agent.stream_events()`, or any other method that invokes a live LLM. Live LLM interaction examples belong in continuation blocks (code blocks without import statements at the top, which are skipped by the line 163 filter). This constraint ensures every snippet that passes the import filter executes in CI without a live API key.

The complete test suite (~479 lines, 14 test functions) is designed and will be implemented during the TDD phase. The additional tests cover: link integrity validation, naming convention enforcement, index completeness checks, Python syntax validation, continuation snippet parsing, page structure enforcement, and provider pattern coverage.

### Key Test Scenarios

- [ ] **Scenario 1 — All files exist**: All 19 pages, 6 phase directories, and `index.md` are present in the correct locations.
- [ ] **Scenario 2 — Naming conventions**: Files use descriptive-hyphenated names (no numeric prefixes). Reading order is defined by `index.md`.
- [ ] **Scenario 3 — Index completeness**: `index.md` lists every page, and every linked page exists. No broken links to non-existent pages.
- [ ] **Scenario 4 — Code snippet integrity**: All ` ```python ` blocks are syntactically valid Python 3.12+. Every page has at least one code block.
- [ ] **Scenario 5 — Standalone snippets run cleanly**: Every snippet with its own `import`/`from` statements is extracted to a temp `.py` file and executed via `subprocess`. Exit code must be 0. Temp files are cleaned up after each run.
- [ ] **Scenario 6 — No secrets**: No hardcoded API keys, tokens, or credentials. All secrets use environment variables.
- [ ] **Scenario 7 — Page structure**: Every page has a title (H1), Overview section, Common Pitfalls section, and Next Steps section as defined in the design template.
- [ ] **Scenario 8 — Provider patterns**: Provider-related pages with explicit provider interaction demonstrate both local (LM Studio) and remote (OpenAI) configurations.
- [ ] **Edge case — No broken internal links**: All relative Markdown links within the cookbook resolve to existing pages or `index.md`.

## Verification Plan

### Automated Tests

- [ ] Integration tests (defined above) — these must pass for implementation to be complete
- [ ] **TDD Phase**: Write `test_cookbook_structure.py` first, confirm it fails (RED) since no files exist
- [ ] **Structure Phase**: Create directories + stub files, confirm structural tests pass, content tests still fail
- [ ] **Content Phase**: Fill in content page by page, re-running tests to confirm each page passes (including runtime snippet execution)
- [ ] **Final Suite**: Full test suite passes (all GREEN) — no regressions: `cd src/tinycua-sdk && uv run pytest tests/test_cookbook_structure.py`

### Manual Verification

- [ ] **Linear reading experience**: Reviewer reads pages 01–19 in order (as defined by `index.md`) and confirms no concept is used before it is introduced.
- [ ] **Self-containment**: Reviewer jumps to a random page, reads only that page, and confirms they can follow and run the example without reading other pages.
- [ ] **Cross-page link integrity**: All "Prerequisites" and "Next Steps" links are manually verified to point to correct pages.
- [ ] **Dual provider verification**: Both local (LM Studio) and remote (OpenAI) paths are tested with actual running instances (the automated runtime test uses page design constraints — standalone import-headed snippets stop at construction; live LLM interactions use continuation blocks skipped by the import filter).

### Performance Considerations

- **N/A** — This is a documentation project with no runtime performance requirements.

## Proposed Changes

### Phase 0 — Scaffolding & Index

#### [NEW] `src/tinycua-sdk/docs/cookbook/`

- **Description**: Root directory for the cookbook. Contains `index.md` and six phase subdirectories.
- **Dependencies**: None (leaf-level documentation directory)

#### [NEW] `src/tinycua-sdk/docs/cookbook/index.md`

- **Description**: Table of contents listing all 19 pages in reading order, organized by phase folder. Each entry includes a one-line description of what the page teaches.
- **Rationale**: Serves as the primary navigation entry point and defines the linear reading order (FR-007, FR-001).

#### [NEW] Phase directories (6 total)

- **Description**: `onboarding/`, `core-concepts/`, `agent-extensions/`, `advanced-file-handling/`, `provider-deep-dives/`, `execution-and-reference/`
- **Rationale**: Folder-based organization groups related topics and makes the progression skimable (FR-001).

### Phase 1 — Onboarding (3 pages)

#### [NEW] `src/tinycua-sdk/docs/cookbook/onboarding/installation-and-setup.md`

- **Description**: pip/uv install, environment variables (`LLM_MODEL`, `OPENAI_API_KEY`, etc.), verify installation, `.env` file setup.
- **Covered API**: None (setup only)

#### [NEW] `src/tinycua-sdk/docs/cookbook/onboarding/your-first-agent.md`

- **Description**: Import `Agent`, create with name/instructions, call `run()`, print response.
- **Covered API**: `Agent(name, instructions)`, `Agent.run()`

#### [NEW] `src/tinycua-sdk/docs/cookbook/onboarding/agent-configuration.md`

- **Description**: `AgentConfig`, `AgentPolicy`, all config fields, `from_config`/`to_config`, serialization to JSON/YAML, `from_json_file`/`from_yaml_file`.
- **Covered API**: `AgentConfig`, `AgentPolicy`

### Phase 2 — Core Concepts (4 pages)

#### [NEW] `src/tinycua-sdk/docs/cookbook/core-concepts/language-models-and-providers.md`

- **Description**: `LanguageModel` fields, model resolution, provider selection, local vs remote, `to_dict`/`from_dict`, `api_key` env expansion.
- **Covered API**: `LanguageModel`

#### [NEW] `src/tinycua-sdk/docs/cookbook/core-concepts/streaming-responses.md`

- **Description**: `stream=True`, async iteration, event types, content accumulation, cancellation, `Agent.stream_events()`.
- **Covered API**: `Agent.stream_events()`, event types from `tinycua_sdk.agent.events`

#### [NEW] `src/tinycua-sdk/docs/cookbook/core-concepts/file-attachments.md`

- **Description**: `FileAttachment.from_path`, `from_bytes`, `from_url`, `file_id` reference, passing to `agent.run(file_attachments=[...])`.
- **Covered API**: `FileAttachment`, `Agent.run(file_attachments=...)`

#### [NEW] `src/tinycua-sdk/docs/cookbook/core-concepts/multimodal-content.md`

- **Description**: `ContentPart` text/file types, building multimodal queries, mixing text and images, provider behavior differences.
- **Covered API**: `ContentPart`

### Phase 3 — Agent Extensions (3 pages)

#### [NEW] `src/tinycua-sdk/docs/cookbook/agent-extensions/creating-tools.md`

- **Description**: `@tool` decorator (bare and parameterized), `Tool.from_callable`, docstring parsing, JSON Schema generation, `Tool.from_dict`, `load_directory`.
- **Covered API**: `Tool`, `tool` (decorator)

#### [NEW] `src/tinycua-sdk/docs/cookbook/agent-extensions/skills-and-skill-registry.md`

- **Description**: `Skill` model, `Skill.from_directory`, `SKILL.md` format, `SkillRegistry`, `agent.add_skills`, how skills appear in system prompt.
- **Covered API**: `Skill`, `SkillRegistry`

#### [NEW] `src/tinycua-sdk/docs/cookbook/agent-extensions/tool-permissions-and-approval.md`

- **Description**: `tool_permissions` map (`allow`/`ask`/`deny`), `ApprovalWorkflow` ABC, `DefaultApprovalWorkflow`, custom workflow example, multi-workflow chaining.
- **Covered API**: `Agent(tool_permissions=...)`, `ApprovalWorkflow` (internal)

### Phase 4 — Advanced File Handling (3 pages)

#### [NEW] `src/tinycua-sdk/docs/cookbook/advanced-file-handling/streaming-file-uploads.md`

- **Description**: `FileAttachment.from_path(stream=True)`, `StreamingFileAttachment`, `iter_base64_chunks`, `hash_content`, when to use vs memory-backed.
- **Covered API**: `StreamingFileAttachment`

#### [NEW] `src/tinycua-sdk/docs/cookbook/advanced-file-handling/upload-cache-and-persistence.md`

- **Description**: `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`, `upload_timeout`, `PersistentCacheStore`, `InFlightTracker`.
- **Covered API**: `Agent(upload_cache=...)`, internal cache store APIs

#### [NEW] `src/tinycua-sdk/docs/cookbook/advanced-file-handling/tool-results-with-files.md`

- **Description**: Tools returning dicts with `content` + `attachments`, multipart content shapes, tool result normalization, provider behavior for tool-result files.
- **Covered API**: Tool return types, `FileAttachment`

### Phase 5 — Provider Deep Dives (3 pages)

#### [NEW] `src/tinycua-sdk/docs/cookbook/provider-deep-dives/chat-completions-provider.md`

- **Description**: `OpenAIChatCompletionsClient`, message translation (ContentPart → image_url/file parts), tool-result synthetic user messages, supported/unsupported fields, error handling.
- **Covered API**: `OpenAIChatCompletionsClient` (internal), `LanguageModel(provider="openai-chat-completions")`

#### [NEW] `src/tinycua-sdk/docs/cookbook/provider-deep-dives/responses-provider.md`

- **Description**: `OpenAIResponsesClient`, input_image/input_file/input_text translation, function_call_output handling, stateful conversations via `_previous_response_id`, field support matrix.
- **Covered API**: `OpenAIResponsesClient` (internal), `LanguageModel(provider="openai-responses")`

#### [NEW] `src/tinycua-sdk/docs/cookbook/provider-deep-dives/custom-providers.md`

- **Description**: `ProviderRegistry.register`, `LLMClient` ABC, implementing `_chat_impl`, `close`, `ProviderFactory` protocol, provider alias resolution, `normalize_base_url`.
- **Covered API**: `LLMClient`, `ProviderRegistry` (internal)

### Phase 6 — Execution & Reference (3 pages)

#### [NEW] `src/tinycua-sdk/docs/cookbook/execution-and-reference/custom-execution-loops.md`

- **Description**: `BaseLoop` internals, `build_system_message`, `_run_sync` vs `_run_stream`, `process_tool_calls`, `last_assistant_content`, overriding `max_iterations`, creating custom loops.
- **Covered API**: `BaseLoop`, `AgentExecutor`

#### [NEW] `src/tinycua-sdk/docs/cookbook/execution-and-reference/canonical-stream-events.md`

- **Description**: Complete reference of all 15 event types, tool call state machine diagram, event ordering guarantees, `LLMResponse` structure, `TokenUsage`, `ToolCallDict`.
- **Covered API**: All 15 canonical events, `LLMResponse`, `LLMMessage`, `AssistantMessage`

#### [NEW] `src/tinycua-sdk/docs/cookbook/execution-and-reference/error-handling.md`

- **Description**: `ProviderApiError`, `ProviderAuthError`, `ProviderNotSupportedError`, try/except patterns, retry with tenacity, cancellation handling.
- **Covered API**: `ProviderApiError`, `ProviderAuthError`, `ProviderNotSupportedError`

### Phase 7 — README Update

#### [MODIFY] `src/tinycua-sdk/README.md`

- **Description**: Add a link to the cookbook (`docs/cookbook/index.md`) from the README so new developers discover the guided learning path.
- **Breaking changes**: None

### Test File

#### [NEW] `src/tinycua-sdk/tests/test_cookbook_structure.py`

- **Description**: Structural validation test suite (see Success Criteria above). Written first during TDD phase.
- **Dependencies**: pytest (already in dev dependencies)

## Architecture Changes

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `src/tinycua-sdk/docs/cookbook/` | New | Root cookbook directory with `index.md` and 6 phase subdirectories |
| `src/tinycua-sdk/docs/cookbook/index.md` | New | Table of contents defining linear reading order |
| `src/tinycua-sdk/docs/cookbook/onboarding/` | New | 3 pages — setup, first agent, configuration |
| `src/tinycua-sdk/docs/cookbook/core-concepts/` | New | 4 pages — models, streaming, files, multimodal |
| `src/tinycua-sdk/docs/cookbook/agent-extensions/` | New | 3 pages — tools, skills, permissions |
| `src/tinycua-sdk/docs/cookbook/advanced-file-handling/` | New | 3 pages — streaming uploads, cache, tool results |
| `src/tinycua-sdk/docs/cookbook/provider-deep-dives/` | New | 3 pages — chat, responses, custom providers |
| `src/tinycua-sdk/docs/cookbook/execution-and-reference/` | New | 3 pages — loops, events, error handling |
| `src/tinycua-sdk/README.md` | Modify | Add cookbook link |
| `src/tinycua-sdk/tests/test_cookbook_structure.py` | New | Structural validation test suite |

No source code changes. This is a documentation-only addition.

## Data Model Changes

**N/A** — No data model changes. Pages are static Markdown files.

## API Changes

**N/A** — No API changes.

## Dependencies

### External Dependencies

**N/A** — No new external dependencies. The validation script uses only `pytest`, `ast`, `subprocess`, `tempfile` (all stdlib). Snippet runtime tests require `tinycua-sdk` to be installed in the dev environment (already satisfied via `pyproject.toml` dev dependencies).

### Internal Dependencies

- [ ] Depends on **tinycua-sdk public API stability**: Code snippets must reference the current API surface. Any API changes after cookbook pages are written must update affected pages.
- [ ] Blocks **nothing** — This is a documentation addition with no downstream code dependencies.

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Code snippets go stale as SDK API evolves | Medium | Medium | Snippets use only public, stable APIs. Runtime snippet tests catch import errors and API mismatches at CI time. When API changes, update affected pages as part of the same PR that changes the API. |
| Cookbook grows beyond ~20 pages (scope creep) | Low | Medium | Cap at 19 pages. New features get appended only if they introduce a genuinely new concept. Variations go in existing pages. |
| Snippet won't run due to missing dependency or API mismatch | Low | High | Automated runtime snippet runner executes every standalone block via subprocess — catches import errors, missing attributes, and signature mismatches before merge. Continuation snippets are at least syntax-validated. |
| Linear ordering becomes wrong as SDK evolves | Low | Low | `index.md` defines the order, not filenames. Pages can be reordered by updating `index.md` without renaming files. The dependency graph in design.md serves as the source of truth. |
| Different provider patterns confuse beginners | Medium | Medium | `language-models-and-providers.md` explicitly teaches the two paths. Later pages show both patterns briefly and refer back for full explanation. |
| Cross-page links break when pages are renamed | Low | Low | Validation tests catch broken links. Renames are coordinated with link updates in the same commit. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-28*
