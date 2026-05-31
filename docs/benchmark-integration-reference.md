# Benchmark Integration Reference — TINYCUA

> Architecture-aware integration plans for each benchmark, evaluated against TINYCUA's four dimensions: **memory**, **sessioning**, **tool calling**, **skills**.

---

## TINYCUA Architecture Baseline

Before integrating any benchmark, understand TINYCUA's current state along the four axes:

| Dimension | Status | Key Details |
|-----------|--------|-------------|
| **Memory** | NONE | Stateless per `Agent.run()`. No vector store, embeddings, RAG, or persistent memory. `storage/` and `session/` directories are dead code (pycache only). Old `short_term_memory`/`long_term_memory` params explicitly rejected via TypeError. Only persistence is file upload cache (`UploadSession`). |
| **Sessioning** | NONE | Agent is stateless. `session/` directory is dead code. OpenAI `previous_response_id` (Responses API only) provides API-level chaining — not SDK-managed. Tests confirm: `test_run_stateless`, `test_multiple_runs_are_independent`. |
| **Tool Calling** | ROBUST | Full pipeline: `@tool` decorator → `Tool(name,desc,params,fn)` → `type_to_json_schema()` → `BaseLoop` dispatches → `ToolExecutor` with permission/approval → `normalize_tool_result()` → injected back. Streaming via accumulator-based chunk assembly. 13 failure modes handled. |
| **Skills** | CLEAN | `Skill(name,desc,instructions)` is an immutable value object. Injected into system message as `[name]\n{instructions}`. Two discovery tools: `skills_list`, `skill_view`. `SkillRegistry` is not singleton. |

---

## What TINYCUA Needs to Run Any Benchmark

TINYCUA has a robust SDK with tool-calling infrastructure, but **no tool implementations** and **no CLI runtime**. Every benchmark below requires some or all of these components.

### A. CLI Runtime (prerequisite for all benchmarks)

| Component | Current State | What's Needed | Est. Lines |
|-----------|---------------|---------------|-----------|
| `tinycua/main.py` | Returns `0` (skeleton) | Functional entry point that loads config, creates Agent, calls `run()` | ~60 |
| `--message` flag | Missing | Accept user input string from CLI | ~15 |
| `--session` / `--new-session` flags | Missing | Session ID for multi-turn conversations across invocations | ~30 |
| `--config` path | Missing | Load agent config (tools, skills, model, permissions) from file | ~40 |
| `--instruction` flag | Missing | Task instruction string (for Harbor-style runners) | ~10 |
| `--output-dir` flag | Missing | Write results/traces to directory | ~15 |
| **Total CLI** | | | **~170** |

### B. Tool Implementations (needed by multiple benchmarks)

| Tool | Needed By | Description | Est. Lines |
|------|-----------|-------------|-----------|
| `shell_exec(command)` | **All** | Run bash command in subprocess, return stdout/stderr/exit code | ~60 |
| `read_file(path)` | WildClawBench, ClawMark, Claw-Eval | Read file contents from workspace | ~25 |
| `write_file(path, content)` | WildClawBench, ClawMark, Claw-Eval | Write content to file | ~25 |
| `list_directory(path)` | WildClawBench, ClawMark | List files in directory | ~20 |
| `web_search(query)` | WildClawBench, Claw-Eval, ClawMark | Search web and return results | ~80 |
| `browser_open(url)` | WildClawBench | Open web page and return rendered content | ~120 |
| `email_send(to, subject, body)` | WildClawBench, ClawMark | Send email via SMTP | ~60 |
| `email_read(query)` | WildClawBench, ClawMark | Read/receive emails | ~60 |
| `image_analyze(path)` | WildClawBench, ClawMark | Analyze image content via VLM | ~40 |
| `video_extract_clips(path, timestamps)` | WildClawBench | Extract video segments via ffmpeg | ~80 |
| `git_clone(url, path)` | WildClawBench, Terminal-Bench | Clone git repository | ~30 |
| `execute_python(code)` | All coding tasks | Run Python snippet in sandbox | ~40 |
| **Total Tools** | | | **~640** |

### C. Service Clients (needed by ClawMark + WildClawBench)

| Client | Needed By | Description | Est. Lines |
|--------|-----------|-------------|-----------|
| `EmailClient` | ClawMark, WildClawBench | GreenMail SMTP/IMAP client | ~150 |
| `CalendarClient` | ClawMark, WildClawBench | Radicale CalDAV client | ~150 |
| `NotionClient` | ClawMark | Notion-compatible knowledge base API client | ~150 |
| `SheetsClient` | ClawMark | Google Sheets-compatible API client | ~150 |
| **Total Service Clients** | | | **~600** |

### D. Session & Memory Infrastructure

| Component | Needed By | Description | Est. Lines |
|-----------|-----------|-------------|-----------|
| `ConversationSession` | ClawEval, Claw-Eval, ClawMark, τ-bench | In-memory message list with serialization | ~100 |
| `FileSessionStore` | ClawEval, Claw-Eval | File-backed session persistence (`sessions/{id}.json`) | ~60 |
| `TaskSession` | ClawMark, τ-bench | Holds task-level state across multi-stage workflows | ~80 |
| `MemoryStore` (SQLite + vector) | Engram, QwenClawBench | Long-term memory persistence + semantic search | ~500 |
| `MemoryExtractor` | Engram | Extract facts from conversation traces | ~300 |
| **Total Session/Memory** | | | **~1040** |

### E. Benchmark Adapters

| Adapter | Needed By | Description | Est. Lines |
|---------|-----------|-------------|-----------|
| `ClawBenchTraceAdapter` | ClawBench | Emit Partner Trace Spec JSONL | ~80 |
| `ClawEvalCLIAdapter` | ClawEval | `--message`/`--session` → Agent.run() | ~40 |
| `ClawEvalHarnessAdapter` | Claw-Eval | Python harness integration | ~120 |
| `WildClawHarnessAdapter` | WildClawBench | Docker image + tool schema alignment | ~300 |
| `ClawMarkHarnessAdapter` | ClawMark | Task YAML parser + stage runner | ~200 |
| `ClawProYAMLParser` | ClawProBench | OpenClaw YAML → TINYCUA config | ~150 |
| `TauBenchHalfDuplexAgent` | τ-bench | `HalfDuplexAgent` interface impl | ~120 |
| `QwenClawBenchAdapter` | QwenClawBench | PinchBench-based format bridge | ~200 |
| `EngramAdapter` | Engram | Seed→Settle→Probe→Judge protocol | ~300 |
| `HermesAtroposAdapter` | Hermes (TB2) | Atropos `BaseEnv` subclass | ~500 |
| `HarborInstalledAgent` | Terminal-Bench | Harbor `BaseInstalledAgent` | ~100 |
| **Total Adapters** | | | **~2110** |

