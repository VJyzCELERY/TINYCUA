# Tools Module Documentation

The tools module provides agent tools for memory management, context retrieval, and computer-use automation (keyboard, mouse, screen capture).

---

## Module Structure

```
agent/tools/
├── __init__.py              # Exports all tools
├── context_tools.py         # Session context retrieval
├── memory_tools.py          # Key-value memory
└── cua/
    ├── __init__.py          # Conditional exports
    ├── keyboard.py          # Keyboard automation
    ├── mouse.py             # Mouse automation
    └── screen_capture.py    # Screen capture
```

---

## `agent/tools/__init__.py`

```python
from tinycua.agent.tools.context_tools import (
    ContextTools,
    get_context_summary_tool,
    get_recent_turns_tool,
    search_context_grep_tool,
    search_context_semantic_tool,
)
from tinycua.agent.tools.memory_tools import (
    clear_memory,
    forget,
    list_memory,
    recall,
    remember,
    reset_memory_backend,
    set_memory_backend,
)

__all__ = [
    "remember", "recall", "forget", "list_memory", "clear_memory",
    "set_memory_backend", "reset_memory_backend",
    "ContextTools", "search_context_grep_tool", "search_context_semantic_tool",
    "get_context_summary_tool", "get_recent_turns_tool",
]
```

---

## `agent/tools/context_tools.py`

### Purpose

Provides tools for retrieving and searching session context (conversation history). These tools allow the agent to look up past messages, search for specific content, and get summaries.

### `ContextTools` Class

```python
class ContextTools:
    def __init__(self, session_store=None, session_id=None):
        self._store = session_store
        self._session_id = session_id
```

**Lazy store initialization:**
```python
def _get_store(self):
    if self._store is None:
        from tinycua_sdk.storage.store import get_session_store
        self._store = get_session_store()
    return self._store
```

If no session store is provided, it resolves the database URL via `SDKConfig` → environment → default fallback.

### `search_context_grep()`

```python
def search_context_grep(self, query: str) -> dict[str, Any]:
```

**Returns:** `{"results": [{"content": "...", "matches": N}]}`

**Error:** Returns `{"error": "No active session. Set session_id first."}` if no session ID is set.

**Implementation:** Delegates to `store.search_grep(session_id, query)`.

### `search_context_semantic()`

```python
def search_context_semantic(self, query: str) -> dict[str, Any]:
```

**Returns:** `{"results": [{"content": "...", "score": 0.95}]}`

**Current status:** Not implemented. Returns error:
```python
return {"error": "Semantic search requires embeddings. Not implemented yet."}
```

**Why included?** Placeholder for future embedding-based semantic search.

### `get_context_summary()`

```python
def get_context_summary(self) -> dict[str, Any]:
```

**Returns:** `{"summary": "...", "has_summary": True}` or `{"summary": None, "has_summary": False}`

Gets the compacted summary of the session from the store.

### `get_recent_turns()`

```python
def get_recent_turns(self, count: int = 3) -> dict[str, Any]:
```

**Returns:** `{"turns": [{"role": "...", "content": "...", "turn_index": N}]}`

Gets the most recent non-archived turns from the session.

### Tool Factory Functions

Each tool is wrapped in a factory function that creates a `@tool()`-decorated function:

```python
def search_context_grep_tool(session_store=None, session_id=None):
    ctx = ContextTools(session_store, session_id)

    @tool()
    def search_context_grep(query: str) -> dict[str, Any]:
        """Search session context using text matching."""
        return ctx.search_context_grep(query)

    return search_context_grep
```

**Factory pattern benefits:**
- Allows injecting `session_store` and `session_id` at creation time
- The returned function is a proper SDK `Tool` via the `@tool()` decorator
- Clean separation between tool logic and tool registration

**Available factory functions:**
- `search_context_grep_tool(session_store, session_id)`
- `search_context_semantic_tool(session_store, session_id)`
- `get_context_summary_tool(session_store, session_id)`
- `get_recent_turns_tool(session_store, session_id)`

---

## `agent/tools/memory_tools.py`

### Purpose

Provides key-value memory storage tools for agents. Uses a singleton `MemoryBackend` instance.

### Global State

```python
_memory_backend: MemoryBackend | None = None
```

**Why global?** Memory should be shared across all agent instances and tool calls. A module-level singleton ensures consistency.

### `_get_memory_backend()`

```python
def _get_memory_backend() -> MemoryBackend:
    global _memory_backend
    if _memory_backend is None:
        backend_url = os.environ.get("TINYCUA_BACKEND_URL")
        api_key = os.environ.get("TINYCUA_API_KEY")
        local_only = os.environ.get("TINYCUA_MEMORY_LOCAL_ONLY", "false").lower() == "true"
        _memory_backend = get_memory_backend(backend_url, api_key, local_only)
    return _memory_backend
```

