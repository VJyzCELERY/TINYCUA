# Implementation: TINYCUA SDK Cookbook

Provide a comprehensive, linearly-structured cookbook of 19 Markdown guides organized into six phase folders under `src/tinycua-sdk/docs/cookbook/`. Each page teaches a specific SDK capability with self-contained, runnable code examples supporting both local (LM Studio) and remote (OpenAI) provider patterns.

## Context

- **Spec Reference**: [spec.md](./spec.md)
- **Design Reference**: [design.md](./design.md)
- **Priority**: P1
- **Estimated Effort**: L (19 pages across 6 phases + index + README update + validation)

## Environment Pre-requisites

**N/A** — This is a documentation-only addition. No running services, database, or special configuration is required. The validation script (written during TDD Phase) depends on Python 3.12+ and the tinycua-sdk development environment, but page content is pure Markdown.

### Developer Tooling

- **Runtime**: Python 3.12+
- **Package manager**: uv (already configured in `src/tinycua-sdk/pyproject.toml`)
- **Linting**: markdownlint or equivalent (for validation script)
- **None** — no additional tooling required

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
from pathlib import Path

import pytest

COOKBOOK_ROOT = Path(__file__).resolve().parent.parent / "docs" / "cookbook"

# Expected pages per phase (from design.md)
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


# --- Structural Tests ---

def test_cookbook_root_exists():
    """Cookbook root directory must exist."""
    assert COOKBOOK_ROOT.is_dir(), f"Cookbook root missing: {COOKBOOK_ROOT}"


def test_all_phase_directories_exist():
    """All six phase folders must exist."""
    for phase in EXPECTED_PAGES:
        phase_dir = COOKBOOK_ROOT / phase
        assert phase_dir.is_dir(), f"Phase directory missing: {phase_dir}"


def test_all_pages_exist():
    """All 19 expected pages must exist in their phase folders."""
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            assert page_path.is_file(), f"Page missing: {page_path}"


def test_no_extra_files_in_phase_dirs():
    """Phase directories should not contain unexpected files."""
    all_expected = set()
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            all_expected.add(COOKBOOK_ROOT / phase / page)

    for phase in EXPECTED_PAGES:
        phase_dir = COOKBOOK_ROOT / phase
        if not phase_dir.is_dir():
            continue
        actual_files = set(phase_dir.glob("*.md"))
        expected_in_phase = {
            COOKBOOK_ROOT / phase / p for p in EXPECTED_PAGES[phase]
        }
        unexpected = actual_files - expected_in_phase
        assert not unexpected, (
            f"Unexpected files in {phase}/: "
            f"{[f.name for f in unexpected]}"
        )


# --- Naming Convention Tests ---

def test_index_md_exists():
    """index.md must exist at the cookbook root."""
    index_path = COOKBOOK_ROOT / "index.md"
    assert index_path.is_file(), f"index.md missing: {index_path}"


def test_page_naming_convention():
    """Page filenames must use descriptive-hyphenated.md format (no numeric prefixes)."""
    pattern = re.compile(r"^[a-z][a-z0-9-]+\.md$")
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            assert pattern.match(page), (
                f"Invalid filename '{page}' in {phase}/ — "
                f"must match pattern '{pattern.pattern}'"
            )


def test_no_numeric_prefixes():
    """Filenames must not start with numbers."""
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            assert not page[0].isdigit(), (
                f"Filename '{page}' in {phase}/ has numeric prefix — "
                f"reading order is defined by index.md, not filenames"
            )


# --- Index Tests ---

def test_index_lists_all_pages():
    """index.md must contain a link to every cookbook page."""
    index_path = COOKBOOK_ROOT / "index.md"
    if not index_path.is_file():
        pytest.skip("index.md does not exist yet")

    content = index_path.read_text(encoding="utf-8")

    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            slug = page.replace(".md", "")
            # Check for relative link pattern: [text](phase/slug.md) or similar
            assert (
                f"({phase}/{page})" in content
                or f"](./{phase}/{page})" in content
                or f"(./{phase}/{page})" in content
            ), f"index.md missing link to {phase}/{page}"


def test_index_no_extra_links():
    """index.md should not link to non-existent pages."""
    index_path = COOKBOOK_ROOT / "index.md"
    if not index_path.is_file():
        pytest.skip("index.md does not exist yet")

    content = index_path.read_text(encoding="utf-8")
    # Extract all markdown links pointing to phase folders
    link_pattern = re.compile(r'\]\((\./)?([a-z-]+)/([a-z0-9-]+\.md)\)')
    all_expected_paths = set()
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            all_expected_paths.add(f"{phase}/{page}")

    for match in link_pattern.finditer(content):
        linked_path = f"{match.group(2)}/{match.group(3)}"
        assert linked_path in all_expected_paths, (
            f"index.md links to non-existent page: {linked_path}"
        )


# --- Link Integrity Tests ---

