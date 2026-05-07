# REVIEW

This is a review report made on the current state of the tinycua SDK progress

Each issue will be formatted as follow:
## TITLE
### FILE LOCATION :
- [file_path]

### ISSUE :
- [ISSUE_CODE] - [ISSUE_DESCRIPTION]

### RECOMMENDATION :
- [ISSUE_CODE] - [RECOMMENDED_ACTION]

### ISSUE_CODE LEGEND :
- [H-xx] = High Priority
- [M-xx] = Medium Priority 
- [L-xx] = Low Priority

---

## DefaultLoop still exists
### FILE_LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/loop.py:121`

### ISSUE :
- [L-01] - We no longer need to have default loop even if for backward compatibilty as to not confuse user since we have not made any release

### RECOMMENDATION :
- [L-01] - Remove DefaultLoop entirely and anything related to DefaultLoop

---

## AgentConfigValidator validates too much
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/validator.py`

### ISSUE :
- [M-01] - KNOWN_MODELS are being validated which is not something this SDK should do. Should a model is unavailable or unidentified it's the LLM Provider responsibilities to declare that model is not available not the SDK.
- [M-02] - KNOWN_LOOP_TYPES is generally no longer needed because loop consist of BaseLoop only by default. Validation like this should be the responsibility of the consumer that "register" the loop data. SDK does not have any knowledge of registry.

### RECOMMENDATION :
- [M-01] - Remove validation for known model
- [M-02] - Remove validation for loop types

---

## LLMModel Class OpenAI API compatibility and Naming — SUPERSEDED BY H-14
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/llm_model.py`

### ISSUE :
- [L-02] - Attribute in LLMModel Class does not seem to be full OpenAI API complete configuration
- [L-03] - Currently the model is called LLMModel which only implies this is for LLM

### RECOMMENDATION :
- **SUPERSEDED BY [H-14]** — See "LLMModel Rename and Parameter Completeness (MERGED)" below.

---

## LLMModel Rename and Parameter Completeness (MERGED)
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/llm_model.py`

### ISSUE :
- [H-14] - `LLMModel` is missing many standard parameters that are essential for OpenAI-compatible APIs and is also poorly named. It should be renamed to `LanguageModel` to support both LLMs and SLMs, and must include all configurable parameters.

### RECOMMENDATION :
- [H-14] - Rename `LLMModel` to `LanguageModel`. Add missing standard OpenAI-compatible parameters: `max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop`, `seed`, `response_format`, `tool_choice`, `logprobs`, `top_logprobs`, `user`. Ensure these are forwarded to the real LLM client when implemented.

---

## BackendKind ambiguous existence
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/backend_kind.py`

### ISSUE :
- [H-01] - SDK is now meant to be stateless and backend kind implies that agent can be remotely or locally executed. This is not something SDK should be concerned of rather should be something SDK consumer adjust. The important part of SDK is that we can create and run agent directly. Whether this agent is "deployed" to remote server and "executed" on remote server should be the concern of consumer to create the system to deploy and trigger Agent remotely.

### RECOMMENDATION :
- [H-01] - Remove backend kind entirely and any reference of "remote" and "local" state as SDK should be stateless.

---

## Unclear AgentTemplate existence importance
### FILE LOCATION :
- src/tinycua-sdk/tinycua_sdk/agent/templates.py

### ISSUE :
- [H-02] - SDK Should not have any "default" agent or any templates for agent as it should be barebone and is simply a tool to "create" agents. Templates role in the codebase is unclear. Is template used to define agent using config based approach? It seems to not be necessary and add bloat so that there is yaml, config and templates where yaml + config is already enough.

### RECOMMENDATION :
- [H-02] - Remove agent templates approach of agent creation.

---

## DEAD RESOLVER
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/loop_resolver.py`
- `src/tinycua-sdk/tinycua_sdk/agent/tool_resolver.py`
- `src/tinycua-sdk/tinycua_sdk/agent/skill_resolver.py`

### ISSUE :
- [H-03] - Loop Resolver seems to be dead and is not used in loop.py or anywhere else as loop.py has it's own resolve_loop function.
- [H-04] - Tool Resolver seems to be dead and is not used by agent in anyway.
- [H-05] - Skill Resolver seems to be dead and is not used by agent in anyway.

### RECOMMENDATION :
- [H-03] - Remove loop_resolver.py
- [H-04] - Verify if resolver is still used. If not remove tool_resolver.py
- [H-05] - Verify if resolver is still used. If not remove skill_resolver.py

---

## AgentExecutor Lack Of Streaming
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py`

