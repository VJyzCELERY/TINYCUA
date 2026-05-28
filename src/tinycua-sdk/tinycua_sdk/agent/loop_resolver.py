"""Loop dependency resolution utilities."""

from __future__ import annotations

import ast
import inspect
from typing import Any


def analyze_loop_source(source: str) -> tuple[list[str], list[dict[str, str]]]:
    """Extract dependencies and helper functions from loop source.

    Args:
        source: Python source code of the loop class

    Returns:
        Tuple of (external_dependencies, helpers)
        - external_dependencies: List of pip package names
        - helpers: List of helper function dicts with name and source
    """
    from tinycua_sdk.tools.resolver import analyze_source as analyze_tool_source

    # Get external dependencies (same as tools)
    dependencies = analyze_tool_source(source)

    # Find helper functions (non-async functions defined in the source)
    helpers = extract_helper_functions(source)

    return dependencies, helpers


def extract_helper_functions(source: str) -> list[dict[str, str]]:
    """Extract helper functions from source code.

    Finds function definitions (not async, not the run method)
    that can be used as helpers in the loop.

    Args:
        source: Python source code

    Returns:
        List of dicts with 'name' and 'source' for each helper function
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    helpers = []

    for node in ast.walk(tree):
        # Look for FunctionDef (not async def)
        if isinstance(node, ast.FunctionDef):
            # Skip the 'run' method
            if node.name == "run":
                continue

            # Get the source code for this function
            try:
                func_source = ast.get_source_segment(source, node)
                if func_source:
                    helpers.append(
                        {
                            "name": node.name,
                            "source": func_source,
                        }
                    )
            except (ValueError, TypeError):
                # Fallback: reconstruct from AST
                func_source = f"def {node.name}("
                args = [arg.arg for arg in node.args.args]
                func_source += ", ".join(args) + "):"
                # This is simplified - full implementation would need more AST traversal
                helpers.append(
                    {
                        "name": node.name,
                        "source": f"def {node.name}(): pass",  # Placeholder
                    }
                )

    return helpers


def extract_loop_source(
    loop_instance: Any,
) -> tuple[str, list[str], list[dict[str, str]]]:
    """Extract source code from a loop instance.

    Args:
        loop_instance: An instance of DefaultLoop subclass

    Returns:
        Tuple of (class_source, dependencies, helpers)
    """
    cls = loop_instance.__class__

    # Get the source code of the class
    try:
        class_source = inspect.getsource(cls)
    except (OSError, TypeError):
        class_source = ""

    # Analyze the source
    dependencies, helpers = analyze_loop_source(class_source)

    return class_source, dependencies, helpers


__all__ = [
    "analyze_loop_source",
    "extract_helper_functions",
    "extract_loop_source",
]
