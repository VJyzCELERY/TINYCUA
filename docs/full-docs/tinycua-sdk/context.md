# Context System Documentation

The `context/` package manages context file discovery, compression, sanitization, and injection detection.

**Package path:** `tinycua_sdk/context/`

---

## discovery.py - Context File Discovery

### Purpose

Discovers and loads context files (`.hermes.md`, `AGENTS.md`, `CLAUDE.md`) from the project directory tree.

### ContextDiscoveryError / ContextLoadError

```python
class ContextDiscoveryError(Exception):
    """Raised when context discovery fails."""

class ContextLoadError(Exception):
    """Raised when context file cannot be loaded."""
```

### ContextDiscovery

```python
class ContextDiscovery:
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox"}
    
    def __init__(self, root_dir: Path | None = None, max_depth: int = 5, follow_symlinks: bool = False)
```

**Default behavior:**
- Starts from current working directory (`Path.cwd()`)
- Traverses up to 5 parent directories
- Does not follow symbolic links
- Skips common development directories

### discover()

```python
def discover(self) -> list[tuple[Path, int]]:
    found_files = []
    current_dir = self.root_dir.resolve()
    depth = 0
    
    while depth <= self.max_depth:
        if not current_dir.exists():
            break
        
        # Skip directories in SKIP_DIRS
        if current_dir.name in self.SKIP_DIRS:
            parent = current_dir.parent
            if parent == current_dir:
                break
            current_dir = parent
            depth += 1
            continue
        
        # Check for context files
        for filename in CONTEXT_FILE_NAMES:
            file_path = current_dir / filename
            if file_path.exists() and file_path.is_file():
                if file_path.is_symlink() and not self.follow_symlinks:
                    continue
                priority = CONTEXT_FILE_NAMES.index(filename)
                found_files.append((file_path, priority))
        
        # Move to parent
        parent = current_dir.parent
        if parent == current_dir:
            break
        current_dir = parent
        depth += 1
    
    found_files.sort(key=lambda x: x[1])
    return found_files
```

**Priority order:** `.hermes.md` (0) > `AGENTS.md` (1) > `CLAUDE.md` (2). Lower index = higher priority.

**Traversal algorithm:**
1. Start from `root_dir`
2. Check for context files in current directory
3. Move to parent directory
4. Repeat until `max_depth` or filesystem root reached

**Why skip `SKIP_DIRS`?** Avoids wasting time searching in directories that are unlikely to contain project context files.

**Symlink handling:** If `follow_symlinks=False`, symlinks are ignored. This prevents escaping the intended directory tree.

### load_contexts()

```python
def load_contexts(self) -> list[str]:
    discovered = self.discover()
    contents = []
    
    for file_path, _ in discovered:
        try:
            content = file_path.read_text(encoding="utf-8")
            contents.append(content)
        except OSError as e:
            raise ContextLoadError(f"Failed to read {file_path}: {e}")
    
    return contents
```

Reads all discovered context files in priority order.

### merge_contexts()

```python
def merge_contexts(self) -> str:
    contents = self.load_contexts()
    return "\n\n---\n\n".join(contents)
```

Joins all contexts with `---` separators for clear delineation.

---

## compression.py - Context Compression

### Purpose

Compresses context for large window management, supporting sliding window and summarization strategies.

### CompressionError

```python
class CompressionError(Exception):
    """Raised when context compression fails."""
```

### ContextCompressor

```python
class ContextCompressor:
    def __init__(self, window_size: int = 8000, token_counter: Callable[[str], int] | None = None)
```

**Parameters:**
- `window_size`: Target window size in tokens (default: 8000)
- `token_counter`: Optional custom token counter function

**Default token counter:**
```python
def _default_token_counter(self, text: str) -> int:
    return len(text) // 4
```

Rough approximation: 4 characters per token.

### compress()

```python
def compress(self, messages: list[Message], strategy: str = "sliding") -> list[Message]:
    if strategy not in ("sliding", "summarize"):
        raise CompressionError(f"Unknown strategy: {strategy}")
    
    if not messages:
        return []
    
    if strategy == "sliding":
        return self.sliding_window(messages)
    else:
        return self.summarize(messages)
```