### ISSUE :
- [H-06] - AgentExecution stream is not implemented yet.

### RECOMMENDATION :
- [H-06] - Implement stream for AgentExecutor. There is two streaming type, event stream and token streaming. Token streaming means LLM token generation stream will be passed as well. Event Streaming means only stream Agent events such as tool_call, response, etc following the OpenAI API Responses format.
Expectation:
Scenario 1:
```python
myAgent = Agent(. . .)
response = await myAgent.run(stream='off',. . .) # Returns a string
print(response)
```
Output : `str of final response`
Scenario 2:
```python
myAgent = Agent(. . .)
response = await myAgent.run(stream='event',. . .) # Returns a Generator
for event in response:
    print(event) # JSON Parsable dict of SSE Events from LLM based on OpenAI Response API events but skips token generation stream event
```
Output :
```
{event_1} # Event such as tool_call
{event_2}
```
Scenario 3:
```python
myAgent = Agent(. . .)
response = await myAgent.run(stream='token',. . .) # Returns a Generator
for event in response:
    print(event) # JSON Parsable dict of the token generation event 
```
Output :
```
{event_1} # Only token generation
{event_2} # Only token generation 
```
Scenario 4:
```python
myAgent = Agent(. . .)
response = await myAgent.run(stream='all',. . .) # Returns a Generator
for event in response:
    print(event) # JSON Parsable dict of the token generation event 
```
Output :
```
{event_1} # Token Generation and Event such as tool call, response etc
{event_2}
```
Acceptable Criteria :
1. if `stream='off'` returns a JSON instead of str is also acceptable as long as it is parsable
2. if actual implementation does not need 'await' or should remove 'await' is also acceptable. Key is to be consistent across scenario usage.
3. event output should adhere to OpenAI API response format based on https://developers.openai.com/api/reference/responses/overview 
4. Agent run streaming should be fully compatible with OpenAI API chat completions and response and have to have support for structured output

---

## LLM Client Stub
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:39-58`

### ISSUE :
- [H-07] - LLMClient chat is defined as NotImplementedError, this should not have been the case because LLM Chat is basic capability that the SDK should be able to handle.

### RECOMMENDATION :
- [H-07] - Implement the LLM response system that connects through the LLM Model base URL

---

## AgentLoader unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/loader.py`

### ISSUE :
- [M-03] - AgentLoader defined but not used anywhere in `agent.py` and agent loading already somewhat exist in Agent class in `agent.py`

### RECOMMENDATION :
- [M-03] - remove `loader.py`

---

## Inconsistent and Any Type definition
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk` whole codebase

### ISSUE :
- [H-08] - Across the codebase there are many definition type as `Any` even if that object should have their own type for example `skills : Any` eventhough we have skill classes. This is bad coding practice and should not be allowed.

### RECOMMENDATION :
- [H-08] - DO NOT ALLOW ANY TYPING DEFINITION IF POSSIBLE AS IT IS UNCLEAR WHAT TYPES THEY ARE.

---

## CUA Native Tool Out of Scope
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/tools/cua`

### ISSUE :
- [L-04] - CUA tools is not part of the native SDK as it will be something that user develop themselves or consumer of the SDK develop

### RECOMMENDATION :
- [L-04] - Remove cua tools entirely

---

## SkillToolResolver is a Stub Implementation
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/skill_resolver.py:28-58`

### ISSUE :
- [H-09] - `SkillToolResolver.resolve_skill_tools()` always returns an empty list regardless of input. The docstring explicitly states "Empty list; tools must be composed explicitly." This is a deliberate stub that provides no actual resolution capability.
- [H-10] - `SkillToolResolver.get_resolved_tools()` also always returns an empty list with the same stub documentation.

### RECOMMENDATION :
- [H-09] - Remove `SkillToolResolver` entirely. Skills are metadata-only in the SDK scope.
- [H-10] - Remove `get_resolved_tools()`. The SDK should not auto-resolve tools from skills.

---

## BaseLoop.run() is a Stub for Agent Execution Loop
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/loop.py:98-117`

