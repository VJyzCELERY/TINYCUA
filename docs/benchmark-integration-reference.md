# TINYCUA Benchmark Tools Gap Analysis

> Per-benchmark analysis: what TINYCUA already has vs. what it still needs for **local evaluation** (testing TINYCUA's own capabilities). NOT about leaderboard submission — harness adapter, Dockerfile, and `run.sh` are only needed for official leaderboard participation, not for running evaluations locally.

---

## TINYCUA Current Tool Arsenal (PR #62)

| Tool | Capability |
|------|-----------|
| `run_shell(command)` | Any CLI — git, ffmpeg, headless browser, process mgmt |
| `read_file(path)` | All file reading |
| `write_file(path, content)` | All file writing |
| `edit_file(path, old, new)` | All file editing |
| `list_files(path, pattern)` | All directory listing |
| `fetch_url(url, method, headers)` | HTTP — web search via Brave API, REST APIs |
| `run_python(code)` | Any Python — smtplib (email), caldav (calendar), PIL (image) |
| Image tool | Image analysis (user-provided) |

---

## Gap Analysis

### 1. WildClawBench — 60 tasks, 6 categories

**Repo**: <https://github.com/InternLM/WildClawBench>
**Purpose**: Measure agent proficiency in practical digital tasks — productivity, coding, social coordination, search, creative synthesis, safety. Primary TINYCUA target.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write/edit | `read_file`, `write_file`, `edit_file` | ✅ none |
| Web search/browse | `fetch_url` (Brave API), `run_shell` (headless Chromium) | ✅ none |
| Git operations | `run_shell("git <args>")` | ✅ none |
| Video/audio processing | `run_shell("ffmpeg <args>")` | ✅ none |
| Email (GreenMail) | `run_python` + smtplib/imaplib | ✅ none |
| Calendar (CalDAV) | `run_python` + caldav | ✅ none |
| Image analysis | Image tool / `run_python` + PIL | ✅ none |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Task reader | ~50-100 | Reads task YAML + Markdown, registers 7 tools, calls `Agent.run()` — need to translate OpenClaw tool names to TINYCUA tools |
| Grader invocation | ~10 | Feeds agent output to WildClawBench grader scripts (already in their repo) — they produce the score |
| = **~60-110 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

| What | Lines | Why |
|------|-------|-----|
| Harness adapter | ~250 | Wraps TINYCUA in WildClawBench runner interface so it runs alongside OpenClaw/Claude Code/Codex/Hermes in their CI |
| Dockerfile | ~40 | Packages TINYCUA CLI + deps into `wildclawbench-tinycua` image — required by their per-harness Docker setup |
| `run.sh` entry | ~50 | Registers `tinycua` case in their shell script so runner can discover and invoke it |
| = **~340 additional lines** | | |

---

### 2. ClawEval — 18 episodes, 7 suites

**Repo**: <https://github.com/clark-labs-inc/claweval>
**Purpose**: Validate that agent tool-calling infrastructure works correctly — echo, JSON output, memory retention, async probes, reliability. NOT a capability benchmark. A soundness check.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Echo/PONG (LLM) | LLM itself | ✅ none |
| JSON structured output | `response_format` in LanguageModel config | ✅ none |
| CLI runner | `tinycua` CLI exists | `--message`, `--session` flags missing (~40 lines) |
| Session continuity | — | `ConversationSession` wrapper (~140 lines) |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| `--message` CLI flag | ~20 | ClawEval sends task prompt via CLI arg — TINYCUA needs `--message "do X"` to accept it |
| `--session` CLI flag | ~20 | ClawEval runs multi-turn episodes — agent must remember previous turns in same session |
| `ConversationSession` wrapper | ~140 | Persists conversation history between `Agent.run()` calls so memory-retention episodes work |
| = **~180 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

*(ClawEval has no formal leaderboard — Rust binary CLI, no Docker harness requirement.)*

---

### 3. ClawBench — 19 curated tasks

**Repo**: <https://github.com/openclaw/clawbench>
**Purpose**: Signal-curated benchmark with 4-axis scoring (completion, trajectory, behavior, judge). Tests tool-use quality beyond pass/fail.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | `read_file`, `write_file` | ✅ none |
| Web search | `fetch_url` (Brave API) | ✅ none |
| Browser | `run_shell("chromium --headless --dump-dom <url>")` | ✅ none |
| Email (mock SMTP) | `run_python` + smtplib | ✅ none |
| Calendar (CalDAV) | `run_python` + caldav | ✅ none |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Task runner | ~100 | Reads ClawBench tasks, maps tool names to TINYCUA implementations, calls `Agent.run()`, collects results for scoring |
| = **~100 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

| What | Lines | Why |
|------|-------|-----|
| Partner Trace Spec JSONL adapter | ~200 | ClawBench requires emission of standard trace format — needed for their scoring pipeline to compute trajectory/behavior axes |
| Tool name mapping | ~50 | Ensures TINYCUA's tool schemas match OpenClaw's exactly — needed for apples-to-apples comparison |
| = **~250 additional lines** | | |

---

### 4. Claw-Eval — 300 tasks, 3 splits

**Repo**: <https://github.com/claw-eval/claw-eval>
**Purpose**: 300 human-verified tasks across 9 domains (communication, finance, operations, etc.) with completion + safety + robustness scoring. Largest human-curated tool-use dataset.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| CSV parse / JSON transform | `run_python` + csv/json stdlib | ✅ none |
| PDF extract | `run_python` + PyMuPDF | ✅ none |
| Email send/read | `run_python` + smtplib/imaplib | ✅ none |
| Spreadsheet read/write | `run_python` + openpyxl | ✅ none |
| Stock price API | `fetch_url` (REST API) | ✅ none |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Eval script | ~150 | Reads Claw-Eval tasks, invokes agent, calls their Python graders — same ecosystem (Python) makes this trivial |
| CLI `--session` flag | ~40 | Needed for multi_turn split (38 tasks) where agent must remember context across turns |
| = **~190 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

| What | Lines | Why |
|------|-------|-----|
| Submission format adapter | ~100 | Claw-Eval has its own output format for leaderboard comparison |
| = **~100 additional lines** | | |

---

### 5. ClawProBench — 102 tasks, 4 profiles

**Repo**: <https://github.com/suyoumo/ClawProBench>
**Purpose**: Multi-profile benchmarking (core, intelligence, native, full) with 3-try runs and coverage summaries. YAML-defined scenarios — tests portability of agent configs across hardware/software stacks.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| Web search | `fetch_url` | ✅ none |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| YAML parser + tool name mapping | ~400 | ClawProBench defines tool profiles in YAML — need to parse scenarios and map profile tool names to TINYCUA tools (same tools underneath, different names) |
| Profile runner | ~200 | Supports `--trials N`, `--continue`, generates avg/max/coverage summaries per profile |
| = **~600 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

*(ClawProBench has no formal leaderboard — runs via OpenClaw CLI locally.)*

---

### 6. τ-bench — 200 tasks, 3 domains

**Repo**: <https://github.com/sierra-research/tau2-bench>
**Purpose**: Tests policy adherence under a simulated human user. Unique — agent must follow domain policies (retail, airline, banking) while interacting with an LLM-simulated customer. Cited in model cards from Anthropic, OpenAI, Google.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Domain REST tools (search_products, book_flight, etc.) | `fetch_url` for HTTP, `run_python` for logic | Need exact schema match for τ-bench's predefined tool set (~150 lines for tool wrappers) |
| Policy adherence | `Skill(name, desc, instructions)` | Policy text injection as Skill — 1:1 fit ✅ |
| Loop inversion (per-turn) | `BaseLoop` drives full conversation | `HalfDuplexAgent` adapter slicing `run()` into per-turn calls (~120 lines) |
| τ³ BM25 retrieval | — | Adapter for τ³ knowledge retrieval (~100 lines) |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Domain tool wrappers | ~150 | τ-bench defines exact tool schemas (search_products, book_flight, etc.) — must match name, params, return types exactly for the simulated environment to work |
| `HalfDuplexAgent` adapter | ~120 | τ-bench's orchestrator drives the loop per-turn (not TINYCUA's BaseLoop) — need to slice `Agent.run()` into turn-by-turn calls |
| τ³ BM25 retrieval | ~100 | τ³ adds knowledge domain with BM25 retrieval — adapter needed to plug TINYCUA into their retriever interface |
| = **~370 lines.** | | |

