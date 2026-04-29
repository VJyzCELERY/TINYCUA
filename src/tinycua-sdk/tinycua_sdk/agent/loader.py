"""Agent loader for loading configurations from AGENT.md files."""

import logging
from pathlib import Path

import yaml

from tinycua_sdk.agent.config import AgentConfig, AgentPolicy
from tinycua_sdk.agent.skill_resolver import SkillActivator, SkillToolResolver
from tinycua_sdk.agent.tool_resolver import ToolResolver
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.tools.decorators import Tool

# Maximum depth for skill dependency resolution
MAX_SKILL_DEPTH = 10


class AgentNotFoundError(Exception):
    """Raised when AGENT.md file does not exist."""

    pass


class AgentParseError(Exception):
    """Raised when AGENT.md cannot be parsed."""

    pass


class AgentLoader:
    """Loads agent configurations from AGENT.md files.

    Parses YAML frontmatter for metadata and Markdown for instructions.
    """

    def load_from_markdown(self, path: Path) -> AgentConfig:
        """Load agent configuration from AGENT.md file or directory.

        Args:
            path: Path to AGENT.md file or directory containing AGENT.md

        Returns:
            AgentConfig instance with parsed configuration

        Raises:
            AgentNotFoundError: If AGENT.md doesn't exist
            AgentParseError: If AGENT.md cannot be parsed
        """
        # Determine if path is file or directory
        if path.is_dir():
            agent_md_path = path / "AGENT.md"
        else:
            agent_md_path = path

        if not agent_md_path.exists():
            raise AgentNotFoundError(f"AGENT.md not found at {agent_md_path}")

        try:
            content = agent_md_path.read_text(encoding="utf-8")
            return self._parse_agent_md(agent_md_path, content)
        except PermissionError as e:
            raise AgentParseError(f"Permission denied reading {path}: {e}")
        except (OSError, ValueError, TypeError) as e:
            if isinstance(e, (AgentNotFoundError, AgentParseError)):
                raise
            raise AgentParseError(f"Failed to parse AGENT.md: {e}")

    def _parse_agent_md(self, path: Path, content: str) -> AgentConfig:
        """Parse AGENT.md content into AgentConfig.

        Args:
            path: Path to the AGENT.md file
            content: The raw AGENT.md content

        Returns:
            Parsed AgentConfig instance
        """
        # Split by YAML frontmatter delimiter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 2:
                yaml_content = parts[1].strip()
                markdown_content = parts[2].strip() if len(parts) > 2 else ""
            else:
                yaml_content = ""
                markdown_content = content
        else:
            yaml_content = ""
            markdown_content = content

        # Parse YAML frontmatter
        metadata = {}
        if yaml_content:
            try:
                metadata = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError as e:
                raise AgentParseError(f"Invalid YAML: {e}")

        # Extract required fields
        name = metadata.get("name", path.stem)  # Use filename as fallback

        # Extract optional fields
        model = metadata.get("model", "gpt-5-nano")
        provider = metadata.get("provider", "openai")
        base_url = metadata.get("base_url")
        api_key = metadata.get("api_key")
        system_prompt = metadata.get("system_prompt", "You are a helpful assistant.")

        # Extract tools (list of tool names)
        tools = metadata.get("tools", [])

        # Resolve tools using ToolResolver
        resolver = ToolResolver(strict_mode=False)
        resolved_tools = resolver.resolve(tools)

        # Store MCP tools in metadata
        config_metadata = {}
        mcp_tools = [t for t in resolved_tools if isinstance(t, dict) and "mcp" in t]
        if mcp_tools:
            config_metadata["mcp_tools"] = mcp_tools

        # Filter out MCP configs from tools list (they're in metadata)
        final_tools = [
            t for t in resolved_tools if not (isinstance(t, dict) and "mcp" in t)
        ]

        # Extract loop configuration
        loop_config = metadata.get("loop")

        # Extract policy configuration
        policy_data = metadata.get("policy", {})
        policy = AgentPolicy(
            max_tool_calls=policy_data.get("max_tool_calls", 10),
            parallel_tool_calls=policy_data.get("parallel_tool_calls", True),
            temperature=policy_data.get("temperature", 1.0),
        )

        # Extract instructions from markdown
        instructions = self._extract_instructions(markdown_content)

        # Extract skill-related fields (Stage 3)
        skills = metadata.get("skills", [])
        skill_dirs = metadata.get("skill_dirs", [])
        auto_load_dependencies = metadata.get("auto_load_dependencies", True)

        # Convert skill_dirs to Path objects
        skill_dirs_paths = [Path(d) for d in skill_dirs]

        # Load skill tools if skills are specified
        skill_tools = []
        skill_instructions_parts = []
        if skills:
            try:
                skill_tools, skill_instructions_parts = self._load_skill_tools(
                    skills, skill_dirs_paths, auto_load_dependencies
                )
            except (OSError, ValueError, TypeError) as e:
                logging.warning(f"Failed to load skill tools: {e}")

        # Merge skill tools with config tools
        all_tools = final_tools + skill_tools

        # Append skill instructions to main instructions
        combined_instructions = instructions
        if skill_instructions_parts:
            combined_instructions += "".join(skill_instructions_parts)

        # Build metadata dict (for backward compatibility)
        if skills:
            config_metadata["skills"] = skills
        if metadata.get("description"):
            config_metadata["description"] = metadata.get("description", "")

        return AgentConfig(
            name=name,
            instructions=combined_instructions,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            tools=all_tools,
            policy=policy,
            loop=loop_config,
            # Skill-related fields (Stage 3)
            skills=skills,
            skill_dirs=skill_dirs_paths,
            auto_load_dependencies=auto_load_dependencies,
            metadata=config_metadata,
        )

    def _extract_instructions(self, markdown_content: str) -> str:
        """Extract instructions from markdown content.

        Args:
            markdown_content: The markdown portion of AGENT.md

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
            if (
                "## Instructions" in line
                or "##instructions" in line.lower()
                or "# Agent Instructions" in line
                or "# Instructions" in line
                or "#instructions" in line.lower()
            ):
                skip_header = True
                continue
            if skip_header and line.strip().startswith("#"):
                break
            result_lines.append(line)

        return "\n".join(result_lines).strip()

    def _validate_skill_dir(self, path: Path, allowed_bases: list[Path]) -> Path:
        """Validate skill directory path to prevent traversal attacks.

        Args:
            path: Skill directory path to validate
            allowed_bases: List of allowed base directories

        Returns:
            Validated path if within allowed bases

        Raises:
            ValueError: If path is outside allowed base directories
        """
        resolved = path.expanduser().resolve()
        for base in allowed_bases:
            base_resolved = base.expanduser().resolve()
            if str(resolved).startswith(str(base_resolved)):
                return resolved
        raise ValueError(
            f"Skill directory '{path}' is outside allowed base directories"
        )

    def _load_skill_tools(
        self,
        skill_names: list[str],
        skill_dirs: list[Path],
        auto_load_dependencies: bool = True,
    ) -> tuple[list[Tool], list[str]]:
        """Load and resolve tools from skills.

        Args:
            skill_names: Names of skills to load
            skill_dirs: Directories to search for skills
            auto_load_dependencies: Whether to load skill dependencies

        Returns:
            Tuple of (resolved_tools, skill_instructions)
        """
        # Initialize registries and loaders
        skill_registry = SkillRegistry()
        tool_resolver = SkillToolResolver()
        skill_activator = SkillActivator()

        # Without a global registry, available toolsets and tools are empty.
        # Tools must be composed explicitly via Agent.add_tools().
        available_toolsets: set[str] = set()
        available_tools: set[str] = set()

        # Load skills from skill_dirs
        for skill_dir in skill_dirs:
            try:
                # Validate path
                validated_path = self._validate_skill_dir(
                    skill_dir, [Path.cwd(), Path.home()]
                )
                if validated_path.exists() and validated_path.is_dir():
                    for entry in sorted(validated_path.iterdir()):
                        if entry.is_dir() and not entry.name.startswith("."):
                            skill_md = entry / "SKILL.md"
                            if skill_md.exists():
                                try:
                                    content = skill_md.read_text(encoding="utf-8")
                                    skill = Skill.load(content)
                                    skill.source = str(entry)
                                    skill_registry.register(skill)
                                except (OSError, ValueError) as e:
                                    logging.warning(f"Failed to load skill from '{entry}': {e}")
            except ValueError as e:
                logging.warning(f"Skipping invalid skill directory '{skill_dir}': {e}")
            except (OSError, ValueError, TypeError) as e:
                logging.warning(f"Failed to load skills from '{skill_dir}': {e}")

        # Track loaded skills and resolve tools
        resolved_tools = []
        skill_instructions = []
        loaded_skills: set[str] = set()

        def _load_skill(
            skill_name: str,
            depth: int = 0,
        ) -> None:
            """Recursively load a skill and its dependencies."""
            if depth > MAX_SKILL_DEPTH:
                logging.warning(
                    f"Max skill depth ({MAX_SKILL_DEPTH}) exceeded for '{skill_name}', skipping"
                )
                return

            if skill_name in loaded_skills:
                return

            skill = skill_registry.get(skill_name)
            if not skill:
                logging.warning(f"Skill '{skill_name}' not found in registry")
                return

            # Check conditional activation
            if not skill_activator.should_activate_skill(
                skill, available_toolsets, available_tools
            ):
                logging.info(f"Skill '{skill_name}' not activated (conditions not met)")
                return

            # Mark as loaded
            loaded_skills.add(skill_name)

            # Resolve tools for this skill
            tools = tool_resolver.resolve_skill_tools(skill)
            resolved_tools.extend(tools)

            # Collect skill instructions
            if skill.instructions:
                skill_instructions.append(
                    f"\n\n=== Skill: {skill.name} ===\n{skill.instructions}"
                )

            # Load dependencies if enabled
            if auto_load_dependencies:
                for dep_name in skill.dependencies:
                    _load_skill(dep_name, depth + 1)

        # Load all requested skills
        for skill_name in skill_names:
            _load_skill(skill_name)

        return resolved_tools, skill_instructions