### ISSUE :
- [H-11] - `BaseLoop.run()` only calls `agent._call_llm()` once and returns the raw string response. It does NOT implement the core agent execution loop: parsing tool calls from the LLM response, executing tools, appending results back to messages, and iterating until completion. This is the most critical stub in the SDK — without it, the agent cannot actually use tools interactively.

### RECOMMENDATION :
- [H-11] - Implement the full agent loop in `BaseLoop.run()`:
  1. Call LLM with messages and tool schemas
  2. Parse the response for tool calls (function_call or tool_calls)
  3. Execute each tool call via `Tool.invoke()`
  4. Append tool results back to the message history
  5. Re-call the LLM with updated messages
  6. Repeat until `max_iterations` is reached or the LLM returns a final response without tool calls
  7. Respect `agent.policy.max_tool_calls` and `agent.cancel_event`

---

## context_tools.py is Completely Empty
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/tools/native/context_tools.py`

### ISSUE :
- [M-04] - The file contains only a module docstring ("""Generic context utilities (stateless).""") and zero implementation. This is a dead empty module.

### RECOMMENDATION :
- [M-04] - Remove `context_tools.py`.

---

## cua/__init__.py is Completely Empty
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/tools/cua/__init__.py`

### ISSUE :
- [L-05] - The `cua` tools package init contains only a docstring with no exports, no classes, no functions. It is a dead empty package.

### RECOMMENDATION :
- [L-05] - Remove the entire `tools/cua/` directory since it is empty and out of scope (see L-04).

---

## AgentExecutor Depends on LLMClient Stub
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:246-263`

### ISSUE :
- [H-12] - `AgentExecutor._call_llm()` instantiates `LLMClient` and awaits `client.chat()`. However, `LLMClient.chat()` unconditionally raises `NotImplementedError` (see H-07). This means `AgentExecutor.run()` will crash at runtime because its core dependency is a stub.

### RECOMMENDATION :
- [H-12] - Define `LLMClient` as an abstract base class (ABC) with an abstract `chat()` method. Create a concrete `OpenAICompatibleClient` implementation that depends on the `openai` package and sends chat completion requests using the `LLMModel` / `LanguageModel` configuration (base_url, api_key, model_name, temperature, etc.). This architecture allows future provider-specific clients (e.g., `AnthropicClient`) to extend the same ABC.

---

## PermissionSystem Hardcodes Non-Existent Tools
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/security/permissions.py:38-60`

### ISSUE :
- [M-05] - `PermissionSystem._setup_default_permissions()` registers permission levels for tools like `calculator`, `web_search`, `get_weather`, `search_code`, `file_read`, `file_write`, `shell_execute`, etc. None of these tools exist in the SDK. This creates confusion and implies a tool suite that does not exist.

### RECOMMENDATION :
- [M-05] - Remove all hardcoded default tool registrations from `PermissionSystem`. Replace the current `PermissionSystem` class with a minimal permission model living on `Agent`: `Agent.tool_permissions: dict[str, Literal['ask', 'allow', 'deny']] = {}`. When `ToolExecutor` executes a tool, it checks `agent.tool_permissions.get(tool_name, 'allow')`. If `'deny'`, skip execution. If `'ask'`, route through the optional `ApprovalWorkflow` guardrail hook. Remove the `PermissionLevel` enum and the standalone `PermissionSystem` class.

---

## ApprovalWorkflow Timeout is Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/security/approval.py:26-34`

### ISSUE :
- [L-06] - `ApprovalWorkflow.__init__` stores a `timeout` parameter but it is never referenced in `request_approval()`, `approve()`, `deny()`, `get_status()`, `list_pending_requests()`, or any other method. The timeout has no effect.

### RECOMMENDATION :
- [L-06] - Remove approval timeout.

---

## VALID_LOOP_TYPES and _validate_loop_type are Dead Code
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/loop.py:14-30`

### ISSUE :
- [M-06] - `VALID_LOOP_TYPES` and `_validate_loop_type()` are defined but never imported or called anywhere in the codebase. `resolve_loop()` does its own validation and never uses `_validate_loop_type()`. This is dead code.

### RECOMMENDATION :
- [M-06] - Remove `VALID_LOOP_TYPES` and `_validate_loop_type()` since they serve no purpose.

---

## Sub-Agent Delegation is Stubbed / Unwired
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/definition.py:162-212`
- `src/tinycua-sdk/tinycua_sdk/agent/loop.py:98-117`

