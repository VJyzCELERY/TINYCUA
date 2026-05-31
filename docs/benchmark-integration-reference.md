# TINYCUA Benchmark Tools Gap Analysis

> Per-benchmark analysis: what TINYCUA already has vs. what it still needs for **local evaluation** (testing TINYCUA's own capabilities). NOT about leaderboard submission — harness adapter, Dockerfile, and `run.sh` are only needed for official WildClawBench leaderboard participation, not for running evaluations locally.

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

**Still needed (local eval)**:
- Task reader: reads task YAML + Markdown → calls `Agent.run()` (~50-100 lines)
- Grader invocation: feeds agent output to WildClawBench grader scripts (already in their repo)
= **~50-100 lines. Zero new tools.**

> Leaderboard submission would additionally need: harness adapter, Dockerfile, run.sh entry (~340 lines) — skip these for local eval.

---

### 2. ClawEval — 18 episodes, 7 suites

**Purpose**: Validate that agent tool-calling infrastructure works correctly — echo, JSON output, memory retention, async probes, reliability. NOT a capability benchmark. A soundness check.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Echo/PONG (LLM) | LLM itself | ✅ none |
| JSON structured output | `response_format` in LanguageModel config | ✅ none |
| CLI runner | `tinycua` CLI exists | `--message`, `--session` flags missing (~40 lines) |
| Session continuity | — | `ConversationSession` wrapper (~140 lines) |

**Still needed (local eval)**:
- `--message` / `--session` CLI flags (~40 lines)
- `ConversationSession` wrapper (~140 lines)
= **~180 lines. Zero new tools.**

---

### 3. ClawBench — 19 curated tasks

**Purpose**: Signal-curated benchmark with 4-axis scoring (completion, trajectory, behavior, judge). Tests tool-use quality beyond pass/fail.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | `read_file`, `write_file` | ✅ none |
| Web search | `fetch_url` (Brave API) | ✅ none |
| Browser | `run_shell("chromium --headless --dump-dom <url>")` | ✅ none |
| Email (mock SMTP) | `run_python` + smtplib | ✅ none |
| Calendar (CalDAV) | `run_python` + caldav | ✅ none |
| Trace emission | `RunResult.trace` carries data | Partner Trace Spec only needed for leaderboard submission |
| Schema alignment | `Tool.to_config()` = OpenAI-compatible | ✅ none for local eval |

**Still needed (local eval)**:
- Task runner: reads ClawBench tasks, maps tool names, calls `Agent.run()`, collects results (~100 lines)
= **~100 lines. Zero new tools.**

> Leaderboard submission would additionally need: Partner Trace Spec JSONL adapter (~250 lines) — skip for local eval.

---

### 4. Claw-Eval — 300 tasks, 3 splits

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

**Still needed (local eval)**:
- Eval script: reads Claw-Eval tasks, invokes agent, calls their Python graders (~150 lines)
- CLI `--session` flag for multi_turn split (~40 lines)
= **~190 lines. Zero new tools.**

---

### 5. ClawProBench — 102 tasks, 4 profiles

**Purpose**: Multi-profile benchmarking (core, intelligence, native, full) with 3-try runs and coverage summaries. YAML-defined scenarios.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| Web search | `fetch_url` | ✅ none |
| YAML-defined tool profiles | — | YAML parser + tool name mapping (~400 lines) — uses same tools underneath |
| Profile runner | — | `--trials N`, summary output (~200 lines) |

**Still needed (local eval)**:
- YAML parser + tool name mapping (~400 lines)
- Profile runner with `--trials N` and summary output (~200 lines)
= **~600 lines. Zero new tools** — same tools underneath, just name mapping.

---

### 6. τ-bench — 200 tasks, 3 domains

**Purpose**: Tests policy adherence under a simulated human user. Agent must follow domain policies (retail, airline, banking) while interacting with an LLM-simulated customer. Cited in model cards from Anthropic, OpenAI, Google.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Domain REST tools (search_products, book_flight, etc.) | `fetch_url` for HTTP, `run_python` for logic | Need exact schema match for τ-bench's predefined tool set (~150 lines for tool wrappers) |
| Policy adherence | `Skill(name, desc, instructions)` | Policy text injection as Skill — 1:1 fit ✅ |
| Loop inversion (per-turn) | `BaseLoop` drives full conversation | `HalfDuplexAgent` adapter slicing `run()` into per-turn calls (~120 lines) |
| τ³ BM25 retrieval | — | Adapter for τ³ knowledge retrieval (~100 lines) |

**Still needed (local eval)**:
- Domain tool wrappers for exact τ-bench schema match (~150 lines)
- `HalfDuplexAgent` adapter slicing `run()` into per-turn calls (~120 lines)
- τ³ BM25 retrieval adapter (~100 lines)
= **~370 lines.**

---

### 7. ClawMark — 100 tasks, 13 domains, 5 services

**Purpose**: Multi-day professional task benchmark with 1,537 fully deterministic checkers (no LLM judge). Unique for exogenous state changes between turns — tests agent's ability to detect silent changes across simulated workdays.

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

**Still needed (local eval)**:
- Docker Compose network integration (~60 lines) — **required even for local eval** (GreenMail, Radicale, etc. are Docker services)
- `ClawMarkTaskSession` for inter-turn state (~200 lines)
- Silent-change detection prompt (~20 lines)
= **~280 lines. Zero new tools.**

---

### 8. QwenClawBench — 100 tasks, 8 domains

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

**Still needed (local eval)**:
- Task runner (~150 lines)
- Memory system for 15 knowledge tasks (~500+ lines — not a tool gap)
= **~150 lines for local eval. Zero new tools.**

---

### 9. Engram — 498 tasks, memory benchmark

**Purpose**: Measures agent memory quality — nothing else. 498 tasks across 9 question types testing fact recall, temporal reasoning, cross-agent memory. Wrong benchmark until TINYCUA has a working memory system.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Simple Q&A | LLM itself | ✅ none |
| Memory extraction | — | Full memory system (persistence + extraction + retrieval + abstention) |
| Multi-session management | — | Seed→Settle→Probe→Judge protocol, `--agent-id` flag |

**Still needed (local eval)**:
- Full memory system (SQLite/vector store, extraction pipeline, retrieval pipeline, abstention)
- `--agent-id`, `--condition` CLI flags (~40 lines)
= **~1800 lines. Memory infrastructure gap, not a tool gap. Tools are irrelevant.**

---

### 10. Hermes Agent (TB2 / TBLite / YC-Bench)

**Purpose**: Terminal-based benchmarks from NousResearch. TB2 (89 tasks) and TBLite (100 tasks) test CLI tool-use. YC-Bench is a long-horizon CEO simulation. Deeply coupled to Atropos RL framework.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Terminal execution | `run_shell` | ✅ none |
| File operations | `read_file`, `write_file`, `edit_file`, `list_files` | ✅ none |
| Task runner | — | Standalone script reading TB2/TBLite task definitions (~300 lines) |

**Still needed (local eval)**:
- Standalone task runner reading TB2/TBLite tasks, launching agent, running test suites (~300 lines)
= **~300 lines. Zero new tools.**

---

### 11. Terminal-Bench 2.0 / 2.1 — 89 tasks

**Purpose**: Pure terminal capability — shell commands, compilers, git, system administration. Binary pass/fail. Only one tool needed.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| `execute_command(cmd)` | `run_shell` | ✅ none |
| Task definition reader | — | Script that reads tasks and invokes agent (~80 lines) |
| `--instruction` CLI flag | — | ~30 lines |

**Still needed (local eval)**:
- Task reader script (~80 lines)
- `--instruction` CLI flag (~30 lines)
= **~110 lines. Zero new tools.**

---

## Summary

| # | Benchmark | Purpose | Tools gap | Locally needed | Est. lines | Real blocker |
|---|-----------|---------|-----------|----------------|-----------|-------------|
| 1 | **WildClawBench** | Real-world tool use | 0 | Task reader + grader caller | ~50-100 | None |
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

The shortest path to a working eval: **WildClawBench** (~50-100 lines for a task reader + grader caller).