### F. Infrastructure & Docker

| Component | Needed By | Description | Est. Lines |
|-----------|-----------|-------------|-----------|
| Docker image (`tinycua-runner`) | WildClawBench, Terminal-Bench | Deployable agent container | ~40 |
| Docker Compose integration | ClawMark | Connect to 5 stateful service containers | ~60 |
| Harbor agent registration | Terminal-Bench | Register tinycua in Harbor registry | ~20 |
| **Total Infra** | | | **~120** |

### G. Overall Build Order (Dependency-Aware)

The components above form a dependency tree. Build order matters:

```
Phase 0 — Foundation (shared by all benchmarks)
├── A: CLI Runtime (~170 lines)
├── B: shell_exec, read_file, write_file (~130 lines)
├── D: ConversationSession (~100 lines)
└── Total: ~400 lines

Phase 0.5 — WildClawBench tools (rich tool ecosystem)
├── B: Remaining tools: web_search, browser_open, email_send/read,
│   image_analyze, video_extract_clips, git_clone (~510 lines)
├── C: EmailClient, CalendarClient (~300 lines)
├── F: Docker image (~40 lines)
└── Total: ~850 lines

Phase 1 — WildClawBench adapter
├── E: WildClawHarnessAdapter (~300 lines)
└── F: CI integration (~50 lines)

Phase 2+ — Other benchmark adapters
├── E: Specific adapter per benchmark (~40–500 lines each)
├── C: Remaining service clients (ClawMark-only, ~300 lines)
└── D: MemoryStore + MemoryExtractor (Engram-only, ~800 lines)
```

The CLI runtime + shell tool + file tools are the **true cross-cutting prerequisites** — they unlock every benchmark. Build these first (Phase 0), then WildClawBench's full tool ecosystem (Phase 0.5), then WildClawBench adapter (Phase 1). Later benchmarks reuse the tools from Phase 0.5 with only adapter-level effort.

---

### 1. WildClawBench (`InternLM/WildClawBench`)

**Repo**: <https://github.com/InternLM/WildClawBench>
**Tasks**: 60 across 6 categories (Productivity 10, Code 12, Social 6, Search 11, Creative 11, Safety 10)
**Harnesses**: OpenClaw, Claude Code, Codex, Hermes Agent
**Scoring**: Hybrid (rule-based + environment-state audit + LLM/VLM judge)
**Infrastructure**: Docker containers, per-harness Docker images

#### Why it fits TINYCUA

**WildClawBench is the primary benchmark target.** Adding TINYCUA as a 5th harness gives apples-to-apples comparison against OpenClaw, Claude Code, Codex, and Hermes Agent on identical 60 tasks. Building the richest tool ecosystem first (browser, email, git, video, image, web search) creates a superset that all later benchmarks can reuse — Phase 0 infrastructure and tools built for WildClawBench unlock ClawEval, ClawBench, Claw-Eval, ClawProBench, and τ-bench with no additional tooling effort.

#### Memory Matter

- **Required for long-horizon tasks.** Average 8 min wall-clock, 20+ tool calls, up to 60+ calls for complex tasks.
- Some tasks span multiple phases within a single session (e.g., "read 50 papers, classify, produce digest").
- TINYCUA's `BaseLoop` with `max_iterations` and `max_tool_calls` handles this within a single `Agent.run()`. The `working_messages` list maintains full conversation context.
- **No cross-day memory needed** — all tasks complete in a single session.

#### Sessioning Matter

- **Single session per task.** WildClawBench tasks run start-to-finish in one session.
- TINYCUA's stateless `run()` is fine for this — each task is one `run()` call.
- Session isolation: each Docker container is fresh. TINYCUA gets a clean `Agent` per task.
- The `working` message list in `BaseLoop._run_sync()` maintains ongoing context.

#### Tool Calling Matter

- **Critical gap.** WildClawBench expects a rich tool ecosystem:
  - Shell execution (`exec`)
  - Process management (`process`)
  - Web search and page fetch (`web`)
  - File reading (`read`)
  - Image inspection and generation (`image`)
  - File creation and editing (`author`)
  - Email, calendar (social tasks)
  - Video/audio processing (creative synthesis tasks)
  - Git operations (code intelligence tasks)

- TINYCUA currently has minimal native tools. The SDK has tool infrastructure (`@tool` decorator, `Tool` dataclass, `ToolExecutor`, `BaseLoop` dispatch) but **no actual tool implementations** beyond `skills_list`/`skill_view`.
- **Need to build**: ShellTool, FileReadTool, FileWriteTool, WebSearchTool, BrowserTool, EmailTool, ImageTool, VideoTool.
- These are not tinycua-sdk responsibilities — they belong in `tinycua` (CLI) app layer or a new `tinycua-tools` package.
- Tool schema format: OpenAI-compatible. TINYCUA matches.
- Tool schemas must be held fixed across harness comparison — TINYCUA's `Tool.to_config()` must produce identical schemas as OpenClaw for equivalent tools.

#### Skills Scenario Matter

- **Somewhat relevant.** WildClawBench tasks use skills implicitly (e.g., "install dependencies from source" needs coding skill, "email scheduling" needs communication skill).
- TINYCUA's `Skill` injection via system prompt provides this context naturally.
- Some tasks reference specific skill-like capabilities (e.g., "use ffmpeg to extract audio"). These are tool calls, not skills.
- Safety tasks test: prompt injection via file content, leaked API key detection. These depend on the agent's inherent safety behavior, not TINYCUA-specific skills.

#### Docker Image Requirements

```dockerfile
# wildclawbench-tinycua: Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git ffmpeg curl wget chromium \
    python3-pip uv

# Install TINYCUA SDK + CLI
COPY src/tinycua-sdk /build/tinycua-sdk
COPY src/tinycua /build/tinycua
RUN cd /build/tinycua && uv sync

# Tool environment binaries
RUN pip install mss Pillow pyautogui opencv-python yt-dlp

# WildClawBench workspace
WORKDIR /workspace
COPY tasks/ /workspace/tasks/

ENTRYPOINT ["tinycua", "--config", "/workspace/openclaw.yaml"]
```

