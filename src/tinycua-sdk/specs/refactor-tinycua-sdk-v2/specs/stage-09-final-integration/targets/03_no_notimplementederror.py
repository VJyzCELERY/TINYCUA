"""Target 9.3: Verify no production code raises NotImplementedError."""

import ast
from pathlib import Path


SDK_DIR = Path(__file__).parent.parent.parent / "tinycua_sdk"

not_implemented_files = []
for py_file in SDK_DIR.rglob("*.py"):
    if "__pycache__" in str(py_file):
        continue
    content = py_file.read_text()
    if "raise NotImplementedError" in content:
        not_implemented_files.append(str(py_file.relative_to(SDK_DIR.parent)))

if not_implemented_files:
    print("Found NotImplementedError in:")
    for f in not_implemented_files:
        print(f"  - {f}")
else:
    print("PASS — no NotImplementedError stubs found")