### ISSUE :
- [H-13] - `AgentDefinition` contains full sub-agent management infrastructure (`add_sub_agent`, `_get_all_sub_agents`, `_find_sub_agent_for_task`, `_pass_context_to_sub_agent`, `_aggregate_results`) and `AgentExecutor` accepts `sub_agents` and `max_depth` parameters. However, `BaseLoop.run()` never uses any of this — there is no delegation logic, no keyword matching during execution, and no depth tracking. The sub-agent feature is completely unwired.

### RECOMMENDATION :
- [H-13] - Remove all sub-agent related code from `AgentDefinition`, `AgentConfig`, `AgentExecutor`, `Agent`, and `__init__.py`. This includes `sub_agents`, `max_depth`, `current_depth`, `keywords`, `add_sub_agent()`, `_get_all_sub_agents()`, `_find_sub_agent_for_task()`, `_pass_context_to_sub_agent()`, and `_aggregate_results()`. Sub-agent delegation will be reintroduced later when properly designed; consumers can still run agents manually by invoking `agent.run()` from within another agent's tool if needed.

---

## Task Planning Models Exist Without Planning Logic
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/models/task.py`
- `src/tinycua-sdk/tinycua_sdk/models/result.py:44-48`

### ISSUE :
- [M-07] - `TaskPlan`, `TodoItem`, `PlanningResult`, and `PlanRunResult` data models exist, but there is no planning engine, no task decomposition logic, and no execution code that uses them. They are unused data structures.

### RECOMMENDATION :
- [M-07] - Remove planning related logic entirely since this will be part of agent development which mean it is outside of SDK Scope where SDK only provide the tools to build the agent.

---

## AgentPolicy Duplicates LLMModel Temperature
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/config.py:61-68`
- `src/tinycua-sdk/tinycua_sdk/agent/llm_model.py:12-27`

### ISSUE :
- [L-07] - Both `AgentPolicy` and `LLMModel` have a `temperature` field. This creates confusion about which one takes precedence when calling the LLM. The duplication suggests unclear separation of concerns between policy and model configuration.

### RECOMMENDATION :
- [L-07] - Remove `temperature` from `AgentPolicy` and keep it only in `LLMModel` since temperature is an LLM inference parameter, not an agent behavioral policy parameter.

---

## ToolExecutor Exists But is Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:61-170`

### ISSUE :
- [M-08] - `ToolExecutor` with `execute()` and `execute_async()` methods exists but is never instantiated or called by `AgentExecutor`, `BaseLoop`, or any other execution path. Tool execution is currently handled inline (or not at all) instead of through this dedicated executor.

### RECOMMENDATION :
- [M-08] - Make `ToolExecutor` the canonical tool execution path. Integrate it into `BaseLoop.run()` so that when the LLM returns tool calls, each call is dispatched through `ToolExecutor.execute()` or `execute_async()`. `ToolExecutor` should also handle the optional `ApprovalWorkflow` guardrail check before invoking the tool.

---

## MCPClient Exists But is Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/tools/mcp.py`

### ISSUE :
- [M-09] - `MCPClient` and `MCPTool` are fully implemented but never integrated into `Agent`, `AgentExecutor`, or `BaseLoop`. MCP tool configurations can be parsed by `ToolResolver` but there is no code that actually uses `MCPClient` to discover or invoke MCP tools during agent execution.

### RECOMMENDATION :
- [M-09] - Remove MCP system for now.

---

## SkillImprover Exists But is Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/skills/improver.py`

### ISSUE :
- [L-08] - `SkillImprover`, `SkillUsage`, and `SkillImprovement` classes exist but are not imported or used anywhere in `agent/`, `skills/`, or the rest of the SDK. This is dead code.

### RECOMMENDATION :
- [L-08] - Remove `skills/improver.py`. Skill bare minimum in SDK should provide add and remove skill. As for improvement it should be part of Agent development not SDK.

---

## ApprovalWorkflow Exists But is Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/security/approval.py`

### ISSUE :
- [L-09] - `ApprovalWorkflow` and `ApprovalRequest` are implemented but never integrated into `AgentExecutor`, `ToolExecutor`, or any tool execution path. The `requires_approval` flag in `PermissionSystem` is checked by static methods in `AgentExecutor`, but those methods are themselves unused in the actual execution flow.