#### Integration Steps

```
1. Build the tool ecosystem
   - ShellExec (bash subprocess), FileRead/Write, WebSearch, Browser
   - Email (GreenMail SMTP), Calendar (CalDAV)
   - Image (Pillow based: read, describe, generate)
   - Video/audio (ffmpeg wrappers)
   - Git operations

2. Create harness adapter
   - Translation layer: task YAML + Markdown → Agent.run()
   - Must match OpenClaw's tool schema format
   - Must handle time budgets (300-1200s) — terminate on timeout

3. Build Docker image
   - Follow WildClawBench's Docker image pattern
   - Tag: wildclawbench-tinycua:v1

4. Register harness in run.sh
   - Add tinycua case alongside openclaw/claudecode/codex/hermesagent

5. Test with single task before full sweep
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Tool ecosystem | ~2000 | High |
| Harness adapter | ~300 | Medium-High |
| Docker image | ~40 | Low |
| CI integration | ~50 | Low |
| **Total** | **~2400** | |

---



### 2. ClawEval (`clark-labs-inc/claweval`)

**Repo**: <https://github.com/clark-labs-inc/claweval>
**Tasks**: 18 episodes across 7 suites
**Scoring**: per-episode checks (contains, regex, equals_trim, json_pointer, llm_judge)
**Language**: Rust binary, command backend

#### Why it fits TINYCUA

ClawEval supports a `command` backend: you point it at any executable with `{session}` and `{message}` placeholders. TINYCUA's CLI skeleton (`tinycua/cli/main.py`) just needs a `--message` flag to accept input.

#### Memory Matter

- **Minimal.** Suites: `matrix_basic` (single-turn), `matrix_memory` (3 episodes multi-turn memory), `matrix_longhorizon_reliability` (2 episodes, 10-turn secret retention).
- For `matrix_memory` and `matrix_longhorizon_reliability`: TINYCUA's stateless Agent **cannot pass these** — it forgets state between turns.
- **Gap to fill**: Need a thin session wrapper that maintains conversation history across multiple `--message` invocations. This is session-level context, not long-term memory.
- A simple `ConversationSession` class storing `messages[]` list, with `session_id → messages` dict, would bridge this. ~100 lines.

#### Sessioning Matter

- **Required** for multi-turn suites. ClawEval invokes the agent once per episode step with `{session}` and `{message}`.
- TINYCUA needs a `--session` flag that loads/saves message history from a session store.
- Simple file-backed store: `sessions/{session_id}.json` → list of messages.
- The `--new-session` flag resets state.

#### Tool Calling Matter

- **Direct fit.** ClawEval episodes exercise: PONG (echo), memory retention, JSON output, structured data, async probes.
- TINYCUA's tool system covers all these categories.
- Tool schemas should be passed alongside the agent config for each suite.
- JSON structured output: TINYCUA's `response_format` in `LanguageModel` config handles this.

#### Skills Scenario Matter

- **Not tested.** ClawEval doesn't probe skill composition.
- Skills irrelevant for these episodes.

#### Integration Steps

```
1. Add --message and --session flags to tinycua CLI (cli/main.py)
   - --message: the user input string
   - --session: session identifier for multi-turn convos
   - --new-session: reset state

2. Create SessionManager
   - In-memory: dict[str, list[dict]] messages
   - File-backed: sessions/{session_id}.json
   - Wire into Agent.run() as the messages parameter

3. Ensure tools are registered
   - Basic echo/reply: handled by LLM itself
   - JSON structured output: set response_format in LanguageModel

4. Test: claweval run suites/matrix_basic.json --command "uv run python -m tinycua --message"
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| CLI --message/--session flags | ~40 | Low |
| SessionManager (in-memory) | ~80 | Low |
| SessionManager (file-backed) | ~60 | Low |
| **Total** | **~180** | |

---



### 3. ClawBench (`openclaw/clawbench`)

**Repo**: <https://github.com/openclaw/clawbench>
**Tasks**: 19 signal-curated (from 40-task dev pool)
**Scoring**: 4-axis (Completion 40%, Trajectory 30%, Behavior 20%, Judge advisory 10%)
**Metric**: pass^k, Taguchi Signal-to-Noise, bootstrap CI

#### Why it fits TINYCUA

ClawBench defines a **Partner Trace Spec** — a JSONL interchange format for agent execution traces. You don't need to run inside OpenClaw; you just emit traces in the agreed schema. TINYCUA's `BaseLoop` already tracks tool calls, results, and timing — converting to JSONL is mechanical.

#### Memory Matter

- **None needed.** Core v1 tasks are single-session (Tier 1–5, max ~60 tool calls).
- TINYCUA's stateless design is fine. Each task starts with a fresh `Agent.run()`.
- No memory persistence across tasks.

#### Sessioning Matter

- **None needed.** Each task = one independent execution.
- TINYCUA's stateless `run()` matches perfectly.
- No session ID, no conversation continuation across tasks.

#### Tool Calling Matter

- **Direct fit.** ClawBench tasks exercise: shell execution, file read/write, web search, browser, email.
- TINYCUA needs to implement tools for each task category. The `@tool` decorator maps 1:1.
- Tool schema is OpenAI-compatible (`type: function, name, description, parameters`) — TINYCUA's `Tool.to_config()` output matches.
- Need to add: browser tool, email tool (mock SMTP), calendar tool (CalDAV).
- The Partner Trace Spec expects: `{turn_id, tool_name, tool_args, tool_result, timestamp, duration_ms, error}` — TINYCUA's `RunResult.trace` and `ToolCall` carry all this.

#### Skills Scenario Matter

- **Not relevant.** ClawBench tests agent capability, not skill composition.
- If TINYCUA has native skills (e.g., code generation, file ops), they're injected via `build_system_message()` as skill instructions.
- ClawBench doesn't probe skill discovery or composition — it tests task completion.

#### Integration Steps

