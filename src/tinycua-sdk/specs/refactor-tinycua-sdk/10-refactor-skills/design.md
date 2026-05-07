# Stage 10 — Design: Refactor Skills Framework

## Overview

Clean up the `skills/` package. Remove the `SkillBackend` hierarchy, make `SkillRegistry` non-singleton, and ensure skills are loaded from strings (not filesystem).

## Design Decisions

### Why Delete SkillBackend?

1. **Stateful**: SkillBackend manages storage, retrieval, and caching of skills — this is a consumer concern.
2. **Parallel invention**: It's the same pattern as `MemoryBackend` and `SessionStore` — storage abstractions that don't belong in the SDK.
3. **Consumer owns skill lifecycle**: The consumer decides where skills live (file, DB, S3, inline) and how they're versioned.

### Why Make SkillRegistry Non-Singleton?

1. **Global state**: Singleton registries are global mutable state.
2. **Multiple agents**: Different agents may need different skill sets. A global registry forces all agents to share the same skills.
3. **Testing**: Singletons make tests order-dependent and harder to parallelize.

### Why Load Skills from Strings?

1. **Stateless**: Reading files is I/O. The SDK should not perform I/O.
2. **Flexible source**: Skills may come from files, databases, S3, APIs, or inline strings. The consumer decides.
3. **Simple API**: `Skill.load(text)` is clean and unambiguous.

## Files to Delete

| File | Reason |
|------|--------|
| `skills/backend.py` | SkillBackend hierarchy — stateful |

## Files to Modify

| File | Changes |
|------|---------|
| `skills/models.py` | Ensure `Skill.load(text)` is the primary loading mechanism |
| `skills/registry.py` | Make non-singleton; remove filesystem I/O |
| `skills/loader.py` | Simplify or delete if redundant |

## Package Layout (Target)

```
skills/
  __init__.py
  models.py              # Skill dataclass, Skill.load()
  registry.py            # SkillRegistry (explicit instance, no I/O)
  improver.py            # Skill improvement logic (keep if pure functions)
  cache.py               # Ephemeral skill cache (not persistent)
```

## Code Changes

### models.py — Skill dataclass

```python
from dataclasses import dataclass, field
from typing import Any
import yaml

@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    source: str | None = None   # URI or path (consumer-managed)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    version: str = "1.0.0"
    
    @classmethod
    def load(cls, text: str) -> "Skill":
        """Parse a skill definition from Markdown text.
        
        Args:
            text: Markdown content following the SKILL.md format.
                  Contains YAML frontmatter between --- markers.
        
        Returns:
            Skill instance.
        """
        # Parse frontmatter
        lines = text.split("\n")
        if lines[0].strip() == "---":
            end = lines[1:].index("---") + 1
            frontmatter = yaml.safe_load("\n".join(lines[1:end]))
            body = "\n".join(lines[end + 1:])
        else:
        frontmatter = {}
            body = text
        
        # Parse body sections
        sections = _parse_markdown_sections(body)
        
        return cls(
            name=frontmatter.get("name", "unnamed"),
            description=sections.get("Description", ""),
            category=frontmatter.get("category", "general"),
            instructions=sections.get("Instructions", ""),
            tools=frontmatter.get("tools", []),
            dependencies=frontmatter.get("dependencies", []),
            metadata=frontmatter.get("metadata", {}),
            version=frontmatter.get("version", "1.0.0"),
        )
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "instructions": self.instructions,
            "tools": self.tools,
            "dependencies": self.dependencies,
            "source": self.source,
            "metadata": self.metadata,
            "is_active": self.is_active,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Skill":
        return cls(**data)
```

### registry.py — Non-singleton SkillRegistry

```python
class SkillRegistry:
    """Explicit skill registry. Not a singleton.
    
    The consumer instantiates this directly:
        registry = SkillRegistry()
        registry.register(Skill.load(skill_text))
    """
    
    def __init__(self):
        self._skills: dict[str, Skill] = {}
    
    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
    
    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)
    
    def list_skills(self, category: str | None = None) -> list[Skill]:
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return skills
    
    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)
    
    def clear(self) -> None:
        self._skills.clear()
```

### __init__.py

```python
from .models import Skill
from .registry import SkillRegistry

__all__ = ["Skill", "SkillRegistry"]
```

## Consumer Usage Patterns

### Pattern 1: Inline skills
```python
from tinycua_sdk import Skill

skill = Skill.load("""
---
name: coder
category: development
tools:
  - read_file
  - write_file
---
# Coder
## Instructions
Write clean, efficient code.
""")
```

### Pattern 2: Consumer loads from file
```python
from tinycua_sdk import Skill

with open("./skills/coder.md") as f:
    skill = Skill.load(f.read())
```

### Pattern 3: Consumer loads from database
```python
from tinycua_sdk import Skill

row = db.query("SELECT markdown FROM skills WHERE name = 'coder'")
skill = Skill.load(row.markdown)
```

### Pattern 4: Explicit registry
```python
from tinycua_sdk import SkillRegistry, Skill

registry = SkillRegistry()
registry.register(Skill.load(coder_text))
registry.register(Skill.load(researcher_text))

agent = Agent(skills=registry.list_skills())
```

## Acceptance Criteria

- [ ] `skills/backend.py` is deleted.
- [ ] `SkillRegistry` is not a singleton.
- [ ] `SkillRegistry` has no filesystem I/O.
- [ ] `Skill.load(text)` parses Markdown with YAML frontmatter.
- [ ] `Skill.to_dict()` / `Skill.from_dict()` round-trip correctly.
- [ ] `CallableTool` wrapper is deleted (from `skills/tools.py`).
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 08.
- **Blocks**: Stage 11 (Agent refactor depends on clean skill framework).
