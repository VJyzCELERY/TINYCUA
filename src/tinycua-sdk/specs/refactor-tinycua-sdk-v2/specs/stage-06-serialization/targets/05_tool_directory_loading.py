"""Target 6.5: Verify Tool.load_directory discovers @tool-decorated functions."""

from pathlib import Path
from tinycua_sdk import Tool


tools_dir = Path(__file__).parent.parent / "goals" / "intermediate" / "examples" / "tools"

all_tools = Tool.load_directory(tools_dir)
assert len(all_tools) >= 1

# Verify calculator package loads correctly
calc_tools = Tool.load_directory(tools_dir / "calculator")
assert len(calc_tools) >= 1
tool_names = {t.name for t in calc_tools}
print(f"Calculator tools: {tool_names}")

print("PASS")
