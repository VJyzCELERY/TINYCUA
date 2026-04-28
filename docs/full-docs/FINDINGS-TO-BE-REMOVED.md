# Findings: Features & Code To Be Removed

> **Branch Context:** `enhance-documentation-and-code-cleanup`
> **Purpose:** Track deprecated, unused, obsolete, or placeholder features that should be removed during this cleanup branch.
> **Last Updated:** 2025-04-28

---

## 1. Guest Mode (HIGH PRIORITY)

**Status:** REMOVED.

**Description:** Guest mode allowed unauthenticated users to run agents via the backend. This was a security risk and did not align with the current auth model.

**Removal completed in commit (see PR).**

**Affected Files & Locations (all cleaned):**

| File | Line(s) | What Was Removed |
|------|---------|------------------|
| `src/tinycua-sdk/tinycua_sdk/agent/agent.py` | 145-159 | `Agent.set_guest_mode()` wrapper |
| `src/tinycua-sdk/tinycua_sdk/agent/definition.py` | 135-137 | `AgentDefinition.is_guest` property |
| `src/tinycua-sdk/tinycua_sdk/agent/executor.py` | 234-241, 340-360, 376-377 | `guest_session_id`, `_run_guest()`, `is_guest` check in `run()` |
| `src/tinycua-sdk/tinycua_sdk/clients/backend.py` | 387-420 | `BackendClient.guest_run()` endpoint caller |
| `src/tinycua-sdk/tinycua_sdk/clients/protocol.py` | 58 | `BackendProtocol.guest_run()` abstract method |
| `src/tinycua/tinycua/agent/lifecycle.py` | 19, 216-232 | `AgentLifecycle.set_guest_mode()` |
| `src/tinycua/tinycua/clients/backend.py` | 331-362 | `BackendClient.guest_run()` endpoint caller |
| `src/tinycua/tinycua/tui/widgets.py` | 89 | Reference to "guest" in docstring |
| `src/tinycua-sdk/examples/08_guest_mode.py` | Entire file | Example script demonstrating guest mode |
| `src/tinycua-sdk/tests/unit/test_agent_executor.py` | 36-45 | `guest_session_id` tests |
| `src/tinycua-sdk/tests/unit/test_agent_definition.py` | 165-168 | `is_guest` tests |
| `src/tinycua/tests/unit/test_agent_lifecycle.py` | 93-105 | `set_guest_mode` tests |

---

## 2. Deprecated Import Shims (tinycua-sdk)

**Status:** REMOVED.

**Description:** Several modules in `tinycua_sdk` existed as backward-compatible import shims. These cluttered the namespace and have been removed.

**Removal completed:**

| File | Status | Notes |
|------|--------|-------|
| `src/tinycua-sdk/tinycua_sdk/cli/main.py` | DELETED | Stub CLI |
| `src/tinycua-sdk/tinycua_sdk/cli/repl.py` | DELETED | Stub REPL |
| `src/tinycua-sdk/tinycua_sdk/config.py` | DELETED | True shim raising ImportError |
| `src/tinycua-sdk/tinycua_sdk/tools/context_tools.py` | DELETED | Redirected to `tinycua.agent.tools.context_tools` |
| `src/tinycua-sdk/tinycua_sdk/tools/memory_tools.py` | DELETED | Redirected to `tinycua.agent.tools.memory_tools` |
| `src/tinycua-sdk/tinycua_sdk/clients/backend.py` | KEPT, CLEANED | This is the canonical SDK `BackendClient` (not a shim). The original spec incorrectly listed it for deletion; spec has been updated to reflect its canonical status. `guest_run()` and deprecation warnings were correctly removed. |
| `src/tinycua-sdk/tinycua_sdk/storage/__init__.py` | CLEANED | Removed DeprecationWarning logic; clean re-exports only |
| `src/tinycua-sdk/tinycua_sdk/cli/__init__.py` | CLEANED | Removed `main` import |
| `src/tinycua-sdk/tinycua_sdk/tools/__init__.py` | CLEANED | Removed deleted shim imports |

**Tests updated/removed:**
- `tests/unit/test_deprecation.py` — DELETED
- `tests/unit/test_deprecation_cleanup.py` — Renamed to `tests/unit/test_import_sanity.py`; docstring updated to reflect actual purpose
- `tests/unit/test_storage_migration.py` — Renamed to `tests/unit/test_session_store_crud.py`; docstring updated to reflect actual purpose
- `tests/unit/test_context_tools.py` — DELETED
- `tests/unit/test_memory.py` — Removed tool wrapper tests
- `tests/integration/test_memory_example.py` — Updated imports to canonical paths
- `examples/03_memory_and_session.py` — Updated imports to canonical paths