### RECOMMENDATION :
- [L-09] - Redesign `ApprovalWorkflow` as an abstract base class (ABC). Provide a default `DefaultApprovalWorkflow` that always returns `{approved: True}`. `ToolExecutor` should accept an optional `approval_workflow: ApprovalWorkflow | None = None` parameter. Before executing any tool, `ToolExecutor` calls `approval_workflow.request_approval(tool_name, arguments)` and checks the returned dict for `approved: True`. If `False`, it returns the approval response dict instead of executing the tool. This lets consumers inject custom guardrails without the SDK mandating a specific permission model.

---

## AgentExecutor Static Permission Methods are Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:402-442`

### ISSUE :
- [L-10] - `check_tool_permission()` and `check_tool_approval_required()` are static methods that instantiate a fresh `PermissionSystem` on every call. They are never called by `BaseLoop.run()`, `ToolExecutor`, or any execution path. They are dead code with poor design (should not be static if they need a permission system instance).

### RECOMMENDATION :
- [L-10] - Remove these method. Permission system such as approval etc should be part of security/approval.py system or is unified in one approval system instead. Permission only exists as part of metadata at best.

---

## AgentExecutor.execute_subprocess is Out of Place
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:365-400`

### ISSUE :
- [L-11] - `execute_subprocess()` is a general-purpose utility for running shell commands. It has nothing to do with agent execution logic and does not belong in `AgentExecutor`. It appears to be a utility that was parked in the wrong class.

### RECOMMENDATION :
- [L-11] - Move `execute_subprocess()` into `ToolExecutor` as a private/internal helper method (`_execute_subprocess`) used when a tool's underlying function needs to run as a subprocess. Remove the static method from `AgentExecutor`.

---

## run_sync() Can Fail in Async Context
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:307-339`

### ISSUE :
- [M-10] - `run_sync()` uses `asyncio.run(self.run(...))` which raises `RuntimeError` if called from within an already running event loop (e.g., inside Jupyter, FastAPI, or another async context). This makes the method unreliable for SDK consumers who may already be in an async environment.

### RECOMMENDATION :
- [M-10] - Remove `run_sync()` from `AgentExecutor` entirely. The SDK should expose only the async `run()` method for now. A synchronous wrapper can be reintroduced later if there is clear demand.

---

## Agent.from_template Still Uses Obsolete Parameters
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/agent.py:207-316`

### ISSUE :
- [M-11] - `Agent.from_template()` extracts and uses obsolete parameters (`system_prompt`, `model`, `provider`, `base_url`, `api_key`, `mode`, `backend_url`, `backend_api_key`, `backend_headers`) individually instead of building a proper `LLMModel`. It also references `BackendConfig` despite H-01. The method contradicts the `_OBSOLETE_PARAMS` rejection logic in `Agent.__init__`.

### RECOMMENDATION :
- [M-11] - Since templates are planned for removal (see H-02). This should also be removed as Template related code are planned to be removed

---

## ResponseRequest.session_id is Obsolete
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/models/request.py:43`
- `src/tinycua-sdk/tinycua_sdk/agent/agent.py:19-34`

### ISSUE :
- [L-12] - `ResponseRequest` has a `session_id` field, but `session_id` is listed in `_OBSOLETE_PARAMS` in `agent.py`. This is inconsistent — the model still carries a field that the agent constructor explicitly rejects.

### RECOMMENDATION :
- [L-12] - Remove `session_id` from `ResponseRequest` as session is no longer handled by SDK.

---

## strip_thinking Defined But Not Implemented
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/config.py:86`
- `src/tinycua-sdk/tinycua_sdk/agent/definition.py:42, 158-160`

### ISSUE :
- [L-13] - `strip_thinking` is defined as a config property on `AgentConfig` and `AgentDefinition`, but it is never referenced or used in `BaseLoop.run()`, `AgentExecutor.run()`, or any response post-processing logic. It is a dead configuration option.

### RECOMMENDATION :
- [L-13] - Strip Thinking should now be part of LanguageModel Class as not all model reasons. Implement `strip_thinking` on LanguageModel Class

---

## LLMModel Missing Standard OpenAI-Compatible Parameters
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/llm_model.py:12-27`

