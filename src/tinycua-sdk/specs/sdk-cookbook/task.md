# Tasks: TINYCUA SDK Cookbook

Implementation tasks for the 19-page SDK cookbook under `src/tinycua-sdk/docs/cookbook/`. Check off items as completed.

## TDD Phase (Tests First)

- [x] Write structural validation test suite at `src/tinycua-sdk/tests/test_cookbook_structure.py` <!-- id: 0 -->
  - [x] Implement all test functions from implementation-plan.md Success Criteria section
  - [x] Test file must pass `uv run python -m py_compile` verification
- [x] Run validation tests — expect RED (all fail) since no cookbook exists yet <!-- id: 1 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/test_cookbook_structure.py -v`
  - [x] Confirm all tests fail with clear, actionable error messages (not crashes)

## Implementation Phase

### Phase 0 — Scaffolding & Index

- [x] Create directory structure <!-- id: 2 -->
  - [x] Create `src/tinycua-sdk/docs/cookbook/` root directory
  - [x] Create all six phase subdirectories: `onboarding/`, `core-concepts/`, `agent-extensions/`, `advanced-file-handling/`, `provider-deep-dives/`, `execution-and-reference/`
- [x] Create `index.md` at `src/tinycua-sdk/docs/cookbook/index.md` <!-- id: 3 -->
  - [x] List all 19 pages grouped by phase with one-line descriptions
  - [x] Pages listed in linear reading order per design.md dependency graph
  - [x] Links use relative paths: `[Page Title](./phase/slug.md)`
- [x] Run validation tests — expect structural tests pass (files exist), content tests still fail <!-- id: 4 -->

### Phase 1 — Onboarding (`onboarding/`)

- [x] Write `onboarding/installation-and-setup.md` <!-- id: 5 -->
  - [x] pip/uv install, environment variables, `.env` setup, verify installation
  - [x] Dual provider patterns: local (LM Studio) and remote (OpenAI) configuration
  - [x] No hardcoded secrets — use `os.environ.get("OPENAI_API_KEY")`
  - [x] Follow page template: title, Prerequisites, Overview, tutorial sections, Common Pitfalls, Next Steps
- [x] Write `onboarding/your-first-agent.md` <!-- id: 6 -->
  - [x] Import `Agent`, create with name/instructions, call `run()`, print response
  - [x] Minimal imports — `from tinycua_sdk import Agent`
- [x] Write `onboarding/agent-configuration.md` <!-- id: 7 -->
  - [x] `AgentConfig`, `AgentPolicy`, `from_config`/`to_config`, JSON/YAML serialization, `from_json_file`/`from_yaml_file`
  - [x] Show load/save patterns

### Phase 2 — Core Concepts (`core-concepts/`)

- [x] Write `core-concepts/language-models-and-providers.md` <!-- id: 8 -->
  - [x] `LanguageModel` fields, model resolution, provider selection, local vs remote, `to_dict`/`from_dict`, `api_key` env expansion
  - [x] Explicitly teach the two provider paths (local and remote) — later pages refer back here
- [x] Write `core-concepts/streaming-responses.md` <!-- id: 9 -->
  - [x] `stream=True`, async iteration, event types, content accumulation, cancellation
  - [x] Import `Agent` and demonstrate `agent.stream_events()`
- [x] Write `core-concepts/file-attachments.md` <!-- id: 10 -->
  - [x] `FileAttachment.from_path`, `from_bytes`, `from_url`, `file_id` reference
  - [x] Passing to `agent.run(file_attachments=[...])`
- [x] Write `core-concepts/multimodal-content.md` <!-- id: 11 -->
  - [x] `ContentPart` text/file types, building multimodal queries, mixing text and images
  - [x] Provider behavior differences between chat-completions and responses

### Phase 3 — Agent Extensions (`agent-extensions/`)

- [x] Write `agent-extensions/creating-tools.md` <!-- id: 12 -->
  - [x] `@tool` decorator (bare and parameterized), `Tool.from_callable`, docstring parsing
  - [x] JSON Schema generation, `Tool.from_dict`, `load_directory`
- [x] Write `agent-extensions/skills-and-skill-registry.md` <!-- id: 13 -->
  - [x] `Skill` model, `Skill.from_directory`, `SKILL.md` format, `SkillRegistry`
  - [x] `agent.add_skills()`, how skills appear in system prompt
- [x] Write `agent-extensions/tool-permissions-and-approval.md` <!-- id: 14 -->
  - [x] `tool_permissions` map (`allow`/`ask`/`deny`), `ApprovalWorkflow` ABC
  - [x] `DefaultApprovalWorkflow`, custom workflow example, multi-workflow chaining

### Phase 4 — Advanced File Handling (`advanced-file-handling/`)

- [x] Write `advanced-file-handling/streaming-file-uploads.md` <!-- id: 15 -->
  - [x] `FileAttachment.from_path(stream=True)`, `StreamingFileAttachment`, `iter_base64_chunks`
  - [x] `hash_content`, when to use vs memory-backed uploads
- [x] Write `advanced-file-handling/upload-cache-and-persistence.md` <!-- id: 16 -->
  - [x] `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`
  - [x] `upload_timeout`, `PersistentCacheStore`, `InFlightTracker`
- [x] Write `advanced-file-handling/tool-results-with-files.md` <!-- id: 17 -->
  - [x] Tools returning dicts with `content` + `attachments`, multipart content shapes
  - [x] Tool result normalization across providers

### Phase 5 — Provider Deep Dives (`provider-deep-dives/`)

- [x] Write `provider-deep-dives/chat-completions-provider.md` <!-- id: 18 -->
  - [x] `OpenAIChatCompletionsClient`, message translation, tool-result synthetic user messages
  - [x] Supported/unsupported fields, error handling, using `LanguageModel(provider="openai-chat-completions")`
- [x] Write `provider-deep-dives/responses-provider.md` <!-- id: 19 -->
  - [x] `OpenAIResponsesClient`, input_image/file/text translation
  - [x] `function_call_output` handling, stateful conversations via `_previous_response_id`, field support matrix
- [x] Write `provider-deep-dives/custom-providers.md` <!-- id: 20 -->
  - [x] `ProviderRegistry.register`, `LLMClient` ABC, implementing `_chat_impl`, `close`
  - [x] `ProviderFactory` protocol, alias resolution, `normalize_base_url`

### Phase 6 — Execution & Reference (`execution-and-reference/`)

- [x] Write `execution-and-reference/custom-execution-loops.md` <!-- id: 21 -->
  - [x] `BaseLoop` internals, `build_system_message`, `_run_sync` vs `_run_stream`
  - [x] `process_tool_calls`, `last_assistant_content`, overriding `max_iterations`, creating custom loops
- [x] Write `execution-and-reference/canonical-stream-events.md` <!-- id: 22 -->
  - [x] Complete reference of all 15 event types, tool call state machine diagram
  - [x] Event ordering guarantees, `LLMResponse` structure, `TokenUsage`, `ToolCallDict`
- [x] Write `execution-and-reference/error-handling.md` <!-- id: 23 -->
  - [x] `ProviderApiError`, `ProviderAuthError`, `ProviderNotSupportedError`
  - [x] try/except patterns, retry with tenacity, cancellation handling

## Testing Phase

- [x] Run full validation suite — expect GREEN (all pass) <!-- id: 24 -->
  - [x] `cd src/tinycua-sdk && uv run pytest tests/test_cookbook_structure.py -v`
  - [x] Structural tests: file existence, naming conventions, index completeness, page structure
  - [x] Runtime snippet tests: every standalone ` ```python ` block is extracted to `./tmp/`, executed via subprocess, and checked for exit code 0
  - [x] Security tests: no secrets, no hardcoded API keys
  - [x] Provider pattern tests: both local and remote patterns present
