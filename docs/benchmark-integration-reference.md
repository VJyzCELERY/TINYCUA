# TINYCUA Benchmark Tools Gap Analysis

> Per-benchmark analysis: what TINYCUA already has vs. what it still needs to implement, evaluated against current 7 native tools + Image tool.

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

**Purpose**: Measure agent proficiency in practical digital tasks — productivity, coding, social coordination, search, creative synthesis, safety. Most comprehensive real-world tool-use benchmark. Primary TINYCUA target.

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

**Still needed**:
- Harness adapter (~250 lines)
- Dockerfile (~40 lines)
- run.sh entry (~50 lines)
= **~340 lines. Zero new tools.**

---

### 2. ClawEval — 18 episodes, 7 suites

**Purpose**: Validate that agent tool-calling infrastructure works correctly — echo, JSON output, memory retention, async probes, reliability. NOT a capability benchmark. A soundness check.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Echo/PONG (LLM) | LLM itself | ✅ none |
| JSON structured output | `response_format` in LanguageModel config | ✅ none |
| CLI runner | `tinycua` CLI exists | `--message`, `--session` flags missing (~40 lines) |
| Session continuity | — | `ConversationSession` wrapper (~140 lines) |

**Still needed**:
- `--message` / `--session` CLI flags (~40 lines)
- `ConversationSession` wrapper (~140 lines)
= **~180 lines. Zero new tools.**

---

### 3. ClawBench — 19 curated tasks

**Purpose**: Signal-curated benchmark with 4-axis scoring (completion, trajectory, behavior, judge). Tests tool-use quality beyond pass/fail — how well the agent traverses solutions. Defines the Partner Trace Spec interchange format.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | `read_file`, `write_file` | ✅ none |
| Web search | `fetch_url` (Brave API) | ✅ none |
| Browser | `run_shell("chromium --headless --dump-dom <url>")` | ✅ none |
| Email (mock SMTP) | `run_python` + smtplib | ✅ none |
| Calendar (CalDAV) | `run_python` + caldav | ✅ none |
| Trace emission | `RunResult.trace` carries data | Partner Trace Spec JSONL adapter (~200 lines) |
| Schema alignment | `Tool.to_config()` = OpenAI-compatible | Need tool name mapping in harness adapter (~50 lines) |

**Still needed**:
- Partner Trace Spec JSONL adapter (~200 lines)
- Tool name mapping in harness adapter (~50 lines)
= **~250 lines. Zero new tools.**

---

### 4. Claw-Eval — 300 tasks, 3 splits

**Purpose**: 300 human-verified tasks across 9 domains (communication, finance, operations, etc.) with completion + safety + robustness scoring. Largest human-curated tool-use dataset. Includes multi-turn and multimodal splits.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| CSV parse / JSON transform | `run_python` + csv/json stdlib | ✅ none |
| PDF extract | `run_python` + PyMuPDF | ✅ none |
| Email send/read | `run_python` + smtplib/imaplib | ✅ none |
| Spreadsheet read/write | `run_python` + openpyxl | ✅ none |
| Stock price API | `fetch_url` (REST API) | ✅ none |

**Still needed**:
- Harness adapter (~250 lines)
- CLI `--session` flag for multi_turn split (~40 lines)
= **~290 lines. Zero new tools.**

---

### 5. ClawProBench — 102 tasks, 4 profiles

**Purpose**: Multi-profile benchmarking (core, intelligence, native, full) with 3-try runs and coverage summaries. Designed for YAML-defined scenarios — tests portability of agent configs across hardware/software stacks.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| Web search | `fetch_url` | ✅ none |
| YAML-defined tool profiles | — | YAML parser + tool name mapping (~400 lines) — uses same tools underneath |
| Profile runner | — | `--trials N`, summary output (~200 lines) |

**Still needed**:
- YAML parser + tool name mapping (~400 lines)
- Profile runner with `--trials N` and summary output (~200 lines)
= **~600 lines. Tool name mapping only — no new tool implementations.**

---

### 6. τ-bench — 200 tasks, 3 domains

**Purpose**: Tests policy adherence under a simulated human user. Unique among benchmarks — agent must follow domain policies (retail, airline, banking) while interacting with an LLM-simulated customer in multi-turn conversations. Cited in model cards from Anthropic, OpenAI, Google.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Domain REST tools (search_products, book_flight, etc.) | `fetch_url` for HTTP, `run_python` for logic | Need exact schema match for τ-bench's predefined tool set (~150 lines for tool wrappers) |
| Policy adherence | `Skill(name, desc, instructions)` | Policy text injection as Skill — 1:1 fit ✅ |
| Loop inversion (per-turn) | `BaseLoop` drives full conversation | `HalfDuplexAgent` adapter slicing `run()` into per-turn calls (~120 lines) |
| τ³ BM25 retrieval | — | Adapter for τ³ knowledge retrieval (~100 lines) |

