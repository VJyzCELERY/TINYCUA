# Middleware & Hooks Guide

Middleware and hooks allow you to intercept and modify agent behavior at key points in the execution pipeline.

## Overview

TinyCUA provides a hooks system with:
- **Pre-execution hooks**: Run before agent operations
- **Post-execution hooks**: Run after agent operations
- **Error hooks**: Handle errors gracefully
- **Custom middleware**: Extend agent functionality

## Basic Hooks

### Creating a Hook

```python
from tinycua_sdk.middleware import Hook, HookRegistry

@Hook(name="log_requests", event="pre_run")
def log_request(agent, user_input):
    """Log all requests before execution."""
    print(f"Request: {user_input}")
    return {"continue": True}  # Return False to stop execution
```

### Registering Hooks

```python
from tinycua_sdk.middleware import HookRegistry

registry = HookRegistry()
registry.register(log_request)
```

## Hook Types

### Pre-Run Hook

```python
@Hook(name="validate_input", event="pre_run")
def validate_input(agent, user_input):
    """Validate user input before running."""
    if len(user_input) > 10000:
        raise ValueError("Input too long")
    return {"continue": True}
```

### Post-Run Hook

```python
@Hook(name="log_response", event="post_run")
def log_response(agent, user_input, response):
    """Log response after execution."""
    print(f"Response: {response}")
    return {"continue": True}
```

### Error Hook

```python
@Hook(name="handle_errors", event="on_error")
def handle_error(agent, user_input, error):
    """Handle errors during execution."""
    print(f"Error: {error}")
    return {"continue": True, "recovery_action": "retry"}
```

## Middleware Pipeline

### Creating Middleware

```python
from tinycua_sdk.middleware import Middleware

class MyMiddleware(Middleware):
    async def process(self, request, next):
        # Pre-processing
        print(f"Processing: {request}")
        
        # Call next middleware
        response = await next(request)
        
        # Post-processing
        print(f"Response: {response}")
        
        return response
```

### Adding to Pipeline

```python
from tinycua_sdk import Agent

agent = Agent(
    name="my-agent",
    middleware=[MyMiddleware()]
)
```

## Hook Registry

### Listing Hooks

```python
registry = HookRegistry()
hooks = registry.list_hooks()

for hook in hooks:
    print(f"{hook.name}: {hook.event}")
```

### Removing Hooks

```python
registry.unregister("log_requests")
```

## Use Cases

### Logging

```python
import logging

@Hook(name="audit_log", event="post_run")
def audit_log(agent, user_input, response):
    logging.info(f"Agent: {agent.name}, Input: {user_input}, Response: {response}")
```

### Rate Limiting

```python
import time

class RateLimiter(Hook):
    def __init__(self, max_calls_per_minute=60):
        self.max_calls = max_calls_per_minute
        self.calls = []
    
    def __call__(self, agent, user_input):
        now = time.time()
        self.calls = [c for c in self.calls if now - c < 60]
        
        if len(self.calls) >= self.max_calls:
            raise ValueError("Rate limit exceeded")
        
        self.calls.append(now)
        return {"continue": True}
```

### Caching

```python
class ResponseCache(Hook):
    def __init__(self):
        self.cache = {}
    
    def __call__(self, agent, user_input):
        if user_input in self.cache:
            return {"continue": False, "response": self.cache[user_input]}
        return {"continue": True}
    
    def cache_response(self, user_input, response):
        self.cache[user_input] = response
```

## Best Practices

1. **Keep hooks simple**: Complex logic should be in middleware
2. **Return control flags**: Always return `{"continue": True/False}`
3. **Handle errors**: Use error hooks for graceful failure
4. **Document hooks**: Clear names and descriptions help maintenance
