# Tasks: TINYCUA SDK Cookbook

Implementation tasks for the 19-page SDK cookbook under `src/tinycua-sdk/docs/cookbook/`. Check off items as completed.

## TDD Phase (Tests First)

- [ ] Write structural validation test suite at `src/tinycua-sdk/tests/test_cookbook_structure.py` <!-- id: 0 -->
  - [ ] Implement all test functions from implementation-plan.md Success Criteria section
  - [ ] Test file must pass `uv run python -m py_compile` verification
- [ ] Run validation tests — expect RED (all fail) since no cookbook exists yet <!-- id: 1 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/test_cookbook_structure.py -v`
  - [ ] Confirm all tests fail with clear, actionable error messages (not crashes)

## Implementation Phase

### Phase 0 — Scaffolding & Index

- [ ] Create directory structure <!-- id: 2 -->
  - [ ] Create `src/tinycua-sdk/docs/cookbook/` root directory
  - [ ] Create all six phase subdirectories: `onboarding/`, `core-concepts/`, `agent-extensions/`, `advanced-file-handling/`, `provider-deep-dives/`, `execution-and-reference/`
- [ ] Create `index.md` at `src/tinycua-sdk/docs/cookbook/index.md` <!-- id: 3 -->
  - [ ] List all 19 pages grouped by phase with one-line descriptions
  - [ ] Pages listed in linear reading order per design.md dependency graph
  - [ ] Links use relative paths: `[Page Title](./phase/slug.md)`
- [ ] Run validation tests — expect structural tests pass (files exist), content tests still fail <!-- id: 4 -->

### Phase 1 — Onboarding (`onboarding/`)

- [ ] Write `onboarding/installation-and-setup.md` <!-- id: 5 -->
  - [ ] pip/uv install, environment variables, `.env` setup, verify installation
  - [ ] Dual provider patterns: local (LM Studio) and remote (OpenAI) configuration
  - [ ] No hardcoded secrets — use `os.environ.get("OPENAI_API_KEY")`
  - [ ] Follow page template: title, Prerequisites, Overview, tutorial sections, Common Pitfalls, Next Steps
- [ ] Write `onboarding/your-first-agent.md` <!-- id: 6 -->
  - [ ] Import `Agent`, create with name/instructions, call `run()`, print response
  - [ ] Minimal imports — `from tinycua_sdk import Agent`
- [ ] Write `onboarding/agent-configuration.md` <!-- id: 7 -->
  - [ ] `AgentConfig`, `AgentPolicy`, `from_config`/`to_config`, JSON/YAML serialization, `from_json_file`/`from_yaml_file`
  - [ ] Show load/save patterns

### Phase 2 — Core Concepts (`core-concepts/`)

- [ ] Write `core-concepts/language-models-and-providers.md` <!-- id: 8 -->
  - [ ] `LanguageModel` fields, model resolution, provider selection, local vs remote, `to_dict`/`from_dict`, `api_key` env expansion
  - [ ] Explicitly teach the two provider paths (local and remote) — later pages refer back here
- [ ] Write `core-concepts/streaming-responses.md` <!-- id: 9 -->
  - [ ] `stream=True`, async iteration, event types, content accumulation, cancellation
  - [ ] Import `Agent` and demonstrate `agent.stream_events()`
- [ ] Write `core-concepts/file-attachments.md` <!-- id: 10 -->
  - [ ] `FileAttachment.from_path`, `from_bytes`, `from_url`, `file_id` reference
  - [ ] Passing to `agent.run(file_attachments=[...])`
- [ ] Write `core-concepts/multimodal-content.md` <!-- id: 11 -->
  - [ ] `ContentPart` text/file types, building multimodal queries, mixing text and images
  - [ ] Provider behavior differences between chat-completions and responses

### Phase 3 — Agent Extensions (`agent-extensions/`)

- [ ] Write `agent-extensions/creating-tools.md` <!-- id: 12 -->
  - [ ] `@tool` decorator (bare and parameterized), `Tool.from_callable`, docstring parsing
  - [ ] JSON Schema generation, `Tool.from_dict`, `load_directory`
- [ ] Write `agent-extensions/skills-and-skill-registry.md` <!-- id: 13 -->
  - [ ] `Skill` model, `Skill.from_directory`, `SKILL.md` format, `SkillRegistry`
  - [ ] `agent.add_skills()`, how skills appear in system prompt
- [ ] Write `agent-extensions/tool-permissions-and-approval.md` <!-- id: 14 -->
  - [ ] `tool_permissions` map (`allow`/`ask`/`deny`), `ApprovalWorkflow` ABC
  - [ ] `DefaultApprovalWorkflow`, custom workflow example, multi-workflow chaining

### Phase 4 — Advanced File Handling (`advanced-file-handling/`)

- [ ] Write `advanced-file-handling/streaming-file-uploads.md` <!-- id: 15 -->
  - [ ] `FileAttachment.from_path(stream=True)`, `StreamingFileAttachment`, `iter_base64_chunks`
  - [ ] `hash_content`, when to use vs memory-backed uploads
- [ ] Write `advanced-file-handling/upload-cache-and-persistence.md` <!-- id: 16 -->
  - [ ] `cache_dir`, `cache_max_entries`, `session_cache_max_entries`, `cache_namespace`
  - [ ] `upload_timeout`, `PersistentCacheStore`, `InFlightTracker`
- [ ] Write `advanced-file-handling/tool-results-with-files.md` <!-- id: 17 -->
  - [ ] Tools returning dicts with `content` + `attachments`, multipart content shapes
  - [ ] Tool result normalization across providers

### Phase 5 — Provider Deep Dives (`provider-deep-dives/`)

- [ ] Write `provider-deep-dives/chat-completions-provider.md` <!-- id: 18 -->
  - [ ] `OpenAIChatCompletionsClient`, message translation, tool-result synthetic user messages
  - [ ] Supported/unsupported fields, error handling, using `LanguageModel(provider="openai-chat-completions")`
- [ ] Write `provider-deep-dives/responses-provider.md` <!-- id: 19 -->
  - [ ] `OpenAIResponsesClient`, input_image/file/text translation
  - [ ] `function_call_output` handling, stateful conversations via `_previous_response_id`, field support matrix
- [ ] Write `provider-deep-dives/custom-providers.md` <!-- id: 20 -->
  - [ ] `ProviderRegistry.register`, `LLMClient` ABC, implementing `_chat_impl`, `close`
  - [ ] `ProviderFactory` protocol, alias resolution, `normalize_base_url`

### Phase 6 — Execution & Reference (`execution-and-reference/`)

- [ ] Write `execution-and-reference/custom-execution-loops.md` <!-- id: 21 -->
  - [ ] `BaseLoop` internals, `build_system_message`, `_run_sync` vs `_run_stream`
  - [ ] `process_tool_calls`, `last_assistant_content`, overriding `max_iterations`, creating custom loops
- [ ] Write `execution-and-reference/canonical-stream-events.md` <!-- id: 22 -->
  - [ ] Complete reference of all 15 event types, tool call state machine diagram
  - [ ] Event ordering guarantees, `LLMResponse` structure, `TokenUsage`, `ToolCallDict`
- [ ] Write `execution-and-reference/error-handling.md` <!-- id: 23 -->
  - [ ] `ProviderApiError`, `ProviderAuthError`, `ProviderNotSupportedError`
  - [ ] try/except patterns, retry with tenacity, cancellation handling

## Testing Phase

- [ ] Run full validation suite — expect GREEN (all pass) <!-- id: 24 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest tests/test_cookbook_structure.py -v`
  - [ ] Structural tests: file existence, naming conventions, index completeness, page structure
  - [ ] Runtime snippet tests: every standalone ` ```python ` block is extracted to `./tmp/`, executed via subprocess, and checked for exit code 0
  - [ ] Security tests: no secrets, no hardcoded API keys
  - [ ] Provider pattern tests: both local and remote patterns present
- [ ] Verify temp file cleanup <!-- id: 25 -->
  - [ ] Confirm `./tmp/` is empty after test suite completes (no leaked `_cookbook_snippet_*.py` files)
  - [ ] Run `ls src/tinycua-sdk/tmp/` — should be empty or contain only gitignore placeholder
- [ ] Run existing test suite — confirm no regressions <!-- id: 26 -->
  - [ ] `cd src/tinycua-sdk && uv run pytest`

## Verification Phase

- [ ] Linear reading experience review <!-- id: 27 -->
  - [ ] Read all 19 pages in `index.md` order
  - [ ] Confirm no concept is used before it is introduced (no forward references)
  - [ ] Confirm the dependency graph in design.md is accurately reflected in the reading order
- [ ] Self-containment spot check <!-- id: 28 -->
  - [ ] Jump to 3 random pages, read only that page, confirm you can follow and run the examples
  - [ ] Verify imports are explicit and prerequisites are stated
  - [ ] Note: automated runtime tests already verify standalone snippets execute cleanly — this check is for the human reading experience
- [ ] Cross-page link verification <!-- id: 29 -->
  - [ ] Click every "Prerequisites" link — confirm it goes to the correct page
  - [ ] Click every "Next Steps" link — confirm it goes to the next logical page
  - [ ] Click every `index.md` link — confirm it goes to the correct page and description matches content
- [ ] Provider pattern verification <!-- id: 30 -->
  - [ ] For every page in provider-related phases, confirm both local and remote patterns are shown
  - [ ] Verify patterns are consistent with page 04 (language-models-and-providers)
- [ ] Secrets audit <!-- id: 31 -->
  - [ ] Grep all cookbook files for API key patterns (`sk-`, bearer tokens, hardcoded secrets)
  - [ ] Confirm all credentials use `os.environ.get("...", "placeholder")` or `"$VAR_NAME"` placeholder notation

### Phase 7 — README Update

- [ ] Update `src/tinycua-sdk/README.md` — add link to cookbook <!-- id: 32 -->
  - [ ] Add a "Cookbook" section or link in the README pointing to `docs/cookbook/index.md`
  - [ ] Brief description: "Guided, basic-to-advanced walkthrough of all SDK capabilities"
- [ ] Review cookbook page consistency <!-- id: 33 -->
  - [ ] All pages follow the design template (title, Prerequisites, Overview, sections, Common Pitfalls, Next Steps)
  - [ ] Consistent tone and depth across pages
  - [ ] All phase folders have consistent naming (lowercase, hyphenated)

## Review and Merge

- [ ] Create pull request with all cookbook content <!-- id: 34 -->
- [ ] Address review feedback <!-- id: 35 -->
- [ ] Merge to main branch <!-- id: 36 -->

---

*Task IDs enable tracking and cross-referencing*
*Run `/implement` to execute these tasks*
*Last updated: 2026-05-28*
