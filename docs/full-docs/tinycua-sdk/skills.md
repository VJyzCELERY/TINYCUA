# Skills System Documentation

The `skills/` package implements a progressive skill disclosure system for agents. Skills are reusable capability packages defined in `SKILL.md` files that can be conditionally loaded based on the environment.

**Package path:** `tinycua_sdk/skills/`

---

## models.py - Skill Data Model

### Purpose

Defines the `Skill` dataclass representing a loaded skill from the filesystem.

### Skill Dataclass

```python
@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "general"
    instructions: str = ""
    tools: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    modified_at: datetime | None = None
```

**Field explanations:**
- `name`: Unique skill identifier
- `description`: Brief explanation for agent discovery
- `category`: Grouping (e.g., "coding", "research", "communication")
- `instructions`: Detailed guidance for the agent on how to use this skill
- `tools`: List of tool names this skill provides/requires
- `dependencies`: Other skills that must be loaded first
- `path`: Filesystem location of the skill directory
- `metadata`: Raw YAML frontmatter data (for conditional activation)

**Why store raw metadata?** Allows `SkillActivator` to check custom conditions without modifying the Skill model.

### Serialization

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "name": self.name,
        "description": self.description,
        "category": self.category,
        "instructions": self.instructions,
        "tools": self.tools,
        "dependencies": self.dependencies,
        "path": str(self.path) if self.path else None,
        "metadata": self.metadata,
        "created_at": self.created_at.isoformat() if self.created_at else None,
        "modified_at": self.modified_at.isoformat() if self.modified_at else None,
    }
```

Converts to JSON-serializable dict with ISO format dates.

---

## loader.py - SKILL.md Loader

### Purpose

Loads and parses `SKILL.md` files from specified directories.

### Exceptions

```python
class SkillNotFoundError(Exception):
    """Raised when a skill is not found in the expected location."""

class SkillParseError(Exception):
    """Raised when skill metadata cannot be parsed."""
```

### SkillLoader

```python
class SkillLoader:
    DEFAULT_SKILL_DIRS = [
        Path(os.path.expanduser("~/.tinycua/skills")),
        Path("./skills"),
    ]
```

**Default search paths:**
1. `~/.tinycua/skills` - User-level skills
2. `./skills` - Project-level skills

### load_skill()

```python
def load_skill(self, path: Path) -> Skill:
    skill_md_path = path / "SKILL.md"
    
    if not skill_md_path.exists():
        raise SkillNotFoundError(f"SKILL.md not found in {path}")
    
    content = skill_md_path.read_text(encoding="utf-8")
    return self._parse_skill_md(path, content)
```

**File structure expected:**
```
skills/
├── my_skill/
│   └── SKILL.md
└── another_skill/
    └── SKILL.md
```

### _parse_skill_md()

```python
def _parse_skill_md(self, path: Path, content: str) -> Skill:
    if content.startswith("---"):
        parts = content.split("---", 2)
        yaml_content = parts[1].strip()
        markdown_content = parts[2].strip()
    else:
        yaml_content = ""
        markdown_content = content
    
    metadata = yaml.safe_load(yaml_content) or {}
    
    name = metadata.get("name", path.name)
    description = metadata.get("description", "")
    category = metadata.get("category", "general")
    tools = metadata.get("tools", [])
    dependencies = metadata.get("dependencies", [])
    instructions = self._extract_instructions(markdown_content)
    
    # File timestamps
    stat = skill_md_path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime)
    created_at = datetime.fromtimestamp(stat.st_ctime)
    
    return Skill(...)
```

**YAML frontmatter format:**
```markdown
---
name: my_skill
description: Does something useful
category: coding
tools:
  - file_read
  - file_write
dependencies:
  - base_coding
---

# My Skill

Detailed instructions for the agent...
```

**Why split by "---"?** Standard YAML frontmatter delimiter used by Jekyll, Hugo, and other static site generators.

### _extract_instructions()

```python
def _extract_instructions(self, markdown_content: str) -> str:
    lines = markdown_content.split("\n")
    result_lines = []
    skip_instructions = False
    
    for line in lines:
        if "## Instructions" in line or "##instructions" in line.lower():
            skip_instructions = True
            continue
        
        if skip_instructions and line.strip().startswith("#"):
            skip_instructions = False
        
        result_lines.append(line)
    
    return "\n".join(result_lines).strip()
