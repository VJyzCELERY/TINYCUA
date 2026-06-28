"""Tool model and decorator."""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
import types
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

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make Tool instances callable.

        Delegates to :meth:`invoke`, allowing tools to be called directly
        (e.g. ``read_file(path="...")``) as well as through
        ``ToolExecutor.execute()``.

        Supports both positional and keyword arguments. When positional
        args are provided, they are matched to the underlying function's
        parameter names.
        """
        if args and self._callable is not None:
            sig = inspect.signature(self._callable)
            param_names = list(sig.parameters.keys())
            for i, arg in enumerate(args):
                if i < len(param_names):
                    kwargs[param_names[i]] = arg
        return self.invoke(**kwargs)

    def invoke(self, **kwargs: Any) -> Any:
        """Invoke the tool function with keyword arguments.

        Coerces each argument to its JSON-schema-declared type first, because
        local models routinely emit ints/bools as strings (e.g. ``"7"`` for an
        ``integer`` param) which would otherwise crash the tool
        (``'<' not supported between str and int``). Scalars, strings, arrays,
        and objects are all coerced; an uncoercible value raises a clear error
        instead of a confusing TypeError deep in the tool.
        """
        if self._callable is None:
            raise RuntimeError(f"Tool {self.name} has no function to invoke")
        properties = self.parameters.get("properties") if isinstance(self.parameters, dict) else None
        if isinstance(properties, dict) and properties:
            coerced: dict[str, Any] = {}
            for key, value in kwargs.items():
                schema = properties.get(key)
                if isinstance(schema, dict):
                    coerced[key] = _coerce_arg(value, schema)
                else:
                    coerced[key] = value
            return self._callable(**coerced)
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

        If *path* itself contains loadable ``.py`` files (i.e. is a single
        tool package), it is scanned directly. Otherwise each immediate
        subdirectory is treated as a package.

        Args:
            path: Path to the directory containing tool subdirectories.

        Returns:
            List of Tool instances found.
        """
        tools: list[Tool] = []
        path = Path(path)
        py_files = sorted(path.glob("*.py"))
        non_private = [f for f in py_files if not f.name.startswith("_")]

        targets: list[Path] = []
        if non_private:
            targets.append(path)
        targets.extend(p for p in sorted(path.iterdir()) if p.is_dir())

        for target in targets:
            global _load_counter
            _load_counter += 1
            uid = str(_load_counter)
            package_name = f"__tinycua_tools_{uid}"
            pkg = types.ModuleType(package_name)
            pkg.__path__ = [str(target)]
            pkg.__package__ = package_name
            sys.modules[package_name] = pkg
            for py_file in sorted(target.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue
                module = _load_module_from_path(py_file, package_name=package_name)
                for _name, obj in inspect.getmembers(module):
                    if isinstance(obj, Tool):
                        tools.append(obj)
        return tools

    @classmethod
    def from_callable(
        cls,
        fn: Callable,
        dependencies: list[str] | None = None,
        *,
        name: str | None = None,
    ) -> "Tool":
        """Create a Tool from a function by inspecting its signature and docstring.

        Args:
            fn: The function to convert into a Tool.
            dependencies: Optional list of external dependency names.
            name: Optional override for the tool name (defaults to function name).

        Returns:
            A Tool instance with generated schema.

        """
        sig = inspect.signature(fn)
        docstring = fn.__doc__ or ""

        # Resolve PEP 563 string annotations (``from __future__ import
        # annotations`` makes ``param.annotation`` a str like "int"). Only
        # swap in the evaluated hint when the raw annotation is a string —
        # otherwise keep the raw annotation so Annotated/Union/Optional
        # metadata (e.g. Annotated[str, "description"]) survives for
        # ``type_to_json_schema`` to extract.
        try:
            from typing import get_type_hints

            hints = get_type_hints(fn, include_extras=True)
        except Exception:  # noqa: BLE001 - best-effort; signature fallback below.
            hints = {}

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
            raw_annotation = param.annotation
            annotation = hints.get(param_name, raw_annotation)
            # Only use the evaluated hint when the raw annotation was a PEP 563
            # string; otherwise prefer the raw annotation (preserves Annotated
            # metadata and already-resolved type objects).
            if isinstance(raw_annotation, str) and annotation is not raw_annotation:
                pass
            else:
                annotation = raw_annotation
            schema = type_to_json_schema(annotation)
            params[param_name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        for param_name, desc in param_descriptions.items():
            if param_name in params:
                params[param_name]["description"] = desc

        # Use first line of docstring as description
        first_line = docstring.strip().split("\n")[0] if docstring.strip() else ""

        return cls(
            name=name or fn.__name__,
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
    name: str | None = None,
    dependencies: list[str] | None = None,
) -> Tool | Callable[[Callable], Tool]:
    """Decorator to convert a function into a Tool.

    Usage:
        @tool
        def func(): ...

        @tool()
        def func(): ...

        @tool(name="custom_name")
        def func(): ...

        @tool(dependencies=["requests"])
        def func(): ...

    Args:
        fn: The function to convert. If None, returns a decorator.
        name: Optional override for the tool name (defaults to function name).
        dependencies: Optional list of external dependency package names.

    Returns:
        A Tool instance, or a decorator function if fn is None.
    """
    if fn is None:

        def decorator(f: Callable) -> Tool:
            return Tool.from_callable(f, name=name, dependencies=dependencies or [])

        return decorator

    return Tool.from_callable(fn, name=name, dependencies=dependencies or [])


__all__ = ["Tool", "tool"]


_TRUE_STRINGS = frozenset({"true", "1", "yes", "on"})
_FALSE_STRINGS = frozenset({"false", "0", "no", "off", ""})


def _coerce_arg(value: Any, schema: dict[str, Any]) -> Any:
    """Coerce a value to its JSON-schema-declared type.

    Local models routinely emit ints/bools/numbers as strings. This keeps
    typed tools (``integer``/``number``/``boolean``) working instead of
    crashing on ``"7" < 1``. Strings, arrays, and objects are also coerced
    so a value that already matches passes through unchanged.

    Coercion is best-effort: an uncoercible scalar (e.g. ``"abc"`` for
    ``integer``) is returned unchanged so the tool's own validation produces a
    clean, tool-specific error instead of a generic ValueError from the SDK.

    ``null``/``None`` is passed through (the tool decides what a missing
    value means).
    """
    if value is None:
        return None
    declared = schema.get("type")
    if isinstance(declared, list):
        # nullable/union schemas: pick the first non-null type that fits.
        for candidate in declared:
            if candidate == "null":
                continue
            try:
                return _coerce_arg(value, {"type": candidate, **{k: v for k, v in schema.items() if k != "type"}})
            except ValueError:
                continue
        return value
    try:
        if declared == "integer":
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            if isinstance(value, str):
                return int(value.strip())
            return value
        if declared == "number":
            # ponytail: int is a valid number — keep it as int (tools like
            # fetch_url slice body[:max_size], which rejects a float). Only
            # float a value that is actually fractional.
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return value
            if isinstance(value, str):
                stripped = value.strip()
                return int(stripped) if stripped.lstrip("-+").isdigit() else float(stripped)
            return value
        if declared == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in _TRUE_STRINGS:
                    return True
                if normalized in _FALSE_STRINGS:
                    return False
            return value
        if declared == "string":
            if isinstance(value, str):
                return value
            if isinstance(value, (int, float, bool)):
                return str(value)
            return value
        if declared == "array":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                import json

                stripped = value.strip()
                if stripped.startswith("["):
                    try:
                        parsed = json.loads(stripped)
                    except json.JSONDecodeError:
                        return value
                    return parsed if isinstance(parsed, list) else value
            return value
        if declared == "object":
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                import json

                stripped = value.strip()
                if stripped.startswith("{"):
                    try:
                        parsed = json.loads(stripped)
                    except json.JSONDecodeError:
                        return value
                    return parsed if isinstance(parsed, dict) else value
            return value
    except (TypeError, ValueError):
        return value
    return value


_load_counter: int = 0


def _load_module_from_path(path: Path, package_name: str | None = None) -> object:
    """Load a Python module from a file path with optional package context.

    Args:
        path: Path to the Python file to load.
        package_name: If provided, the module is loaded as a child of this
            package, enabling relative imports.

    Returns:
        The loaded module.

    Raises:
        ImportError: If the module cannot be loaded.
    """
    module_name = f"{package_name}.{path.stem}" if package_name else path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        msg = f"Cannot load module from {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    if package_name:
        module.__package__ = package_name
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    # ponytail: self-check — coercion of every supported type.
    assert _coerce_arg("7", {"type": "integer"}) == 7
    assert _coerce_arg(7.0, {"type": "integer"}) == 7
    assert _coerce_arg(True, {"type": "integer"}) == 1
    assert _coerce_arg("3.5", {"type": "number"}) == 3.5
    assert _coerce_arg(7, {"type": "number"}) == 7  # int stays int (slice-safe)
    assert isinstance(_coerce_arg("8", {"type": "number"}), int)
    assert isinstance(_coerce_arg("8.0", {"type": "number"}), float)
    assert _coerce_arg("true", {"type": "boolean"}) is True
    assert _coerce_arg("0", {"type": "boolean"}) is False
    assert _coerce_arg(7, {"type": "string"}) == "7"
    assert _coerce_arg('["a", "b"]', {"type": "array"}) == ["a", "b"]
    assert _coerce_arg('{"x": 1}', {"type": "object"}) == {"x": 1}
    assert _coerce_arg(None, {"type": "integer"}) is None
    assert _coerce_arg("abc", {"type": "integer"}) == "abc"  # uncoercible passes through
    print("ok")