**Configuration via environment:**
- `TINYCUA_BACKEND_URL` — Remote backend URL for distributed memory
- `TINYCUA_API_KEY` — API key for remote memory
- `TINYCUA_MEMORY_LOCAL_ONLY` — Force local SQLite memory (default: false)

**Why environment variables?** Memory backend configuration is low-level and should be controllable without modifying config files.

### `set_memory_backend()`

```python
def set_memory_backend(backend: MemoryBackend) -> None:
```

Allows injecting a custom backend (useful for testing).

### `reset_memory_backend()`

```python
def reset_memory_backend() -> None:
```

Resets to default (creates new backend on next access).

### Memory Tool Functions

All functions are decorated with `@tool()` from the SDK.

#### `remember(key, value)`

```python
@tool()
def remember(key: str, value: str) -> dict:
    backend = _get_memory_backend()
    return backend.set(key, value)
```

Stores a key-value pair in memory.

#### `recall(key)`

```python
@tool()
def recall(key: str) -> dict:
    backend = _get_memory_backend()
    value, found = backend.get(key)
    if found:
        return {"key": key, "value": value, "found": True}
    return {"key": key, "value": None, "found": False}
```

Retrieves a value by key. Returns `found` flag to indicate existence.

**Why not raise on missing key?** The LLM handles missing values better when they receive a structured response with `found: False` rather than an exception.

#### `forget(key)`

```python
@tool()
def forget(key: str) -> dict:
    backend = _get_memory_backend()
    return backend.delete(key)
```

Deletes a key from memory.

#### `list_memory()`

```python
@tool()
def list_memory() -> dict:
    backend = _get_memory_backend()
    return {"keys": backend.list_keys()}
```

Returns all memory keys.

#### `clear_memory()`

```python
@tool()
def clear_memory() -> dict:
    backend = _get_memory_backend()
    return backend.clear()
```

Clears all memory.

---

## `agent/tools/cua/__init__.py`

### Conditional Exports

```python
try:
    from tinycua.agent.tools.cua.keyboard import keyboard_press, keyboard_type
    from tinycua.agent.tools.cua.mouse import mouse_click, mouse_move
    from tinycua.agent.tools.cua.screen_capture import screen_capture

    __all__ = [
        "screen_capture", "mouse_move", "mouse_click",
        "keyboard_type", "keyboard_press",
    ]
except ImportError:
    __all__: list[str] = []
```

**Why conditional?** The CUA tools depend on `pyautogui`, `mss`, and `Pillow`. If these are not installed, the module exports nothing rather than crashing on import.

---

## `agent/tools/cua/keyboard.py`

### Purpose

Provides keyboard automation tools using `pyautogui`.

### Graceful Degradation Pattern

```python
try:
    import pyautogui
    from tinycua_sdk.tools.decorators import tool

    # Real implementations...

except ImportError:
    from tinycua_sdk.tools.decorators import tool

    # Stub implementations...
```

**Why this pattern?** Allows the package to be installed without CUA dependencies. Users can install them later with `pip install tinycua[cua]`.

### Real Implementation (`pyautogui` available)

#### `keyboard_type(text)`

```python
@tool()
def keyboard_type(text: str) -> dict[str, Any]:
    try:
        pyautogui.typewrite(text)
        return {"success": True}
    except (OSError, ValueError, TypeError) as e:
        return {"error": f"Keyboard type failed: {e}"}
```

Types the given text as if typed on the keyboard.

#### `keyboard_press(key)`

```python
@tool()
def keyboard_press(key: str) -> dict[str, Any]:
    try:
        if "+" in key:
            keys = key.split("+")
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return {"success": True}
    except (OSError, ValueError, TypeError) as e:
        return {"error": f"Keyboard press failed: {e}"}
```

Supports:
- Single key: `"enter"`, `"tab"`, `"esc"`
- Key combinations: `"ctrl+c"`, `"alt+f4"`, `"cmd+v"`

### Stub Implementation (`pyautogui` not available)

```python
@tool()
def keyboard_type(text: str) -> dict[str, Any]:
    return {
        "error": (
            "Keyboard control requires 'pyautogui'. "
            "Install with: pip install tinycua[cua]"
        )
    }
```

Returns a helpful error message telling users how to install the missing dependency.

---

## `agent/tools/cua/mouse.py`

### Purpose

Provides mouse automation tools using `pyautogui`.

### Real Implementation

#### `mouse_move(x, y)`

