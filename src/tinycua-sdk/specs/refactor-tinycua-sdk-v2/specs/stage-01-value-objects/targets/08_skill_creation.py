"""Target 1.8: Verify Skill creation, to_dict, from_dict."""

from tinycua_sdk import Skill


s = Skill(
    name="web_research",
    description="Research topics using web search.",
    instructions="Use the web_search tool for current events.",
    metadata={"category": "research"},
)

d = s.to_dict()
assert d["name"] == "web_research"
assert d["description"] == "Research topics using web search."
assert d["metadata"]["category"] == "research"

restored = Skill.from_dict(d)
assert restored.name == s.name
assert restored.description == s.description
print("PASS")
