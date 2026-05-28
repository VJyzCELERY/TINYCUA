# Modeling Documentation

The `modeling/` package provides personality customization, communication profiling, and user preference tracking.

**Package path:** `tinycua_sdk/modeling/`

---

## personality.py - Personality System

### Purpose

Defines and applies personality traits to agent responses for behavior customization.

### PersonalityTraits Dataclass

```python
@dataclass
class PersonalityTraits:
    name: str = "helpful assistant"
    tone: str = "friendly"
    verbosity: str = "balanced"
    humor: float = 0.3
    empathy: float = 0.7
    creativity: float = 0.5
```

**Traits explained:**
- `name`: Persona identifier (e.g., "professional consultant", "casual friend")
- `tone`: Communication style ("formal", "friendly", "casual")
- `verbosity`: Response length preference ("concise", "balanced", "detailed")
- `humor`: Humor level (0.0-1.0)
- `empathy`: Emotional responsiveness (0.0-1.0)
- `creativity`: Creative expression level (0.0-1.0)

### Personality Class

```python
class Personality:
    DEFAULT_TRAITS = PersonalityTraits()
    
    def __init__(self, long_term_memory):
        self.memory = long_term_memory
        self.traits = PersonalityTraits()
        self._load()
```

**Persistence:** Loads/saves traits to `USER.md` via `LongTermMemory`.

### Backup System

```python
def _backup_user(self) -> None:
    user_file = self.memory._file_path("USER.md")
    if user_file.exists():
        backup_file = user_file.with_suffix(".md.bak")
        shutil.copy2(user_file, backup_file)
        self._cleanup_backups(user_file)

def _cleanup_backups(self, user_file: Path) -> None:
    backup_files = sorted(
        user_file.parent.glob(f"{user_file.stem}*.bak"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for backup in backup_files[5:]:
        backup.unlink(missing_ok=True)
```

**Backup strategy:**
1. Before each write, copy current file to `.md.bak`
2. Keep only the 5 most recent backups
3. Delete older backups

**Why backups?** Prevents data loss from corruption or bugs during writes.

### Loading and Saving

```python
def _load(self) -> None:
    data = self.memory.read_user()
    if data:
        try:
            model = json.loads(data)
            if "personality" in model:
                self.traits = PersonalityTraits.from_dict(model["personality"])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

def _save(self) -> None:
    self._backup_user()
    data = self.memory.read_user()
    model = json.loads(data) if data else {}
    model["personality"] = self.traits.to_dict()
    self.memory.write_user(json.dumps(model, indent=2))
```

**JSON structure in USER.md:**
```json
{
  "personality": {
    "name": "helpful assistant",
    "tone": "friendly",
    "verbosity": "balanced",
    "humor": 0.3,
    "empathy": 0.7,
    "creativity": 0.5
  }
}
```

### set_traits()

```python
def set_traits(self, **kwargs) -> None:
    current = self.traits.to_dict()
    updates = {k: v for k, v in kwargs.items() if v is not None}
    merged = self._merge_strategy(current, updates)
    self.traits = PersonalityTraits.from_dict(merged)
    self._save()

def _merge_strategy(self, current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = current.copy()
    for key, value in updates.items():
        if value is not None:
            merged[key] = value
    return merged
```

**Merge behavior:** Only updates fields with non-None values. Preserves existing values for unspecified fields.

### apply_to_response()

```python
def apply_to_response(self, response: str) -> str:
    result = response
    
    if self.traits.tone == "formal":
        result = result.replace("hey", "hello")
        result = result.replace("gonna", "going to")
        result = result.replace("wanna", "want to")
    elif self.traits.tone == "friendly":
        if "hello" in result.lower():
            result = result.replace("hello", "hey", 1)
    
    if self.traits.verbosity == "concise" and len(result) > 200:
        result = result[:200] + "..."
    elif self.traits.verbosity == "detailed" and len(result) < 50:
        result = result + " Let me know if you need more details."
    
    if self.traits.humor > 0.7 and "error" in result.lower():
        result = result.replace("error", "oopsie")
    
    return result
```

