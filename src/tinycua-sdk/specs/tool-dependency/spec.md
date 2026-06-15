# Specification: Tool Dependency Resolution

## Problem Statement

When deploying agents with custom tools to the backend, tools may depend on:
1. **External dependencies**: Python packages (e.g., `requests`, `pandas`)
2. **Internal dependencies**: Other custom tools defined in the same agent

Currently, the SDK only supports external dependencies via `@tool(dependencies=[...])`. There's no mechanism to:
- Automatically detect internal tool dependencies from source code
- Resolve and bundle all required tools before sending to the runner
- Track tool versions to avoid re-uploading unchanged tools
- Detect circular dependencies at deploy time

## Scope

### Included
- Auto-detection of internal tool dependencies via AST analysis
- External dependency detection (existing) + internal dependency detection (new)
- Circular dependency detection at deploy time
- Version tracking (hash of source + dependencies)
- Optimized upload: skip tools with matching version
- Topological sort: upload dependencies before dependent tools
- Backend tool CRUD APIs
- Runner receives fully bundled tools (no runtime fetching)

### Excluded
- Runtime tool dependency resolution (backend handles at deploy time)
- Persistent tool registry in runner (stateless)
- Plugin discovery at runner startup

---

## Requirements

### FR-001: Tool Model Enhancement
`Tool` dataclass must have:
- `_external_dependencies: list[str]` - pip packages
- `_tool_dependencies: list[dict]` - internal deps: `[{"id": "uuid", "name": "tool_name", "version": "hash"}]`
- `_version: str` - hash of source + dependency versions

### FR-002: Tool Bundle Serialization
`Tool.to_bundle() -> dict` must include:
```python
{
    "name": str,
    "description": str,
    "parameters": dict,
    "source": str,
    "external_dependencies": list[str],
    "tool_dependencies": list[dict],  # NEW
    "version": str,  # NEW
}
```

### FR-003: External Dependency Detection
When `@tool` decorator processes a function, it must:
- Parse source AST
- Extract `import X` and `from X import Y` statements
- Filter out standard library modules
- Store result in `_external_dependencies`

### FR-004: Internal Dependency Detection
When deploying an agent, the SDK must:
- Scan all tools in the agent
- For each tool, parse AST to find function calls
- Match calls against other tool names in the agent
- Also query backend for existing tools to detect matches
- Store matches as `_tool_dependencies`

### FR-005: Circular Dependency Detection
Deploy must fail with clear error if circular dependency detected:
- A → B → A
- A → B → C → A
Error message: "Circular dependency detected: A → B → A"

### FR-006: Version Tracking
- Version = SHA256(source code + sorted(tool_dependency_versions))
- Generated at deploy time before upload
- Stored in backend Tool model

### FR-007: Optimized Upload
When deploying:
1. Query backend for existing tools and versions
2. For each tool to upload:
   - Compute version
   - If version matches backend → SKIP
   - Else → UPLOAD
3. Upload in topological order (dependencies first)

### FR-008: Backend Tool CRUD
Backend must provide:
- `GET /v1/tools` - list all tools (with version)
- `GET /v1/tools/{tool_id}` - get tool by ID
- `POST /v1/tools` - create tool
- `PUT /v1/tools/{tool_id}` - update tool
- `DELETE /v1/tools/{tool_id}` - delete tool

All endpoints require tenant isolation.

### FR-009: Run Endpoint Dependency Resolution
When backend receives `/run` request:
1. Load agent + tools from DB
2. For each tool, resolve tool_dependencies:
   - Fetch dependency tools from DB
   - Add to request bundle
3. Send to runner:
   - Agent config
   - ALL tools (agent tools + all dependencies)
   - db_url for session context

### FR-010: Runner Receives Bundled Tools
Runner receives all required tools in the execution request:
- No runtime fetching needed
- Tools registered to local registry
- Execute with resolved dependencies

---

## Example Usage

### Define tools with dependencies

```python
from tinycua_sdk.tools import tool
from tinycua_sdk import Agent

@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@tool
def calculate_and_format(a: int, b: int) -> str:
    """Calculate and return formatted result."""
    result = calculate(a, b)  # internal dependency
    return f"Result: {result}"

agent = Agent(
    name="math-agent",
    instructions="You are a math assistant.",
    tools=[calculate_and_format],  # calculate is auto-detected as dependency
)
```

### Deploy with auto-resolution

```python
await agent.deploy(client)
# Internally:
# 1. Detects calculate_and_format depends on calculate
# 2. No circular deps
# 3. Version hash computed
# 4. Uploads calculate first, then calculate_and_format
# 5. Backend stores tool_dependencies metadata
```

### Run deployed agent

```python
response = await agent.run("What is 5 + 3?")
# Backend resolves dependencies before sending to runner
# Runner receives both tools in bundle
```

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Tool calls unknown function | Ignored (not a registered tool) |
| Tool B updated, A depends on B | A must be redeployed (version mismatch) |
| Circular dependency | Deploy fails with error |
| Backend tool already exists with same version | Skip upload |
| Tool depends on deleted tool | Runtime error when executing |

---

## Acceptance Scenarios

### Scenario 1: External dependency detection
```
Given: @tool with "import requests" in source
When: Tool is bundled via to_bundle()
Then: external_dependencies contains "requests"
```

### Scenario 2: Internal dependency detection
```
Given: Tool A calls function "tool_b", and tool_b exists in agent
When: agent.deploy() is called
Then: A.tool_dependencies contains {"name": "tool_b", ...}
```

### Scenario 3: Circular dependency detection
```
Given: Tool A depends on B, B depends on A
When: agent.deploy() is called
Then: Raises CircularDependencyError with path "A → B → A"
```

### Scenario 4: Version tracking
```
Given: Tool with source "def foo(): return 1"
When: version is computed
Then: version is consistent SHA256 hash
```

### Scenario 5: Skip unchanged tools
```
Given: Tool "foo" with version "abc123" exists in backend
When: Deploy same tool (version "abc123")
Then: Tool is NOT uploaded (skipped)
```

### Scenario 6: Run bundles dependencies
```
Given: Agent has tool A (depends on tool B)
When: POST /run is called
Then: Request to runner includes BOTH tool A and tool B
```

---

## Testing Plan

- Unit: AST parsing for external deps detection
- Unit: Internal dep detection with mock known tools
- Unit: Circular dependency DFS detection
- Unit: Version hash consistency
- Unit: Topological sort order
- Integration: Full deploy flow with mock backend
- Integration: Run endpoint bundles all deps