- [x] Verify temp file cleanup <!-- id: 25 -->
  - [x] Confirm `./tmp/` is empty after test suite completes (no leaked `_cookbook_snippet_*.py` files)
  - [x] Run `ls src/tinycua-sdk/tmp/` — should be empty or contain only gitignore placeholder
- [x] Run existing test suite — confirm no regressions <!-- id: 26 -->
  - [x] `cd src/tinycua-sdk && uv run pytest`

## Verification Phase

- [x] Linear reading experience review <!-- id: 27 -->
  - [x] Read all 19 pages in `index.md` order
  - [x] Confirm no concept is used before it is introduced (no forward references)
  - [x] Confirm the dependency graph in design.md is accurately reflected in the reading order
- [x] Self-containment spot check <!-- id: 28 -->
  - [x] Jump to 3 random pages, read only that page, confirm you can follow and run the examples
  - [x] Verify imports are explicit and prerequisites are stated
  - [x] Note: automated runtime tests already verify standalone snippets execute cleanly — this check is for the human reading experience
- [x] Cross-page link verification <!-- id: 29 -->
  - [x] Click every "Prerequisites" link — confirm it goes to the correct page
  - [x] Click every "Next Steps" link — confirm it goes to the next logical page
  - [x] Click every `index.md` link — confirm it goes to the correct page and description matches content
- [x] Provider pattern verification <!-- id: 30 -->
  - [x] For every page in provider-related phases, confirm both local and remote patterns are shown
  - [x] Verify patterns are consistent with page 04 (language-models-and-providers)
- [x] Secrets audit <!-- id: 31 -->
  - [x] Grep all cookbook files for API key patterns (`sk-`, bearer tokens, hardcoded secrets)
  - [x] Confirm all credentials use `os.environ.get("...", "placeholder")` or `"$VAR_NAME"` placeholder notation

### Phase 7 — README Update

- [x] Update `src/tinycua-sdk/README.md` — add link to cookbook <!-- id: 32 -->
  - [x] Add a "Cookbook" section or link in the README pointing to `docs/cookbook/index.md`
  - [x] Brief description: "Guided, basic-to-advanced walkthrough of all SDK capabilities"
- [x] Review cookbook page consistency <!-- id: 33 -->
  - [x] All pages follow the design template (title, Prerequisites, Overview, sections, Common Pitfalls, Next Steps)
  - [x] Consistent tone and depth across pages
  - [x] All phase folders have consistent naming (lowercase, hyphenated)

## Review and Merge

- [x] Create pull request with all cookbook content <!-- id: 34 -->
- [ ] Address review feedback <!-- id: 35 -->
- [ ] Merge to main branch <!-- id: 36 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-29*
