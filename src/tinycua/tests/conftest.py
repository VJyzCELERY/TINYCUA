"""Root conftest for tinycua tests.

Sets TINYCUA_TOOL_ROOT to /tmp so that tests using temp files in /tmp
can pass the sandbox boundary check. Tests that need stricter sandboxing
should override this with a fixture-scoped value.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _set_tool_root():
    """Set TINYCUA_TOOL_ROOT to /tmp for each test."""
    original = os.environ.get("TINYCUA_TOOL_ROOT")
    os.environ["TINYCUA_TOOL_ROOT"] = "/tmp"
    yield
    if original is None:
        os.environ.pop("TINYCUA_TOOL_ROOT", None)
    else:
        os.environ["TINYCUA_TOOL_ROOT"] = original