**Transformations:**
- **Formal tone:** Replace casual words with formal equivalents
- **Friendly tone:** Replace "hello" with "hey" (first occurrence only)
- **Concise verbosity:** Truncate to 200 characters
- **Detailed verbosity:** Append offer for more details if response is very short
- **High humor:** Replace "error" with "oopsie" (playful error handling)

**Why simple string replacement?** Fast, no LLM call required, predictable behavior. More sophisticated transformations would require re-prompting the LLM.

---

## profiler.py - Communication Profiler

### Purpose

Profiles user communication style by analyzing message patterns.

### CommunicationStyle Dataclass

```python
@dataclass
class CommunicationStyle:
    formality: float = 0.5
    verbosity: float = 0.5
    technical_level: float = 0.5
```

**Scales:**
- `formality`: 0.0 = very casual, 1.0 = very formal
- `verbosity`: 0.0 = very brief, 1.0 = very verbose
- `technical_level`: 0.0 = layperson, 1.0 = highly technical

### CommunicationProfiler

```python
class CommunicationProfiler:
    FORMAL_WORDS = ["please", "thank", "would", "could", "appreciate", "kindly"]
    CASUAL_WORDS = ["hey", "yeah", "gonna", "wanna", "cool", "awesome"]
    TECHNICAL_WORDS = ["api", "algorithm", "function", "class", "method", "parameter", "return", "import"]
    
    def __init__(self, sensitivity: int = 10)
```

**Sensitivity:** Number of messages to collect before recalculating style profile.

### analyze()

```python
def analyze(self, message: dict[str, Any]) -> None:
    self._message_samples.append(message)
    
    if len(self._message_samples) >= self._sensitivity:
        self._recalculate_style()
```

Accumulates messages. Recalculates style when threshold reached.

### _recalculate_style()

```python
def _recalculate_style(self) -> None:
    content = " ".join(m.get("content", "") for m in self._message_samples)
    content_lower = content.lower()
    
    # Formality
    formal_count = sum(1 for w in self.FORMAL_WORDS if w in content_lower)
    casual_count = sum(1 for w in self.CASUAL_WORDS if w in content_lower)
    if formal_count + casual_count > 0:
        self.style.formality = formal_count / (formal_count + casual_count)
    
    # Verbosity
    avg_length = sum(len(m.get("content", "")) for m in self._message_samples) / len(self._message_samples)
    self.style.verbosity = min(1.0, avg_length / 500)
    
    # Technical level
    tech_count = sum(1 for w in self.TECHNICAL_WORDS if w in content_lower)
    total_words = len(content.split())
    if total_words > 0:
        self.style.technical_level = min(1.0, tech_count / max(1, total_words * 0.2))
```

**Formality calculation:**
```
formality = formal_word_count / (formal_word_count + casual_word_count)
```

- 1.0 = only formal words
- 0.0 = only casual words
- 0.5 = equal mix

**Verbosity calculation:**
```
verbosity = min(1.0, avg_message_length / 500)
```

- 500 characters per message = 1.0 (max verbosity)
- Shorter messages scale proportionally

**Technical level calculation:**
```
technical_level = min(1.0, tech_word_count / (total_words * 0.2))
```

- 20% of words being technical = 1.0 (max technical)
- Based on the assumption that natural language rarely exceeds 20% technical terms

**Why word lists instead of ML?** Simple, fast, no training data required, works offline. Quality is lower than neural approaches but sufficient for basic adaptation.

---

## user.py - User Modeling

### Purpose

Tracks user preferences, goals, and context with persistence via `LongTermMemory`.

### UserPreference Dataclass

```python
@dataclass
class UserPreference:
    key: str
    value: str
    confidence: float
    updated_at: datetime = field(default_factory=datetime.now)
```

