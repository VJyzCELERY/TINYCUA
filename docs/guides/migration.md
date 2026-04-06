# Migration Guide

This guide helps developers migrate from old SDK versions to the new TinyCUA SDK structure.

## Breaking Changes

### Import Path Changes

The most significant change is the restructuring of import paths:

#### Old Import Paths (Deprecated)

```python
# Old import paths - DEPRECATED
from tinycua_sdk.config import Config
from tinycua_sdk.config import configure
```

#### New Import Paths

```python
# New import paths - RECOMMENDED
from tinycua_sdk.core.config import SDKConfig
```

### Configuration Changes

#### Old Configuration

```python
# Old way (deprecated)
from tinycua_sdk.config import Config, configure

configure(
    backend_url="http://localhost:8000",
    api_key="your-api-key",
    provider="openai",
    model="gpt-4",
    base_url="http://api.openai.com"
)

config = Config()
print(config.BACKEND_URL)
```

#### New Configuration

```python
# New way (recommended)
from tinycua_sdk.core.config import SDKConfig

# Create config with defaults
config = SDKConfig()

# Or load from YAML
config = SDKConfig.from_yaml("config.yaml")

# Or load from environment
config = SDKConfig.from_env()

# Access configuration
print(config.backend_url)
print(config.llm.provider)
print(config.llm.model)
```

### Agent Creation Changes

#### Old Agent Creation

```python
# Old way (deprecated)
from tinycua_sdk import Agent

agent = Agent(
    name="my-agent",
    instructions="You are a helpful assistant",
    model="gpt-4"
)
```

#### New Agent Creation

```python
# New way (recommended)
from tinycua_sdk import Agent

agent = Agent(
    name="my-agent",
    instructions="You are a helpful assistant",
    model="gpt-4",
    provider="openai",
    base_url="http://api.openai.com"
)
```

## Migration Steps

1. **Update Import Statements**
   - Replace `from tinycua_sdk.config import Config` with `from tinycua_sdk.core.config import SDKConfig`

2. **Update Configuration Usage**
   - Replace `Config.BACKEND_URL` with `config.backend_url`
   - Replace `configure()` calls with `SDKConfig.from_env()` or `SDKConfig.from_yaml()`

3. **Update Agent Creation**
   - Update agent initialization to use new parameter names
   - Use `provider` and `base_url` instead of `llm_provider` and `llm_base_url`

## Feature Flags

The new SDK supports feature flags in `SDKConfig`:

```python
from tinycua_sdk.core.config import SDKConfig

config = SDKConfig(
    enable_mcp=False,      # MCP server support
    enable_search=False,   # FTS5 search
)
```

## Getting Help

If you encounter issues during migration:
- Check the API documentation
- Review the examples in `docs/examples/`
- Open an issue on GitHub
