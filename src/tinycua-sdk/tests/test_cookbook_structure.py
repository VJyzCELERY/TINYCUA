"""Structural validation tests for the SDK cookbook.

These tests verify that all cookbook files exist, follow naming conventions,
have valid links, contain valid Python snippets, and avoid hardcoded secrets.
"""

import ast
import os
import re
import subprocess
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

# Phases that should demonstrate both local and remote provider patterns
PROVIDER_DUAL_PHASES = frozenset({
    "onboarding",
    "core-concepts",
    "provider-deep-dives",
})

# Provider-related pages that MUST show both local and remote patterns
PROVIDER_DUAL_PAGES = frozenset({
    "onboarding/installation-and-setup.md",
    "onboarding/your-first-agent.md",
    "onboarding/agent-configuration.md",
    "core-concepts/language-models-and-providers.md",
    "core-concepts/streaming-responses.md",
    "core-concepts/file-attachments.md",
    "core-concepts/multimodal-content.md",
    "provider-deep-dives/chat-completions-provider.md",
    "provider-deep-dives/responses-provider.md",
    "provider-deep-dives/custom-providers.md",
})


def _find_project_root(start: Path) -> Path:
    """Find the project root by locating pyproject.toml."""
    for parent in start.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        "Could not find project root (no pyproject.toml found in ancestors)"
    )


_PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
_TMP_DIR = _PROJECT_ROOT / "tmp"
_IMPORT_PATTERN = re.compile(r"^\s*(import |from \w)", re.MULTILINE)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_page_paths() -> list[Path]:
    """Return all expected page paths (not index.md)."""
    paths: list[Path] = []
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            paths.append(COOKBOOK_ROOT / phase / page)
    return paths


def _all_phase_dirs() -> list[Path]:
    """Return all expected phase directory paths."""
    return [COOKBOOK_ROOT / phase for phase in EXPECTED_PAGES]


def _extract_python_blocks(
    md_content: str,
) -> list[tuple[int, str]]:
    """Extract ```python ... ``` blocks with their starting line numbers."""
    blocks: list[tuple[int, str]] = []
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


def _strip_code_blocks(md_content: str) -> str:
    """Remove fenced code blocks from markdown content.

    Returns the prose-only content for heading/structure checks.
    """
    lines = md_content.splitlines()
    result: list[str] = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_block = not in_block
            continue
        if not in_block:
            result.append(line)
    return "\n".join(result)


def _extract_markdown_links(md_content: str) -> list[tuple[str, str]]:
    """Extract [text](url) links from markdown content.

    Returns list of (link_text, url) tuples.
    """
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    return [(m.group(1), m.group(2)) for m in link_pattern.finditer(md_content)]


SECRET_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "OpenAI API key pattern"),
    (re.compile(r'api_key\s*=\s*"[^$"]{8,}"'), "Hardcoded non-placeholder API key"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9\-_=]{20,}"), "Hardcoded Bearer token"),
    (re.compile(r'api_key\s*=\s*"[^$"]{8,}"'), "Hardcoded non-placeholder API key"),
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_tmp() -> None:
    """Ensure tmp directory is clean after tests."""
    yield
    if _TMP_DIR.exists():
        for f in _TMP_DIR.glob("_cookbook_snippet_*.py"):
            try:
                f.unlink()
            except OSError:
                pass


# =============================================================================
# Structural Tests — File existence
# =============================================================================


def test_all_pages_exist():
    """All 19 expected pages must exist in their phase folders."""
    missing: list[str] = []
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                missing.append(f"{phase}/{page}")
    assert not missing, f"Missing pages: {', '.join(missing)}"


def test_index_exists():
    """index.md must exist at the cookbook root."""
    index_path = COOKBOOK_ROOT / "index.md"
    assert index_path.is_file(), "index.md is missing from cookbook root"


def test_phase_dirs_exist():
    """All 6 phase directories must exist."""
    for phase_dir in _all_phase_dirs():
        assert phase_dir.is_dir(), f"Phase directory missing: {phase_dir}"


# =============================================================================
# Naming Convention Tests
# =============================================================================


def test_no_numeric_prefixes():
    """No file should have a numeric prefix like '01-' or '01_'."""
    numeric_pattern = re.compile(r"^\d+[-_]")
    violations: list[str] = []
    for page_path in _all_page_paths():
        if page_path.is_file() and numeric_pattern.match(page_path.name):
            violations.append(str(page_path.relative_to(COOKBOOK_ROOT)))
    assert not violations, (
        f"Numeric prefixes found in {len(violations)} files: "
        f"{', '.join(violations)}"
    )