```

Removes the "## Instructions" header section if present. This allows skills to have a dedicated instructions section that gets extracted separately from other markdown content.

### discover_skills()

```python
def discover_skills(self, base_dir: Path) -> list[Skill]:
    if not base_dir.exists() or not base_dir.is_dir():
        return []
    
    skills = []
    for entry in sorted(base_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            try:
                skill = self.load_skill(entry)
                skills.append(skill)
            except (SkillNotFoundError, SkillParseError):
                continue
    
    return skills
```

**Discovery rules:**
- Skips non-directories
- Skips hidden directories (starting with `.`)
- Ignores directories without valid `SKILL.md`
- Sorts entries for deterministic ordering

### convert_to_tools()

```python
def convert_to_tools(self, skills: list[Skill]) -> list[dict]:
    tools = []
    for skill in skills:
        tool = {
            "name": skill.name.lower().replace(" ", "_"),
            "description": skill.description or skill.instructions[:100],
            "input_schema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "User input for the skill"}
                },
                "required": ["input"]
            },
            "_skill": skill,
        }
        tools.append(tool)
    return tools
```

Converts skills to a tool-like format for agent integration. Each skill becomes a pseudo-tool with a single `input` parameter.

---

## registry.py - Skill Registry

### Purpose

Central registry for managing loaded skills with caching support.

### SkillRegistry

```python
class SkillRegistry:
    def __init__(self, cache: Any | None = None):
        self._skills: dict[str, Skill] = {}
        self._loader = SkillLoader()
        self._cache = cache
```

**Design:** Simple dict-based storage with a default `SkillLoader`.

### Core Methods

```python
def register_skill(self, skill: Skill) -> None:
    self._skills[skill.name] = skill

def get_skill(self, name: str) -> Skill | None:
    return self._skills.get(name)

def list_skills(self, category: str | None = None) -> list[Skill]:
    skills = list(self._skills.values())
    if category:
        skills = [s for s in skills if s.category == category]
    return sorted(skills, key=lambda s: s.name)
```

**Why no automatic loading?** The registry is passive - skills must be explicitly loaded via `load_skills_from_directory()` or `register_skill()`.

### Directory Loading

```python
def load_skills_from_directory(self, base_dir: Path) -> list[Skill]:
    skills = self._loader.discover_skills(base_dir)
    for skill in skills:
        self.register_skill(skill)
    return skills
```

Discovers and registers all valid skills in a directory.

---

## tools.py - Skills Tools

### Purpose

Creates tools for progressive skill disclosure - allowing agents to discover and view available skills at runtime.

### CallableTool

```python
class CallableTool:
    def __init__(self, tool_instance):
        self._tool = tool_instance
    
    @property
    def name(self) -> str:
        return self._tool.name
    
    def __call__(self, *args, **kwargs):
        sig = inspect.signature(self._tool._fn)
        param_names = list(sig.parameters.keys())
        
        for i, arg in enumerate(args):
            if i < len(param_names):
                kwargs[param_names[i]] = arg
        
        return self._tool.invoke(**kwargs)
```

**Wrapper purpose:** Converts positional arguments to keyword arguments based on parameter names. This makes tools callable with both `tool("value")` and `tool(param="value")` syntax.

### create_skills_list_tool()

```python
def create_skills_list_tool(registry: SkillRegistry):
    @tool
    def skills_list(category: str | None = None) -> dict[str, Any]:
        """List available skills with their metadata.
        
        Use this to discover what skills are available...
        """
        skills = registry.list_skills(category=category)
        return {
            "skills": [
                {"name": s.name, "description": s.description, "category": s.category, "tools": s.tools}
                for s in skills
            ]
        }
    
    return CallableTool(skills_list)
```

Creates a tool that lists available skills. The docstring is exposed to the LLM so it knows when to use this tool.

### create_skill_view_tool()

```python
def create_skill_view_tool(registry: SkillRegistry):
    @tool
    def skill_view(skill_name: str) -> dict[str, Any]:
        """View full details of a specific skill..."""
        skill = registry.get_skill(skill_name)
        if skill is None:
            raise ValueError(f"Skill '{skill_name}' not found")
        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "instructions": skill.instructions,
            "tools": skill.tools,
            "dependencies": skill.dependencies,
        }
    
    return CallableTool(skill_view)
```

Creates a tool that returns full skill details including instructions. Agents can use this to "learn" a skill on demand.

---

## cache.py - Skills Cache

### Purpose

Two-layer cache: LRU in-memory + disk snapshot for fast skill access across sessions.

### SkillCache

```python
class SkillCache:
    def __init__(
        self,
        max_size: int = 100,
        snapshot_dir: Path | None = None,
        check_modification: bool = True,
    )
```

### LRU Cache Implementation

```python
def get(self, key: str) -> Skill | None:
    with self._lock:
        skill = self._cache.get(key)
        
        if skill is not None:
            if self.check_modification and self.invalidate_if_stale(skill):
                self.invalidate(key)
                return None
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
        
        return skill
```

**Access order tracking:** Maintains a list of keys in access order. Most recently used at the end, least recently used at the beginning.

### Stale Detection

```python
def invalidate_if_stale(self, skill: Skill) -> bool:
    if skill.path is None:
        return False
    
    skill_md_path = skill.path / "SKILL.md"
    if not skill_md_path.exists():
        return True
    
    current_mtime = skill_md_path.stat().st_mtime
    skill_mtime = skill.modified_at.timestamp() if skill.modified_at else 0
    
    return current_mtime > skill_mtime
