"""Skill tool resolver and activator for agent skill integration."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from tinycua_sdk.skills.models import Skill
from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.core.registry import ToolRegistry
    from tinycua_sdk.skills.registry import SkillRegistry


class SkillToolResolver:
    """Resolves skill tool names to Tool instances.

    This class performs read-only lookups from the ToolRegistry.
    It does NOT register tools with the registry - it only resolves
    tool names to Tool instances for use in agent creation.
    """

    def __init__(self, tool_registry: "ToolRegistry | None" = None):
        """Initialize the resolver.

        Args:
            tool_registry: Optional ToolRegistry instance. If not provided,
                          uses the singleton ToolRegistry.
        """
        self._tool_registry = tool_registry
        self._resolved_tools: dict[str, Tool] = {}

    @property
    def tool_registry(self) -> "ToolRegistry":
        """Get the ToolRegistry instance.

        Note: ToolRegistry is a singleton, so ToolRegistry() always returns
        the same instance. This is intentional behavior.
        """
        if self._tool_registry is None:
            from tinycua_sdk.core.registry import ToolRegistry

            return ToolRegistry()
        return self._tool_registry

    def resolve_skill_tools(self, skill: Skill) -> list[Tool]:
        """Resolve tools declared by a skill to Tool instances.

        This is a read-only lookup from ToolRegistry - it does NOT
        register tools with the registry.

        Args:
            skill: Skill with tools to resolve

        Returns:
            List of resolved Tool instances
        """
        resolved = []

        for tool_name in skill.tools:
            entry = self.tool_registry.get(tool_name)
            if entry and entry.tool:
                self._resolved_tools[tool_name] = entry.tool
                resolved.append(entry.tool)
            else:
                logging.warning(
                    f"Skill '{skill.name}' declares tool '{tool_name}' not found in registry"
                )
        return resolved

    def get_resolved_tools(
        self,
        skill_names: list[str],
        registry: "SkillRegistry",
    ) -> list[Tool]:
        """Get all tools for a list of skills.

        Args:
            skill_names: Names of skills to get tools from
            registry: SkillRegistry to look up skills

        Returns:
            List of resolved Tool instances
        """
        tools = []
        for name in skill_names:
            skill = registry.get_skill(name)
            if skill:
                tools.extend(self.resolve_skill_tools(skill))
        return tools


class SkillActivator:
    """Handles conditional skill activation based on environment.

    Logic semantics:
    - Within a single condition type (e.g., requires_toolsets): OR semantics
      (any match is sufficient)
    - Between different condition types (platform, toolset, tool): AND semantics
      (all conditions must pass)
    """

    PLATFORM_MAP = {
        "macos": "darwin",
        "linux": "linux",
        "windows": "win32",
    }

    def should_activate_skill(
        self,
        skill: Skill,
        available_toolsets: set[str],
        available_tools: set[str],
    ) -> bool:
        """Determine if a skill should be activated.

        All conditions must pass (AND logic between condition types).
        Within each condition type, OR semantics apply (any match is sufficient).

        Args:
            skill: Skill to check
            available_toolsets: Set of available toolset names
            available_tools: Set of available tool names

        Returns:
            True if skill should be activated, False otherwise
        """
        metadata = skill.metadata

        # Check platform requirement (AND with other conditions)
        platforms = metadata.get("platforms", [])
        if platforms and not self._check_platform(platforms):
            return False

        # Check requires_toolsets - OR semantics (any toolset matches)
        requires_toolsets = metadata.get("requires_toolsets", [])
        if requires_toolsets:
            if not any(ts in available_toolsets for ts in requires_toolsets):
                return False

        # Check fallback_for_toolsets - OR semantics (any toolset hides)
        fallback_toolsets = metadata.get("fallback_for_toolsets", [])
        if fallback_toolsets:
            if any(ts in available_toolsets for ts in fallback_toolsets):
                return False

        # Check requires_tools - OR semantics (any tool matches)
        requires_tools = metadata.get("requires_tools", [])
        if requires_tools:
            if not any(t in available_tools for t in requires_tools):
                return False

        # Check fallback_for_tools - OR semantics (any tool hides)
        fallback_tools = metadata.get("fallback_for_tools", [])
        if fallback_tools:
            if any(t in available_tools for t in fallback_tools):
                return False

        return True

    def _check_platform(self, platforms: list[str]) -> bool:
        """Check if current platform matches requirement.

        Args:
            platforms: List of required platforms

        Returns:
            True if current platform is in the list
        """
        current = sys.platform
        mapped = [self.PLATFORM_MAP.get(p, p) for p in platforms]
        return current in mapped


__all__ = ["SkillToolResolver", "SkillActivator"]
