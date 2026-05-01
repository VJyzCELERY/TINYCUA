"""02 - Skills Creation

Shows how to create and manage Skills inline.
Skills are metadata-only in the SDK — they provide instructions and context
that can be injected into an agent's system prompt, but they do NOT auto-resolve
tools. Tools must always be composed explicitly via Agent.add_tools().

For loading skills from a directory, see 08_loading_skills_from_directory.py.
"""

from tinycua_sdk import Skill

# ---------------------------------------------------------------------------
# 1. Inline skill creation
# ---------------------------------------------------------------------------
web_research_skill = Skill(
    name="web_research",
    description="Research topics using web search.",
    instructions=(
        "When the user asks about current events, trends, or facts that may "
        "have changed after your knowledge cutoff, use the web_search tool "
        "to find up-to-date information. Summarize sources concisely."
    ),
    metadata={
        "category": "research",
        "author": "tinycua-team",
    },
)

coding_skill = Skill(
    name="python_expert",
    description="Write idiomatic Python code.",
    instructions=(
        "When writing Python code, follow PEP 8, use type hints, "
        "prefer dataclasses over raw dicts, and always include docstrings."
    ),
)

# ---------------------------------------------------------------------------
# 2. Skill Registry (for discovery)
# ---------------------------------------------------------------------------
from tinycua_sdk.skills.registry import SkillRegistry

registry = SkillRegistry()
registry.register(web_research_skill)
registry.register(coding_skill)

print("Registered skills:")
for skill in registry.list_skills():
    print(f"  - {skill.name}: {skill.description}")

# ---------------------------------------------------------------------------
# 3. Short description vs full instructions
# ---------------------------------------------------------------------------
# The short `description` is what the model sees when deciding whether to use
# a skill. The full `instructions` are only injected when the skill is active.
print(f"\nShort desc: {web_research_skill.description}")
print(f"Full instructions length: {len(web_research_skill.instructions)} chars")

if __name__ == "__main__":
    pass
