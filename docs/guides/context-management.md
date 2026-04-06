# Context Management Guide

TinyCUA provides sophisticated context management including compression, injection detection, and file discovery.

## Overview

The context management system handles:
- **Context Discovery**: Finding relevant context files
- **Compression**: Reducing context size while preserving meaning
- **Injection Detection**: Preventing prompt injection attacks
- **Memory Snapshots**: Saving and loading agent memory states

## Context Discovery

### File Discovery

```python
from tinycua_sdk.context import ContextDiscovery

discovery = ContextDiscovery()

# Find relevant files
files = discovery.find_context_files(
    directory="./context",
    patterns=["*.md", "*.txt"]
)

for file in files:
    print(f"Found: {file.path}")
```

### Context Types

```python
from tinycua_sdk.context import ContextFile

# System context
system_ctx = ContextFile(
    path="./system.md",
    type="system"
)

# User context
user_ctx = ContextFile(
    path="./user.md", 
    type="user"
)
```

## Context Compression

### Basic Compression

```python
from tinycua_sdk.context import ContextCompressor

compressor = ContextCompressor()

# Compress context
compressed = compressor.compress(
    context="Long context text...",
    max_tokens=2000
)

print(compressed)
```

### Custom Compression

```python
from tinycua_sdk.context import CompressionStrategy

class MyStrategy(CompressionStrategy):
    def compress(self, context: str, max_tokens: int) -> str:
        # Custom compression logic
        return context[:max_tokens]

compressor = ContextCompressor(strategy=MyStrategy())
```

## Injection Detection

### Basic Usage

```python
from tinycua_sdk.context import InjectionDetector

detector = InjectionDetector()

# Check for injection
result = detector.check("Normal user input")

if result.is_safe:
    print("Input is safe")
else:
    print(f"Potential injection detected: {result.threat}")
```

### Custom Rules

```python
from tinycua_sdk.context import InjectionDetector

detector = InjectionDetector()

# Add custom detection rules
detector.add_rule(
    pattern=r"ignore previous instructions",
    severity="high"
)
```

## Memory Snapshots

### Saving Memory

```python
from tinycua_sdk.storage import MemorySnapshot

snapshot = MemorySnapshot()

# Save current agent memory
snapshot.save(
    agent_id="agent-123",
    session_id="session-456",
    include_messages=True
)
```

### Loading Memory

```python
# Load previous memory state
snapshot.load(
    agent_id="agent-123",
    session_id="session-456"
)
```

## Configuration

### Context Config

The context management system is configured through environment variables and session settings:

```python
from tinycua_sdk.core.config import SDKConfig

# Configure memory/storage settings
config = SDKConfig(
    memory={
        "database_url": "sqlite:///./tinycua.db",
        "embedding_dimension": 1536
    }
)
```

Note: Context compression and injection detection are enabled by default and do not require explicit configuration.

## Best Practices

1. **Set appropriate token limits**: Balance context size with performance
2. **Enable injection detection**: Protect against prompt injection attacks
3. **Use compression wisely**: Test compression quality for your use case
4. **Regular snapshots**: Save important memory states periodically
