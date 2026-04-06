"""SKILL.md loader and parser."""

from pathlib import Path
from datetime import datetime

from tinycua_sdk.skills.models import Skill


class SkillNotFoundError(Exception):
    """Raised when a skill directory does not contain SKILL.md."""

    pass


class SkillParseError(Exception):
    """Raised when SKILL.md cannot be parsed."""

    pass


class SkillLoader:
    """Loads skills from the filesystem.

    Parses SKILL.md files with YAML frontmatter and markdown instructions.
    """

    def load_skill(self, path: Path) -> Skill:
        """Load a single skill from a directory.

        Args:
            path: Path to the skill directory containing SKILL.md

        Returns:
            Loaded Skill instance

        Raises:
            SkillNotFoundError: If SKILL.md does not exist
            SkillParseError: If SKILL.md cannot be parsed
        """
        skill_md_path = path / "SKILL.md"

        if not skill_md_path.exists():
            raise SkillNotFoundError(f"SKILL.md not found in {path}")

        try:
            content = skill_md_path.read_text(encoding="utf-8")
            return self._parse_skill_md(path, content)
        except PermissionError as e:
            raise SkillParseError(f"Permission denied reading {path}: {e}")
        except Exception as e:
            if isinstance(e, (SkillNotFoundError, SkillParseError)):
                raise
            raise SkillParseError(f"Failed to parse SKILL.md: {e}")

    def _parse_skill_md(self, path: Path, content: str) -> Skill:
        """Parse SKILL.md content.

        Args:
            path: Path to the skill directory
            content: The raw SKILL.md content

        Returns:
            Parsed Skill instance
        """
        import yaml

        # Split by YAML frontmatter delimiter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) < 3:
                raise SkillParseError("Invalid YAML frontmatter format")

            yaml_content = parts[1].strip()
            markdown_content = parts[2].strip()
        else:
            yaml_content = ""
            markdown_content = content

        # Parse YAML frontmatter
        metadata = {}
        if yaml_content:
            try:
                metadata = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError as e:
                raise SkillParseError(f"Invalid YAML: {e}")

        # Extract required fields
        name = metadata.get("name", path.name)
        description = metadata.get("description", "")
        category = metadata.get("category", "general")
        tools = metadata.get("tools", [])
        dependencies = metadata.get("dependencies", [])

        # Extract instructions from markdown
        instructions = self._extract_instructions(markdown_content)

        # Get file modification time
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
        """Extract instructions from markdown content.

        Args:
            markdown_content: The markdown portion of SKILL.md

        Returns:
            The instructions text
        """
        # Remove ## Instructions header if present
        lines = markdown_content.split("\n")
        result_lines = []
        skip_header = False

        for line in lines:
            if skip_header and line.strip().startswith("#"):
                skip_header = False
                continue
            if "## Instructions" in line or "##instructions" in line.lower():
                skip_header = True
                continue
            if skip_header and line.strip().startswith("#"):
                break
            result_lines.append(line)

        return "\n".join(result_lines).strip()

    def discover_skills(self, base_dir: Path) -> list[Skill]:
        """Discover all skills in a directory.

        Args:
            base_dir: Base directory to search for skills

        Returns:
            List of discovered Skill instances
        """
        if not base_dir.exists() or not base_dir.is_dir():
            return []

        skills = []

        # Only look at direct children
        for entry in sorted(base_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                try:
                    skill = self.load_skill(entry)
                    skills.append(skill)
                except (SkillNotFoundError, SkillParseError):
                    # Skip directories without valid SKILL.md
                    continue

        return skills
