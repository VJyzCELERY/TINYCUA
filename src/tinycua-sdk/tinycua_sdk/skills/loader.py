"""SKILL.md loader and parser."""

import os
from pathlib import Path
from datetime import datetime

from tinycua_sdk.skills.models import Skill


class SkillNotFoundError(Exception):
    """Raised when a skill is not found in the expected location."""
    pass


class SkillParseError(Exception):
    """Raised when skill metadata cannot be parsed."""
    pass


class SkillLoader:
    """Loads and parses SKILL.md files from specified directories."""

    DEFAULT_SKILL_DIRS = [
        Path(os.path.expanduser("~/.tinycua/skills")),
        Path("./skills"),
    ]

    def __init__(self, skill_directories: list[Path] | None = None):
        self.skill_directories = skill_directories or self.DEFAULT_SKILL_DIRS

    def discover(self) -> list[Skill]:
        """Discover all skills in configured directories.

        Returns:
            List of discovered skills
        """
        all_skills = []
        for directory in self.skill_directories:
            if directory.exists() and directory.is_dir():
                skills = self.discover_skills(directory)
                all_skills.extend(skills)
        return all_skills

    def load(self, path: Path) -> Skill:
        """Load a skill from the given path.

        Args:
            path: Path to the skill directory

        Returns:
            Loaded skill
        """
        return self.load_skill(path)

    def load_all(self, directories: list[Path] | None = None) -> list[Skill]:
        """Load all skills from specified directories.

        Args:
            directories: Optional list of directories to load from

        Returns:
            List of loaded skills
        """
        dirs = directories or self.skill_directories
        all_skills = []
        for directory in dirs:
            if directory.exists() and directory.is_dir():
                skills = self.discover_skills(directory)
                all_skills.extend(skills)
        return all_skills

    def load_skill(self, path: Path) -> Skill:
        """Load a single skill from the given path.

        Args:
            path: Path to the skill directory

        Returns:
            Loaded skill

        Raises:
            SkillNotFoundError: If SKILL.md not found
            SkillParseError: If metadata cannot be parsed
        """
        skill_md_path = path / "SKILL.md"

        if not skill_md_path.exists():
            raise SkillNotFoundError(f"SKILL.md not found in {path}")

        try:
            content = skill_md_path.read_text(encoding="utf-8")
            return self._parse_skill_md(path, content)
        except PermissionError as e:
            raise SkillParseError(f"Permission denied reading {path}: {e}")
        except (OSError, ValueError, TypeError) as e:
            if isinstance(e, (SkillNotFoundError, SkillParseError)):
                raise
            raise SkillParseError(f"Failed to parse SKILL.md: {e}")

    def _parse_skill_md(self, path: Path, content: str) -> Skill:
        import yaml

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) < 3:
                raise SkillParseError("Invalid YAML frontmatter format")

            yaml_content = parts[1].strip()
            markdown_content = parts[2].strip()
        else:
            yaml_content = ""
            markdown_content = content

        metadata = {}
        if yaml_content:
            try:
                metadata = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError as e:
                raise SkillParseError(f"Invalid YAML: {e}")

        name = metadata.get("name", path.name)
        description = metadata.get("description", "")
        category = metadata.get("category", "general")
        tools = metadata.get("tools", [])
        dependencies = metadata.get("dependencies", [])

        instructions = self._extract_instructions(markdown_content)

        skill_md_path = path / "SKILL.md"
        stat = skill_md_path.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime)
        created_at = datetime.fromtimestamp(stat.st_ctime)

        return Skill(
            name=name,
            description=description,
            category=category,
            instructions=instructions,
            tools=tools,
            dependencies=dependencies,
            path=path,
            metadata=metadata,
            created_at=created_at,
            modified_at=modified_at,
        )

    def _extract_instructions(self, markdown_content: str) -> str:
        lines = markdown_content.split("\n")
        result_lines = []
        skip_instructions = False

        for line in lines:
            if "## Instructions" in line or "##instructions" in line.lower():
                skip_instructions = True
                continue

            if skip_instructions and line.strip().startswith("#"):
                skip_instructions = False

            result_lines.append(line)

        return "\n".join(result_lines).strip()

    def discover_skills(self, base_dir: Path) -> list[Skill]:
        """Discover all skills in a directory.

        Args:
            base_dir: Directory to search for skills

        Returns:
            List of discovered skills
        """
        if not base_dir.exists() or not base_dir.is_dir():
            return []

        skills = []

        for entry in sorted(base_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                try:
                    skill = self.load_skill(entry)
                    skills.append(skill)
                except (SkillNotFoundError, SkillParseError):
                    continue

        return skills

    def convert_to_tools(self, skills: list[Skill]) -> list[dict]:
        """Convert skills to tool format for agent integration.

        Args:
            skills: List of skills to convert

        Returns:
            List of tool dictionaries
        """
        tools = []
        for skill in skills:
            tool = {
                "name": skill.name.lower().replace(" ", "_"),
                "description": skill.description or skill.instructions[:100],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string", "description": "User input for the skill"}
                    },
                    "required": ["input"]
                },
                "_skill": skill,
            }
            tools.append(tool)
        return tools

    def _create_handler(self, skill: Skill):
        async def handler(arguments: dict) -> str:
            return skill.instructions
        return handler