#### Still needed — Leaderboard submission

| What | Lines | Why |
|------|-------|-----|
| τ-bench agent registration | ~50 | Register TINYCUA as a named agent in τ-bench's runner for official comparison |
| = **~50 additional lines** | | |

---

### 7. ClawMark — 100 tasks, 13 domains, 5 services

**Repo**: <https://github.com/evolvent-ai/ClawMark>
**Purpose**: Multi-day professional task benchmark with 1,537 fully deterministic checkers (no LLM judge). Unique for exogenous state changes between turns — tests agent's ability to detect silent changes across simulated workdays. Highest bar for robust session management.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Filesystem read/write/list | `read_file`, `write_file`, `list_files` | ✅ none |
| Email (GreenMail SMTP/IMAP) | `run_python` + smtplib/imaplib | ✅ none |
| Calendar (Radicale CalDAV) | `run_python` + caldav | ✅ none |
| Notion mock (HTTP API) | `fetch_url` | ✅ none |
| Sheets mock (HTTP API) | `fetch_url` | ✅ none |
| Docker Compose infrastructure | — | Must join `clawmark` network with 5 stateful services (~60 lines) |
| Multimodal artifacts (PDF, image, audio, video) | `run_python` + PyMuPDF/PIL, `run_shell` + ffmpeg | ✅ none |
| Task-level session | — | `ClawMarkTaskSession` managing inter-turn state (~200 lines) |
| Silent-change detection | — | Prompt engineering in system message (~20 lines) |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Docker Compose network integration | ~60 | ClawMark runs 5 Docker services (GreenMail, Radicale, Notion mock, Sheets mock, filesystem) — agent container must join their network to access them |
| `ClawMarkTaskSession` | ~200 | Multi-day simulation: task_id, current_stage, accumulated messages across 2-6 turns — needed for stage-wise instruction injection |
| Silent-change detection prompt | ~20 | 56.5% fail rate on silent changes — agent needs explicit instruction: "identify what changed since yesterday" |
| = **~280 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

