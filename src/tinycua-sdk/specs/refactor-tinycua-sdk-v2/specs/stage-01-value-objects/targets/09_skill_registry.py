"""Target 1.9: Verify SkillRegistry register, list, get."""

from tinycua_sdk import Skill
from tinycua_sdk.skills.registry import SkillRegistry


s1 = Skill(name="coder", description="Write code", instructions="Use PEP 8.")
s2 = Skill(name="tester", description="Write tests", instructions="Cover edge cases.")

registry = SkillRegistry()
registry.register(s1)
registry.register(s2)

assert len(registry.list_skills()) == 2
assert registry.get("coder").name == "coder"
assert registry.get("nonexistent") is None

# Overwrite: register s1 again with different name
s3 = Skill(name="coder_v2", description="Write code v2", instructions="Use PEP 8.")
registry.register(s3)
assert len(registry.list_skills()) == 2
assert registry.get("coder").name == "coder_v2"

print("PASS")