---

## 3. Legacy Base64 Credential Encoding (tinycua)

**Status:** REMOVED.

**Description:** `SetupWizard` had a backward-compatible base64 fallback for credential storage. It was replaced with Fernet encryption and the fallback has been removed.

**Changes:**
- `src/tinycua/tinycua/config/wizard.py` — Removed base64 fallback branch; only Fernet decryption remains
- `src/tinycua/tests/unit/test_credentials_encryption.py` — Removed legacy base64 tests

---

## 4. Placeholder / Empty Modules

### 4.1 `tinycua_sdk.events` (Placeholder)

**Status:** Empty placeholder module. Either implement or remove.

**File:** `src/tinycua-sdk/tinycua_sdk/events/__init__.py`

**Description:** Contains only a docstring: `"Events module placeholder (future)."`. No actual code. If events are not on the near-term roadmap, this module should be removed to reduce cognitive overhead.

**Removal Checklist:**
- [ ] Delete `tinycua_sdk/events/` directory
- [ ] Remove any references in `__init__.py` or package configs

### 4.2 `tinycua_finetune` (Entire Subproject - Unimplemented)

**Status:** Skeleton subproject. **DECISION: KEEP.** Planned for future roadmap.

**Files:**
- `src/tinycua-finetune/tinycua_finetune/dummy.py` (only source file)
- `src/tinycua-finetune/README.md` (describes unimplemented features)
- `src/tinycua-finetune/Makefile` (targets call non-existent modules)
- `src/tinycua-finetune/pyproject.toml`

**Description:** The README and Makefile describe a fine-tuning pipeline (`preprocess.py`, `synthesize_dataset.py`, `train.py`, `convert_to_gguf.py`), but none of these modules exist. The only Python file is `dummy.py` which is a placeholder listing what *should* be implemented.

**Decision:** This is a planned future feature, not a candidate for removal. It is the responsibility of a different team/effort. Leave as-is.

---

## 5. Unimplemented / Stub Features

### 5.1 `MemorySession` (IMPLEMENTED)

**Status:** IMPLEMENTED.

**What `MemorySession` is:**
A high-level convenience class that provides a session-scoped API for storing/retrieving memories:

```python
session = MemorySession(session_id="test-session")
memory_id = session.add(content="Test memory content", memory_type="conversation")
memory = session.get(memory_id)
results = session.search("Python")
session.delete(memory_id)
```

**Implementation:**
- `src/tinycua-sdk/tinycua_sdk/memory/session.py` — NEW
- `src/tinycua-sdk/tinycua_sdk/memory/__init__.py` — Exports `MemorySession`
- `src/tinycua-sdk/tests/integration/test_memory_operations.py` — Enabled and adapted

---

## 6. Unused / Dead Code Patterns

### 6.1 `Agent` class docstring references `set_guest_mode`

**Status:** REMOVED with guest mode cleanup.

### 6.2 `pass  # Fall back to default` in `storage/store.py`

**Status:** Still present. Low priority review item.

---

## Summary Table

| # | Feature | Priority | Effort | Decision Status |
|---|---------|----------|--------|-----------------|
| 1 | Guest Mode | HIGH | Medium | **REMOVED** |
| 2 | Deprecated import shims | HIGH | Low | **REMOVED** (with canonical BackendClient kept) |
| 3 | Legacy base64 credentials | MEDIUM | Low | **REMOVED** |
| 4.1 | `events` placeholder | LOW | Trivial | Pending decision |
| 4.2 | `tinycua-finetune` subproject | — | — | **KEEP** (future roadmap) |
| 5.1 | `MemorySession` | MEDIUM | Medium | **IMPLEMENTED** |
| 5.2 | CUA tool stubs | LOW | Trivial | **KEEP** (optional deps) |
| 6.1 | Guest mode docstring refs | HIGH | Trivial | Removed with #1 |
| 6.2 | `pass # Fall back` block | LOW | Trivial | Review needed |

---

## How to Update This Document

As the comprehensive docs are reviewed and as code is actually removed:
1. Move completed items to a "Removed" section at the bottom.
2. Add new findings as they are discovered.
3. Update the "Last Updated" date.
4. Link to the PR/commit that performed each removal.
