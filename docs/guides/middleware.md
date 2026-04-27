# Middleware & Hooks Guide

Middleware and hooks allow you to intercept and modify agent behavior at key points in the execution pipeline.

## Overview

TinyCUA provides a hooks system with:
- **Pre-execution hooks**: Run before tool calls
- **Post-execution hooks**: Run after tool calls

## Basic Hooks

### Creating a Hook

```python
from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class LogRequestsHook(Hook):
    """Log all requests before execution."""
    
    def pre_call(self, context: HookContext) -> HookResult:
        print(f"Request: {context.parameters}")
        return HookResult(modified=False)
```

### Registering Hooks

```python
from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class LogRequestsHook(Hook):
    """Log all requests before execution."""
    
    def pre_call(self, context: HookContext) -> HookResult:
        print(f"Request: {context.parameters}")
        return HookResult(modified=False)

# Register the hook (requires Hook INSTANCE, not class)
registry = HookRegistry()
registry.register_pre_hook(LogRequestsHook())
# Or with priority: registry.register_pre_hook(LogRequestsHook(), priority=50)
```

## Hook Types

### Pre-Run Hook

```python
from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class ValidateInputHook(Hook):
    """Validate user input before running."""
    
    def pre_call(self, context: HookContext) -> HookResult:
        if len(context.parameters.get("input", "")) > 10000:
            return HookResult(modified=False, error="Input too long")
        return HookResult(modified=False)
```

### Post-Run Hook

```python
from typing import Any

from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class LogResponseHook(Hook):
    """Log response after execution."""
    
    def post_call(self, context: HookContext, result: Any) -> HookResult:
        print(f"Response: {result}")
        return HookResult(modified=False, result=result)
```

### Error Handling

```python
from typing import Any

from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class ErrorHandlerHook(Hook):
    """Handle errors during execution."""
    
    def post_call(self, context: HookContext, result: Any) -> HookResult:
        if isinstance(result, Exception):
            print(f"Error: {result}")
            return HookResult(modified=False, result=result)
        return HookResult(modified=False, result=result)
```

## Use Cases

### Logging

```python
import logging
from typing import Any

from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class AuditLogHook(Hook):
    """Audit log for agent operations."""
    
    def post_call(self, context: HookContext, result: Any) -> HookResult:
        logging.info(f"Tool: {context.tool_name}, Parameters: {context.parameters}, Result: {result}")
        return HookResult(modified=False, result=result)
```

### Rate Limiting

```python
import time
from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class RateLimiterHook(Hook):
    """Rate limiting hook."""
    
    def __init__(self, max_calls_per_minute=60):
        self.max_calls = max_calls_per_minute
        self.calls = []
    
    def pre_call(self, context: HookContext) -> HookResult:
        now = time.time()
        self.calls = [c for c in self.calls if now - c < 60]
        
        if len(self.calls) >= self.max_calls:
            return HookResult(modified=False, error="Rate limit exceeded")
        
        self.calls.append(now)
        return HookResult(modified=False)
```

### Caching

```python
from typing import Any

from tinycua_sdk.middleware import Hook, HookRegistry, HookContext, HookResult

class ResponseCacheHook(Hook):
    """Cache responses for repeated requests."""
    
    def __init__(self):
        self.cache = {}
    
    def pre_call(self, context: HookContext) -> HookResult:
        input_key = str(context.parameters)
        if input_key in self.cache:
            return HookResult(modified=True, result=self.cache[input_key])
        return HookResult(modified=False)
    
    def post_call(self, context: HookContext, result: Any) -> HookResult:
        input_key = str(context.parameters)
        self.cache[input_key] = result
        return HookResult(modified=False, result=result)
```

## Best Practices

1. **Keep hooks simple**: Complex logic should be in separate modules
2. **Use HookResult**: Return modified parameters or results through HookResult
3. **Handle errors**: Return error in HookResult for graceful failure
4. **Document hooks**: Clear names and descriptions help maintenance
5. **Use priority**: Lower priority values run first for ordering