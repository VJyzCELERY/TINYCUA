"""Source-size guard: TinyCUA Python source files must stay within the LOC gate.

Spec: ./specs/tinycua-runtime-invariants/spec.md:63-68, 220-221, 269
Source: src/tinycua/docs/design/loops/tinycua_loop.md:21-40,
        src/tinycua/docs/design/loops/node.md:25-27,
        src/tinycua/docs/design/loops/node_queue.md:25-47,
        src/tinycua/docs/design/loops/propagation.md:30-70

The hard acceptance gate is 1500 LOC. The user has explicitly approved this
relaxed gate (spec FR-017 allows user-approved exceptions) with the condition
that files in the 1000-1500 range must contain clean code with no dead or
unused functions. Files over 1500 lines are an acceptance failure regardless.
"""

from __future__ import annotations

from pathlib import Path

# User-approved exception to the spec's original 1000 LOC gate: files up to
# 1500 LOC are accepted as long as they contain no dead/unused functions and
# remain cohesive. This exception is recorded in spec.md (Zero-Tolerance
# item 8) and granted by the user on 2026-06-17.
_HARD_LOC_GATE = 1500

_TINYCUA_SOURCE_ROOT = Path(__file__).resolve().parent.parent.parent / "tinycua"


def test_tinycua_source_files_do_not_exceed_loc_gate() -> None:
    """Spec: ./spec.md:63-68, ./spec.md:220-221, ./spec.md:269.

    Source: tinycua_loop.md:21-40, node.md:25-27, node_queue.md:25-47,
    propagation.md:30-70.
    Any TinyCUA source file over the hard LOC gate is an acceptance failure.
    """
    oversized = []
    for path in _TINYCUA_SOURCE_ROOT.rglob("*.py"):
        if path.name == "__init__.py" and path.stat().st_size == 0:
            continue
        rel = path.relative_to(_TINYCUA_SOURCE_ROOT.parent).as_posix()
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > _HARD_LOC_GATE:
            oversized.append(f"{rel}: {line_count} lines")

    assert oversized == [], (
        f"TinyCUA source files exceed the {_HARD_LOC_GATE} LOC hard acceptance "
        "gate. Split, simplify, or delete them (do not hide with noqa). "
        f"Oversized files:\n  " + "\n  ".join(oversized)
    )