```python
@tool()
def mouse_move(x: int, y: int) -> dict[str, Any]:
    try:
        pyautogui.moveTo(x, y)
        return {"success": True}
    except (OSError, ValueError, TypeError) as e:
        return {"error": f"Mouse move failed: {e}"}
```

Moves the mouse cursor to absolute screen coordinates.

**Coordinates:**
- `x` — pixels from left edge of screen
- `y` — pixels from top edge of screen

#### `mouse_click(button)`

```python
@tool()
def mouse_click(button: str = "left") -> dict[str, Any]:
    try:
        pyautogui.click(button=button)
        return {"success": True}
    except (OSError, ValueError, TypeError) as e:
        return {"error": f"Mouse click failed: {e}"}
```

Performs a mouse click at the current cursor position.

**Supported buttons:** `"left"`, `"right"`, `"middle"`

### Stub Implementation

Same pattern as keyboard stubs, returning installation instructions.

---

## `agent/tools/cua/screen_capture.py`

### Purpose

Captures the current screen and returns a base64-encoded JPEG image.

### Dependencies

- `mss` — Multi-screen shot library (fast cross-platform screen capture)
- `Pillow` (PIL) — Image processing

### Real Implementation

```python
@tool()
def screen_capture(
    region: tuple[int, int, int, int] | None = None,
    quality: int = 85,
) -> dict[str, Any]:
```

**Parameters:**
- `region` — Optional `(left, top, width, height)` tuple for partial capture
- `quality` — JPEG quality 1-100 (default 85)

**Implementation:**
```python
with mss.mss() as sct:
    if region:
        monitor = {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
    else:
        monitor = sct.monitors[1]  # Primary monitor

    screenshot = sct.grab(monitor)
    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    image_b64 = base64.b64encode(buffer.read()).decode("utf-8")

    return {
        "image": image_b64,
        "format": "jpeg",
        "width": screenshot.width,
        "height": screenshot.height,
    }
```

**Why `mss` instead of PIL's ImageGrab?**
- Faster (uses native APIs directly)
- Better multi-monitor support
- Cross-platform consistency

**Color format conversion:** `screenshot.bgra` → `"BGRX"` raw mode → `Image.frombytes("RGB", ...)`

The MSS library returns BGRA format. Pillow's `frombytes` with `"BGRX"` raw mode handles the conversion.

**Base64 encoding:** The image is returned as a base64 string so it can be:
- Sent to LLMs with vision capabilities
- Stored in session history
- Displayed in web UIs

### Stub Implementation

Returns error indicating `mss` and `Pillow` are required, with install instructions.

---

## Tool Data Flow

### Context Tools

```
Agent needs context
    │
    ▼
search_context_grep_tool() [factory]
    │
    ▼
ContextTools.search_context_grep()
    │
    ├─ Check session_id
    ├─ Get SessionStore
    └─ Call store.search_grep(session_id, query)
         │
         ▼
    Return {"results": [...]}
```

### Memory Tools

```
Agent stores memory
    │
    ▼
remember(key, value)
    │
    ▼
_get_memory_backend()
    │
    ├─ Check env vars
    └─ Create MemoryBackend
         │
         ▼
    backend.set(key, value)
         │
         ▼
    Return {"success": True}
```

### CUA Tools

```
Agent captures screen
    │
    ▼
screen_capture(region, quality)
    │
    ▼
mss.grab(monitor)
    │
    ▼
PIL Image.frombytes()
    │
    ▼
Save to JPEG buffer
    │
    ▼
base64 encode
    │
    ▼
Return {"image": "base64...", "format": "jpeg", "width": W, "height": H}
```

---

## Design Decisions

1. **Factory functions for context tools:** Allows injecting `session_store` and `session_id` at tool creation time while keeping the tool interface simple.

2. **Global memory backend:** Memory is inherently global state. A module-level singleton ensures all agents share the same memory.

3. **Environment-based memory config:** `TINYCUA_BACKEND_URL`, `TINYCUA_API_KEY`, and `TINYCUA_MEMORY_LOCAL_ONLY` allow changing memory backend without code changes.

4. **Graceful degradation for CUA:** Try/except ImportError pattern allows the package to function without heavy GUI automation dependencies.

5. **Structured return values:** All tools return dictionaries rather than raising exceptions. This gives the LLM structured information about success/failure.

6. **No `raise` in tools:** Tools catch errors and return `{"error": "..."}`. The agent loop can then decide how to handle failures.

7. **JPEG for screen capture:** JPEG provides good compression for photos/screenshots. Quality 85 balances size and fidelity.

8. **Base64 encoding:** Makes images portable across JSON APIs and LLM contexts.
