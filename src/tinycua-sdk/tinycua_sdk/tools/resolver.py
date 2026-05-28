"""Tool dependency resolution utilities."""

from __future__ import annotations

import ast
import hashlib
from typing import Any

STDLIB_MODULES: set[str] = {
    "os",
    "sys",
    "json",
    "datetime",
    "time",
    "re",
    "collections",
    "itertools",
    "functools",
    "operator",
    "random",
    "math",
    "typing",
    "uuid",
    "logging",
    "traceback",
    "warnings",
    "contextlib",
    "pathlib",
    "abc",
    "copy",
    "io",
    "pickle",
    "sqlite3",
    "csv",
    "xml",
    "html",
    "urllib",
    "base64",
    "binascii",
    "struct",
    "codecs",
    "locale",
    "gettext",
    "threading",
    "multiprocessing",
    "concurrent",
    "asyncio",
    "subprocess",
    "socket",
    "ssl",
    "signal",
    "platform",
    "errno",
    "ctypes",
    "gc",
    "weakref",
    "types",
    "inspect",
    "dis",
    "compile",
    "ast",
    "fractions",
    "decimal",
}


def _is_external_module(module: str) -> bool:
    """Check if a module is external (not stdlib or tinycua internal)."""
    if module in STDLIB_MODULES:
        return False
    if module.startswith("tinycua"):
        return False
    return True


def analyze_source(source: str) -> list[str]:
    """Extract external dependencies from source AST.

    Parses the source code and extracts import statements,
    filtering out standard library modules and internal tinycua packages.

    Args:
        source: Python source code as string

    Returns:
        Sorted list of external (non-stdlib) module names
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if _is_external_module(module):
                    imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if _is_external_module(module):
                    imports.add(module)

    return sorted(imports)


def find_internal_calls(source: str) -> set[str]:
    """Find function calls in source that might be internal tools.

    Parses the source and extracts function/method call names.

    Args:
        source: Python source code as string

    Returns:
        Set of function call names found in the source
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    calls: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)

    return calls


def detect_circular(
    tools: list[Any],
    tool_map: dict[str, Any],
) -> list[str] | None:
    """Detect circular dependencies using DFS.

    Args:
        tools: List of Tool objects
        tool_map: Dict mapping tool names to Tool objects

    Returns:
        Cycle path if found (e.g., ["A", "B", "A"]), None otherwise
    """
    graph: dict[str, set[str]] = {}

    for tool in tools:
        deps: set[str] = set()
        for td in tool._tool_dependencies:
            deps.add(td.get("name", ""))
        graph[tool.name] = deps

    visited: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        if node in visited:
            idx = path.index(node)
            return path[idx:] + [node]

        visited.add(node)
        path.append(node)

        for dep in graph.get(node, set()):
            if dep in tool_map:
                result = dfs(dep)
                if result:
                    return result

        path.pop()
        return None

    for tool in tools:
        visited.clear()
        path.clear()
        cycle = dfs(tool.name)
        if cycle:
            return cycle

    return None


def compute_version(source: str, tool_deps: list[dict[str, Any]]) -> str:
    """Compute version hash from source and dependency versions.

    Args:
        source: Tool source code
        tool_deps: List of tool dependencies with versions

    Returns:
        16-character SHA256 hash
    """
    dep_versions = sorted([td.get("version", "") for td in tool_deps])
    content = source + "|" + "|".join(dep_versions)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def topological_sort(tools: list[Any]) -> list[Any]:
    """Sort tools so dependencies come first.

    Uses Kahn's algorithm for topological sorting.

    Args:
        tools: List of Tool objects

    Returns:
        Sorted list of tools
    """
    if not tools:
        return []

    graph: dict[str, set[str]] = {}
    in_degree: dict[str, int] = {}

    for tool in tools:
        deps = {td.get("name", "") for td in tool._tool_dependencies}
        graph[tool.name] = deps
        in_degree[tool.name] = len(deps)

    queue = [name for name, degree in in_degree.items() if degree == 0]
    result: list[Any] = []

    while queue:
        node = queue.pop(0)
        result.append(node)

        for tool in tools:
            if node in graph.get(tool.name, set()):
                in_degree[tool.name] -= 1
                if in_degree[tool.name] == 0:
                    queue.append(tool.name)

    tool_dict = {t.name: t for t in tools}
    return [tool_dict[name] for name in result if name in tool_dict]


__all__ = [
    "analyze_source",
    "find_internal_calls",
    "detect_circular",
    "compute_version",
    "topological_sort",
]
