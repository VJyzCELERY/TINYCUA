# Design: Tool Dependency Resolution

## Overview

This document describes the implementation design for tool dependency resolution in TINYCUA. It covers the data models, API changes, and sequence flows.

---

## Data Models

### SDK: Tool Dataclass (`tools/decorators.py`)

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    _fn: Callable | None = field(default=None, repr=False)
    _source: str | None = field(default=None, repr=False)
    _dependencies: list[str] = field(default_factory=list)  # external pip packages
    _tool_dependencies: list[dict] = field(default_factory=list)  # NEW: internal deps
    _version: str | None = field(default=None, repr=False)  # NEW: hash
    _is_builtin: bool = False

    def to_bundle(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "source": self._source,
            "external_dependencies": self._dependencies,
            "tool_dependencies": self._tool_dependencies,
            "version": self._version,
        }

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> Tool:
        return cls(
            name=data["name"],
            description=data["description"],
            parameters=data.get("parameters", {}),
            _tool_dependencies=data.get("tool_dependencies", []),
            _version=data.get("version"),
        )
```

### Backend: Tool Model (`models/tool.py`)

```python
class Tool(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tools"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)
    source: Mapped[str] = mapped_column(String(50000), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # NEW fields:
    external_dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    tool_dependencies: Mapped[list[dict]] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(64), nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="tools")
```

---

## API Changes

### SDK: BackendClient (`clients/backend.py`)

```python
class BackendClient:
    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools in backend with versions."""
        
    async def get_tool(self, tool_id: str) -> dict[str, Any]:
        """Get a specific tool by ID."""
        
    async def deploy_tool(self, tool_bundle: dict[str, Any]) -> dict[str, Any]:
        """Deploy a tool bundle to backend."""
```

### Backend: Tools Router (`routers/tools.py`)

```python
@router.get("/tools", response_model=list[ToolResponse])
async def list_tools(tenant_id: str = Depends(get_tenant_id)):
    """List all tools for tenant."""
    
@router.get("/tools/{tool_id}", response_model=ToolResponse)
async def get_tool(tool_id: str, tenant_id: str = Depends(get_tenant_id)):
    """Get a specific tool."""
    
@router.post("/tools", response_model=ToolResponse)
async def create_tool(
    tool: ToolCreate,
    tenant_id: str = Depends(get_tenant_id),
):
    """Create a new tool."""
    
@router.put("/tools/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    tool: ToolUpdate,
    tenant_id: str = Depends(get_tenant_id),
):
    """Update an existing tool."""
    
@router.delete("/tools/{tool_id}")
async def delete_tool(
    tool_id: str,
    tenant_id: str = Depends(get_tenant_id),
):
    """Delete a tool."""
```

---

## Sequence Diagrams

### Deploy Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Developer│     │   SDK   │     │ Backend │     │   DB   │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │ agent.deploy()               │               │
     │──────────────>│               │               │
     │               │               │               │
     │               │ GET /v1/tools │               │
     │               │──────────────>│               │
     │               │<───────────────│               │
     │               │  [tool list]  │               │
     │               │               │               │
     │               │ analyze_dependencies()        │
     │               │ (AST parsing)  │               │
     │               │               │               │
     │               │ detect_circular()             │
     │               │               │               │
     │               │ compute_version()             │
     │               │               │               │
     │               │ topological_sort()            │
     │               │               │               │
     │               │ POST /v1/tools (dep 1)         │
     │               │──────────────>│               │
     │               │<───────────────│               │
     │               │               │               │
     │               │ POST /v1/tools (dep 2)         │
     │               │──────────────>│               │
     │               │<───────────────│               │
     │               │               │               │
     │               │ POST /v1/tools (main tool)     │
     │               │──────────────>│               │
     │               │<───────────────│               │
     │               │               │               │
     │<──────────────│ {agent_id}    │               │
     │               │               │               │
```

### Run Flow (Dependency Resolution)

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Client │     │ Backend │     │   DB    │     │ Runner  │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │ POST /run    │               │               │
     │─────────────>│               │               │
     │               │               │               │
     │               │ Load agent + tools          │
     │               │─────────────>│               │
     │               │<─────────────│               │
     │               │               │               │
     │               │ For each tool:               │
     │               │   resolve_dependencies()     │
     │               │   (fetch from DB)            │
     │               │               │               │
     │               │ Bundle all tools             │
     │               │               │               │
     │               │ POST /internal/run           │
     │               │─────────────────────────────>│
     │               │               │               │
     │               │               │  [bundle]     │
     │               │               │               │
     │<─────────────│               │               │
     │               │               │               │
```

---

## Dependency Resolution Logic

### 1. AST Analysis (`tools/resolver.py`)

```python
import ast
import hashlib

STDLIB_MODULES = {
    "os", "sys", "json", "datetime", "time", "re", "collections",
    "itertools", "functools", "operator", "random", "math", "typing",
    "uuid", "logging", "traceback", "warnings", "contextlib",
}

def analyze_source(source: str) -> list[str]:
    """Extract external dependencies from source AST."""
    tree = ast.parse(source)
    imports = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module not in STDLIB_MODULES:
                    imports.add(module)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.split(".")[0]
                if module not in STDLIB_MODULES:
                    imports.add(module)
    
    return sorted(imports)

def find_internal_calls(source: str) -> set[str]:
    """Find function calls that might be internal tools."""
    tree = ast.parse(source)
    calls = set()
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    
    return calls
```

### 2. Circular Detection

```python
def detect_circular(
    tools: list[Tool],
    known_tools: set[str],
) -> list[str] | None:
    """DFS to detect circular dependencies.
    
    Returns cycle path if found, None otherwise.
    """
    graph = {}
    for tool in tools:
        deps = set()
        for td in tool._tool_dependencies:
            deps.add(td["name"])
        graph[tool.name] = deps
    
    def dfs(node: str, visited: set[str], path: list[str]) -> list[str] | None:
        if node in visited:
            return path + [node]
        visited.add(node)
        path.append(node)
        
        for dep in graph.get(node, set()):
            result = dfs(dep, visited.copy(), path.copy())
            if result:
                return result
        return None
    
    for tool in tools:
        cycle = dfs(tool.name, set(), [])
        if cycle:
            return cycle
    return None
```

### 3. Version Computation

```python
def compute_version(source: str, tool_deps: list[dict]) -> str:
    """Compute version hash from source + dependency versions."""
    dep_versions = sorted([td.get("version", "") for td in tool_deps])
    content = source + "|" + "|".join(dep_versions)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

### 4. Topological Sort

```python
def topological_sort(tools: list[Tool]) -> list[Tool]:
    """Sort tools so dependencies come first."""
    graph = {t.name: [td["name"] for td in t._tool_dependencies] for t in tools}
    in_degree = {t.name: len(graph[t.name]) for t in tools}
    queue = [t.name for t in tools if in_degree[t.name] == 0]
    result = []
    
    while queue:
        node = queue.pop(0)
        result.append(node)
        
        for tool in tools:
            if node in graph.get(tool.name, []):
                in_degree[tool.name] -= 1
                if in_degree[tool.name] == 0:
                    queue.append(tool.name)
    
    return [t for t in tools if t.name in result]
```

---

## Component Structure

### New Module: `tools/resolver.py`

```
tinycua_sdk/
├── tools/
│   ├── __init__.py
│   ├── decorators.py      # Tool class (updated)
│   ├── resolver.py        # NEW: dependency resolution
│   └── ...
```

### Updated Files

| File | Changes |
|------|---------|
| `tools/decorators.py` | Add `_tool_dependencies`, `_version` fields, update `to_bundle()` |
| `tools/resolver.py` | NEW - analyze, detect_circular, compute_version, topological_sort |
| `agent/agent.py` | Update `deploy()` with resolution logic |
| `clients/backend.py` | Add `list_tools()`, `get_tool()`, `deploy_tool()` |
| `models/tool.py` | Add `external_dependencies`, `tool_dependencies`, `version` |
| `routers/tools.py` | NEW - CRUD endpoints |

---

## Open Questions

None - all resolved in spec.
