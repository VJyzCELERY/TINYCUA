# Skills Guide

Skills enable progressive disclosure of capabilities, allowing agents to discover and use specialized tools dynamically.

## What are Skills?

Skills are packages of related tools that can be loaded on-demand. They provide:
- **Modularity**: Group related tools together
- **Discovery**: Agents can discover available skills
- **Lazy Loading**: Skills are loaded only when needed

## Creating a Skill

### Basic Skill Structure

```python
from tinycua_sdk.skills import skill, SkillLoader

@skill(name="code_analysis", description="Tools for code analysis")
class CodeAnalysisSkill:
    """Skill for analyzing code."""
    
    @staticmethod
    def get_tools():
        """Return list of tools in this skill."""
        from tinycua_sdk.tools import tool
        
        @tool(name="analyze_complexity", description="Analyze code complexity")
        def analyze_complexity(code: str) -> dict:
            """Analyze code complexity."""
            # Implementation here
            return {"complexity": 10, "lines": 100}
        
        @tool(name="find_bugs", description="Find potential bugs")
        def find_bugs(code: str) -> list[dict]:
            """Find potential bugs in code."""
            # Implementation here
            return []
        
        return [analyze_complexity, find_bugs]
```

### Skill with Dependencies

```python
@skill(name="web_scraper", description="Tools for web scraping")
class WebScraperSkill:
    """Skill for web scraping."""
    
    dependencies = ["http_client"]  # Required skills
    
    @staticmethod
    def get_tools():
        """Return list of tools in this skill."""
        # Tools implementation
        return []
```

## Loading Skills

### Manual Loading

```python
from tinycua_sdk.skills import SkillLoader

loader = SkillLoader()
loader.load_skill("code_analysis")
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
if cache.has("code_analysis"):
    skill = cache.get("code_analysis")
```

## Best Practices

1. **Keep skills focused**: Each skill should have a single responsibility
2. **Document clearly**: Provide clear descriptions for skills and tools
3. **Handle errors gracefully**: Tools should handle errors and return meaningful results
4. **Use type hints**: Enable better IDE support and validation

## Examples

See `examples/agent_with_skills.py` for a complete example.
