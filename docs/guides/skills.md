# Skills Guide

Skills enable progressive disclosure of capabilities, allowing agents to discover and use specialized tools dynamically.

## What are Skills?

Skills are packages of related tools that can be loaded on-demand. They provide:
- **Modularity**: Group related tools together
- **Discovery**: Agents can discover available skills
- **Lazy Loading**: Skills are loaded only when needed

## Creating a Skill

### SKILL.md Structure

Skills are defined using a SKILL.md file in the skill directory:

```yaml
---
name: code_analysis
description: Tools for code analysis
category: development
tools:
  - analyze_complexity
  - find_bugs
dependencies: []
---

# Code Analysis Skill

This skill provides tools for analyzing code.
```

The SKILL.md file uses YAML frontmatter for metadata:
- **name**: Skill identifier
- **description**: Human-readable description
- **category**: Skill category (development, data, etc.)
- **tools**: List of tool names provided by this skill
- **dependencies**: Other skill names required by this skill

### Skill with Dependencies

```yaml
---
name: web_scraper
description: Tools for web scraping
category: data
tools:
  - fetch_page
  - parse_html
dependencies:
  - http_client
---

# Web Scraper Skill

This skill provides tools for scraping web pages.
```

## Loading Skills

### Manual Loading

```python
from pathlib import Path
from tinycua_sdk.skills import SkillLoader

loader = SkillLoader()
skill = loader.load_skill(Path("skills/code_analysis"))
```

### Automatic Loading

```python
from tinycua_sdk import Agent

agent = Agent(
    name="my-agent",
    skills=["code_analysis", "web_scraper"]
)
```

## Skill Registry

### Discovering Available Skills

```python
from tinycua_sdk.skills import SkillRegistry

registry = SkillRegistry()
available_skills = registry.list_skills()

for skill in available_skills:
    print(f"{skill.name}: {skill.description}")
```

### Skill Caching

Skills are cached for performance:

```python
from tinycua_sdk.skills import SkillCache

cache = SkillCache()

# Check if skill is cached
skill = cache.get("code_analysis")
if skill is not None:
    # Use cached skill
    print(f"Found cached skill: {skill.name}")
```

## Best Practices

1. **Keep skills focused**: Each skill should have a single responsibility
2. **Document clearly**: Provide clear descriptions for skills and tools
3. **Handle errors gracefully**: Tools should handle errors and return meaningful results
4. **Use type hints**: Enable better IDE support and validation

## Examples

See `examples/agent_with_skills.py` for a complete example.