# Skills and Memory Features - Planning Document

This document outlines the current implementation of Skills and Memory in TINYCUA SDK, and provides a plan for creating examples and integration tests.

---

## Part 1: Skills System

### Overview

The Skills system allows agents to dynamically load capabilities from the filesystem. Skills are directories containing a `SKILL.md` file that defines the skill's metadata and instructions.

### Key Components

#### 1. Skill Model (`tinycua_sdk/skills/models.py`)
```python
@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = []          # Tool names provided by this skill
    dependencies: list[str] = []   # Other skills this depends on
    path: Path | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime | None = None
    modified_at: datetime | None = None
```

#### 2. SkillLoader (`tinycua_sdk/skills/loader.py`)
- Loads skills from filesystem
- Parses `SKILL.md` with YAML frontmatter + markdown instructions
- Discovery method finds all skill directories

**SKILL.md Format:**
```yaml
---
name: web-search
description: Search the web for information
category: tools
tools: [requests, BeautifulSoup]
dependencies: []
---

## Instructions
You can use this skill to search the web...
```

#### 3. SkillRegistry (`tinycua_sdk/skills/registry.py`)
- Central registry for managing loaded skills
- `register_skill()` - Register a skill
- `get_skill(name)` - Get skill by name
- `list_skills(category)` - List skills, optionally filtered
- `load_skills_from_directory(path)` - Load all skills from a directory

#### 4. Skill Tools (`tinycua_sdk/skills/tools.py`)
Provides two tools for agents:
- `skills_list(category)` - List available skills
- `skill_view(skill_name)` - View full details of a skill

#### 5. SkillResolver (`tinycua_sdk/agent/skill_resolver.py`)
- Resolves skill tool names to Tool instances from ToolRegistry
- Used during agent creation to get tools from skills

#### 6. SkillActivator (`tinycua_sdk/agent/skill_resolver.py`)
- Conditional skill activation based on environment
- Platform checking (linux, darwin, win32)
- Toolset requirements (`requires_toolsets`)
- Tool requirements (`requires_tools`)
- Fallback logic (`fallback_for_tools`)

### How Skills Work

1. **Loading:** Skills are loaded from a directory (default: `~/.tinycua/skills/`)
2. **Registration:** Skills are registered with SkillRegistry
3. **Agent Creation:** When creating an agent with `skills=["web-search"]`:
   - SkillResolver looks up each skill in the registry
   - Resolves declared tool names to actual Tool instances
   - Tools are added to the agent
4. **Runtime:** Agent can use `skills_list()` and `skill_view()` tools to discover capabilities

### Current Test Coverage

- Unit tests: `tests/unit/test_skills_loader.py`, `tests/unit/test_skills_registry.py`
- Integration tests: `tests/integration/test_skills_integration.py`
- Agent tests: `tests/agent/test_skill_resolver.py`, `tests/agent/test_config_skills.py`

---

## Part 2: Memory System

### Overview

The Memory system provides persistent key-value storage that agents can use to remember information across conversations.

### Key Components

#### 1. MemoryBackend (Abstract) (`tinycua_sdk/tools/memory.py`)
```python
class MemoryBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> tuple[str | None, bool]
    @abstractmethod
    def set(self, key: str, value: str) -> dict[str, Any]
    @abstractmethod
    def delete(self, key: str) -> dict[str, Any]
    @abstractmethod
    def list_keys(self) -> list[str]
    @abstractmethod
    def clear(self) -> dict[str, Any]
```

#### 2. LocalMemoryBackend
- Stores memory in JSON file (`~/.tinycua/memory.json`)
- No external dependencies

#### 3. RemoteMemoryBackend
- Stores memory via backend API
- Requires backend server

#### 4. HybridMemoryBackend
- Tries remote first, falls back to local
- Good for development without backend

### Memory Tools (`tinycua_sdk/tools/memory_tools.py`)

```python
@tool()
def remember(key: str, value: str) -> dict:
    """Store a value in memory."""

@tool()
def recall(key: str) -> dict:
    """Retrieve a value from memory."""

@tool()
def forget(key: str) -> dict:
    """Delete a value from memory."""

@tool()
def list_memory() -> dict:
    """List all keys in memory."""

@tool()
def clear_memory() -> dict:
    """Clear all memory."""
```

### How Memory Works

