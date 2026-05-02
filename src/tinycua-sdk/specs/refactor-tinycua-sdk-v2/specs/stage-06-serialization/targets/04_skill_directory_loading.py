"""Target 6.4: Verify Skill.load_directory discovers and parses SKILL.md files."""

from pathlib import Path
from tinycua_sdk import Skill


skills_dir = Path(__file__).parent.parent / "goals" / "intermediate" / "examples" / "skills"

all_skills = Skill.load_directory(skills_dir)
assert len(all_skills) == 3

names = {s.name for s in all_skills}
assert names == {"cli_assistant", "data_analyst", "web_research"}

# Verify single skill loading
single = Skill.from_directory(skills_dir / "web_research")
assert single.name == "web_research"
assert len(single.instructions) > 0

print("PASS")