```
1. Create tinycua-sdk/tinycua_sdk/trace/clawbench.py
   - Adapter: wraps Agent.run(), emits Partner Trace Spec JSONL
   - Fields: turn_id, tool_name, tool_args, tool_result, timestamp_ms, duration_ms, error, token_usage

2. Register trace emission hook in BaseLoop.process_tool_calls()
   - After normalize_tool_result(), write trace entry
   - Gate behind flag (e.g., loop.trace_callback)

3. Implement task tools:
   - ShellExecTool, FileReadTool, FileWriteTool (maybe exist)
   - WebSearchTool, BrowserTool, EmailTool (new)

4. Run: point clawbench at the trace output directory
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Trace adapter | ~80 | Low |
| BaseLoop hook | ~20 | Low |
| Task tools (shell, file) | ~60 | Low (reuse existing) |
| Task tools (browser, email) | ~400 | Medium |
| **Total** | **~560** | |

---



### 4. Claw-Eval (`claw-eval/claw-eval`)

**Repo**: <https://github.com/claw-eval/claw-eval>
**Tasks**: 300 human-verified across 3 splits (general 161, multimodal 101, multi_turn 38)
**Scoring**: Completion + Safety + Robustness, Pass^3 (must pass all 3 runs)
**Language**: Python

#### Why it fits TINYCUA

Claw-Eval is a Python-based evaluation harness — same language, same ecosystem as TINYCUA. The assessment framework is directly embeddable. 300 tasks give broad signal across 9 categories.

#### Memory Matter

- **Required for multi_turn split (38 tasks).** These involve simulated user personas with clarification and advice — requires conversation continuity within a task.
- **Not needed** for `general` and `multimodal` splits (single-turn).
- TINYCUA's stateless Agent passes `general` and `multimodal` splits as-is.
- For `multi_turn`: need `--session` support (same as ClawEval integration).
- No long-term memory needed — only within-task conversation history.

#### Sessioning Matter

- **Required for multi_turn split.** The task defines a user persona; the agent must maintain context across 3-8+ turns.
- Same session wrapper from ClawEval integration applies.
- Pass^3 metric: run same task 3 times independently. TINYCUA's stateless Agent naturally gives independent runs.
- If session-level state is needed (e.g., "remember the user said X on turn 2"), the session wrapper maintains it.

#### Tool Calling Matter

- **Good fit.** Tasks exercise: communication, finance, operations, productivity.
- TINYCUA's `@tool` decorator, `type_to_json_schema()`, and `BaseLoop` dispatcher cover this.
- Need to implement some domain-specific tools:
  - Finance tools (spreadsheet, API calls)
  - Communication tools (email, messaging)
  - Data processing (CSV, JSON, PDF)
- Tool schema format: OpenAI-compatible. TINYCUA matches.
- Grading uses `gemini-3-flash` for general/multimodal, `claude-opus-4.6` for multi_turn grader and user-agent. TINYCUA needs to support these models via OpenRouter or direct API.

#### Skills Scenario Matter

- **Not directly tested.** But skills help performance on domain tasks.
- TINYCUA's `Skill` injection via system prompt can provide domain context:
  - `skill_finance`: "You have access to financial analysis tools..."
  - `skill_communication`: "You can send emails, manage contacts..."
- Skill discovery tools (`skills_list`, `skill_view`) let the agent introspect its capabilities — useful for this benchmark's broad domain coverage.

#### Integration Steps

```
1. Create Claw-Eval adapter module
   - tinycua-sdk/tinycua_sdk/eval/claweval_adapter.py
   - Implements the task interface (setup, format_prompt, compute_reward)

2. Register domain-specific tools
   - Finance tools (stock_price, spreadsheet_read/write)
   - Communication tools (email_send, email_read)
   - Data tools (csv_parse, pdf_extract, json_transform)

3. Session support for multi_turn split (reuse from ClawEval)

4. Wire into Claw-Eval's harness:
   - agent.run(task_prompt) → collect trace → evaluate with rubric

5. Run with Pass^3:
   - Each task executed 3×, must pass all 3
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Eval adapter | ~120 | Medium |
| Domain tools (finance, comms) | ~350 | Medium-High |
| Session support | ~80 | Low (reuse) |
| **Total** | **~550** | |

---

### 5. ClawProBench (`suyoumo/ClawProBench`)

**Repo**: <https://github.com/suyoumo/ClawProBench>
**Tasks**: 102 active (core=26, intelligence=95, native=36, full=102)
**Scoring**: Multi-profile, 3-try runs, avg/max/coverage summaries
**Infrastructure**: OpenClaw CLI binary (YAML scenarios, live OpenClaw runtime)

#### Why it fits TINYCUA

ClawProBench's YAML scenario format is well-defined and portable. Its profiles (core/intelligence/coverage/native/full) let you start small. The `--trials N` and `--continue` flags are mature infrastructure.

#### Memory Matter

- **Minimal.** Core profile (26 scenarios) is single-session.
- Intelligence profile (95 scenarios) may include multi-step tasks but all within one session.
- TINYCUA's stateless Agent handles these within a single `run()` call.

#### Sessioning Matter

- **Minimal.** Each scenario is independent. No cross-scenario state.
- No session management needed beyond the `working_messages` list in BaseLoop.

#### Tool Calling Matter

- **YAML-to-tool mapping required.** ClawProBench scenarios reference OpenClaw-specific tool patterns.
- TINYCUA needs a translation layer that reads ClawProBench YAML and converts scenario definitions to tool configurations.
- Tool categories exercised (from run.py inventory output): various across profiles.
- Without OpenClaw binary, TINYCUA must implement equivalent tools.
- The `--openclaw-binary` flag hints at a local OpenClaw process — TINYCUA could run alongside OpenClaw and only execute scenarios where tools overlap.

#### Skills Scenario Matter

- **Tested indirectly.** Scenarios reference skills through tool use.
- TINYCUA's Skill injection provides flexible domain context.
- ClawProBench's native profile (36 scenarios) tests OpenClaw-native skills specifically — these need direct tool equivalents.

#### Integration Steps