### sliding_window()

```python
def sliding_window(self, messages: list[Message], keep_recent: int = 5) -> list[Message]:
    if not messages:
        return []
    
    # Group by turn_index
    turns: dict[int, list[Message]] = {}
    for msg in messages:
        if msg.turn_index not in turns:
            turns[msg.turn_index] = []
        turns[msg.turn_index].append(msg)
    
    # Get recent turns
    sorted_turns = sorted(turns.keys(), reverse=True)
    recent_turns = sorted_turns[:keep_recent]
    
    # Collect messages from recent turns
    result = []
    for turn in recent_turns:
        result.extend(turns[turn])
    
    # Sort by original order
    result.sort(key=lambda m: (m.turn_index, m.created_at or 0))
    
    return result
```

**Algorithm:**
1. Group messages by `turn_index`
2. Sort turns in reverse chronological order
3. Take the N most recent turns
4. Flatten and re-sort by original order

**Why group by turn_index?** A single "turn" may have multiple messages (user message + tool results). Keeping complete turns preserves conversation coherence.

### summarize()

```python
def summarize(self, messages: list[Message], llm_client: Any = None, summary_length: int = 500) -> list[Message]:
    if not messages:
        return []
    
    # Fallback if no LLM client
    if llm_client is None or not hasattr(llm_client, "chat"):
        return self.sliding_window(messages, keep_recent=10)
    
    # Separate recent and older messages
    recent_threshold = max(m.turn_index for m in messages) - 5
    recent = [m for m in messages if m.turn_index > recent_threshold]
    older = [m for m in messages if m.turn_index <= recent_threshold]
    
    if not older:
        return messages
    
    # Build summary prompt
    older_content = "\n".join(
        f"{m.role}: {m.content[:200]}..." if len(m.content) > 200 else f"{m.role}: {m.content}"
        for m in older
    )
    
    prompt = f"Summarize the following conversation concisely, preserving key information:\n\n{older_content}"
    
    try:
        response = llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=summary_length,
        )
        summary = response.choices[0].message.content
        
        # Create summary message
        msg_id = older[0].id
        if hasattr(msg_id, "hex"):
            msg_id = str(msg_id)
        
        summary_msg = Message(
            id=msg_id,
            session_id=older[0].session_id,
            role="system",
            content=f"[Summary of previous conversation]\n{summary}",
            turn_index=recent[0].turn_index if recent else 0,
        )
        
        return [summary_msg] + recent
    
    except (OSError, ValueError, TypeError, RuntimeError):
        return self.sliding_window(messages)
```

**Two-phase summarization:**
1. Keep the 5 most recent turns intact
2. Summarize older turns into a single system message

**Fallback chain:**
1. If no LLM client → sliding window
2. If LLM client lacks `chat` method → sliding window
3. If LLM call fails → sliding window

**Why keep recent turns?** Recent context is more relevant than older context. Summarizing only old messages preserves the most important recent details.

---

## injection.py - Prompt Injection Detection

### Purpose

Detects prompt injection attempts by scanning for known malicious patterns.

### InjectionThreat Dataclass

```python
@dataclass
class InjectionThreat:
    pattern: str
    location: str
    matched_text: str
    severity: str = "medium"
```

### InjectionDetector

```python
class InjectionDetector:
    INJECTION_PATTERNS = [
        (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE), "high"),
        (re.compile(r"ignore\s+(previous|all|above)\s+instructions", re.IGNORECASE), "high"),
        (re.compile(r"(system|admin)\s+mode", re.IGNORECASE), "high"),
        (re.compile(r"you\s+are\s+(now|acting\s+as)", re.IGNORECASE), "medium"),
        (re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL), "high"),
        (re.compile(r"javascript:", re.IGNORECASE), "high"),
        (re.compile(r"on\w+\s*=", re.IGNORECASE), "high"),
        (re.compile(r"</?[a-z]+[^>]*>", re.IGNORECASE), "medium"),
        (re.compile(r"\{\{.*\}\}"), "medium"),
        (re.compile(r"\{\%\s*\w+\s*\%\}"), "medium"),
        (re.compile(r"\$\{.*\}"), "low"),
    ]
```