def test_file_names_are_hyphenated():
    """All cookbook page files should use descriptive-hyphenated names."""
    invalid: list[str] = []
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        stem = page_path.stem  # filename without .md
        # Must be lowercase, hyphenated, alphanumeric + hyphens only
        if not re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", stem):
            invalid.append(str(page_path.relative_to(COOKBOOK_ROOT)))
    assert not invalid, (
        f"Non-hyphenated file names: {', '.join(invalid)}"
    )


def test_file_extensions():
    """All cookbook files must have .md extension."""
    if not COOKBOOK_ROOT.is_dir():
        return
    non_md: list[str] = []
    for f in COOKBOOK_ROOT.rglob("*"):
        if f.is_file() and f.suffix != ".md":
            non_md.append(str(f.relative_to(COOKBOOK_ROOT)))
    assert not non_md, f"Non-.md files in cookbook: {', '.join(non_md)}"


# =============================================================================
# Index Completeness Tests
# =============================================================================


def test_index_lists_all_pages():
    """index.md must link to every expected page."""
    index_path = COOKBOOK_ROOT / "index.md"
    if not index_path.is_file():
        pytest.skip("index.md does not exist")
    content = index_path.read_text(encoding="utf-8")
    # All links from the index
    links = _extract_markdown_links(content)
    linked_files: set[str] = set()
    for _text, url in links:
        # Only consider relative links to .md files within the cookbook
        if url.startswith(("http://", "https://", "#")):
            continue
        # Resolve the link relative to the index location
        resolved = (index_path.parent / url).resolve()
        try:
            relative = resolved.relative_to(COOKBOOK_ROOT)
        except ValueError:
            continue
        linked_files.add(str(relative))

    # Check every expected page is linked
    expected: set[str] = set()
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            expected.add(f"{phase}/{page}")

    missing_from_index = expected - linked_files
    assert not missing_from_index, (
        f"Pages not linked from index.md: {', '.join(sorted(missing_from_index))}"
    )


def test_index_links_resolve():
    """Every link in index.md must point to an existing file."""
    index_path = COOKBOOK_ROOT / "index.md"
    if not index_path.is_file():
        pytest.skip("index.md does not exist")
    content = index_path.read_text(encoding="utf-8")
    links = _extract_markdown_links(content)
    broken: list[str] = []
    for text, url in links:
        if url.startswith(("http://", "https://", "#")):
            continue
        anchor = None
        if "#" in url:
            url, anchor = url.rsplit("#", 1)
        resolved = (index_path.parent / url).resolve()
        if not resolved.exists():
            broken.append(f"[{text}]({url}) -> {resolved}")
    assert not broken, f"Broken links in index.md: {', '.join(broken)}"


# =============================================================================
# Internal Link Integrity Tests
# =============================================================================


def test_internal_links_valid():
    """All relative markdown links within cookbook pages must resolve."""
    broken: list[tuple[str, str]] = []
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")
        links = _extract_markdown_links(content)
        for text, url in links:
            if url.startswith(("http://", "https://", "#")):
                continue
            anchor = None
            if "#" in url:
                url, anchor = url.rsplit("#", 1)
            resolved = (page_path.parent / url).resolve()
            if not resolved.exists():
                rel_page = str(page_path.relative_to(COOKBOOK_ROOT))
                broken.append((rel_page, f"[{text}]({url})"))
    assert not broken, (
        f"Broken internal links in {len(broken)} locations: "
        + "; ".join(f"{page}: {link}" for page, link in broken)
    )


# =============================================================================
# Code Block Tests
# =============================================================================


def test_page_has_code_blocks():
    """Every page must have at least one ```python code block."""
    no_blocks: list[str] = []
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")
        blocks = _extract_python_blocks(content)
        if not blocks:
            no_blocks.append(str(page_path.relative_to(COOKBOOK_ROOT)))
    assert not no_blocks, (
        f"Pages without any ```python blocks: {', '.join(no_blocks)}"
    )


def test_python_syntax_valid():
    """All ```python blocks must be syntactically valid Python 3.12+."""
    syntax_errors: list[tuple[str, int, str]] = []
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")
        for start_line, code in _extract_python_blocks(content):
            if code.strip() in ("", "..."):
                continue
            try:
                ast.parse(code)
            except SyntaxError as e:
                rel = str(page_path.relative_to(COOKBOOK_ROOT))
                syntax_errors.append((rel, start_line, str(e)))
    assert not syntax_errors, (
        f"Python syntax errors in {len(syntax_errors)} blocks: "
        + "; ".join(f"{page}:{line} — {err}" for page, line, err in syntax_errors)
    )


