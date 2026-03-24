"""Tool model and decorator."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    """A tool that can be invoked by the agent."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    _fn: Callable | None = field(default=None, repr=False)
    _source: str | None = field(default=None, repr=False)
    _external_dependencies: list[str] = field(default_factory=list)
    _tool_dependencies: list[dict[str, Any]] = field(default_factory=list)
    _version: str | None = field(default=None, repr=False)
    _is_builtin: bool = False
    allowed_in_plan_mode: bool = True

    def to_config(self) -> dict[str, Any]:
        """Return tool descriptor for API."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "allowed_in_plan_mode": self.allowed_in_plan_mode,
        }

    def to_bundle(self) -> dict[str, Any]:
        """Return full deployment bundle."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "source": self._source,
            "external_dependencies": self._external_dependencies,
            "tool_dependencies": self._tool_dependencies,
            "version": self._version,
            "allowed_in_plan_mode": self.allowed_in_plan_mode,
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> Tool:
        """Reconstruct tool from config."""
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=data.get("parameters", {}),
            _tool_dependencies=data.get("tool_dependencies", []),
            _version=data.get("version"),
            allowed_in_plan_mode=data.get("allowed_in_plan_mode", True),
        )

    def invoke(self, **kwargs: Any) -> Any:
        """Invoke the tool function."""
        import asyncio

        if self._fn is None:
            raise RuntimeError(f"Tool {self.name} has no function to invoke")
        result = self._fn(**kwargs)
        if asyncio.iscoroutine(result):
            try:
                asyncio.get_running_loop()
                return result
            except RuntimeError:
                return asyncio.run(result)
        return result


def _make_tool(fn: Callable, dependencies: list[str]) -> Tool:
    """Create a Tool from a function."""
    sig = inspect.signature(fn)
    description = fn.__doc__ or ""

    params = {}
    for param_name, param in sig.parameters.items():
        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is float:
                param_type = "number"
            elif param.annotation is bool:
                param_type = "boolean"
            elif hasattr(param.annotation, "__origin__"):
                param_type = "string"

        params[param_name] = {
            "type": param_type,
            "description": "",
        }
        if param.default is not inspect.Parameter.empty:
            params[param_name]["default"] = param.default

    source = inspect.getsource(fn)

    return Tool(
        name=fn.__name__,
        description=description.strip().split("\n")[0],
        parameters={
            "type": "object",
            "properties": params,
            "required": [
                p.name
                for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
            ],
        },
        _fn=fn,
        _source=source,
        _external_dependencies=dependencies,
    )


def tool(
    dependencies: list[str] | Callable | None = None,
) -> Callable[[Callable], Tool] | Tool:
    """Decorator to convert a function into a Tool.

    Usage:
        @tool
        def func(): ...

        @tool()
        def func(): ...

        @tool(dependencies=["requests"])
        def func(): ...
    """
    if callable(dependencies):
        return _make_tool(dependencies, [])

    _external_deps = dependencies or []

    def decorator(fn: Callable) -> Tool:
        return _make_tool(fn, _external_deps)

    return decorator


__all__ = ["Tool", "tool"]
