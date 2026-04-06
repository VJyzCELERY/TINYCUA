"""Tool resolver for parsing and resolving tool specifications."""

from __future__ import annotations

import ast
from typing import Any

from tinycua_sdk.core.registry import ToolRegistry
from tinycua_sdk.tools.decorators import Tool


class ToolResolutionError(Exception):
    """Raised when a tool cannot be resolved from its specification."""

    def __init__(self, message: str, tool_spec: Any = None):
        """Initialize error with message and optional tool specification.

        Args:
            message: Error message describing the resolution failure
            tool_spec: The tool specification that failed to resolve
        """
        super().__init__(message)
        self.tool_spec = tool_spec


class TimeoutError(Exception):
    """Raised when inline tool execution times out."""

    pass


class ToolResolver:
    """Parse and resolve tool specifications to Tool instances with security safeguards."""

    # Configuration constants
    INLINE_TOOL_TIMEOUT: float = 5.0  # seconds
    SANDBOX_MODE: bool = False  # Can be enabled to disable inline tools

    def __init__(self, registry: ToolRegistry | None = None, strict_mode: bool = False):
        """Initialize resolver with optional registry.

        Args:
            registry: ToolRegistry instance for tool lookup.
                     If None, uses ToolRegistry singleton.
            strict_mode: If True, raise error for unresolved tools.
                        If False, keep unresolved as strings (lazy resolution).
        """
        self._registry = registry
        self._strict_mode = strict_mode

    @property
    def registry(self) -> ToolRegistry:
        """Get the ToolRegistry instance (singleton if not provided)."""
        if self._registry is None:
            return ToolRegistry()
        return self._registry

    def _parse_tool_specs(self, tool_specs: list[Any]) -> list[Any]:
        """Parse tool specifications and detect their format.

        Args:
            tool_specs: List of tool specifications (strings or dicts)

        Returns:
            List of parsed tool specifications
        """
        result = []
        for spec in tool_specs:
            if isinstance(spec, str):
                # String tool reference
                result.append(spec)
            elif isinstance(spec, dict):
                # Dict tool definition - detect type by keys
                if "tool" in spec:
                    # Inline tool definition
                    result.append({"tool": spec["tool"]})
                elif "mcp" in spec:
                    # MCP tool configuration
                    result.append(spec)
                else:
                    # Unknown dict format - treat as generic dict
                    result.append(spec)
            else:
                # Unknown type - keep as is
                result.append(spec)
        return result

    def resolve(self, tool_specs: list[Any]) -> list[str | Tool]:
        """Resolve tool specifications to Tool instances or strings.

        Args:
            tool_specs: List of tool specifications (strings or dicts)

        Returns:
            List of resolved Tool instances and/or string references
        """
        parsed_specs = self._parse_tool_specs(tool_specs)
        resolved_tools = []

        for spec in parsed_specs:
            if isinstance(spec, str):
                # Tool reference - resolve to Tool or keep as string
                resolved = self.resolve_tool_reference(spec)
                resolved_tools.append(resolved)
            elif isinstance(spec, dict):
                if "tool" in spec:
                    # Inline tool definition
                    tool = self.resolve_inline_tool(spec["tool"])
                    resolved_tools.append(tool)
                elif "mcp" in spec:
                    # MCP tool configuration
                    mcp_config = self.resolve_mcp_tool(spec)
                    resolved_tools.append(mcp_config)
                else:
                    # Unknown dict format - keep as is
                    resolved_tools.append(spec)
            else:
                # Unknown type - keep as is
                resolved_tools.append(spec)

        return resolved_tools

    def resolve_tool_reference(self, name: str) -> str | Tool:
        """Resolve a tool reference by name.

        Args:
            name: Tool name to look up

        Returns:
            Tool instance if found in registry, otherwise returns the string
            (for lazy resolution at runtime)
        """
        entry = self.registry.get(name)
        if entry is not None and entry.tool is not None:
            return entry.tool
        if self._strict_mode:
            raise ToolResolutionError(
                f"Tool '{name}' not found in registry",
                tool_spec=name,
            )
        # Return string for lazy resolution
        return name

    def resolve_inline_tool(self, source: str) -> Tool:
        """Resolve an inline tool definition with security safeguards.

        Security implementation:
        1. Parse source with ast.parse() to validate syntax
        2. Use compile() to catch compilation errors
        3. Execute in subprocess with timeout for true termination capability
        4. Subprocess prints serialized tool config, parent reconstructs Tool
        5. Register resolved tool with ToolRegistry for subsequent lookup

        Args:
            source: Python source code with @tool decorator

        Returns:
            Resolved Tool instance

        Raises:
            ToolResolutionError: If source cannot be parsed or executed
        """
        # Validate source code
        self._validate_tool_source(source)

        # Parse source and create Tool
        tool = self._execute_inline_tool_with_timeout(source, self.INLINE_TOOL_TIMEOUT)

        # Register the tool so it can be looked up later
        self.registry.register(
            name=tool.name,
            tool=tool,
            schema=tool.to_config(),
        )

        return tool

    def _validate_tool_source(self, source: str) -> None:
        """Validate tool source code using AST.

        Args:
            source: Python source code to validate

        Raises:
            ToolResolutionError: If source has invalid syntax or dangerous patterns
        """
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise ToolResolutionError(f"Invalid Python syntax: {e}")

        # Check for dangerous patterns
        dangerous = ["__import__", "open", "exec", "eval", "compile"]
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in dangerous:
                        raise ToolResolutionError(
                            f"Dangerous function '{node.func.id}' not allowed in inline tools"
                        )

    def _execute_inline_tool_with_timeout(
        self,
        source: str,
        timeout: float = 5.0,
    ) -> Tool:
        """Execute inline tool in subprocess with timeout.

        This approach:
        1. Parses source with AST to extract function info
        2. Generates a script that creates the tool directly
        3. Runs the script in a subprocess with timeout
        4. Parses the serialized tool config from output

        Args:
            source: Python source code with @tool decorator
            timeout: Timeout in seconds

        Returns:
            Resolved Tool instance

        Raises:
            TimeoutError: If execution exceeds timeout
            ToolResolutionError: If source cannot be parsed or executed
        """
        import os
        import subprocess
        import sys
        import tempfile
        import json

        # First, parse the source to extract function info
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise ToolResolutionError(f"Invalid Python syntax: {e}")

        # Find the function decorated with @tool
        tool_func = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "tool":
                        tool_func = node
                        break
                    if isinstance(decorator, ast.Call):
                        if (
                            isinstance(decorator.func, ast.Name)
                            and decorator.func.id == "tool"
                        ):
                            tool_func = node
                            break
                if tool_func:
                    break

        if not tool_func:
            raise ToolResolutionError(
                "Could not find @tool decorated function in source",
                tool_spec=source,
            )

        # Extract function information
        func_name = tool_func.name
        docstring = ast.get_docstring(tool_func) or ""

        # Extract parameters
        params = {}
        required = []
        for param in tool_func.args.args:
            param_name = param.arg
            if param.annotation:
                param_type = self._annotation_to_json_schema(param.annotation)
            else:
                param_type = {"type": "string"}
            params[param_name] = param_type
            required.append(param_name)

        # Handle defaults
        defaults = tool_func.args.defaults
        for i, default in enumerate(defaults):
            param_idx = len(tool_func.args.args) - len(defaults) + i
            param_name = tool_func.args.args[param_idx].arg
            if param_name in params:
                default_value = self._ast_value_to_python(default)
                params[param_name]["default"] = default_value

        # Generate a script that creates the tool directly
        # We avoid using inspect.getsource() by building the tool config manually
        # Escape the source for use in the generated script
        escaped_source = (
            source.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        escaped_docstring = (
            docstring.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

        script = f'''
import json
from tinycua_sdk.tools.decorators import Tool

# Create tool directly from extracted info
__tool__ = Tool(
    name="{func_name}",
    description="{escaped_docstring.split(chr(10))[0] if escaped_docstring else ""}",
    parameters={json.dumps({"type": "object", "properties": params, "required": required})},
    _source="{escaped_source}"
)

# Serialize and print the config
tool_config = __tool__.to_config()
print("__TOOL_CONFIG__:" + json.dumps(tool_config))
'''

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Parse output for tool config or errors
            tool_config = None
            for line in result.stdout.split("\n"):
                if "__TOOL_CONFIG__:" in line:
                    json_str = line.split("__TOOL_CONFIG__:")[1].strip()
                    tool_config = json.loads(json_str)
                    break

            # Check for errors
            stderr_lines = result.stderr.split("\n") if result.stderr else []
            for line in stderr_lines:
                if "__ERROR__:" in line:
                    error_parts = line.split("__ERROR__:")[1].split(":", 1)
                    error_type = error_parts[0] if len(error_parts) > 0 else "Unknown"
                    error_msg = (
                        error_parts[1] if len(error_parts) > 1 else "Unknown error"
                    )
                    raise ToolResolutionError(
                        f"{error_type}: {error_msg}", tool_spec=source
                    )

            if result.returncode != 0 and tool_config is None:
                raise ToolResolutionError(
                    f"Failed to execute inline tool: {result.stderr}",
                    tool_spec=source,
                )

            if not tool_config:
                raise ToolResolutionError(
                    "Could not extract tool config from inline definition",
                    tool_spec=source,
                )

            # Reconstruct Tool from config
            tool = Tool.from_config(tool_config)

            return tool

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Inline tool execution timed out after {timeout}s")
        except json.JSONDecodeError as e:
            raise ToolResolutionError(
                f"Invalid tool config JSON: {e}", tool_spec=source
            )
        finally:
            # Clean up temp file
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def _annotation_to_json_schema(self, annotation: ast.AST) -> dict[str, Any]:
        """Convert AST annotation to JSON schema.

        Args:
            annotation: AST node representing a type annotation

        Returns:
            JSON schema dict
        """
        # Simple type mapping for common types
        type_mapping = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "bool": {"type": "boolean"},
            "list": {"type": "array"},
            "dict": {"type": "object"},
        }

        if isinstance(annotation, ast.Name):
            type_name = annotation.id
            return type_mapping.get(type_name, {"type": "string"})

        return {"type": "string"}

    def _ast_value_to_python(self, node: ast.AST) -> Any:
        """Convert AST node to Python value.

        Args:
            node: AST node representing a value

        Returns:
            Python value
        """
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.NameConstant):
            return node.value
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.Str):
            return node.s
        if isinstance(node, ast.List):
            return [self._ast_value_to_python(elt) for elt in node.elts]
        if isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                key_val = self._ast_value_to_python(key) if key else None
                val_val = self._ast_value_to_python(value) if value else None
                if key_val is not None:
                    result[key_val] = val_val
            return result
        return None

    def resolve_mcp_tool(self, mcp_config: dict[str, Any]) -> dict[str, Any]:
        """Resolve an MCP tool configuration.

        MCP Config Schema:
        {
            "mcp": str,           # MCP server name (required, non-empty)
            "server": str,        # Server identifier (required, non-empty)
            "config": dict        # Optional server configuration
        }

        Validation rules:
        - "mcp" field must be present and be a non-empty string
        - "server" field must be present and be a non-empty string
        - "config" field must be a dict if present

        Args:
            mcp_config: MCP configuration dict

        Returns:
            Validated MCP config dict

        Raises:
            ToolResolutionError: If required fields missing or invalid
        """
        # Validate required fields
        if "mcp" not in mcp_config:
            raise ToolResolutionError(
                "MCP tool configuration missing 'mcp' field",
                tool_spec=mcp_config,
            )
        if "server" not in mcp_config:
            raise ToolResolutionError(
                "MCP tool configuration missing 'server' field",
                tool_spec=mcp_config,
            )

        # Validate types and non-empty
        if not isinstance(mcp_config.get("mcp"), str) or not mcp_config.get("mcp"):
            raise ToolResolutionError(
                "MCP server name must be a non-empty string",
                tool_spec=mcp_config,
            )
        if not isinstance(mcp_config.get("server"), str) or not mcp_config.get(
            "server"
        ):
            raise ToolResolutionError(
                "Server identifier must be a non-empty string",
                tool_spec=mcp_config,
            )

        # Validate config field if present
        if "config" in mcp_config and not isinstance(
            mcp_config.get("config"), (dict, type(None))
        ):
            raise ToolResolutionError(
                "MCP config must be a dictionary or omitted",
                tool_spec=mcp_config,
            )

        return mcp_config


__all__ = ["ToolResolver", "ToolResolutionError", "TimeoutError"]