```
1. Create YAML scenario parser
   - Parse ClawProBench's scenario YAML format
   - Extract tool requirements, workspace state, evaluation criteria

2. Create tool compatibility map
   - Match ClawProBench tool names to TINYCUA tool implementations
   - Where no match exists, implement or stub

3. Create profile runner
   - Wraps Agent.run() with ClawProBench-style output format
   - Supports --trials N, --continue
   - Generates avg_score, max_score, coverage summaries

4. Test with core profile first
   - run.py dry → validates YAML parsing
   - run.py --trials 1 core → single pass
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| YAML parser | ~150 | Medium |
| Tool compatibility | ~400 | Medium |
| Profile runner | ~200 | Medium |
| **Total** | **~750** | |

---



### 6. τ-bench (`sierra-research/tau2-bench`)

**Repo**: <https://github.com/sierra-research/tau2-bench> (968 stars)
**Version**: τ³-bench (evolved from τ-bench → τ²-bench → τ³-bench)
**Tasks**: ~200 across domains (retail, airline, banking_knowledge)
**Scoring**: Database state comparison (no LLM judge), pass^k metric
**Infrastructure**: Own agent framework (`HalfDuplexAgent`, `FullDuplexAgent`, `LLMAgent`), LLM-simulated user
**Languages**: Python, supports voice full-duplex in τ³

#### Why it fits TINYCUA

τ-bench tests **policy adherence with a simulated human user** — something no other benchmark on this list measures. The agent gets domain-specific API tools AND a policy document; the user makes requests that may be out-of-policy, require judgment calls, or span multiple sub-tasks. This directly tests rule-following, not just task completion. τ-bench is cited in model cards from Anthropic, OpenAI, and Google — it's one of the most widely-adopted agentic benchmarks.

#### Memory Matter

- **Single-session across domains.** Retail/airline tasks are 3–15 turns within one session. τ³ knowledge domain adds retrieval-augmented memory (BM25 or neural).
- TINYCUA's stateless Agent handles core domains within one `run()` — the `working_messages` list maintains conversation context naturally.
- For τ³ knowledge domain: needs a retrieval pipeline (BM25 is built-in, ~50 lines of adapter).
- **No long-term memory needed** for retail/airline — each task is a fresh conversation.

#### Sessioning Matter

- **Own agent state model.** τ-bench defines `HalfDuplexAgent` and `FullDuplexAgent` with `get_init_state()` and `generate_next_message()`.
- TINYCUA must implement this interface. The state is just a message list (`system_messages` + `messages`) — maps directly to TINYCUA's existing loop internals.
- **Key inversion**: τ-bench's orchestrator drives the loop (calls agent per-turn), not TINYCUA's `BaseLoop`. TINYCUA's `Agent.run()` needs to be sliced into per-turn calls.
- This is the main integration surface: ~120 lines for the `HalfDuplexAgent` subclass + factory.

#### Tool Calling Matter

- **Domain-specific APIs, not shell commands.** τ-bench tools are retail/airline REST endpoints:
  - `search_products(query)`, `get_product_details(product_id)`, `get_order_status(order_id)`
  - `exchange_delivered_order_items(order_id, item_ids, new_item_ids, payment_method_id)`
  - `search_flights(origin, dest, date)`, `book_flight(flight_id, passenger, seat_class)`
  - Cancellation policies, refund logic, upgrade rules, baggage policies
- TINYCUA's `@tool` decorator maps 1:1. Tool schemas come from `env.get_tools()`.
- **Schema must match exactly**: tool name, parameter names/types, return structure — all must align with τ-bench's domain definitions.
- τ-bench passes tools to the agent constructor: `MyAgent(tools=env.get_tools(), domain_policy=env.get_policy())`.

#### Skills Scenario Matter

- **The policy IS a skill.** τ-bench's `domain_policy` text (e.g., "exchanges only within 30 days", "non-delivered orders cannot be exchanged") is semantically identical to TINYCUA's `Skill` — injected into the system prompt as instruction text:
  ```python
  Skill(name="retail_policy",
        description="Retail customer service policies — follow these rules exactly",
        instructions=domain_policy_text)
  ```
- τ-bench heavily penalizes policy violations (the database state check catches unauthorized actions). How the policy is presented in the system prompt directly affects scores — this is where skill injection quality matters most.

#### Integration Steps

```
1. Implement HalfDuplexAgent interface:
   - Factory function: create_agent(tools, domain_policy, llm, **kwargs)
   - get_init_state: builds system message with domain_policy as Skill
   - generate_next_message: calls Agent.run() for one turn, returns response

2. Register agent in tau2/registry.py

3. Run:
   tau2 run --domain retail --agent tinycua --agent-llm gpt-4.1

4. For τ³ knowledge retrieval:
   - Enable --retrieval-config bm25
   - Adapter wraps BM25 retriever into a memory-lookup tool
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Agent adapter (HalfDuplexAgent) | ~120 | Medium |
| Factory + registry | ~40 | Low |
| Tool schema alignment | ~80 | Low |
| τ³ knowledge retrieval adapter | ~50 | Medium |
| **Total** | **~290** | |

---

### 7. ClawMark (`evolvent-ai/ClawMark`)

**Repo**: <https://github.com/evolvent-ai/ClawMark>
**Tasks**: 100 across 13 professional domains
**Scoring**: Fully rule-based (1,537 deterministic Python checkers, no LLM-as-judge)
**Infrastructure**: Docker Compose with 5 stateful services (filesystem, GreenMail, Notion mock, Sheets mock, Radicale CalDAV)
**Metrics**: Weighted score + Strict Task Success

#### Why it fits TINYCUA

ClawMark's tool schema is **harness-agnostic by design** — any agent framework that implements the 5 service interfaces can be scored. TINYCUA's SDK architecture makes implementing these interfaces straightforward. The no-LLM-judge scoring is also the cleanest methodology for reproducible results.

#### Memory Matter

- **Required at task level.** Each task spans 2-6 turns (mean 3.6), representing 1-3 simulated workdays.
- Between turns, **exogenous state changes occur** — this is the benchmark's unique differentiator. New emails arrive, calendar events shift, files are appended. The agent must refresh state proactively.
- TINYCUA's stateless Agent **per-turn** is fine (each turn is one `Agent.run()`) BUT:
  - The agent must detect what changed between turns (silent-change detection — 56.5% fail rate)
  - This requires comparing current state against remembered state
  - **No long-term memory needed** — the agent re-reads environment state each turn
  - The fail rate on state detection means TINYCUA must implement state comparison logic in the agent prompt: "Before starting today's work, identify what has changed since yesterday."

#### Sessioning Matter

- **Required across turns within a task.** Task stages map to "days": Stage 0 (Day 1), Stage 1 (Day 2), Stage 2 (Day 3).
- Each stage is a separate agent invocation with the accumulated context.
- TINYCUA needs a **task-level session** that:
  - Stores the task prompt across stages
  - Preserves agent conversation history (working_messages) across turns
  - Provides tools to re-read environment state at each stage
- This is the same session wrapper pattern from ClawEval/Claw-Eval, but with explicit environment-state awareness.

#### Tool Calling Matter

