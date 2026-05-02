# Stage 4: Skills & Composition — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-04-skills/spec.md`

## Implementation

No new files. This is a behavioral enhancement to `BaseLoop._build_system_message()` from Stage 3.

### Updated `BaseLoop._build_system_message()`

```python
def _build_system_message(
    self,
    agent: Agent,
    override_instructions: str | None = None,
) -> dict:
    parts = []

    # Agent-level instructions
    instructions = override_instructions or agent.instructions
    if instructions:
        parts.append(instructions)

    # Skill instructions (in registration order)
    for skill in agent.skills:
        skill_block = f"[{skill.name}]\n{skill.instructions}"
        parts.append(skill_block)

    content = "\n\n".join(parts)
    return {"role": "system", "content": content}
```

## Design Decisions

### Single System Message vs Multiple
Some providers support multiple system messages. We use a single system message with concatenated sections because:
1. It's universally supported.
2. It preserves ordering clearly.
3. It makes the full prompt inspectable in one place.

### Skill Block Format
```
[python_expert]
When writing Python code, follow PEP 8...

[testing_guru]
Always write pytest test cases...
```

The `[name]` header makes it easy for the LLM to understand which instructions come from which skill. It also makes logs/debugging clearer.

### No Auto-Tool Resolution
We deliberately do NOT implement skill-to-tool mapping. The goal script explicitly states:
> "Skills are metadata-only in the SDK — they provide instructions and context that can be injected into an agent's system prompt, but they do NOT auto-resolve tools."

This is a feature, not a bug. It keeps the SDK simple and avoids magic.

## Data Flow

```
Agent.run("Write a function.")
    │
    ▼
BaseLoop.run(agent, messages, tools)
    │
    ├──► _build_system_message(agent)
    │       ├──► agent.instructions
    │       ├──► agent.skills[0].instructions  ──► [python_expert] block
    │       └──► agent.skills[1].instructions  ──► [testing_guru] block
    │       Returns: {"role": "system", "content": "...concatenated..."}
    │
    ├──► agent._call_llm(messages_with_system, tools)
    │
    └──► ... rest of loop from Stage 3
```

## Testing Strategy

- Unit test `_build_system_message` directly:
  - Empty agent → system message contains only instructions.
  - Agent with 2 skills → system message contains both skill blocks in order.
  - Override instructions → override replaces agent.instructions.
- Integration tests validate that the LLM receives the combined prompt (via mock client inspection).
