"""Target 9.4: Verify ruff check passes on the SDK."""

import subprocess
from pathlib import Path


SDK_DIR = Path(__file__).parent.parent.parent

result = subprocess.run(
    ["ruff", "check", str(SDK_DIR / "tinycua_sdk")],
    capture_output=True, text=True, cwd=SDK_DIR,
)

if result.returncode != 0:
    print(f"FAIL:\n{result.stdout}\n{result.stderr}")
else:
    print("PASS — ruff check passed")
