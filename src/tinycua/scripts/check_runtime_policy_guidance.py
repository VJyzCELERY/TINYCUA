#!/usr/bin/env python
"""Audit TinyCUA runtime code for spec-guidance violations.

This is a standalone audit script, NOT a pytest test. The spec is explicit
that policy guidance (forbidden prompt-category heuristics, hardcoded task
titles, task-count caps, analyzer rewrites) must NOT be encoded as pytest
assertions. It belongs here so a human or CI can run it directly.

Spec: ./specs/tinycua-runtime-invariants/spec.md:29-42, 242-255, 261-262
Source: src/tinycua/docs/design/loops/task_analyzer.md:6-17, 23-31,
        src/tinycua/docs/design/models/task.md:10-28,
        src/tinycua/docs/design/tools/task.md:19-28

Exit code:
    0 — no forbidden patterns found.
    1 — one or more forbidden patterns found (printed to stdout).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Each entry: (pattern, why_it_is_forbidden, spec_reference).
# Patterns are matched case-insensitively against the joined source text of
# every TinyCUA .py file under src/tinycua/tinycua/. The design-doc tree
# (src/tinycua/docs/design/**) and the SDK (src/tinycua-sdk/**) are excluded.
_FORBIDDEN_GUIDANCE_PATTERNS: list[tuple[str, str, str]] = [
    (
        "minimal runnable vertical-slice",
        "Hardcoded vertical-slice task title forced by runtime code.",
        "spec.md:29-42, 246-249, 261",
    ),
    (
        "_one_shot_app_subtasks",
        "App/web-ui collapse heuristic that rewrites analyzer output.",
        "spec.md:29-42, 246-249",
    ),
    (
        "_MAX_DECOMPOSE_SUBTASKS",
        "Hard task-count cap on TaskAnalyzer decomposition.",
        "spec.md:208-210, 246-249, 262",
    ),
    (
        '"maxItems": 3',
        "JSON schema cap advertising a 3-subtask limit to the LLM.",
        "spec.md:246-249, 262",
    ),
    (
        '"maxItems": 1,',
        "JSON schema cap restricting tool calls to one per turn.",
        "spec.md:246-249",
    ),
    (
        "create_vertical_slice",
        "Recovery path that fabricates a vertical-slice task when the "
        "analyzer misses its tool call.",
        "spec.md:29-42, 218-219, 261",
    ),
    (
        "one-shot app builds, prefer one runnable vertical-slice",
        "Node prompt instructs the LLM to prefer a vertical slice for "
        "one-shot app builds — prompt-category forcing.",
        "spec.md:29-42, 206-210, 261",
    ),
    (
        "prefer one vertical",
        "Node prompt vertical-slice forcing (shorter variant).",
        "spec.md:29-42, 206-210, 261",
    ),
    (
        "backend/frontend/api tasks",
        "Prompt guidance that forbids backend/frontend/API splits — a "
        "prompt-category decomposition rule.",
        "spec.md:29-42, 206-210",
    ),
]


def _tinycua_source_files() -> list[Path]:
    """Return every TinyCUA runtime .py file, excluding docs and SDK."""
    root = Path(__file__).resolve().parent.parent / "tinycua"
    if not root.is_dir():
        # Allow running from repo root too.
        root = Path("src/tinycua/tinycua").resolve()
    return sorted(root.rglob("*.py"))


def main() -> int:
    """Audit runtime source and return non-zero if forbidden patterns exist."""
    files = _tinycua_source_files()
    if not files:
        print("check_runtime_policy_guidance: no TinyCUA source files found.")
        return 1

    violations: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"warning: could not read {path}: {exc}", file=sys.stderr)
            continue
        lower = text.lower()
        for pattern, reason, ref in _FORBIDDEN_GUIDANCE_PATTERNS:
            if pattern.lower() in lower:
                rel = path.relative_to(path.parent.parent).as_posix()
                violations.append(
                    f"- {rel}: {pattern!r}\n    {reason}\n    ref: {ref}"
                )

    if not violations:
        print("check_runtime_policy_guidance: no forbidden patterns found.")
        return 0

    print("check_runtime_policy_guidance: forbidden patterns found:")
    for violation in violations:
        print(violation)
    print(
        "\nRemove these patterns from runtime code. They violate the "
        "Zero-Tolerance Ultimatum (spec.md:25-68) and Prohibited Patterns "
        "(spec.md:242-255)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