def test_no_broken_internal_links():
    """No page should contain broken relative links to other cookbook pages."""
    all_pages: set[str] = set()
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            all_pages.add(f"{phase}/{page}")

    link_pattern = re.compile(r'\]\(([^)]*\.md)\)')

    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue  # Test all_pages_exist already catches this

            content = page_path.read_text(encoding="utf-8")
            for match in link_pattern.finditer(content):
                target = match.group(1)
                # Resolve relative links
                if target.startswith("http"):
                    continue  # Skip external links
                resolved = (page_path.parent / target).resolve()
                # Convert back to relative cookbook path
                try:
                    rel = resolved.relative_to(COOKBOOK_ROOT)
                    assert rel.as_posix() in all_pages or rel.name == "index.md", (
                        f"Broken link in {phase}/{page}: "
                        f"'{target}' -> '{rel}' does not exist"
                    )
                except ValueError:
                    pass  # Link outside cookbook root — not an error


# --- Code Snippet Runtime Tests ---
#
# Strategy:
#   - Extract ```python blocks from each cookbook page.
#   - For blocks that start with `import`/`from` (standalone snippets), write
#     them to a temporary .py script and run it with subprocess.
#   - Blocks without imports are continuation snippets — they are syntax-checked
#     but NOT executed (they depend on prior blocks from the same page).
#   - Temporary scripts are written to ./tmp/ under the subproject, then
#     deleted after verification (both on success and on failure).
#
# Why runtime, not just ast.parse():
#   Syntax checking catches trivial typos but misses import errors, missing
#   attributes, API signature mismatches, and broken dependency chains. Running
#   the actual snippet proves it works against the installed SDK.

import importlib
import subprocess
import tempfile
import textwrap
from pathlib import Path

# Project root — resolved relative to this test file
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_TMP_DIR = _PROJECT_ROOT / "src" / "tinycua-sdk" / "tmp"
_IMPORT_PATTERN = re.compile(r"^\s*(import |from \w)", re.MULTILINE)


def extract_python_blocks(md_content: str) -> list[tuple[int, str]]:
    """Extract ```python ... ``` blocks with their starting line numbers.

    Returns list of (line_number_in_file, code_string) tuples.
    """
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


def test_all_pages_have_python_blocks():
    """Every cookbook page must have at least one ```python code block."""
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                pytest.skip(f"{phase}/{page} does not exist yet")

            content = page_path.read_text(encoding="utf-8")
            blocks = extract_python_blocks(content)
            assert len(blocks) > 0, (
                f"{phase}/{page} has no ```python code blocks"
            )


def test_python_snippets_are_syntactically_valid():
    """All ```python blocks must be syntactically valid Python.

    This is a fast pre-check run before the slower runtime tests.
    Catches trivial errors (missing colons, unbalanced parens) that would
    otherwise waste time spawning subprocesses.
    """
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue

            content = page_path.read_text(encoding="utf-8")
            for start_line, code in extract_python_blocks(content):
                if code.strip() in ("", "..."):
                    continue
                try:
                    ast.parse(code)
                except SyntaxError as e:
                    pytest.fail(
                        f"Syntax error in {phase}/{page} "
                        f"(line {start_line} in file): {e}"
                    )


def test_standalone_snippets_run_without_errors():
    """Every standalone snippet (with its own imports) must execute cleanly.

    A snippet is considered "standalone" if its first non-blank, non-comment
    line is `import ...` or `from ...`. Standalone snippets are written to
    temporary .py files under ./tmp/, executed with `subprocess.run`, and
    checked for exit code 0. Temporary files are deleted after each run.
    """
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

                # Only run snippets that are self-contained (have their own imports)
                first_code_lines = [l for l in code.splitlines()
                                    if l.strip() and not l.strip().startswith("#")]
                if not first_code_lines:
                    continue
                if not _IMPORT_PATTERN.match(first_code_lines[0]):
                    # Continuation snippet — skip runtime test
                    continue

                snippet_index += 1
                tmp_file = _TMP_DIR / f"_cookbook_snippet_{snippet_index}.py"
                try:
                    tmp_file.write_text(code, encoding="utf-8")
                    result = subprocess.run(
                        ["uv", "run", "python", str(tmp_file)],
                        cwd=str(_PROJECT_ROOT / "src" / "tinycua-sdk"),
                        capture_output=True,
                        text=True,
                        timeout=30,  # seconds — generous for any cookbook example
                    )
                    assert result.returncode == 0, (
                        f"Standalone snippet in {phase}/{page} "
                        f"(line {start_line}) exited with code {result.returncode}.\n"
                        f"--- stdout ---\n{result.stdout[-2000:]}\n"
                        f"--- stderr ---\n{result.stderr[-2000:]}"
                    )
                finally:
                    # Always clean up the temp file
                    if tmp_file.exists():
                        tmp_file.unlink()


