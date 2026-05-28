"""Target 0.2: Verify deleted modules cannot be imported."""

import subprocess
import sys

deleted_modules = [
    "tinycua_sdk.agent.backend_kind",
    "tinycua_sdk.tools.mcp",
    "tinycua_sdk.events.something",
    "tinycua_sdk.utils.helpers",
]

for mod in deleted_modules:
    result = subprocess.run(
        [sys.executable, "-c", f"import {mod}"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, f"{mod} should not be importable"
    assert "ModuleNotFoundError" in result.stderr or "ImportError" in result.stderr

print("PASS")