**Pattern categories:**
- **High severity:** Instructions override, script tags, JavaScript protocols, event handlers
- **Medium severity:** HTML-like tags, template injection syntax
- **Low severity:** Template literals

**Why ordered patterns?** More specific patterns (like `<script>`) are checked before generic HTML tags to ensure correct severity classification.

### scan_text()

```python
def scan_text(self, text: str, location: str = "text") -> list[InjectionThreat]:
    threats = []
    
    # Check whitelist first
    for wp in self._whitelist_patterns:
        if wp.search(text):
            return []
    
    # Check injection patterns
    for pattern, severity in self.INJECTION_PATTERNS:
        matches = pattern.finditer(text)
        for match in matches:
            threats.append(InjectionThreat(
                pattern=pattern.pattern,
                location=location,
                matched_text=match.group(0)[:100],
                severity=severity,
            ))
    
    return threats
```

**Whitelist support:** If text matches any whitelist pattern, all threats are suppressed. This allows known-safe content to bypass scanning.

**Truncation:** `match.group(0)[:100]` limits matched text to 100 characters for readability.

### scan_file()

```python
def scan_file(self, path: Path) -> list[InjectionThreat]:
    if not path.exists() or not path.is_file():
        return []
    
    try:
        content = path.read_text(encoding="utf-8")
        return self.scan_text(content, location=str(path))
    except OSError:
        return []
```

Reads file and scans content. Returns empty list if file doesn't exist or can't be read.

### scan_memory()

```python
def scan_memory(self, session_id: uuid.UUID) -> list[InjectionThreat]:
    threats = []
    
    try:
        from tinycua_sdk.storage.store import get_session_store
        store = get_session_store()
        messages = store.list_messages(session_id)
        
        for msg in messages:
            content = msg.content or ""
            threats.extend(self.scan_text(content, location=f"memory:{msg.id}"))
    
    except (OSError, ValueError, ImportError, TypeError):
        pass
    
    return threats
```

Scans session messages from the database for injection patterns.

**Why catch ImportError?** If SQLAlchemy or storage is not available, silently returns empty list rather than crashing.

### scan_messages()

```python
def scan_messages(self, messages: list[dict[str, Any]]) -> list[InjectionThreat]:
    threats = []
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        
        # Scan content
        content = msg.get("content", "")
        if isinstance(content, str):
            threats.extend(self.scan_text(content, location=f"message[{i}].{role}"))
        elif isinstance(content, list):
            for j, block in enumerate(content):
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if isinstance(text, str):
                        threats.extend(self.scan_text(text, location=f"message[{i}].{role}[{j}]"))
        
        # Scan tool calls
        tool_calls = msg.get("tool_calls", [])
        for tc in tool_calls:
            if isinstance(tc, dict):
                args = tc.get("arguments", "")
                if isinstance(args, str):
                    threats.extend(self.scan_text(args, location=f"tool_call[{i}]"))
    
    return threats
```

Scans a list of message dicts (OpenAI format). Handles:
- String content
- List content blocks (e.g., GPT-4 Vision format)
- Tool call arguments

**Why scan tool call arguments?** Injection attempts may be hidden in tool arguments that the LLM generates.

### is_safe()

```python
def is_safe(self, text: str) -> bool:
    return len(self.scan_text(text)) == 0
```

Convenience method for boolean safety checks.

---

## sanitizer.py - Message Sanitization

### Purpose

Sanitizes tool calls, results, and messages before sending to LLM to ensure message integrity.

### SanitizationError

```python
class SanitizationError(Exception):
    """Raised when sanitization fails."""
```

### MessageSanitizer

```python
class MessageSanitizer:
    CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    HTML_TAGS = re.compile(r"</?[a-zA-Z][^>]*>", re.IGNORECASE)
    TEMPLATE_SYNTAX = re.compile(r"\{\{.*?\}\}")
    DANGEROUS_PATTERNS = [
        re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript:", re.IGNORECASE),
        re.compile(r"on\w+\s*=", re.IGNORECASE),
    ]
```

