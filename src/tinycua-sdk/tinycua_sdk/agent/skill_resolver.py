"""Skill tool resolver and activator for agent skill integration."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from tinycua_sdk.skills.models import Skill
from tinycua_sdk.tools.decorators import Tool

if TYPE_CHECKING:
    from tinycua_sdk.skills.registry import SkillRegistry


class SkillToolResolver:
    """Resolves skill tool names to Tool instances.

    Without a global registry, tools must be provided explicitly.
    This resolver returns an empty list; tools should be composed
    directly via Agent.add_tools().
    """

    def __init__(self):
        """Initialize the resolver."""
        self._resolved_tools: dict[str, Tool] = {}

    def resolve_skill_tools(self, skill: Skill) -> list[Tool]:
        """Resolve tools declared by a skill to Tool instances.

        Args:
            skill: Skill with tools to resolve

        Returns:
            Empty list; tools must be composed explicitly.
        """
        if skill.tools:
            logging.warning(
                f"Skill '{skill.name}' declares tools {skill.tools} "
                "but no global registry is available; pass tools explicitly to Agent"
            )
        return []

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
            Empty list; tools must be composed explicitly.
        """
        return []


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
