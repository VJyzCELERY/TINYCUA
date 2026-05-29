# TINYCUA SDK Cookbook

A guided, basic-to-advanced walkthrough of all TINYCUA SDK capabilities. Each page is
self-contained with runnable code examples supporting both local and
remote (OpenAI) providers.

Read through in order for a complete learning path, or jump to any page for a
specific topic.

---

## Phase 1 — Onboarding

1. **[Installation and Setup](./onboarding/installation-and-setup.md)** — Install `tinycua-sdk`, configure environment variables, set up `.env`, and verify your installation.
2. **[Your First Agent](./onboarding/your-first-agent.md)** — Create a minimal `Agent`, call `run()`, and get your first response.
3. **[Agent Configuration](./onboarding/agent-configuration.md)** — Understand `AgentConfig` and `AgentPolicy`, serialize agents to JSON/YAML, and load from files.

## Phase 2 — Core Concepts

4. **[Language Models and Providers](./core-concepts/language-models-and-providers.md)** — Configure `LanguageModel` fields, select providers, and understand local vs remote model resolution.
5. **[Streaming Responses](./core-concepts/streaming-responses.md)** — Stream agent responses with `stream=True`, iterate over events, and accumulate content.
6. **[File Attachments](./core-concepts/file-attachments.md)** — Attach files to agent queries using `FileAttachment.from_path`, `from_bytes`, and `from_url`.
7. **[Multimodal Content](./core-concepts/multimodal-content.md)** — Build multimodal queries with `ContentPart`, mixing text, images, and file content.

## Phase 3 — Agent Extensions

8. **[Creating Tools](./agent-extensions/creating-tools.md)** — Define tools with the `@tool` decorator, parse docstrings, and generate JSON Schema.
9. **[Skills and Skill Registry](./agent-extensions/skills-and-skill-registry.md)** — Load `Skill` objects from `SKILL.md` files, register them, and inject them into agent prompts.
10. **[Tool Permissions and Approval](./agent-extensions/tool-permissions-and-approval.md)** — Control tool execution with permissions (`allow`/`ask`/`deny`) and custom approval workflows.

## Phase 4 — Advanced File Handling

11. **[Streaming File Uploads](./advanced-file-handling/streaming-file-uploads.md)** — Upload large files without buffering using `StreamingFileAttachment` and chunked base64 encoding.
12. **[Upload Cache and Persistence](./advanced-file-handling/upload-cache-and-persistence.md)** — Configure persistent upload caching with `cache_dir`, content-addressed deduplication, and namespaces.
13. **[Tool Results with Files](./advanced-file-handling/tool-results-with-files.md)** — Return files from tools, normalize multipart content, and handle provider differences.

## Phase 5 — Provider Deep Dives

14. **[Chat Completions Provider](./provider-deep-dives/chat-completions-provider.md)** — Deep dive into `OpenAIChatCompletionsClient`: message translation, tool-result synthetic messages, and field support.
15. **[Responses Provider](./provider-deep-dives/responses-provider.md)** — Deep dive into `OpenAIResponsesClient`: input translation, stateful conversations, and `function_call_output` handling.
16. **[Custom Providers](./provider-deep-dives/custom-providers.md)** — Build your own LLM provider by implementing `LLMClient` and registering with `ProviderRegistry`.

## Phase 6 — Execution and Reference

17. **[Custom Execution Loops](./execution-and-reference/custom-execution-loops.md)** — Understand `BaseLoop` internals, override `max_iterations`, and build custom execution loops.
18. **[Canonical Stream Events](./execution-and-reference/canonical-stream-events.md)** — Complete reference of all 15 event types, event ordering guarantees, and tool call state machine.
19. **[Error Handling](./execution-and-reference/error-handling.md)** — Catch `ProviderApiError`, `ProviderAuthError`, and `ProviderNotSupportedError` with retry and cancellation patterns.

---

Read through the pages in order for a complete tour of the SDK, or jump directly
to any topic above.