**Still needed**:
- Domain tool wrappers for exact τ-bench schema match (~150 lines)
- `HalfDuplexAgent` adapter slicing `run()` into per-turn calls (~120 lines)
- τ³ BM25 retrieval adapter (~100 lines)
= **~370 lines.**

---

### 7. ClawMark — 100 tasks, 13 domains, 5 services

**Purpose**: Multi-day professional task benchmark with 1,537 fully deterministic checkers (no LLM judge). Unique for exogenous state changes between turns — tests agent's ability to detect silent changes across simulated workdays. Highest bar for robust session management.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Filesystem read/write/list | `read_file`, `write_file`, `list_files` | ✅ none |
| Email (GreenMail SMTP/IMAP) | `run_python` + smtplib/imaplib | ✅ none |
| Calendar (Radicale CalDAV) | `run_python` + caldav | ✅ none |
| Notion mock (HTTP API) | `fetch_url` | ✅ none |
| Sheets mock (HTTP API) | `fetch_url` | ✅ none |
| Docker Compose integration | — | Agent joining `clawmark` network (~60 lines) |
| Multimodal artifacts (PDF, image, audio, video) | `run_python` + PyMuPDF/PIL, `run_shell` + ffmpeg | ✅ none |
| Task-level session | — | `ClawMarkTaskSession` managing inter-turn state (~200 lines) |
| Silent-change detection | — | Prompt engineering in system message (~20 lines) |

**Still needed**:
- Docker Compose network integration (~60 lines)
- `ClawMarkTaskSession` for inter-turn state (~200 lines)
- Silent-change detection prompt (~20 lines)
= **~280 lines. Zero new tools.** (All service operations composable from existing tools.)

---

### 8. QwenClawBench — 100 tasks, 8 domains

**Purpose**: Breadth benchmark across 8 domains (workflow, sysops, knowledge, finance, data, security, comms, research) with hybrid automated + LLM-judge scoring. Strength is infrastructure reliability (anomaly detection, resumable runs). Overlaps heavily with WildClawBench and ClawMark.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Shell execution | `run_shell` | ✅ none |
| File read/write | file tools | ✅ none |
| Web search | `fetch_url` (Brave API) | ✅ none |
| Finance tools (backtesting, arbitrage, analysis) | `run_python` + pandas/numpy, `fetch_url` for APIs | ✅ none (composable) |
| Security tools (credential audit, injection defense) | `run_shell`, `run_python` | ✅ none (composable) |
| Data tools (statistics, regression) | `run_python` + scipy/sklearn | ✅ none (composable) |
| Communication (notifications, reminders) | `run_python` | ✅ none (composable) |
| Knowledge base / vector store | — | **Memory system needed** for 15/100 tasks (knowledge domain) — not a tool gap |
| Workflow sessions | — | Session continuity for 21/100 workflow tasks |

**Still needed**:
- Harness adapter (~200 lines)
- Knowledge base / vector store for 15/100 knowledge-domain tasks (~500+ lines — memory gap, not tool gap)
= **~200 lines for harness. New tool count: 0.**

---

### 9. Engram — 498 tasks, memory benchmark

**Purpose**: Measures agent memory quality — nothing else. 498 tasks across 9 question types testing fact recall, temporal reasoning, cross-agent memory, multi-session knowledge. Wrong benchmark until TINYCUA has a working memory system. Baseline TINYCUA would score near 0.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Simple Q&A | LLM itself | ✅ none |
| Memory extraction | — | Full memory system needed (persistence + extraction + retrieval + abstention) |
| Multi-session management | — | `--agent-id`, session ID tracking, Seed→Settle→Probe→Judge protocol |
| `tinycua agent` CLI | `tinycua` CLI exists | `--agent-id`, `--condition` flags missing (~40 lines) |

**Still needed**:
- Memory persistence layer (SQLite or vector store)
- Memory extraction pipeline (facts from conversations)
- Memory retrieval pipeline (semantic search)
- Abstention mechanism (when to say "I don't know")
- Multi-session management (Seed→Settle→Probe→Judge protocol)
- `--agent-id`, `--condition` CLI flags (~40 lines)
= **~1800 lines total. This is a memory infrastructure gap, not a tool gap. Tools are almost irrelevant here.**

