# tinycua-sdk

Developer SDK for TINYCUA.

## Cookbook

Guided, basic-to-advanced walkthrough of all SDK capabilities. Start with the
[index](./docs/cookbook/index.md) for a complete learning path covering agents,
configuration, tools, skills, streaming, file handling, providers, execution
loops, and error handling — with runnable code examples for both local and
remote (OpenAI) providers.

### Quick Start

```python
import asyncio
from tinycua_sdk import Agent

async def main():
    agent = Agent(name="assistant", instructions="You are a helpful assistant.")
    response = await agent.run("Hello!")
    print(response)

asyncio.run(main())
```

See the [cookbook](./docs/cookbook/index.md) for a complete walkthrough covering
agents, tools, streaming, file handling, providers, and more.

### Key Features at a Glance

- **Agent creation** with local and remote LLM providers via `LanguageModel`
- **File attachments** via `FileAttachment.from_path`, `from_bytes`, and `from_url`
- **Multimodal queries** mixing text and files with `ContentPart`
- **Streaming responses** with canonical event types
- **Custom tools** via the `@tool` decorator
- **Skills** loaded from `SKILL.md` files with a `SkillRegistry`
- **Tool permissions** (`allow`/`ask`/`deny`) with pluggable approval workflows
- **Streaming file uploads** for large files without memory buffering
- **Persistent upload cache** with content-addressed deduplication
- **Custom providers** via the `LLMClient` ABC and `ProviderRegistry`
- **Custom execution loops** by subclassing `BaseLoop`
- **Error handling** with `ProviderApiError`, `ProviderAuthError`, `ProviderNotSupportedError`

See each cookbook page for runnable code examples, common pitfalls, and provider-level details.
