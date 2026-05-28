# Middleware Documentation

The `middleware/` package provides a hook-based middleware system for intercepting tool calls.

**Package path:** `tinycua_sdk/middleware/`

---

## hooks.py - Middleware Hook System

### Purpose

Provides a class-based hook system for executing code before and after tool calls. This is distinct from the `agent/hooks.py` system (which hooks into agent loops) - this system hooks into individual tool invocations.

### HookContext Dataclass

```python
@dataclass
class HookContext:
    tool_name: str
    parameters: dict[str, Any]
    session_id: uuid.UUID | None = None
    messages: list[Message] = field(default_factory=list)
```

**Fields:**
- `tool_name`: Name of the tool being called
- `parameters`: Arguments passed to the tool
- `session_id`: Optional session identifier for context
- `messages`: Current conversation message list

### HookResult Dataclass

```python
@dataclass
class HookResult:
    modified: bool = False
    parameters: dict[str, Any] | None = None
    result: Any = None
    error: str | None = None
```

**Fields:**
- `modified`: Whether the hook changed anything
- `parameters`: Modified parameters (for pre-hooks)
- `result`: Modified result (for post-hooks)
- `error`: Error message if hook failed

### HookError

```python
class HookError(Exception):
    """Raised when hook execution fails."""
```

### Hook Base Class

```python
class Hook:
    def pre_call(self, context: HookContext) -> HookResult:
        return HookResult(modified=False, parameters=None, result=None, error=None)
    
    def post_call(self, context: HookContext, result: Any) -> HookResult:
        return HookResult(modified=False, parameters=None, result=result, error=None)
```

**Subclassing pattern:**
```python
class LoggingHook(Hook):
    def pre_call(self, context: HookContext) -> HookResult:
        print(f"Calling {context.tool_name} with {context.parameters}")
        return HookResult()
    
    def post_call(self, context: HookContext, result: Any) -> HookResult:
        print(f"Result: {result}")
        return HookResult(result=result)
```

### HookRegistry

```python
class HookRegistry:
    def __init__(self):
        self._pre_hooks: list[tuple[int, Hook]] = []
        self._post_hooks: list[tuple[int, Hook]] = []
```

**Priority-based ordering:** Hooks are stored as `(priority, hook)` tuples and sorted by priority (lower runs first).

### Registration

```python
def register_pre_hook(self, hook: Hook, priority: int = 100) -> None:
    self._pre_hooks.append((priority, hook))
    self._pre_hooks.sort(key=lambda x: x[0])

def register_post_hook(self, hook: Hook, priority: int = 100) -> None:
    self._post_hooks.append((priority, hook))
    self._post_hooks.sort(key=lambda x: x[0])
```

Re-sorts after each registration. This is O(n log n) but registration is typically infrequent.

### Execution

```python
def execute_pre_hooks(self, context: HookContext) -> HookContext:
    for _, hook in self._pre_hooks:
        try:
            result = hook.pre_call(context)
            
            if result.error:
                raise HookError(f"Pre-hook error: {result.error}")
            
            if result.modified and result.parameters is not None:
                context.parameters = result.parameters
        
        except HookError:
            raise
        except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as e:
            raise HookError(f"Pre-hook failed: {e}")
    
    return context
```

**Execution flow:**
1. Iterate pre-hooks in priority order
2. Call `pre_call(context)`
3. If error returned, raise `HookError`
4. If modified, update `context.parameters`
5. Catch unexpected exceptions and wrap in `HookError`

```python
def execute_post_hooks(self, context: HookContext, result: Any) -> Any:
    for _, hook in self._post_hooks:
        try:
            hook_result = hook.post_call(context, result)
            
            if hook_result.error:
                raise HookError(f"Post-hook error: {hook_result.error}")
            
            if hook_result.modified and hook_result.result is not None:
                result = hook_result.result
        
        except HookError:
            raise
        except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as e:
            raise HookError(f"Post-hook failed: {e}")
    
    return result
```

**Why wrap exceptions in HookError?** Provides a single exception type for callers to catch, regardless of what specific error occurred inside a hook.

---

## Comparison: middleware/hooks.py vs agent/hooks.py

| Aspect | middleware/hooks.py | agent/hooks.py |
|--------|---------------------|----------------|
| **Scope** | Individual tool calls | Agent execution loops |
| **Hook type** | Class-based (`Hook`) | Function-based (`HookFunc`) |
| **Context** | `HookContext` (tool-focused) | `dict[str, Any]` (agent-focused) |
| **Timing** | Pre/post tool call | Pre/post agent loop |
| **Use case** | Tool logging, parameter validation, result transformation | Loop customization, timing, metrics |

---

## Inter-Module Data Flow

### Middleware Hook Flow
```
Tool invocation
  → HookRegistry.execute_pre_hooks(context)
    → For each pre-hook (ordered by priority):
      → hook.pre_call(context)
      → If modified: update context.parameters
  → Execute tool with (possibly modified) parameters
  → HookRegistry.execute_post_hooks(context, result)
    → For each post-hook (ordered by priority):
      → hook.post_call(context, result)
      → If modified: update result
  → Return (possibly modified) result
```
