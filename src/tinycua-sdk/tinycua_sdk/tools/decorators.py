"""Tool model and decorator."""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, get_origin

class Tool:
    """A tool that can be invoked by the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    _callable: Callable | None
    dependencies: list[str]

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        _callable: Callable | None = None,
        dependencies: list[str] | None = None,
    ) -> None:
        """Initialize a Tool instance.

        Args:
            name: The tool name.
            description: The tool description.
            parameters: The tool parameters schema.
            _callable: The underlying callable.
            dependencies: List of external dependencies.

        """
        self.name = name
        self.description = description
        self.parameters = parameters or {}
        self._callable = _callable
        self.dependencies = dependencies or []

    def to_config(self) -> dict[str, Any]:
        """Return OpenAI function-calling schema format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def invoke(self, **kwargs: Any) -> Any:
        """Invoke the tool function with keyword arguments."""
        if self._callable is None:
            raise RuntimeError(f"Tool {self.name} has no function to invoke")
        return self._callable(**kwargs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Tool":
        """Create a Tool from a configuration dict.

        Args:
            data: A dict with tool configuration (name, description, parameters).

        Returns:
            A Tool instance.

        """
        if "function" in data:
            func_config = data["function"]
            name = func_config.get("name", "")
            description = func_config.get("description", "")
            parameters = func_config.get("parameters", {})
        else:
            name = data.get("name", "")
            description = data.get("description", "")
            parameters = data.get("parameters", {})
        return cls(
            name=name,
            description=description,
            parameters=parameters,
        )

    @classmethod
    def from_callable(
        cls, fn: Callable, dependencies: list[str] | None = None
    ) -> "Tool":
        """Create a Tool from a function by inspecting its signature and docstring.

        Args:
            fn: The function to convert into a Tool.
            dependencies: Optional list of external dependency names.

        Returns:
            A Tool instance with generated schema.

        """
        sig = inspect.signature(fn)
        docstring = fn.__doc__ or ""

        param_descriptions = _parse_param_descriptions(docstring)

        params: dict[str, Any] = {}
        required: list[str] = []
        for param_name, param in sig.parameters.items():
            schema = _python_type_to_json_schema(param.annotation)
            if schema is not None:
                params[param_name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        # Use first line of docstring as description
        first_line = docstring.strip().split("\n")[0] if docstring.strip() else ""

        return cls(
            name=fn.__name__,
            description=first_line,
            parameters={
                "type": "object",
                "properties": params,
                "required": required,
            },
            _callable=fn,
            dependencies=dependencies or [],
        )


def _python_type_to_json_schema(type_hint: Any) -> dict[str, Any] | None:
    """Map Python types to JSON Schema types.

    Args:
        type_hint: A Python type annotation.

    Returns:
        JSON Schema dict, or None for unsupported types (allows any).

    """
    origin = get_origin(type_hint) if isinstance(type_hint, type) or hasattr(type_hint, "__origin__") else None
    if type_hint is str:
        return {"type": "string"}
    elif type_hint in (int, float):
        return {"type": "number"}
    elif type_hint is bool:
        return {"type": "boolean"}
    elif type_hint in (list, list[Any]) or origin is list:
        return {"type": "array"}
    elif type_hint in (dict, dict[Any, Any]) or origin is dict:
        return {"type": "object"}
    return None


def _parse_param_descriptions(docstring: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style docstring Args: section.

    Args:
        docstring: The function docstring.

    Returns:
        Dictionary mapping parameter names to their descriptions.

    """
    descriptions: dict[str, str] = {}
    in_args = False
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if in_args:
            if stripped and not stripped.startswith(("-", "*", "#")):
                match = re.match(r"^(\w+):\s*(.+)$", stripped)
                if match:
                    param_name = match.group(1)
                    desc = match.group(2).strip()
                    descriptions[param_name] = desc
            else:
                in_args = False
    return descriptions


def tool(
    fn: Callable | None = None,
    *,
    dependencies: list[str] | None = None,
) -> Tool | Callable[[Callable], Tool]:
    """Decorator to convert a function into a Tool.

    Usage:
        @tool
        def func(): ...

        @tool()
        def func(): ...

        @tool(dependencies=["requests"])
        def func(): ...
    """
    if fn is None:
        def decorator(f: Callable) -> Tool:
            return Tool.from_callable(f, dependencies or [])
        return decorator

    return Tool.from_callable(fn, dependencies or [])


__all__ = ["Tool", "tool"]