*(ClawMark has no formal leaderboard — runs via Docker Compose locally.)*

---

### 8. QwenClawBench — 100 tasks, 8 domains

**Repo**: <https://github.com/SKYLENAGE-AI/QwenClawBench>
**Purpose**: Breadth benchmark across 8 domains (workflow, sysops, knowledge, finance, data, security, comms, research) with hybrid automated + LLM-judge scoring. Overlaps heavily with WildClawBench and ClawMark.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| Web search | `fetch_url` (Brave API) | ✅ none |
| Finance tools (backtesting, arbitrage, analysis) | `run_python` + pandas/numpy, `fetch_url` for APIs | ✅ none (composable) |
| Security tools (credential audit, injection defense) | `run_shell`, `run_python` | ✅ none (composable) |
| Data tools (statistics, regression) | `run_python` + scipy/sklearn | ✅ none (composable) |
| Communication (notifications, reminders) | `run_python` | ✅ none (composable) |
| Knowledge base / vector store | — | **Memory system** for 15/100 knowledge-domain tasks — not a tool gap |
| Workflow sessions | — | Session continuity for 21/100 workflow tasks |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Task runner | ~150 | Reads tasks, invokes agent, calls hybrid scorer (automated + LLM judge) |
| Memory system (knowledge domain) | ~500+ | 15/100 tasks need persistent knowledge — vector store or RAG pipeline. Not a tool gap |
| = **~150 lines. Zero new tools.** (+500 when memory system is built) | | |

#### Still needed — Leaderboard submission

*(QwenClawBench has no formal leaderboard — runs via PinchBench-based adapter locally.)*

---

### 9. Engram — 498 tasks, memory benchmark

**Repo**: <https://github.com/Ubundi/engram-benchmark>
**Purpose**: Measures agent memory quality — nothing else. 498 tasks across 9 question types testing fact recall, temporal reasoning, cross-agent memory, multi-session knowledge. Wrong benchmark until TINYCUA has a working memory system. Baseline TINYCUA would score near 0.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Simple Q&A | LLM itself | ✅ none |
| Memory extraction | — | Full memory system (persistence + extraction + retrieval + abstention) |
| Multi-session management | — | Seed→Settle→Probe→Judge protocol, `--agent-id` flag |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Memory persistence layer | ~300 | SQLite or vector store to hold conversation history across sessions |
| Memory extraction pipeline | ~500 | Extract facts/concepts from conversation turns and store them |
| Memory retrieval pipeline | ~500 | Semantic search over stored facts to answer probes |
| Abstention mechanism | ~200 | Know when to say "I don't know" instead of hallucinating — critical for grounded rate |
| Multi-session management | ~200 | Seed→Settle→Probe→Judge protocol: replay conversations, wait for indexing, probe in fresh session |
| `--agent-id`, `--condition` CLI flags | ~40 | Engram expects persistent agent identity across sessions for cross-agent memory tests |
| = **~1800 lines. Memory infrastructure — not a tool gap.** | | |

#### Still needed — Leaderboard submission

*(Engram has no formal leaderboard — runs locally via OpenClaw CLI adapter.)*

---

