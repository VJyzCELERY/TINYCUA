"""Target 6.3: Verify to_yaml/from_dict round-trip."""

import tempfile
from pathlib import Path
from tinycua_sdk import Agent


a = Agent(name="yaml_test", instructions="test")

# Export to YAML file
with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
    f.write(a.to_yaml())
    path = Path(f.name)

# Import back
a2 = Agent.from_yaml_file(path)
assert a2.name == "yaml_test"
assert a2.instructions == "test"

path.unlink()
print("PASS")
