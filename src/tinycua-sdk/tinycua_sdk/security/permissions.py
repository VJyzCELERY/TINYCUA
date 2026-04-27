"""Permission system for tool execution security."""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional

_security_logger = logging.getLogger("tinycua_sdk.security")


class PermissionLevel(Enum):
    """Permission levels for tools."""
    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"


@dataclass
class ToolPermission:
    """Permission for a tool."""
    name: str
    level: PermissionLevel
    requires_approval: bool = False


class PermissionSystem:
    """Permission system for tool execution.
    
    Provides permission checking for tools based on their security level.
    Safe tools are allowed immediately, warning tools are logged but allowed,
    and dangerous tools require explicit approval.
    """
    
    def __init__(self):
        self._permissions: dict[str, ToolPermission] = {}
        self._setup_default_permissions()
    
    def _setup_default_permissions(self):
        """Setup default permissions for known tools."""
        self.register("calculator", PermissionLevel.SAFE)
        self.register("web_search", PermissionLevel.SAFE)
        self.register("file_read", PermissionLevel.WARNING)
        self.register("file_write", PermissionLevel.WARNING)
        self.register("shell_execute", PermissionLevel.DANGEROUS, requires_approval=True)
        self.register("delete_file", PermissionLevel.DANGEROUS, requires_approval=True)
        self.register("network_request", PermissionLevel.WARNING)
        self.register("get_weather", PermissionLevel.SAFE)
        self.register("search_code", PermissionLevel.SAFE)
        self.register("list_directory", PermissionLevel.WARNING)
        self.register("read_file", PermissionLevel.WARNING)
        self.register("write_file", PermissionLevel.WARNING)
        self.register("delete_file", PermissionLevel.DANGEROUS, requires_approval=True)
        self.register("execute_command", PermissionLevel.DANGEROUS, requires_approval=True)
        self.register("http_request", PermissionLevel.WARNING)
        self.register("send_email", PermissionLevel.DANGEROUS, requires_approval=True)
        self.register("access_database", PermissionLevel.DANGEROUS, requires_approval=True)
        self.register("manage_memory", PermissionLevel.SAFE)
        self.register("store_data", PermissionLevel.WARNING)
        self.register("retrieve_data", PermissionLevel.SAFE)
        self.register("delegate_to", PermissionLevel.WARNING)

    def register_tool(self, tool_name: str, level: PermissionLevel, requires_approval: bool = False):
        """Register a tool dynamically.

        Args:
            tool_name: Name of the tool.
            level: Permission level.
            requires_approval: Whether approval is required.
        """
        self.register(tool_name, level, requires_approval)

    def unregister_tool(self, tool_name: str) -> bool:
        """Unregister a tool.

        Args:
            tool_name: Name of the tool to unregister.

        Returns:
            True if tool was removed, False if not found.
        """
        if tool_name in self._permissions:
            del self._permissions[tool_name]
            return True
        return False

    def get_all_tools(self) -> dict[str, ToolPermission]:
        """Get all registered tools.

        Returns:
            Dict of tool name to ToolPermission.
        """
        return self._permissions.copy()
    
    def register(
        self,
        tool_name: str,
        level: PermissionLevel,
        requires_approval: bool = False,
    ):
        """Register a tool with a permission level."""
        self._permissions[tool_name] = ToolPermission(
            name=tool_name,
            level=level,
            requires_approval=requires_approval,
        )
        _security_logger.info("Registered tool: %s (level=%s, requires_approval=%s)", tool_name, level.value, requires_approval)

    def check_permission(self, tool_name: str) -> bool:
        """Check if tool can be executed.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if tool is allowed, False otherwise.
        """
        permission = self._permissions.get(tool_name)
        if not permission:
            _security_logger.debug("Tool %s not registered, allowing by default", tool_name)
            return True

        allowed = permission.level == PermissionLevel.SAFE

        if allowed:
            _security_logger.debug("Permission granted for tool: %s", tool_name)
        else:
            _security_logger.warning("Permission denied for tool: %s (level=%s)", tool_name, permission.level.value)

        return allowed

    def requires_approval(self, tool_name: str) -> bool:
        """Check if tool requires approval before execution.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if approval is required, False otherwise.
        """
        permission = self._permissions.get(tool_name)
        if not permission:
            _security_logger.debug("Tool %s not registered, no approval required", tool_name)
            return False

        if permission.requires_approval:
            _security_logger.info("Approval required for tool: %s", tool_name)

        return permission.requires_approval if permission else False
    
    def get_permission_level(self, tool_name: str) -> Optional[PermissionLevel]:
        """Get the permission level for a tool.
        
        Args:
            tool_name: Name of the tool.
            
        Returns:
            PermissionLevel if found, None otherwise.
        """
        permission = self._permissions.get(tool_name)
        return permission.level if permission else None