def test_standalone_snippets_run_without_errors():
    """Every standalone snippet (with its own imports) must execute cleanly.

    Only blocks starting with import/from statements are tested.
    LLM-calling snippets must stop at construction; they must not invoke
    live API calls.
    """
    _TMP_DIR.mkdir(parents=True, exist_ok=True)
    snippet_index = 0
    failures: list[tuple[str, int, str]] = []

    # Ensure required env vars are set so snippets with os.environ.get() don't fail
    test_env = os.environ.copy()
    test_env.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
    test_env.setdefault("OPENAI_RESPONSES_API_KEY", "sk-test-placeholder")
    test_env.setdefault("OPENAI_CHAT_COMPLETIONS_API_KEY", "sk-test-placeholder")
    test_env.setdefault("LLM_MODEL", "gpt-4o-mini")
    test_env.setdefault("LLM_BASE_URL", "http://localhost:1234/v1")

    # Patterns that indicate a snippet is NOT standalone (should be skipped)
    SKIP_PATTERNS = [
        # Live LLM calls / streaming loops
        r"agent\.run\(",
        r"agent\.stream_events\(",
        r"attach\.run\(",
        r"\.stream_events\(",
        r"\bawait\s",
        # Async wrappers around live calls
        r"asyncio\.run\(main\(\)\)",
        r"async with",
        r"async for",
        # File operations on placeholder paths that don't exist
        r"from_json_file\(\s*[\"']path/to/",
        r"from_yaml_file\(\s*[\"']path/to/",
        r"\.write_text\(\s*[\"']path/to/",
        # File path operations that will fail with placeholder paths
        r"FileAttachment\.from_path\(",
        r"file_attachments\s*=\s*\[",
        # Skill/directory loading from placeholder paths
        r"from_directory\(\s*Path\(\s*[\"']\./",
        r"load_directory\(\s*Path\(\s*[\"']\./",
        # Tool directory loading
        r"Tool\.load_directory\(",
        # Resource cleanup that requires live connection
        r"client\.close\(\)",
        r"executor\.close\(\)",
    ]
    _skip_re = re.compile("|".join(SKIP_PATTERNS))

    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue
            content = page_path.read_text(encoding="utf-8")
            for start_line, code in _extract_python_blocks(content):
                if code.strip() in ("", "..."):
                    continue
                # Check if this is a standalone snippet (starts with import/from)
                first_code_lines = [
                    ln
                    for ln in code.splitlines()
                    if ln.strip() and not ln.strip().startswith("#")
                ]
                if not first_code_lines:
                    continue
                if not _IMPORT_PATTERN.match(first_code_lines[0]):
                    continue

                # Skip snippets that call live LLM endpoints or read placeholder files
                if _skip_re.search(code):
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
                        env=test_env,
                    )
                    if result.returncode != 0:
                        rel = f"{phase}/{page}"
                        failures.append(
                            (
                                rel,
                                start_line,
                                f"exit={result.returncode}\n"
                                f"stdout: {result.stdout[-1000:]}\n"
                                f"stderr: {result.stderr[-1000:]}",
                            )
                        )
                finally:
                    if tmp_file.exists():
                        tmp_file.unlink()

    assert not failures, (
        f"Runtime failures in {len(failures)} standalone snippets: "
        + "; ".join(
            f"{page}:{line} — {err[:200]}" for page, line, err in failures
        )
    )


# =============================================================================
# Security Tests
# =============================================================================


def test_no_hardcoded_secrets():
    """No page should contain hardcoded API keys, tokens, or secrets."""
    findings: list[tuple[str, str, str]] = []
    for phase, pages in EXPECTED_PAGES.items():
        for page in pages:
            page_path = COOKBOOK_ROOT / phase / page
            if not page_path.is_file():
                continue
            content = page_path.read_text(encoding="utf-8")
            for pattern, desc in SECRET_PATTERNS:
                match = pattern.search(content)
                if match:
                    findings.append(
                        (
                            f"{phase}/{page}",
                            desc,
                            match.group()[:60],
                        )
                    )
    assert not findings, (
        f"Potential secrets in {len(findings)} locations: "
        + "; ".join(f"{loc}: {desc} near '{snippet}'" for loc, desc, snippet in findings)
    )


# =============================================================================
# Page Structure Tests
# =============================================================================