---

### 10. Hermes Agent (TB2 / TBLite / YC-Bench)

**Purpose**: Terminal-based benchmarks from NousResearch's Hermes Agent. TB2 (89 tasks) and TBLite (100 tasks) test CLI tool-use. YC-Bench is a long-horizon CEO simulation. Deeply coupled to Atropos RL framework — high integration effort for limited marginal benefit over WildClawBench.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| Terminal execution | `run_shell` | ✅ none |
| File operations | `read_file`, `write_file`, `edit_file`, `list_files` | ✅ none |
| Atropos `BaseEnv` interface | — | Adapter wrapping TINYCUA as Hermes agent (~400 lines) OR standalone runner (~400 lines) |

**Still needed**:
- Atropos `BaseEnv` adapter OR standalone Docker task runner (~400 lines)
= **~400 lines. Zero new tools.** (Overlaps with WildClawBench's Code Intelligence category — redundant effort.)

---

### 11. Terminal-Bench 2.0 / 2.1 — 89 tasks

**Purpose**: Pure terminal capability benchmark — shell commands, compilers, git, system administration. Binary pass/fail. Only one tool needed (`execute_command`). Harnesses include Claude Code, Codex, OpenHands, Gemini CLI. Lowest integration effort on this list.

| Benchmark needs | TINYCUA has | Gap |
|----------------|-------------|-----|
| `execute_command(cmd)` | `run_shell` | ✅ none |
| Harbor `BaseInstalledAgent` interface | — | Harbor adapter (~100 lines) |
| `--instruction` CLI flag | — | ~30 lines |

**Still needed**:
- Harbor `BaseInstalledAgent` adapter (~100 lines)
- `--instruction` CLI flag (~30 lines)
= **~130 lines. Zero new tools.** (Simplest integration of all benchmarks — single tool needed, TINYCUA has it.)

---

## Summary

| # | Benchmark | Purpose | Tools gap | Still need to build | Est. lines | Priority lock |
|---|-----------|---------|-----------|---------------------|-----------|---------------|
| 1 | **WildClawBench** | Real-world tool use (60 tasks, 6 categories) | 0 | • Harness adapter<br>• Dockerfile<br>• run.sh entry | ~340 | Primary target |
| 2 | **ClawEval** | Infrastructure soundness check | 0 | • `--message`/`--session` flags<br>• Session wrapper | ~180 | Needs session |
| 3 | **ClawBench** | Signal-curated tool-use quality | 0 | • Trace adapter<br>• Tool name mapping | ~250 | WildClawBench overlap |
| 4 | **Claw-Eval** | 300 human-verified domain tasks | 0 | • Harness adapter<br>• CLI `--session` flag | ~290 | WildClawBench overlap |
| 5 | **ClawProBench** | Multi-profile YAML-defined scenarios | 0 | • YAML parser + tool mapping<br>• Profile runner | ~600 | WildClawBench overlap |
| 6 | **τ-bench** | Policy adherence with simulated user | 0 | • Domain tool wrappers<br>• HalfDuplexAgent adapter | ~370 | WildClawBench overlap |
| 7 | **ClawMark** | Multi-day tasks, silent state changes | 0 | • Docker Compose<br>• Task session | ~280 | WildClawBench overlap |
| 8 | **QwenClawBench** | 8-domain breadth benchmark | 0 | • Harness adapter<br>• Memory for knowledge tasks | ~200 (+500) | Needs memory |
| 9 | **Engram** | Memory quality (498 tasks) | 0 | • Full memory system | ~1800 | Needs memory |
| 10 | **Hermes (TB2/TBLite/YC)** | Terminal + long-horizon CEO sim | 0 | • Atropos adapter or standalone runner | ~400 | WildClawBench overlap |
| 11 | **Terminal-Bench** | Pure terminal capability | 0 | • Harbor adapter<br>• `--instruction` flag | ~130 | WildClawBench overlap |

**Key finding**: Zero benchmarks require new tool implementations that can't be composed from TINYCUA's 7 existing tools + Image tool. Every integration is a harness/adapter problem, not a tool capability problem. The two genuine blockers are:
- **Session infrastructure** (ClawEval, Claw-Eval multi_turn, ClawMark, QwenClawBench workflows) — ~200 lines of session wrapper
- **Memory infrastructure** (Engram, QwenClawBench knowledge) — ~1800 lines of full memory system
