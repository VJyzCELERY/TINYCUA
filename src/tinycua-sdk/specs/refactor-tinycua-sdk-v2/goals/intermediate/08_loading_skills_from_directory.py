"""08 - Loading Skills from Directory

Shows how the SDK discovers and loads skills from a directory structure.

Expected directory layout:
    skills/
    ├── web_research/
    │   ├── SKILL.md
    │   └── utils.py          (supporting code, NOT auto-registered as tools)
    ├── data_analyst/
    │   ├── SKILL.md
    │   └── stats.py          (supporting code)
    └── cli_assistant/
        └── SKILL.md

The SDK loads SKILL.md for each subdirectory. Supporting Python files
are available for import if the skill's code needs them, but they are
NOT automatically registered as agent tools.
"""

from pathlib import Path

from tinycua_sdk import Agent, LanguageModel, Skill


def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Load ALL skills from a directory tree
    # -----------------------------------------------------------------------
    skills_dir = Path(__file__).parent / "examples" / "skills"
    all_skills: list[Skill] = Skill.load_directory(skills_dir)

    print(f"Loaded {len(all_skills)} skills from {skills_dir}:")
    for skill in all_skills:
        print(f"  - {skill.name}: {skill.description}")

    # -----------------------------------------------------------------------
    # 2. Load a single skill from its folder
    # -----------------------------------------------------------------------
    web_research = Skill.from_directory(skills_dir / "web_research")
    print(f"\nSingle skill: {web_research.name}")
    print(f"Instructions length: {len(web_research.instructions)} chars")

    # -----------------------------------------------------------------------
    # 3. SkillRegistry for lookup by name
    # -----------------------------------------------------------------------
    from tinycua_sdk.skills.registry import SkillRegistry

    registry = SkillRegistry()
    for skill in all_skills:
        registry.register(skill)

    data_analyst = registry.get("data_analyst")
    print(f"\nLookup from registry: {data_analyst.name if data_analyst else 'not found'}")

    # -----------------------------------------------------------------------
    # 4. Attach loaded skills to an agent
    # -----------------------------------------------------------------------
    agent = Agent(
        name="multi_skilled_assistant",
        instructions="You are a versatile assistant.",
        llm_model=LanguageModel(model_name="qwen/qwen3.5-9b"),
        skills=all_skills,
    )

    print(f"\nAgent '{agent.name}' has {len(agent.skills)} skills.")


if __name__ == "__main__":
    main()
