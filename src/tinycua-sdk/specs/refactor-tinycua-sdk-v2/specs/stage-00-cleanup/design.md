# Stage 0: Scorched-Earth Cleanup — Design

**Spec**: `specs/refactor-tinycua-sdk-v2/specs/stage-00-cleanup/spec.md`

## Implementation Order

The deletion must happen in dependency order to avoid broken imports at any intermediate step.

### Phase 1: Delete Leaf Modules (no downstream SDK deps)
These can be deleted immediately without breaking imports of kept modules.

```bash
# Commands to run (conceptual — actual deletion is via git rm or rm)
rm -rf tinycua_sdk/events/
rm -rf tinycua_sdk/utils/
rm -rf tinycua_sdk/tools/cua/
rm tinycua_sdk/tools/native/context_tools.py
rm tinycua_sdk/tools/parser.py
rm tinycua_sdk/tools/resolver.py
rm tinycua_sdk/tools/mcp.py
rm tinycua_sdk/skills/cache.py
rm tinycua_sdk/skills/improver.py
rm tinycua_sdk/models/task.py
rm tinycua_sdk/core/config.py
rm tinycua_sdk/agent/validator.py
rm tinycua_sdk/agent/loader.py
rm tinycua_sdk/agent/loop_resolver.py
rm tinycua_sdk/agent/tool_resolver.py
rm tinycua_sdk/agent/skill_resolver.py
rm tinycua_sdk/agent/templates.py
rm tinycua_sdk/agent/backend_kind.py
rm tinycua_sdk/agent/hooks.py
```

### Phase 2: Gut Keeping Files

#### `agent/loop.py`

**Current dead code to remove:**
```python
# REMOVE:
VALID_LOOP_TYPES = {"default", "react", "plan"}

def _validate_loop_type(loop_type: str) -> None: ...

class DefaultLoop(BaseLoop): ...

# REMOVE HookManager usage from BaseLoop.__init__:
self._hook_manager = HookManager()

# REMOVE methods:
def add_pre_hook(self, hook): ...
def add_post_hook(self, hook): ...
```

**Keep:**
```python
class BaseLoop:
    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations

    async def run(self, agent, messages, tools):
        # Stub for now — implemented in Stage 3
        pass
```

#### `agent/executor.py`

**Remove:**
- `run_sync()` method (M-10)
- `stream()` / `stream_sync()` methods (M-16)
- `check_tool_permission()` static method (L-10)
- `check_tool_approval_required()` static method (L-10)
- `execute_subprocess()` static method (L-11)
- `_get_global_config()` method (M-14)
- `sub_agents` parameter from `__init__`
- `max_depth` parameter from `__init__`
- `current_depth` parameter from `__init__`

**Keep:**
- `AgentExecutor` class skeleton
- `run()` method signature (stub for Stage 3)
- `_call_llm()` method signature (stub for Stage 3)

#### `agent/config.py`

**Remove:**
- `temperature` field from `AgentPolicy`
- `BackendConfig` import and field from `AgentConfig`
- `strip_thinking` field

**Keep:**
```python
class AgentPolicy(BaseModel):
    max_tool_calls: int = 10
    parallel_tool_calls: bool = True

class AgentConfig(BaseModel):
    name: str = "assistant"
    instructions: str = ""
    llm_model: LLMModel  # Will become LanguageModel in Stage 1
    tools: list[Any] = []
    skills: list[Any] = []
    policy: AgentPolicy = Field(default_factory=AgentPolicy)
    metadata: dict = {}
    loop: Any = None
```

#### `agent/definition.py`

**Remove:**
- `sub_agents` field
- `max_depth` field
- `current_depth` field
- `keywords` field
- `add_sub_agent()` method
- `_get_all_sub_agents()` method
- `_find_sub_agent_for_task()` method
- `_pass_context_to_sub_agent()` method
- `_aggregate_results()` method
- `BackendConfig` references
- `strip_thinking` references

**Keep:**
- Agent definition data container (to be collapsed into `AgentConfig` in Stage 2).

#### `agent/agent.py`

**Remove:**
- `from_template()` classmethod
- `BackendConfig` import
- `sub_agents` parameter from `__init__`
- `max_depth` parameter from `__init__`
- `backend` parameter from `__init__`
- `strip_thinking` parameter from `__init__`

**New constructor signature (stub):**
```python
def __init__(
    self,
    name: str = "assistant",
    instructions: str = "",
    llm_model: LLMModel | None = None,
    tools: list[Tool] | None = None,
    skills: list[Skill] | None = None,
    policy: AgentPolicy | None = None,
    metadata: dict | None = None,
    loop: BaseLoop | None = None,
    **kwargs,
):
```

#### `security/approval.py`

**Remove:**
- `timeout` parameter from `ApprovalWorkflow.__init__`
- Any method that references `self.timeout`

**Keep:**
- `ApprovalWorkflow` class (will become ABC in Stage 3)

#### `security/permissions.py`

**Remove:**
- `PermissionLevel` enum
- `PermissionSystem` class
- `_setup_default_permissions()` method

**Keep:**
- File can be deleted entirely or kept as an empty module for Stage 7.

#### `core/providers.py`

**Remove:**
```python
# REMOVE:
"anthropic": ProviderInfo(...)
```

#### `__init__.py`

**New exports:**
```python
from tinycua_sdk.agent import (
    Agent,
    AgentConfig,
    AgentDefinition,
    AgentExecutor,
    AgentPolicy,
    BaseLoop,
    LLMModel,
)
from tinycua_sdk.skills.models import Skill
from tinycua_sdk.skills.registry import SkillRegistry
from tinycua_sdk.tools.decorators import Tool, tool

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentDefinition",
    "AgentExecutor",
    "AgentPolicy",
    "BaseLoop",
    "LLMModel",
    "Skill",
    "SkillRegistry",
    "Tool",
    "tool",
]
```

### Phase 3: Clean Old Tests

Delete unit test files that test removed modules:
- `test_backend_config.py`
- `test_agent_templates.py`
- `test_loop_resolver.py`
- `test_tool_resolver.py`
- `test_mcp.py`
- `test_skills_cache.py`
- `test_skills_improver.py`
- `test_command_parser.py`
- `test_agent_hooks.py`
- `test_middleware_hooks.py`
- `test_injection_detection.py`
- `test_context_discovery.py`
- `test_sanitizer.py`

## Verification After Each Phase

After Phase 1:
```bash
cd src/tinycua-sdk && python -c "import tinycua_sdk"
```

After Phase 2:
```bash
cd src/tinycua-sdk && python -c "from tinycua_sdk import Agent, LLMModel, Tool, tool, Skill"
```

After Phase 3:
```bash
cd src/tinycua-sdk && pytest tests/unit/ -x --ignore=tests/unit/test_backend_config.py ...
```

## Risk: Import Chain Breakage

If deleting a file breaks an import chain in a kept file, fix the kept file immediately. Do not leave broken imports.

Example:
- `agent/agent.py` imports `BackendConfig` from `agent/backend_kind.py`.
- Fix: Remove the import from `agent/agent.py` at the same time `backend_kind.py` is deleted.

## Git Strategy

Do not commit until all success criteria pass. This is a single atomic commit: "Stage 0: Remove dead code, stubs, and obsolete concepts".
