# Stage 10 — Refactor Skills Framework

## Objective

Clean up the `skills/` package: remove stateful backends, add `Skill.load()`, and make `SkillRegistry` non-singleton with no filesystem I/O.

## Files to Delete

| File | Reason |
|------|--------|
| `skills/backend.py` | SkillBackend hierarchy — stateful |

## Files to Keep / Modify

| File | Changes |
|------|---------|
| `skills/models.py` | Keep Skill dataclass; add `load()` classmethod |
| `skills/registry.py` | Remove `load_from_directory()`; ensure non-singleton |
| `skills/loader.py` | Remove or simplify — no filesystem scanning |
| `skills/improver.py` | Keep if pure logic |
| `skills/cache.py` | Keep if ephemeral (not persistent) |

## Code Changes

### Add Skill.load()

In `skills/models.py`:
```python
@dataclass
class Skill:
    # ... existing fields ...

    @classmethod
    def load(cls, text: str) -> Skill:
        """Parse skill definition from Markdown text.

        Args:
            text: Markdown content following SKILL.md format.

        Returns:
            Skill instance.
        """
        # Parse YAML frontmatter between --- markers
        # Parse sections: # Name, ## Description, ## Instructions, ## Tools
        ...
```

### Update SkillRegistry

In `skills/registry.py`:
```python
class SkillRegistry:
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

    # load_from_directory() REMOVED
```

### Update skills/__init__.py

Remove exports for deleted modules.

## Acceptance Criteria

- [ ] `skills/backend.py` does not exist.
- [ ] `Skill.load(text)` works for Markdown input.
- [ ] `SkillRegistry` has no filesystem I/O methods.
- [ ] `SkillRegistry` instances are independent (not singleton).
- [ ] `pytest` still passes for remaining tests.

## Dependencies

- **Requires**: Stage 01, Stage 02, Stage 08