### ISSUE :
- [H-14] - `LLMModel` is missing many standard parameters that are essential for OpenAI-compatible APIs and are commonly used across providers: `max_tokens`, `top_p`, `frequency_penalty`, `presence_penalty`, `stop`, `seed`, `response_format`, `tool_choice`, `logprobs`, `top_logprobs`, `user`. Without these, consumers cannot configure basic LLM behavior.

### RECOMMENDATION :
- [H-14] - Add the missing standard parameters to `LLMModel` with sensible defaults (e.g., `max_tokens: int | None = None`, `top_p: float = 1.0`, `frequency_penalty: float = 0.0`, `presence_penalty: float = 0.0`, `response_format: dict | None = None`). Ensure these are forwarded to the real LLM client when implemented (see H-07, H-12). NOTE: LLMModel Class should be renamed as LanguageModel in general in the future

---

## BackendConfig and BackendKind Still Exported Despite H-01
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/__init__.py:9-10`
- `src/tinycua-sdk/tinycua_sdk/agent/config.py:14, 82`
- `src/tinycua-sdk/tinycua_sdk/agent/definition.py:36-37, 138-140`
- `src/tinycua-sdk/tinycua_sdk/agent/agent.py:52`

### ISSUE :
- [H-15] - Despite the recommendation in H-01 to remove `BackendKind` entirely, `BackendConfig` and `BackendKind` are still imported and exported from `__init__.py`, still present in `AgentConfig`, `AgentDefinition`, and `Agent`. They are still referenced in `Agent.from_template()`, `AgentLoader`, and serialization logic. The removal is incomplete.

### RECOMMENDATION :
- [H-15] - Fully execute H-01: remove `backend_kind.py`, remove `BackendConfig` and `BackendKind` from `AgentConfig`, `AgentDefinition`, `AgentExecutor`, `Agent`, `AgentLoader`, `__init__.py`, and all serialization/deserialization paths. Also remove `backend_url` from `SDKConfig`.

---

## Anthropic Provider is an Intentional Future Stub
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/core/providers.py:28-31`

### ISSUE :
- [L-14] - The code explicitly documents `"anthropic"` as an "intentional future stub for native Anthropic API support" that "will require separate implementation." This is a known stub left in the codebase for future work.

### RECOMMENDATION :
- [L-14] - Remove the `"anthropic"` stub from `VALID_PROVIDERS` until native Anthropic support is actually implemented. The SDK currently only supports OpenAI-compatible endpoints, so advertising an unsupported provider is misleading.

---

## _OBSOLETE_PARAMS EXISTENCE
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/agent.py`
### ISSUE:
- [M-12] - _OBSOLETE_PARAMS are obsolete we should remove this and EVERYTHING parameter that is inside of _OBSOLETE_PARAMS

### RECOMMENDATION :
- [M-12] - Remove all of the parameter mentioned in _OBSOLETE_PARAMS from the codebase then delete the _OBSOLETE_PARAMS variable and any mention of it.

---

## Hook System is Unwired
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/loop.py:60-96`
- `src/tinycua-sdk/tinycua_sdk/agent/hooks.py:124-165`

### ISSUE :
- [H-16] - `BaseLoop` instantiates a `HookManager` and exposes `add_pre_hook()` / `add_post_hook()` methods, but `HookManager.execute_pre_hooks()` and `execute_post_hooks()` are NEVER called inside `BaseLoop.run()` or anywhere else in the execution path. Hooks can be registered but will never execute, making the entire hook system a facade.

### RECOMMENDATION :
- [H-16] - Remove the entire hook system: delete `agent/hooks.py`, remove `HookManager` import and usage from `BaseLoop`, and remove `add_pre_hook()` / `add_post_hook()` from `BaseLoop`. Customization should be done by subclassing `BaseLoop` and overriding `run()` directly.

This way when someone wants to extend BaseLoop it can be done by modifying the BaseLoop directly and replacing the run() logic of BaseLoop
```python
class CustomLoop(BaseLoop):
    def run():
        . . .
```

---

