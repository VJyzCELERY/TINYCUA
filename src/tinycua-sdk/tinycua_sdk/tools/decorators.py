"""Tool model and decorator."""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path
from typing import Any, Callable

from tinycua_sdk.tools.schema import type_to_json_schema


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
        """Return Responses API tool schema format."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
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
    def from_config(cls, data: dict[str, Any]) -> "Tool":
        """Create a Tool from a configuration dict (public alias for from_dict).

        Args:
            data: A dict with tool configuration, supports both bare
                (name/description/parameters) and OpenAI-style
                (function/name/description/parameters) formats.

        Returns:
            A Tool instance.
        """
        return cls.from_dict(data)

    @classmethod
    def load_directory(cls, path: Path) -> list["Tool"]:
        """Load all tools from a directory of tool subdirectories.

        Scans each immediate subdirectory for Python modules (skipping files
        prefixed with _), loads them via importlib, and collects all Tool
        instances.

        Args:
            path: Path to the directory containing tool subdirectories.

        Returns:
            List of Tool instances found.
        """
        tools: list[Tool] = []
        for subdir in sorted(Path(path).iterdir()):
            if not subdir.is_dir():
                continue
            for py_file in sorted(subdir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                module = _load_module_from_path(py_file)
                for _name, obj in inspect.getmembers(module):
                    if isinstance(obj, Tool):
                        tools.append(obj)
        return tools

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
        for i, (param_name, param) in enumerate(sig.parameters.items()):
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if param_name in ("self", "cls") and i == 0:
                continue
            schema = type_to_json_schema(param.annotation)
            params[param_name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        for param_name, desc in param_descriptions.items():
            if param_name in params:
                params[param_name]["description"] = desc

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


def _parse_param_descriptions(docstring: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style docstring Args: section.

    Args:
        docstring: The function docstring.

    Returns:
        Dictionary mapping parameter names to their descriptions.

    """
    descriptions: dict[str, str] = {}
    in_args = False
    current_param: str | None = None
    for line in docstring.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("args:"):
            in_args = True
            continue
        if in_args:
            if not stripped or stripped.startswith("#"):
                in_args = False
                current_param = None
                continue
            clean_line = stripped
            if clean_line.startswith(("-", "*")):
                clean_line = clean_line[1:].strip()
            match = re.match(r"^(\w+)(?:\s*\([^)]*\))?:\s*(.*)$", clean_line)
            if match:
                current_param = match.group(1)
                desc = match.group(2).strip()
                descriptions[current_param] = desc
            elif line.startswith((" ", "\t")) and current_param is not None:
                descriptions[current_param] += " " + clean_line
            else:
                in_args = False
                current_param = None
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

    Args:
        fn: The function to convert. If None, returns a decorator.
        dependencies: Optional list of external dependency package names.

    Returns:
        A Tool instance, or a decorator function if fn is None.
    """
    if fn is None:

        def decorator(f: Callable) -> Tool:
            return Tool.from_callable(f, dependencies or [])

        return decorator

    return Tool.from_callable(fn, dependencies or [])


__all__ = ["Tool", "tool"]


def _load_module_from_path(path: Path) -> object:
    """Load a Python module from a file path.

    Args:
        path: Path to the Python file to load.

    Returns:
        The loaded module.

    Raises:
        ImportError: If the module cannot be loaded.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        msg = f"Cannot load module from {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
