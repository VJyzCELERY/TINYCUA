# Skills and Skill Registry

**Prerequisites**: [Creating Tools](./creating-tools.md) — you know how to
define and attach tools to an agent.

## Overview

Skills are reusable knowledge packages that inject instructions, workflows, and
context into an agent's system prompt. Unlike tools — which the agent *calls* —
skills are *always active* background guidance. They are ideal for domain
expertise (e.g., "you are a legal document reviewer"), procedural playbooks
(e.g., "handle support tickets this way"), or guardrails ("never reveal
internal IDs").

Skills are immutable `pydantic` models that can be loaded from `SKILL.md` files
with YAML frontmatter, registered in a `SkillRegistry`, and attached to agents
individually or in bulk.

## The `Skill` Model

A `Skill` has four fields:

```python
from tinycua_sdk import Skill

skill = Skill(
    name="customer-support",
    description="Guidelines for handling customer support tickets.",
    instructions=(
        "Always greet the customer by name. "
        "Prioritize refund requests over feature requests. "
        "Escalate to a human when confidence is low."
    ),
    metadata={"version": "1.0", "author": "support-team"},
)
```

- **`name`** — unique identifier used for registration and lookup.
- **`description`** — human-readable summary (may be shown in UIs).
- **`instructions`** — prose instructions injected into the agent's system
  prompt. This is the core payload.
- **`metadata`** — arbitrary key-value data (versioning, authorship, tags).

Skills are frozen (immutable) through Pydantic's `frozen=True` configuration.

## Loading from `SKILL.md` Files

### `Skill.from_directory`

Each skill lives in its own directory containing a `SKILL.md` file with YAML
frontmatter. The frontmatter provides `name`, `description`, and arbitrary
`metadata`. Everything after the second `---` delimiter becomes
`instructions`:

```
my_skills/
└── code-review/
    └── SKILL.md
```

Here is a complete `SKILL.md` example:

```markdown
---
name: code-review
description: Best practices for code review comments.
version: "2.1"
author: eng-team
---

When reviewing code, follow these guidelines:

1. Start with a summary of what the change does.
2. Flag security concerns before style nits.
3. Suggest concrete alternatives, not just criticism.
4. Use a respectful, collaborative tone.

Never approve code that:
- Exposes secrets or API keys.
- Has SQL queries without parameterization.
- Lacks error handling on external calls.
```

Load it with:

```python
from pathlib import Path
from tinycua_sdk import Skill

skill = Skill.from_directory(Path("./my_skills/code-review"))
print(skill.name)            # code-review
print(skill.description)     # Best practices for code review comments.
print(skill.metadata)        # {'version': '2.1', 'author': 'eng-team'}
print(skill.instructions)    # The full instruction text below the frontmatter
```

If `name` or `description` are omitted from the frontmatter, `from_directory`
falls back to the directory name for `name` and an empty string for
`description`.

### `Skill.load_directory` — Bulk Loading

Scan a parent directory and load every subdirectory that contains a `SKILL.md`:

```
skills_bundle/
├── code-review/
│   └── SKILL.md
├── data-privacy/
│   └── SKILL.md
└── tone-guide/
    └── SKILL.md
```

```python
from pathlib import Path
from tinycua_sdk import Skill

skills = Skill.load_directory(Path("./skills_bundle"))
print([s.name for s in skills])
# ['code-review', 'data-privacy', 'tone-guide']
```

Subdirectories without a `SKILL.md` are silently skipped.

## The `SkillRegistry`

The registry stores skills and supports retrieval by name. Registering a skill
with the same name overwrites the previous entry:

```python
from tinycua_sdk import Skill, SkillRegistry

skill_a = Skill(
    name="safety-guardrails",
    description="Safety rules for the agent.",
    instructions="Never share user PII.",
)

skill_b = Skill(
    name="domain-expertise",
    description="Medical domain knowledge.",
    instructions="You specialize in cardiology.",
)

registry = SkillRegistry()
registry.register(skill_a)
registry.register(skill_b)

# Overwrite — registration is last-write-wins
registry.register(Skill(
    name="safety-guardrails",
    description="Updated safety rules.",
    instructions="Never share PII. Also block profanity.",
))

print([s.name for s in registry.list_skills()])
# ['safety-guardrails', 'domain-expertise']

retrieved = registry.get("domain-expertise")
print(retrieved.description)
# Medical domain knowledge.

missing = registry.get("nonexistent")
print(missing)
# None
```

## Attaching Skills to an Agent

Skills are injected into the system prompt alongside the agent's
`instructions`. Pass them at construction or call `add_skills` later:

### Local (local LLM server)

```python
import os

from tinycua_sdk import Agent, LanguageModel, Skill

safety = Skill(
    name="safety",
    description="Safety rules.",
    instructions="Never disclose passwords or API keys.",
)

model = LanguageModel(
    provider="openai-compatible",
    model_name="qwen/qwen3.5-9b",
    base_url="http://localhost:1234/v1",
)

agent = Agent(
    name="safe-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
    skills=[safety],
)
```

### Remote (OpenAI)

```python
import os

from tinycua_sdk import Agent, LanguageModel, Skill

safety = Skill(
    name="safety",
    description="Safety rules.",
    instructions="Never disclose passwords or API keys.",
)

model = LanguageModel(
    provider="openai-responses",
    model_name="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key=os.environ.get("OPENAI_API_KEY"),
)

agent = Agent(
    name="safe-assistant",
    instructions="You are a helpful assistant.",
    llm_model=model,
    skills=[safety],
)
```

Use `add_skills` to register skills after construction — duplicates are
silently skipped:

```python
tone = Skill(
    name="professional-tone",
    description="Tone guidelines.",
    instructions="Maintain a professional tone. Avoid slang.",
)

agent.add_skills(tone)
agent.add_skills([safety])  # already registered — skipped
```

## Serialization

Skills support round-trip serialization:

```python
from tinycua_sdk import Skill

skill = Skill(
    name="test-skill",
    description="A test skill.",
    instructions="Be helpful.",
)
data = skill.to_dict()
restored = Skill.from_dict(data)

assert restored.name == skill.name
assert restored.instructions == skill.instructions
```

## Common Pitfalls

**Mutable metadata illusions**. `Skill` is frozen, but `metadata` is a plain
`dict`. Modifying it after construction is technically possible but
discouraged — the skill will not reflect changes in the system prompt.
Recreate the skill instead.

**Forgetting the YAML frontmatter delimiters**. `SKILL.md` files must start
with `---` followed by valid YAML, then another `---`. If the frontmatter is
malformed or missing, `from_directory` treats the entire file content as
instructions, and `name` falls back to the directory name.

**Overwriting via `register`**. The registry uses last-write-wins semantics.
If two skills share a name, only the most recently registered one is
retrievable. Use unique names or a naming convention like
`{team}/{skill-name}`.

## Next Steps

- **[Tool Permissions and Approval](./tool-permissions-and-approval.md)** —
  Control which tools run automatically and which require user approval.
- **[Creating Tools](./creating-tools.md)** — Define callable tools for your
  agent.