## AgentConfigValidator Tested But Never Used in Production
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/validator.py`

### ISSUE :
- [M-13] - `AgentConfigValidator` has comprehensive unit tests but is never instantiated or called in any production code path. `Agent.__init__()`, `Agent.from_config()`, `AgentLoader.load_from_markdown()`, and `AgentConfig.from_config()` do not perform any validation using this class.

### RECOMMENDATION :
- [M-13] - Integrate `AgentConfigValidator` into `Agent.__init__()` so that validation runs automatically on agent creation. Also expose a public `Agent.validate()` method (or `AgentConfig.validate()`) so consumers can call it manually when constructing configs programmatically. Remove the obsolete checks (`KNOWN_MODELS`, `KNOWN_LOOP_TYPES`) first (see M-01, M-02, M-06).

---

## SDKConfig and _get_global_config Are Dead Code
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/core/config.py`
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:173-182`

### ISSUE :
- [M-14] - `SDKConfig`, `LLMConfig`, and `LoopConfig` in `core/config.py` are never used in any production execution path. `_get_global_config()` in `executor.py` is defined but never called. The module-level `_global_config` cache serves no purpose.

### RECOMMENDATION :
- [M-14] - Remove `SDKConfig`, `LLMConfig`, `LoopConfig`, and `_get_global_config()` unless there is a planned global configuration system. If global config is needed later, it can be reintroduced with a clear design.

---

## stream Parameter Type Mismatch
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:265-305`
- `src/tinycua-sdk/tinycua_sdk/agent/executor.py:341-363`

### ISSUE :
- [M-16] - `AgentExecutor.run()` currently accepts `stream: bool = False`, but the streaming specification expects `stream: str` with values `'off'`, `'event'`, `'token'`, `'all'`. The current boolean API is incompatible with the intended design. Additionally, `AgentExecutor.stream()` and `stream_sync()` unconditionally raise `NotImplementedError`, which contradicts the existence of a `stream` parameter in `run()`.

### RECOMMENDATION :
- [M-16] - Change `AgentExecutor.run()` signature to `stream: Literal['off', 'event', 'token', 'all'] = 'off'`. Implement all four streaming modes. Remove the separate `stream()` and `stream_sync()` methods entirely.

---

## SkillCache Exists But Is Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/skills/cache.py`

### ISSUE :
- [L-15] - `SkillCache` is fully implemented but never instantiated or used by `SkillRegistry`, `AgentLoader`, or any other component. It is dead code.

### RECOMMENDATION :
- [L-15] - Remove `skills/cache.py` until skill caching is a planned and needed feature.

---

## events/ Module Is an Empty Placeholder
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/events/__init__.py`

### ISSUE :
- [L-16] - The `events/` package contains only a placeholder docstring ("""Events module placeholder (future).""") with no exports, classes, or functions.

### RECOMMENDATION :
- [L-16] - Remove the `events/` directory until event types or event bus functionality is actually implemented.

---

## utils/ Package Is Empty
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/utils/__init__.py`

### ISSUE :
- [L-17] - The `utils/` package has `__all__ = []` and contains no utility functions. It serves no purpose.

### RECOMMENDATION :
- [L-17] - Remove the `utils/` directory. If general-purpose utilities are needed later, create the package at that time.

---

## tools/resolver.py Functions Exported But Unused
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/tools/resolver.py`
- `src/tinycua-sdk/tinycua_sdk/tools/__init__.py`

### ISSUE :
- [M-15] - `analyze_source`, `detect_circular`, `compute_version`, `find_internal_calls`, and `topological_sort` are exported from `tools/__init__.py` but are never used in any production code path. They are only referenced in tests and by the dead `loop_resolver.py`.

### RECOMMENDATION :
- [M-15] - Remove `tools/resolver.py` and its exports from `tools/__init__.py`. If dependency analysis is needed for tool bundling/deployment in the future, it can be reintroduced as a dedicated module.

---

## tools/parser.py Contains General-Purpose Utilities
### FILE LOCATION :
- `src/tinycua-sdk/tinycua_sdk/tools/parser.py`

### ISSUE :
- [L-18] - `CommandParser` and `safe_eval` are general-purpose utilities with no connection to agent execution or tool invocation. They are only used in tests and appear to be parked in the wrong module. `safe_eval` is particularly odd as it evaluates mathematical expressions, which is unrelated to the SDK's purpose.

### RECOMMENDATION :
- [L-18] - Remove `tools/parser.py`. If command parsing or safe math evaluation are needed, they should live in consumer code, not the SDK.

---