1. **Setup:** Memory tools are added to an agent
2. **Storage:** Backend (local/remote/hybrid) stores key-value pairs
3. **Usage:** LLM can call `remember(key, value)`, `recall(key)`, etc.
4. **Agents can persist:** Information between runs by using these tools

### Current Test Coverage

- Unit tests: `tests/unit/test_memory.py`
- Integration tests: `tests/integration/test_memory_session.py`

---

## Part 3: Plan for Examples

### Skills Examples (new file: `examples/12_skills_example.py`)

**1. Basic Skill Discovery**
- Load skills from directory
- List all skills
- Filter by category
- View skill details

**2. Using Skills with Agent**
- Create agent with skills parameter
- Show how tools from skills are loaded
- Demonstrate runtime skill discovery

**3. Custom Skill Creation**
- Create a simple skill directory
- Write SKILL.md
- Load and test the skill

**4. Skill Activation Logic**
- Platform-specific skills
- Conditional skill loading based on available tools

### Memory Examples (new file: `examples/13_memory_example.py`)

**1. Basic Memory Operations**
- Remember and recall
- List and delete memory
- Clear all memory

**2. Memory with Agent**
- Add memory tools to agent
- Agent remembers user preferences
- Agent recalls previous context

**3. Custom Memory Backend**
- Use LocalMemoryBackend with custom path
- Use HybridMemoryBackend
- Show fallback behavior

**4. Session Memory**
- Store session-specific data
- Retrieve session context

---

## Part 4: Plan for Integration Tests

### Skills Tests (new file: `tests/integration/test_skills_example.py`)

```python
class TestSkillDiscovery:
    - test_load_skills_from_directory()
    - test_list_skills_no_filter()
    - test_list_skills_with_category()
    - test_get_skill_by_name()

class TestSkillWithAgent:
    - test_agent_with_skills_parameter()
    - test_skill_tools_available()
    - test_runtime_skill_discovery()

class TestSkillLoader:
    - test_skill_md_parsing()
    - test_skill_with_yaml_frontmatter()
    - test_skill_instructions_extraction()

class TestSkillActivation:
    - test_platform_activation()
    - test_requires_toolsets_activation()
    - test_fallback_logic()
```

### Memory Tests (enhance: `tests/integration/test_03_memory_session.py`)

```python
class TestMemoryBackend:
    - test_local_backend_set_get()
    - test_local_backend_delete()
    - test_local_backend_list_keys()
    - test_local_backend_clear()

class TestRemoteMemory:
    - test_remote_backend_set_get()
    - test_remote_fallback_to_local()

class TestHybridMemory:
    - test_hybrid_prefers_remote()
    - test_hybrid_fallback_on_error()

class TestMemoryToolsWithAgent:
    - test_remember_with_agent()
    - test_recall_with_agent()
    - test_memory_persists_across_runs()
```

---

## Part 5: Example Test Scenarios

### Skills Test Scenarios

1. **Cold Start Performance**
   - Load 10 skills under 2 seconds
   - Measure discovery time

2. **Skill Metadata**
   - Parsing YAML frontmatter correctly
   - Extracting instructions from markdown

3. **Agent Integration**
   - Skills loaded into agent at creation
   - Tools from skills available at runtime

4. **Conditional Activation**
   - Platform-specific skills activate correctly
   - Tool requirements work properly

### Memory Test Scenarios

1. **Basic CRUD**
   - Can store and retrieve values
   - Can delete values
   - Can list all keys
   - Can clear all memory

2. **Persistence**
   - Values persist between Python runs (local backend)
   - Session data can be retrieved later

3. **Agent Integration**
   - LLM can use remember/recall tools
   - Memory works correctly in multi-turn conversations

4. **Backend Fallback**
   - Hybrid backend tries remote first
   - Falls back to local when remote unavailable

---

## Summary

| Feature | Current Tests | Need New Examples | Need New Tests |
|---------|--------------|-------------------|------------------|
| Skills | Yes (unit + integration) | Yes: 12_skills_example.py | Yes: test_skills_example.py |
| Memory | Yes (basic) | Yes: 13_memory_example.py | Yes: Enhanced test coverage |

The existing tests cover the basics but there are no standalone examples demonstrating these features clearly. Creating dedicated examples and expanding integration tests will help users understand how to use Skills and Memory effectively.