```

Compares cached modification time with actual file modification time. If the file has been modified since caching, the skill is considered stale.

**Why check mtime?** Skills are file-based and may be edited by users. Stale detection ensures agents use the latest skill definitions.

### Snapshot Persistence

```python
def save_snapshot(self) -> None:
    snapshot = {
        "saved_at": datetime.now().isoformat(),
        "skills": {},
    }
    
    for key, skill in self._cache.items():
        skill_data = skill.to_dict()
        skill_data["_cached_mtime"] = skill.modified_at.timestamp() if skill.modified_at else 0
        skill_data["_cached_ctime"] = skill.created_at.timestamp() if skill.created_at else 0
        snapshot["skills"][key] = skill_data
    
    snapshot_path = self.snapshot_dir / "skills_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
```

Saves cache to `~/.tinycua/cache/skills/skills_snapshot.json`. Includes cached timestamps for stale detection on next load.

### Snapshot Loading

```python
def load_snapshot(self) -> None:
    snapshot_path = self.snapshot_dir / "skills_snapshot.json"
    if not snapshot_path.exists():
        return
    
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    
    for key, skill_data in snapshot.get("skills", {}).items():
        skill = Skill(
            name=skill_data.get("name", key),
            description=skill_data.get("description", ""),
            # ...
        )
        # Restore timestamps
        cached_mtime = skill_data.get("_cached_mtime", 0)
        if cached_mtime:
            skill.modified_at = datetime.fromtimestamp(cached_mtime)
        
        self._cache[key] = skill
        self._access_order.append(key)
```

Reconstructs `Skill` objects from snapshot. Restores modification times for stale detection.

---

## improver.py - Skill Auto-Improvement

### Purpose

Tracks skill usage patterns and generates procedural improvement suggestions.

### Data Models

```python
@dataclass
class SkillUsage:
    skill_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: str | None = None
    duration_ms: int = 0

@dataclass
class SkillImprovement:
    skill_name: str
    improvement_type: str
    description: str
    generated_at: datetime = field(default_factory=datetime.now)
```

### SkillImprover

```python
class SkillImprover:
    def __init__(self):
        self._usage_history: list[SkillUsage] = []
        self._improvements: list[SkillImprovement] = []
```

### track_usage()

```python
async def track_usage(self, skill_name: str, success: bool = True, error: str | None = None, duration_ms: int = 0) -> None:
    usage = SkillUsage(skill_name=skill_name, success=success, error=error, duration_ms=duration_ms)
    self._usage_history.append(usage)
```

Records each skill invocation with outcome and timing.

### analyze_patterns()

```python
async def analyze_patterns(self) -> dict[str, dict[str, Any]]:
    patterns = {}
    
    for usage in self._usage_history:
        if usage.skill_name not in patterns:
            patterns[usage.skill_name] = {
                "total_uses": 0,
                "successful_uses": 0,
                "failed_uses": 0,
                "total_duration_ms": 0,
                "errors": [],
            }
        
        stats = patterns[usage.skill_name]
        stats["total_uses"] += 1
        if usage.success:
            stats["successful_uses"] += 1
        else:
            stats["failed_uses"] += 1
            if usage.error:
                stats["errors"].append(usage.error)
        stats["total_duration_ms"] += usage.duration_ms
    
    # Compute averages
    for skill_name, stats in patterns.items():
        if stats["total_uses"] > 0:
            stats["success_rate"] = stats["successful_uses"] / stats["total_uses"]
            stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["total_uses"]
    
    return patterns
```

Aggregates usage statistics per skill: total uses, success rate, average duration, error frequencies.

### generate_improvements()

```python
async def generate_improvements(self, patterns: dict[str, dict[str, Any]]) -> list[SkillImprovement]:
    improvements = []
    
    for skill_name, stats in patterns.items():
        # Low success rate
        if stats["success_rate"] < 0.8 and stats["total_uses"] >= 3:
            improvements.append(SkillImprovement(
                skill_name=skill_name,
                improvement_type="prompt_refinement",
                description=f"Success rate is {stats['success_rate']:.0%}. Consider improving instructions.",
            ))
        
        # High latency
        if stats["avg_duration_ms"] > 5000 and stats["total_uses"] >= 2:
            improvements.append(SkillImprovement(
                skill_name=skill_name,
                improvement_type="efficiency",
                description=f"Average duration {stats['avg_duration_ms']:.0f}ms exceeds threshold. Consider optimizing.",
            ))
        
        # Recurring errors
        if stats["errors"]:
            error_counts = {}
            for error in stats["errors"]:
                error_counts[error] = error_counts.get(error, 0) + 1
            most_common_error = max(error_counts, key=error_counts.get)
            if error_counts[most_common_error] >= 2:
                improvements.append(SkillImprovement(
                    skill_name=skill_name,
                    improvement_type="error_handling",
                    description=f"Common error: '{most_common_error}'. Add error handling.",
                ))
    
    return improvements
