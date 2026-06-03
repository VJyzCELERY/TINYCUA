"""Root conftest for tinycua tests.

Sets TINYCUA_TOOL_ROOT to a per-test temporary directory so that tests
using temp files pass the sandbox boundary check. Tests that need stricter
sandboxing (e.g., path-escape regression tests) should override this with
a fixture-scoped value.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _set_tool_root(tmp_path):
    """Set TINYCUA_TOOL_ROOT to a per-test temporary directory."""
    original = os.environ.get("TINYCUA_TOOL_ROOT")
    os.environ["TINYCUA_TOOL_ROOT"] = str(tmp_path)
    yield tmp_path
    if original is not None:
        os.environ["TINYCUA_TOOL_ROOT"] = original
    else:
        os.environ.pop("TINYCUA_TOOL_ROOT", None)