def test_continuation_snippets_parse():
    """Continuation snippets (no imports) must at least parse.

    Blocks without imports are continuation snippets that depend on earlier
    blocks in the same page. We can't run them in isolation, but they must
    at least be syntactically valid Python (already checked above) and not
    be empty/placeholder garbage.
    """
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue

            content = page_path.read_text(encoding="utf-8")
            for start_line, code in extract_python_blocks(content):
                if code.strip() in ("", "..."):
                    continue

                first_code_lines = [l for l in code.splitlines()
                                    if l.strip() and not l.strip().startswith("#")]
                if not first_code_lines:
                    continue
                if _IMPORT_PATTERN.match(first_code_lines[0]):
                    continue  # Standalone — already tested above

                # Continuation block should have some content
                # (no further assertion needed — syntax check handles parse errors)


# --- Security Tests ---

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


# --- Page Structure Tests ---

REQUIRED_SECTIONS = [
    (re.compile(r"^# .+", re.MULTILINE), "Title (H1 heading)"),
    (re.compile(r"## Overview", re.MULTILINE), "Overview section"),
    (re.compile(r"## Next Steps", re.MULTILINE), "Next Steps section"),
]


def test_pages_have_required_sections():
    """Each page must have a title, Overview, and Next Steps section."""
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue

            content = page_path.read_text(encoding="utf-8")
            for pattern, desc in REQUIRED_SECTIONS:
                assert pattern.search(content), (
                    f"{phase}/{page} missing '{desc}'"
                )


# --- Provider Pattern Tests ---

PROVIDER_PHASES = {
    "onboarding", "core-concepts", "agent-extensions",
    "advanced-file-handling", "provider-deep-dives",
}


def test_provider_pages_show_both_patterns():
    """Provider-related pages must show both local (LM Studio) and remote (OpenAI) patterns."""
    for phase, pages in EXPECTED_PAGES.items():
        if phase not in PROVIDER_PHASES:
            continue
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue

            content = page_path.read_text(encoding="utf-8")
            # Check for both provider patterns
            has_local = bool(re.search(r"(1234|localhost|LM\s*Studio|lmstudio)", content, re.IGNORECASE))
            has_remote = bool(re.search(r"(openai\.com|OPENAI_API_KEY|api\.openai)", content, re.IGNORECASE))

            if not has_local:
                pytest.fail(
                    f"{phase}/{page}: missing local (LM Studio) provider pattern"
                )
            if not has_remote:
                pytest.fail(
                    f"{phase}/{page}: missing remote (OpenAI) provider pattern"
                )
```

### Key Test Scenarios

- [ ] **Scenario 1 — All files exist**: All 19 pages, 6 phase directories, and `index.md` are present in the correct locations.
- [ ] **Scenario 2 — Naming conventions**: Files use descriptive-hyphenated names (no numeric prefixes). Reading order is defined by `index.md`.
- [ ] **Scenario 3 — Index completeness**: `index.md` lists every page, and every linked page exists. No broken links to non-existent pages.
- [ ] **Scenario 4 — Code snippet integrity**: All ` ```python ` blocks are syntactically valid Python 3.12+. Every page has at least one code block.
- [ ] **Scenario 4b — Standalone snippets run cleanly**: Every snippet with its own `import`/`from` statements is extracted to a temp `.py` file and executed via `subprocess`. Exit code must be 0. Temp files are cleaned up after each run.
- [ ] **Scenario 5 — No secrets**: No hardcoded API keys, tokens, or credentials. All secrets use environment variables.
- [ ] **Scenario 6 — Page structure**: Every page has a title (H1), Overview section, and Next Steps section as defined in the design template.
- [ ] **Scenario 7 — Provider patterns**: Provider-related pages demonstrate both local (LM Studio) and remote (OpenAI) configurations.
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
- [ ] **Dual provider verification**: Both local (LM Studio) and remote (OpenAI) paths are tested with actual running instances (the automated test only checks exit code 0 for code that doesn't require a live LLM).

### Performance Considerations

- **N/A** — This is a documentation project with no runtime performance requirements.

## Proposed Changes

### Directory Structure

#### [NEW] `src/tinycua-sdk/docs/cookbook/`

- **Description**: Root directory for the cookbook. Contains `index.md` and six phase subdirectories.
- **Dependencies**: None (leaf-level documentation directory)

#### [NEW] `src/tinycua-sdk/docs/cookbook/index.md`

- **Description**: Table of contents listing all 19 pages in reading order, organized by phase folder. Each entry includes a one-line description of what the page teaches.
- **Rationale**: Serves as the primary navigation entry point and defines the linear reading order (FR-008, FR-001).

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

### README Update

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
| Different provider patterns confuse beginners | Medium | Medium | Page 04 (language-models-and-providers) explicitly teaches the two paths. Later pages show both patterns briefly and refer back to 04 for full explanation. |
| Cross-page links break when pages are renamed | Low | Low | Validation tests catch broken links. Renames are coordinated with link updates in the same commit. |

---

*Generated from spec.md and design.md*
*Last updated: 2026-05-28*