### sanitize_tool_call()

```python
def sanitize_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
    sanitized = {}
    
    if "name" in tool_call:
        sanitized["name"] = self._sanitize_string(tool_call["name"])
    
    if "arguments" in tool_call:
        args = tool_call["arguments"]
        if isinstance(args, str):
            sanitized["arguments"] = self.sanitize_tool_args(args)
        elif isinstance(args, dict):
            sanitized["arguments"] = self._sanitize_dict(args)
        else:
            sanitized["arguments"] = args
    
    if "id" in tool_call:
        sanitized["id"] = tool_call["id"]
    
    return sanitized
```

Sanitizes tool call name and arguments while preserving the ID.

### sanitize_tool_args()

```python
def sanitize_tool_args(self, args: str) -> str:
    try:
        parsed = json.loads(args)
        sanitized = self._sanitize_dict(parsed)
        return json.dumps(sanitized, ensure_ascii=False)
    except json.JSONDecodeError:
        return self._sanitize_string(args)
```

**Two paths:**
1. If valid JSON: parse, sanitize values, re-serialize
2. If invalid JSON: sanitize as plain string

### sanitize_system_prompt()

```python
def sanitize_system_prompt(self, prompt: str) -> str:
    prompt = self.CONTROL_CHARS.sub("", prompt)
    prompt = self.TEMPLATE_SYNTAX.sub(lambda m: "\\" + m.group(0), prompt)
    
    for pattern in self.DANGEROUS_PATTERNS:
        prompt = pattern.sub("", prompt)
    
    return prompt.strip()
```

**Sanitization steps:**
1. Remove control characters (null bytes, bell, etc.)
2. Escape template syntax (`{{...}}` → `\{{...}}`) to prevent template injection
3. Strip dangerous patterns (scripts, JS protocols, event handlers)

**Why escape rather than remove templates?** Templates might be legitimate content (e.g., explaining Jinja syntax). Escaping preserves the text while preventing execution.

### _sanitize_string()

```python
def _sanitize_string(self, text: str) -> str:
    if not isinstance(text, str):
        return text
    
    text = self.CONTROL_CHARS.sub("", text)
    text = self.TEMPLATE_SYNTAX.sub(lambda m: "\\" + m.group(0), text)
    text = self.HTML_TAGS.sub("", text)
    text = re.sub(r"\s+", " ", text)
    
    return text.strip()
```

**Normalization:** Collapses multiple whitespace characters into a single space. This prevents whitespace-based obfuscation attacks.

---

## Inter-Module Data Flow

### Context Discovery Flow
```
Agent initialization
  → ContextDiscovery()
    → discover()
      → Traverse directory tree upward
      → Find .hermes.md, AGENTS.md, CLAUDE.md
      → Sort by priority
    → load_contexts()
      → Read each file
      → Return list of contents
    → merge_contexts()
      → Join with --- separators
```

### Compression Flow
```
Context window full
  → ContextCompressor.compress(messages, strategy="summarize")
    → If summarize:
      → Split into recent (5 turns) + older
      → Build summary prompt
      → LLM call for summary
      → Create summary system message
      → Return [summary_msg] + recent
    → If sliding:
      → Group by turn_index
      → Keep N most recent turns
      → Return filtered messages
```

### Security Scan Flow
```
User input received
  → InjectionDetector.scan_messages(messages)
    → For each message:
      → scan_text(content)
        → Check whitelist
        → Check injection patterns
        → Return InjectionThreat list
  → If threats found:
    → Log warning (don't block - detection only)
```

### Sanitization Flow
```
Before sending to LLM
  → MessageSanitizer.sanitize_message(message)
    → Sanitize role
    → Sanitize content
    → Preserve tool_calls, tool_call_id
  → MessageSanitizer.sanitize_tool_call(tool_call)
    → Sanitize name
    → Sanitize arguments (JSON parse + sanitize dict)
```