### 10. Hermes Agent (TB2 / TBLite / YC-Bench)

**Repo**: Integrated into NousResearch/hermes-agent, Atropos framework
**Purpose**: Terminal-based benchmarks from NousResearch. TB2 (89 tasks) and TBLite (100 tasks) test CLI tool-use. YC-Bench is a long-horizon CEO simulation. Deeply coupled to Atropos RL framework — high integration effort for limited marginal benefit over WildClawBench.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Terminal execution | `run_shell` | ✅ none |
| File operations | `read_file`, `write_file`, `edit_file`, `list_files` | ✅ none |
| Task runner | — | Standalone script reading TB2/TBLite task definitions (~300 lines) |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Standalone task runner | ~300 | Reads TB2/TBLite task definitions, launches Docker sandbox, runs TINYCUA CLI, runs test suites, collects pass/fail. Overlaps with WildClawBench Code Intelligence category |
| = **~300 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

*(Hermes benchmarks are internal to NousResearch — no public leaderboard for TINYCUA to submit to.)*

---

### 11. Terminal-Bench 2.0 / 2.1 — 89 tasks

**Repo**: <https://github.com/harbor-framework/terminal-bench-2> (2.0), <https://github.com/harbor-framework/terminal-bench-2-1> (2.1)
**Purpose**: Pure terminal capability — shell commands, compilers, git, system administration. Binary pass/fail. Only one tool needed. Simplest integration on this list.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| `execute_command(cmd)` | `run_shell` | ✅ none |
| Task definition reader | — | Script that reads tasks and invokes agent (~80 lines) |
| `--instruction` CLI flag | — | ~30 lines |

#### Still needed — Local evaluation

| What | Lines | Why |
|------|-------|-----|
| Task reader script | ~80 | Reads Terminal-Bench tasks (JSON/YAML), invokes TINYCUA via CLI, captures stdout for test suite evaluation |
| `--instruction` CLI flag | ~30 | Terminal-Bench supplies task instruction as CLI arg — need `tinycua --instruction "compile linux kernel" --output-dir /results` |
| = **~110 lines. Zero new tools.** | | |

#### Still needed — Leaderboard submission

| What | Lines | Why |
|------|-------|-----|
| Harbor `BaseInstalledAgent` adapter | ~100 | Terminal-Bench uses Harbor framework — adapter installs TINYCUA CLI in Docker and invokes it as a subprocess. Needed for official comparison against Claude Code, Codex, OpenHands, etc. |
| = **~100 additional lines** | | |

---

## Summary

| # | Benchmark | Purpose | Tools gap | Locally needed | Est. lines | Real blocker |
|---|-----------|---------|-----------|----------------|-----------|-------------|
| 1 | **WildClawBench** | Real-world tool use | 0 | Task reader + grader caller | ~60-110 | None |
| 2 | **ClawEval** | Infrastructure soundness | 0 | CLI flags + session wrapper | ~180 | Session |
| 3 | **ClawBench** | Tool-use quality | 0 | Task runner | ~100 | None |
| 4 | **Claw-Eval** | 300 domain tasks | 0 | Eval script + session flag | ~190 | Session |
| 5 | **ClawProBench** | YAML scenarios | 0 | YAML parser + profile runner | ~600 | None |
| 6 | **τ-bench** | Policy + simulated user | 0 | Tool wrappers + agent adapter | ~370 | Loop inversion |
| 7 | **ClawMark** | Multi-day silent changes | 0 | Docker Compose + task session | ~280 | Session + Docker |
| 8 | **QwenClawBench** | 8-domain breadth | 0 | Task runner + memory | ~150 (+500) | Memory |
| 9 | **Engram** | Memory quality | 0 | Full memory system | ~1800 | Memory |
| 10 | **Hermes** | Terminal + CEO sim | 0 | Standalone task runner | ~300 | None |
| 11 | **Terminal-Bench** | Pure terminal | 0 | Task reader + `--instruction` | ~110 | None |

**Key finding**: Zero benchmarks need new tool implementations. The 7 existing tools + Image tool compose everything. Every integration is either:
- **Trivial** (task reader only): WildClawBench, ClawBench, Claw-Eval, ClawProBench, Hermes, Terminal-Bench
- **Needs session wrapper** (~200 lines): ClawEval, Claw-Eval multi_turn, ClawMark
- **Needs memory system** (~1800 lines): Engram, QwenClawBench knowledge domain
- **Special cases**: τ-bench (loop inversion), ClawMark (Docker Compose)

The shortest path to a working eval: **WildClawBench** (~60-110 lines for a task reader + grader caller).