**Confidence tracking:** Allows the agent to know how certain a preference is. Low confidence preferences might be confirmed before acting on them.

### UserGoal Dataclass

```python
@dataclass
class UserGoal:
    description: str
    status: str  # "active", "completed", "abandoned"
    created_at: datetime = field(default_factory=datetime.now)
```

### UserModel

```python
class UserModel:
    def __init__(self, long_term_memory):
        self.memory = long_term_memory
        self.preferences: dict[str, UserPreference] = {}
        self.goals: list[UserGoal] = []
        self.context: dict[str, Any] = {}
        self._load()
```

### Persistence

```python
def _load(self) -> None:
    data = self.memory.read_user()
    if data:
        try:
            model = json.loads(data)
            self.preferences = {k: UserPreference.from_dict(v) for k, v in model.get("preferences", {}).items()}
            self.goals = [UserGoal.from_dict(g) for g in model.get("goals", [])]
            self.context = model.get("context", {})
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

def _save(self) -> None:
    model = {
        "preferences": {k: p.to_dict() for k, p in self.preferences.items()},
        "goals": [g.to_dict() for g in self.goals],
        "context": self.context,
    }
    self.memory.write_user(json.dumps(model, indent=2))
```

**JSON structure in USER.md:**
```json
{
  "personality": {...},
  "preferences": {
    "theme": {"key": "theme", "value": "dark", "confidence": 0.9, "updated_at": "2024-01-15T10:30:00"},
    "language": {"key": "language", "value": "python", "confidence": 1.0, "updated_at": "2024-01-15T10:30:00"}
  },
  "goals": [
    {"description": "Build a web app", "status": "active", "created_at": "2024-01-15T10:30:00"}
  ],
  "context": {
    "current_project": "my_app"
  }
}
```

### Preference Management

```python
def add_preference(self, key: str, value: str, confidence: float = 1.0) -> None:
    self.preferences[key] = UserPreference(key=key, value=value, confidence=confidence)
    self._save()

def get_preference(self, key: str) -> Optional[str]:
    pref = self.preferences.get(key)
    return pref.value if pref else None

def get_all_preferences(self) -> dict[str, str]:
    return {k: p.value for k, p in self.preferences.items()}
```

### Goal Management

```python
def add_goal(self, description: str) -> None:
    goal = UserGoal(description=description, status="active")
    self.goals.append(goal)
    self._save()

def update_goal_status(self, index: int, status: str) -> None:
    if 0 <= index < len(self.goals):
        self.goals[index].status = status
        self._save()

def get_goals_by_status(self, status: str) -> list[UserGoal]:
    return [g for g in self.goals if g.status == status]
```

**Why index-based rather than ID-based?** Simpler API for common use cases. Goals are typically managed in sequence ("mark the third goal as completed").

### Context Management

```python
def update_context(self, key: str, value: Any) -> None:
    self.context[key] = value
    self._save()
```

Stores arbitrary key-value pairs for session-spanning context.

---

## Inter-Module Data Flow

### Personality Flow
```
Agent initialization
  → Personality(long_term_memory)
    → _load()
      → Read USER.md
      → Parse JSON
      → Extract personality traits
  → During conversation:
    → personality.apply_to_response(response)
      → Apply tone transformations
      → Apply verbosity adjustments
      → Return modified response
  → User updates traits:
    → personality.set_traits(tone="formal")
      → Merge with current traits
      → _save()
        → Write to USER.md
```

### Profiling Flow
```
User sends message
  → CommunicationProfiler.analyze(message)
    → Append to samples
    → If samples >= sensitivity:
      → _recalculate_style()
        → Count formal/casual words
        → Calculate average length
        → Count technical words
        → Update style scores
```

### User Model Flow
```
User expresses preference
  → UserModel.add_preference("theme", "dark", confidence=0.9)
    → Update preferences dict
    → _save()
      → Serialize to JSON
      → Write to USER.md
  → Later:
    → UserModel.get_preference("theme")
      → Return "dark"
```
