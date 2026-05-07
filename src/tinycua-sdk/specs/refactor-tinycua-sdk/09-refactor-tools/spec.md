# Stage 09 — Refactor Tools Framework

## Objective

Clean up the `tools/` package to contain only the framework (decorator, schema, parser, resolver) and generic built-in tools. Remove memory-dependent tools.

## Files to Delete

| File | Reason |
|------|--------|
| `tools/memory.py` | MemoryBackend hierarchy — stateful |
| `tools/memory_tools.py` | remember, recall, forget — depend on memory |

## Files to Keep

| File | Purpose |
|------|---------|
| `tools/decorators.py` | `@tool` decorator, `Tool` dataclass |
| `tools/schema.py` | JSON-schema generation |
| `tools/parser.py` | Source parsing |
| `tools/resolver.py` | Dependency resolution (pure functions) |
| `tools/mcp.py` | MCP integration |
| `tools/cua/` | CUA sub-package |
| `tools/native/context_tools.py` | Generic context utilities |

## Code Changes

### Update tools/__init__.py

Remove exports for deleted modules:
```python
# Remove these exports:
# - MemoryBackend
# - LocalMemoryBackend
# - HybridMemoryBackend
# - get_memory_backend
# - set_memory_backend
# - reset_memory_backend
# - remember
# - recall
# - forget
# - list_memory
# - clear_memory
```

### Flatten tools/native/

Move generic tool implementations to `tools/native/`.

## Acceptance Criteria

- [ ] `tools/memory.py` does not exist.
- [ ] `tools/memory_tools.py` does not exist.
- [ ] `tools/__init__.py` does not export memory-related symbols.
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 08