```

**Improvement triggers:**
- **Success rate < 80%** with ≥3 uses → `prompt_refinement`
- **Average duration > 5000ms** with ≥2 uses → `efficiency`
- **Same error ≥2 times** → `error_handling`

**Why thresholds?** Prevents generating improvements from insufficient data. 3 uses minimum for success rate ensures statistical relevance.

### persist_improvements()

```python
async def persist_improvements(self, memory: Any) -> None:
    for improvement in self._improvements:
        key = f"skill_improvement:{improvement.skill_name}:{improvement.improvement_type}"
        value = {
            "skill_name": improvement.skill_name,
            "improvement_type": improvement.improvement_type,
            "description": improvement.description,
            "generated_at": improvement.generated_at.isoformat(),
        }
        
        if hasattr(memory, "set"):
            await memory.set(key, value)
        elif hasattr(memory, "store"):
            memory.store(key, value)
```

Stores improvements to memory backend. Uses duck typing (`hasattr`) to support different memory interfaces.

---

## backend.py - Skill Storage Backend

### Purpose

Provides skill storage backends with DB-first + local fallback, mirroring the memory backend pattern.

### SkillBackend (ABC)

```python
class SkillBackend(ABC):
    @abstractmethod
    def get(self, name: str) -> Skill | None: ...
    @abstractmethod
    def set(self, skill: Skill) -> dict[str, Any]: ...
    @abstractmethod
    def delete(self, name: str) -> dict[str, Any]: ...
    @abstractmethod
    def list(self, category: str | None = None) -> list[Skill]: ...
    @abstractmethod
    def clear(self) -> dict[str, Any]: ...
```

### LocalSkillBackend

```python
class LocalSkillBackend(SkillBackend):
    def __init__(self, storage_path: str | None = None)
```

Stores skills in `~/.tinycua/skills.json` as a JSON object mapping skill names to skill data.

**Conversion methods:**
```python
def _skill_to_data(self, skill: Skill) -> dict[str, Any]:
    return {
        "description": skill.description,
        "category": skill.category,
        "instructions": skill.instructions,
        "tools": skill.tools,
        "dependencies": skill.dependencies,
        "metadata": skill.metadata,
        "is_active": getattr(skill, "is_active", True),
        "version": getattr(skill, "version", "1.0.0"),
    }

def _data_to_skill(self, name: str, data: dict) -> Skill:
    return Skill(
        name=name,
        description=data.get("description", ""),
        category=data.get("category", "general"),
        instructions=data.get("instructions", ""),
        tools=data.get("tools", []),
        dependencies=data.get("dependencies", []),
        metadata=data.get("metadata", {}),
    )
```

### RemoteSkillBackend

```python
class RemoteSkillBackend(SkillBackend):
    def __init__(self, backend_url: str, api_key: str | None = None)
```

Communicates with backend API:
- `GET /api/v1/skills/{name}` → Get skill
- `POST /api/v1/skills` → Create/update skill
- `DELETE /api/v1/skills/{name}` → Delete skill
- `GET /api/v1/skills` → List skills

### HybridSkillBackend

```python
class HybridSkillBackend(SkillBackend):
    def __init__(self, backend_url: str | None = None, api_key: str | None = None, local_storage_path: str | None = None)
```

Tries remote first, falls back to local on failure. Health check probes remote before each operation.

---

## Inter-Module Data Flow

### Skill Discovery Flow
```
Agent initialization with skills=["coding", "research"]
  → AgentLoader._load_skill_tools()
    → SkillRegistry.load_skills_from_directory(skill_dir)
      → SkillLoader.discover_skills()
        → For each subdirectory:
          → load_skill() → _parse_skill_md()
            → yaml.safe_load(frontmatter)
            → _extract_instructions(markdown)
          → register_skill()
    → SkillActivator.should_activate_skill()
      → Check platforms, toolsets, tools
    → SkillToolResolver.resolve_skill_tools()
      → ToolRegistry.get(tool_name)
    → _load_skill() recursively for dependencies
```

### Skill Usage Flow
```
Agent uses skill
  → SkillImprover.track_usage("coding", success=True, duration_ms=150)
    → Append SkillUsage to history
  → (Later) SkillImprover.analyze_patterns()
    → Aggregate statistics per skill
  → SkillImprover.generate_improvements()
    → Check thresholds
    → Create SkillImprovement suggestions
  → SkillImprover.persist_improvements(memory)
    → Store to memory backend
```