- **Significant new surface.** ClawMark exercises 5 stateful services:
  1. **Filesystem** (Docker-mounted): TINYCUA should already have file tools
  2. **Email** (GreenMail SMTP/IMAP): Send, read, search, delete emails — new
  3. **Calendar** (Radicale CalDAV): Create, read, update, delete events — new
  4. **Knowledge base** (Notion-compatible mock): Create, read, update, search pages — new
  5. **Spreadsheet** (Google Sheets mock): Read/write cells, rows, sheets — new

- **1,072 multimodal artifacts**: PDFs, images, audio, video, spreadsheets.
- TINYCUA must implement tool wrappers for each service. The `@tool` decorator pattern maps cleanly.
- Tool schema must match ClawMark's expected format (standard OpenAI `type: function` — TINYCUA's `Tool.to_config()` matches).
- **Progressive enhancement**: start with filesystem-only tasks, add services incrementally.

#### Skills Scenario Matter

- **Directly relevant.** 13 professional domains:
  - Clinical assistant, content operation, e-commerce, EDA, executive assistant
  - HR, insurance, investment analyst, journalist, legal assistant
  - Project management, real estate, research assistant

- TINYCUA's `Skill` injection via system message is ideal here:
  ```python
  Skill(name="clinical_assistant", 
        description="Medical documentation and analysis",
        instructions="You are a clinical assistant. Extract information from medical PDFs, lab reports, and patient notes. Format according to clinical standards.")
  ```

- Skills provide domain context that significantly affects performance.
- 87 distinct in-task roles — each could have a `Skill` describing the role, norms, and expected output format.

#### Docker Compose Requirements

ClawMark runs its 5 services in Docker Compose. TINYCUA's agent container needs network access to:
- `greenmail:3025` (SMTP)
- `greenmail:3143` (IMAP)
- `radicale:5232` (CalDAV)
- `notion-mock:8000` (Knowledge base API)
- `sheets-mock:8001` (Spreadsheet API)

#### Integration Steps

```
1. Implement StatefulServiceClient base class
   - Base client with health check, retry, timeout
   - Subclasses: EmailClient, CalendarClient, NotionClient, SheetsClient

2. Implement tool wrappers (using @tool decorator):
   - email_send, email_read, email_search, email_delete
   - calendar_create, calendar_read, calendar_update, calendar_delete
   - notion_page_create, notion_page_read, notion_page_search
   - sheets_read_range, sheets_write_cell, sheets_add_row
   - filesystem_read, filesystem_write, filesystem_list

3. Create ClawMarkTaskSession
   - Holds task_id, current_stage, accumulated messages
   - Manages tool client lifecycle (→ reset between tasks)

4. Create harness adapter:
   - Reads task definition (YAML + Markdown)
   - Injects stage instructions sequentially
   - Collects traces per stage
   - Runs checker scripts post-task

5. Wire into docker-compose:
   - TINYCUA agent container joins clawmark network
   - Service endpoints passed as env vars
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| 5 service clients | ~600 | Medium |
| Tool wrappers (20+ tools) | ~500 | Medium |
| Task session harness | ~200 | Medium |
| Multimodal artifact handling | ~400 | Medium-High |
| Docker Compose integration | ~60 | Low |
| **Total** | **~1760** | |

---



### 8. QwenClawBench (`SKYLENAGE-AI/QwenClawBench`)

**Repo**: <https://github.com/SKYLENAGE-AI/QwenClawBench>
**Tasks**: 100 across 8 domains (workflow 21, sysops 20, knowledge 15, finance 10, data 10, security 9, comms 8, research 7)
**Scoring**: Automated + LLM Judge + Hybrid (penalized if automated < 0.75)
**Infrastructure**: Docker isolation, concurrent execution, anomaly detection

#### Why wait

QwenClawBench's strength is infrastructure reliability (anomaly detection, resumable runs) — features TINYCUA doesn't need in early evaluation. The penalized scoring (zeroing LLM judge when automated score < 0.75) is valuable but only after basic tool capability is proven.

#### Memory Matter

- **Required for knowledge domain tasks** (knowledge base construction, memory system design, document management).
- These test whether the agent can build, query, and maintain a knowledge base across interactions.
- TINYCUA's lack of memory means poor performance on 15/100 tasks.
- **Needed**: a KnowledgeBase tool (vector store or RAG) to pass these tasks.

#### Sessioning Matter

- **Required for workflow tasks** (21 tasks: workflow orchestration, cron jobs, multi-agent coordination).
- These test session continuity and multi-step orchestration.
- TINYCUA's single `run()` handles orchestration but not multi-agent coordination (which TINYCUA doesn't have).

#### Tool Calling Matter

- **Substantial overlap** with tools already needed for WildClawBench and ClawMark.
- Finance tools: quant strategy backtesting, arbitrage monitoring, trade analysis, position management.
- Security tools: credential auditing, injection defense.
- Data tools: statistical analysis, regression modeling.
- Communication tools: notifications, scheduling, reminders.

#### Skills Scenario Matter

- **Domains map directly to skills** — each of the 8 domains could be a TINYCUA `Skill`:
  - `skill_workflow`, `skill_sysops`, `skill_knowledge`, `skill_finance`
  - `skill_data_analysis`, `skill_security`, `skill_communication`, `skill_research`
- The skills provide system-prompt context that helps the LLM use tools correctly for each domain.

#### Integration Steps

```
1. Implement domain tool packages:
   - tinycua-tools/finance/
   - tinycua-tools/security/
   - tinycua-tools/data/
   - tinycua-tools/comms/

2. Implement KnowledgeBase tool (memory gap)