def test_page_structure():
    """Every page must have H1 title, Overview section, Common Pitfalls, and Next Steps."""
    violations: list[tuple[str, str]] = []
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")
        prose = _strip_code_blocks(content)
        rel = str(page_path.relative_to(COOKBOOK_ROOT))

        # Must have an H1 title
        h1s = re.findall(r"^# [^#].*", prose, re.MULTILINE)
        if not h1s:
            violations.append((rel, "missing H1 title"))
            continue

        # Must have an Overview section
        if not re.search(r"^##\s+Overview\s*$", prose, re.MULTILINE):
            violations.append((rel, "missing ## Overview section"))

        # Must have a Common Pitfalls section
        if not re.search(r"^##\s+Common Pitfalls\s*$", prose, re.MULTILINE):
            violations.append((rel, "missing ## Common Pitfalls section"))

        # Must have a Next Steps section (or See Also)
        if not re.search(
            r"^##\s+(Next Steps|See Also)\s*$", prose, re.MULTILINE
        ):
            violations.append((rel, "missing ## Next Steps section"))

    assert not violations, (
        f"Structure violations in {len(violations)} pages: "
        + "; ".join(f"{page}: {v}" for page, v in violations)
    )


def test_page_title_exists():
    """Every page must have exactly one H1 title (outside code blocks)."""
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")
        prose = _strip_code_blocks(content)
        h1s = re.findall(r"^# [^#].*", prose, re.MULTILINE)
        rel = str(page_path.relative_to(COOKBOOK_ROOT))
        assert len(h1s) == 1, (
            f"{rel}: expected exactly 1 H1 title, found {len(h1s)}: {h1s}"
        )


def test_pages_have_substantive_content():
    """Pages must not be empty stubs — they need more than just a title."""
    for page_path in _all_page_paths():
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")
        rel = str(page_path.relative_to(COOKBOOK_ROOT))
        # Strip markdown headings and whitespace
        stripped = re.sub(r"^#.*$", "", content, flags=re.MULTILINE).strip()
        assert len(stripped) > 200, (
            f"{rel}: page has insufficient content "
            f"({len(stripped)} chars after removing headings, expected >200)"
        )


# =============================================================================
# Provider Pattern Tests
# =============================================================================


def test_provider_patterns():
    """Provider-related pages must demonstrate both local and remote patterns.

    Checks that each provider dual page mentions both LM Studio / localhost
    configuration AND OpenAI / remote API key configuration.
    """
    missing_patterns: list[tuple[str, str]] = []
    for page_key in PROVIDER_DUAL_PAGES:
        page_path = COOKBOOK_ROOT / page_key
        if not page_path.is_file():
            continue
        content = page_path.read_text(encoding="utf-8")

        # Check for local pattern: LM Studio, localhost, or openai-compatible
        has_local = bool(
            re.search(
                r"(lm.?studio|localhost:1234|openai.compatible|provider\s*=\s*[\"'](?:openai-compatible|lmstudio))",
                content,
                re.IGNORECASE,
            )
        )
        # Check for remote pattern: OpenAI API key, api.openai.com
        has_remote = bool(
            re.search(
                r"(api\.openai\.com|OPENAI_API_KEY|openai[-_]responses|openai[-_]chat.completions)",
                content,
                re.IGNORECASE,
            )
        )

        if not has_local:
            missing_patterns.append((page_key, "missing local (LM Studio) pattern"))
        if not has_remote:
            missing_patterns.append((page_key, "missing remote (OpenAI) pattern"))

    assert not missing_patterns, (
        f"Provider pattern gaps in {len(missing_patterns)} pages: "
        + "; ".join(f"{page}: {msg}" for page, msg in missing_patterns)
    )


# =============================================================================
# Index Format Test
# =============================================================================


def test_index_has_phase_groups():
    """index.md should organize pages by phase with descriptions."""
    index_path = COOKBOOK_ROOT / "index.md"
    if not index_path.is_file():
        pytest.skip("index.md does not exist")
    content = index_path.read_text(encoding="utf-8")

    # Should reference at least 4 of the 6 phase names as section headers or in text
    phase_names = ["Onboarding", "Core Concepts", "Agent Extensions",
                   "Advanced File Handling", "Provider Deep Dives",
                   "Execution and Reference"]

    found = 0
    for name in phase_names:
        if name.lower() in content.lower():
            found += 1

    assert found >= 4, (
        f"index.md references only {found}/6 expected phase groups "
        f"(need at least 4)"
    )