3. Create adapter (follows QwenClawBench's PinchBench-based format)

4. Enable hybrid scoring mode
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Domain tools | ~800 | High |
| KnowledgeBase | ~500 | High |
| Adapter | ~200 | Medium |
| **Total** | **~1500** | |

---



### 9. Engram (`Ubundi/engram-benchmark`)

**Repo**: <https://github.com/Ubundi/engram-benchmark>
**Tasks**: 498 across 9 question types
**Scoring**: Memory-quality judge score (0-3), additional: grounded rate, hallucination rate, abstention rate
**Protocol**: Seed → Settle → Probe → Judge

#### Why wait

Engram tests **only memory** — it's the wrong benchmark for TINYCUA until a memory system is built. Without it, TINYCUA will score near 0 (baseline native memory scores 1.10/3.0 with 4% grounded, 64% abstention — and TINYCUA has less memory than even that baseline).

#### Memory Matter

- **THE entire benchmark.** Engram has zero value without a memory system.
- 498 tasks across 9 question types:
  - `multi-session` (79): Facts from multiple separate conversations
  - `temporal-reasoning` (78): Ordering and recency
  - `cross-agent-memory` (71): Knowledge shared across agent instances
  - `multi-hop-reasoning` (68): Connecting facts via intermediate entities
  - `recurring-pattern` (54): Conventions established across sessions
  - `knowledge-update` (53): Tracking how facts evolved
  - `single-session-user` (45): Direct recall of specifics
  - `single-session-assistant` (32): Recall of assistant's past statements
  - `fact-recall` (18): Direct single-fact retrieval

- **What's needed** (before Engram is viable):
  1. A persistence layer (SQLite or vector store) for conversation history
  2. Memory extraction pipeline (extract facts from conversations)
  3. Memory retrieval pipeline (semantic search over stored facts)
  4. Session-to-session state management
  5. Abstention mechanism (know when to say "I don't know" vs hallucinate)

#### Sessioning Matter

- **Critical.** Engram's Seed phase replays conversations into the agent, the Settle phase waits for indexing, then Probe phase asks questions in a **fresh session**.
- TINYCUA needs: multi-session management, session ID tracking, ability to "replay" old conversations.
- The `--agent-id` and `--condition` flags expect persistent agent identity across sessions.

#### Tool Calling Matter

- **Minimal.** Engram probes are simple Q&A against memory — no complex tool orchestration.
- The OpenClaw adapter (`openclaw` in Engram's CLI) runs `openclaw agent` commands — TINYCUA needs `tinycua agent` equivalent.

#### Skills Scenario Matter

- **Not relevant.** Skills don't affect memory performance.

#### Integration Steps

```
1. Build memory system first:
   - MemoryStore: SQLite-backed with vector search
   - Memory extractor: extracts facts from conversation traces
   - Memory retriever: semantic search over stored facts

2. Implement Engram adapter:
   - Adapter for TINYCUA CLI (--agent, --message, --session flags)
   - Supports Seed → Settle → Probe → Judge protocol
   - Reports metrics.json, run_metadata.json, etc.

3. Benchmark with baseline (no memory) → measure natural capability
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Memory system | ~1500 | Very High |
| Engram adapter | ~300 | Medium |
| **Total** | **~1800** | |

---



### 10. Hermes Agent Benchmarks (TB2 / TBLite / YC-Bench)

**Repos**: integrated into NousResearch/hermes-agent, Atropos framework
**Tasks**: TB2=89, TBLite=100, YC-Bench=long-horizon CEO sim
**Scoring**: TB2=test suite pass/fail, TBLite=binary pass/fail, YC-Bench=composite
**Infrastructure**: Atropos RL environment framework + Modal cloud sandboxes

#### Why wait

These benchmarks are deeply coupled to the Atropos/Hermes infrastructure. TINYCUA would need to either:
- (a) Implement the Atropos environment interface, or
- (b) Reimplement the task runners directly

Both are high-effort with limited marginal benefit over WildClawBench (which already targets the same capability space).

#### Memory Matter (by benchmark)

- **TB2/TBLite**: Minimal — single-task execution, no cross-task state.
- **YC-Bench**: Critical — hundreds of decision turns, long-term strategy maintenance. The agent must remember its startup strategy, financial position, employee status, and competitor analysis across the entire simulated year.

#### Sessioning Matter

- **TB2/TBLite**: None needed — each task is independent.
- **YC-Bench**: Required — the simulation spans an entire simulated year, with state changes at each turn. Session continuity is essential.

#### Tool Calling Matter

- **TB2/TBLite**: `terminal` + `file` tools only — straightforward. TINYCUA's existing tool infrastructure handles this.
- **YC-Bench**: `terminal` only (CLI-based simulation) — even simpler.

#### Skills Scenario Matter

- **Not relevant** for these benchmarks.

#### Integration Option A: Atropos Environment

```
1. Implement AtroposBaseEnv subclass for TINYCUA
   - setup(), get_next_item(), format_prompt(), compute_reward(), evaluate()
   - Point at tinycua-sdk instead of hermes-agent
   - Tool resolution: call get_tool_definitions() equivalent from TINYCUA

2. Register TB2/TBLite/YC-Bench task sets
   - Each task: load Docker image, run agent, run test suite

3. Wire into Atropos CLI (evaluate subcommand)
```

#### Integration Option B: Standalone Runner

```
1. Implement task runners inline:
   - Read TB2 task definitions
   - Launch Docker sandbox
   - Run tinycua CLI
   - Run test suite
   - Collect results
```

#### Estimated effort (either option)

| Component | Lines | Complexity |
|-----------|-------|------------|
| Atropos environment | ~500 | High |
| Task runners | ~400 | Medium |
| Docker sandbox management | ~300 | Medium |
| **Total** | **~1200** | |

---



### 11. Terminal-Bench 2.0 / 2.1 (`harbor-framework/terminal-bench-2`)

**Repos**: <https://github.com/harbor-framework/terminal-bench-2> (v2.0), <https://github.com/harbor-framework/terminal-bench-2-1> (v2.1)
**Tasks**: 89 (2.0), 26 fixed in 2.1
**Scoring**: Binary pass/fail via test suite, pass@k
**Infrastructure**: Docker containers via Harbor framework
**Harnesses**: Claude Code, Codex, OpenHands, Mini-SWE-Agent, Terminus 2, Gemini CLI, Qwen Coder, OpenCode

#### Why wait

Terminal-Bench tests pure terminal capability — shell commands, compilers, git, system administration. TINYCUA's differentiation (structured tool calling, skills, session management) doesn't show here because the benchmark only needs one tool: `execute_command(cmd)`. Any agent with shell access performs similarly.

It **overlaps significantly** with WildClawBench's "Code Intelligence" tasks (12/60 tasks) and Hermes TB2 (already in Tier 3). The marginal value is low unless Harbor ecosystem compatibility becomes a requirement.

#### Memory Matter

- **None needed.** Each task is a self-contained terminal session. Container state IS memory.
- TINYCUA's stateless Agent per task is ideal.

#### Sessioning Matter

- **None needed.** Each task = `spin_up_terminal()` → `agent.perform_task()` → `run_tests()` → `cleanup()`.
- Harbor manages full isolation (Docker network, filesystem, tmux session, output paths).

#### Tool Calling Matter

- **Single tool: shell execution.** No JSON schema, no tool dispatch, no structured outputs needed.
- TINYCUA's `@tool` decorator and `BaseLoop` are overkill here. A single `shell_exec(command: str) -> dict` is sufficient.
- The challenge is making TINYCUA work inside Harbor's `BaseInstalledAgent` or `BaseAgent` interface — not the tool complexity itself.

#### Skills Scenario Matter

- **Irrelevant.** Terminal-Bench tests raw system-call capability. Skill descriptions don't help an agent compile a kernel or reverse-engineer a binary.

#### Integration Options

**Option A: Harbor BaseInstalledAgent** (lowest effort)
```
1. Subclass BaseInstalledAgent
2. Install tinycua CLI into the task Docker container as a subprocess
3. Harbor invokes per task:
   tinycua run --instruction "compile linux kernel" --output-dir /results
4. Harbor runs test suite on final container state
```

**Option B: Harbor BaseAgent** (more control)
```
1. Subclass BaseAgent
2. Implement perform_task(terminal, instruction) → AgentResult
3. Use terminal.execute() for command I/O
4. TINYCUA's loop wraps reasoning around shell commands
```

**Option C: Direct Harbor CLI**
```
harbor run --dataset terminal-bench@2.0 --agent tinycua
# Requires registering tinycua in Harbor's agent registry
```

#### Estimated effort

| Component | Lines | Complexity |
|-----------|-------|------------|
| Harbor BaseInstalledAgent adapter | ~100 | Low |
| CLI --instruction flag | ~30 | Low |
| Shell execution tool | ~60 | Low (reuse from ClawBench) |
| **Total** | **~190** | |

---



## Comparative Summary

| Benchmark | Tasks | Effort | Evaluates | Memory Need | Session Need | Tools Need | Skills Need | Unique Value |
|-----------|-------|--------|-----------|-------------|--------------|------------|-------------|--------------|
| **WildClawBench** | 60 | 2400 | General-purpose agent capability across 6 real-world domains | Single session | None | High | Indirect | Harness-comparable, 4 rivals |
| **ClawEval** | 18 | 180 | Agent correctness on targeted capability probes | Minimal | Session wrapper | None | None | Fastest time-to-signal |
| **ClawBench** | 19 | 560 | Execution quality via 4-axis scoring (completion, trajectory, behavior, judge) | None | None | Low | None | Trace-based, lowest friction |
| **Claw-Eval** | 300 | 550 | Broad-domain task completion across general/multimodal/multi-turn splits | For multi_turn only | Session wrapper | Medium | Indirect | Broadest task coverage |
| **ClawProBench** | 102 | 750 | Skill composition via YAML-defined scenario profiles | None | None | Medium | Indirect | Good breadth, YAML format |
| **τ-bench** | ~200 | 290 | Policy adherence with simulated human users in domain workflows | Single session | Agent state interface | Low | Policy = Skill | Policy + simulated user |
| **ClawMark** | 100 | 1760 | Multi-day persistent task execution with exogenous state changes | Per-turn only | Task-level session | Very High | Direct | Most differentiated (multi-day) |
| **QwenClawBench** | 100 | 1500 | Infrastructure reliability with resumable runs and anomaly detection | For knowledge tasks | For workflow tasks | High | Direct | Mature infra (resumable) |
| **Engram** | 498 | 1800 | Long-term memory quality (recall, grounding, hallucination) | THE benchmark | Critical | None | None | Memory-only signal |
| **Hermes (TB2)** | 89 | 1200 | Terminal-based task execution via test suite pass/fail | None | None | Low | None | CLI gold standard |
| **Terminal-Bench** | 89 | 190 | Shell command capability in isolated Docker environments | None | None | Minimal | None | Harbor ecosystem |

## Recommended Rollout Sequence

```
Phase 1 (now):       WildClawBench                       → 60 tasks,  ~2400 lines
Phase 2 (next):      ClawEval                            → 18 tasks,  ~180 lines
Phase 3 (next):      ClawBench                           → 19 tasks,  ~560 lines
Phase 4 (medium):    Claw-Eval + ClawProBench + τ-bench  → ~600 tasks, ~1590 lines
Phase 5 (later):     ClawMark                            → 100 tasks, ~1760 lines
Phase 6 (maturity):  QwenClawBench + Engram              → Need memory system first
Phase 7 (optional):  Hermes (TB2) / Terminal-Bench       → Integrate if ecosystem demands it
```

## Implementation Prerequisites

### Common Across All Benchmarks

1. **Session wrapper** (~100 lines): `ConversationSession` holding `messages: list[dict]`, serializable to JSON. Required by ClawEval, Claw-Eval, ClawMark.

2. **Shell execution tool** (~60 lines): `@tool def shell_exec(command: str) -> dict`. Required by all benchmarks.

3. **File operations** (~80 lines): `read_file`, `write_file`, `list_directory`, `search_files`. Required by all benchmarks.

4. **Web search tool** (~80 lines): `@tool def web_search(query: str) -> list[dict]`. Required by WildClawBench, Claw-Eval, ClawMark.

### Benchmark-Specific Prerequisites

| Benchmark | Prerequisite | Effort |
|-----------|-------------|--------|
| WildClawBench | Full tool ecosystem (browser, email, video, git) | 2000 |
| ClawEval | CLI --message/--session flags | 40 |
| ClawBench | Trace JSONL generator | 80 |
| Claw-Eval | Domain tools (finance, comms) | 350 |
| ClawProBench | YAML scenario parser | 150 |
| **τ-bench** | **HalfDuplexAgent adapter + tool schema alignment** | **200** |
| ClawMark | 5 stateful service clients | 600 |
| QwenClawBench | KnowledgeBase tool, finance tools | 1300 |
| Engram | Full memory system | 1500 |
| Hermes (TB2) | Atropos environment adapter | 1200 |
| Terminal-Bench | Harbor BaseInstalledAgent adapter | 100 |

---

## Tool Schema Compatibility

All benchmarks listed here use OpenAI-compatible tool schemas:

```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What this tool does",
    "parameters": { /* JSON Schema */ }
  }
}
```

TINYCUA's `Tool.to_config()` outputs exactly this format:

```python
def to_config(self) -> dict[str, Any]:
    return {
        "type": "function",
        "name": self.name,
        "description": self.description,
        "parameters": self.parameters,
    }
```

**No schema translation layer is needed** — the format is identical across all benchmarks.
