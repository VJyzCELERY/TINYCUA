# Design Document: Hermes-Agent Benchmark Integration

**Spec**: `specs/hermes-benchmarks/spec.md`
**Status**: Draft
**Last Updated**: 2026-06-15

---

## Overview

Design and implement the Hermes agent integration into the TinyCUA benchmark pipeline so that Hermes runs as a first-class harness alongside TinyCUAAgent in WildClawBench. This covers: Docker image setup, agent backend wiring, config loading, transcript output, grading pipeline reuse, and side-by-side result comparison.

---

## Architecture

### Component Overview

```
┌──────────────────────────────────────────────────────┐
│                Benchmark Pipeline                      │
│  (tinycua-benchmark / tinycua.scripts.run_benchmark) │
└───────┬──────────────────────┬────────────────────────┘
        │                      │
        ▼                      ▼
┌──────────────────┐  ┌──────────────────┐
│  TinyCUAAgent    │  │  HermesAgent     │
│  (local/Docker)  │  │  (Docker only)   │
│                  │  │                  │
│  ┌────────────┐  │  │  ┌────────────┐ │
│  │ transcript │  │  │  │ transcript │ │
│  │  (JSONL)   │  │  │  │  (JSONL)   │ │
│  └────────────┘  │  │  └────────────┘ │
└──────────────────┘  └──────────────────┘
        │                      │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │   Grading Pipeline   │
        │  (same criteria for  │
        │   both agents)       │
        └──────────────────────┘
                   ▼
        ┌──────────────────────┐
        │  Side-by-Side Report │
        └──────────────────────┘
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `tinycua.wildclawbench.hermes_agent` | New | Hermes agent adapter module |
| `tinycua.wildclawbench.__init__` | Modified | Register HermesAgent |
| `tinycua.scripts.run_benchmark` | Modified | Add `hermesagent` to agent-backend choices |
| `tinycua-benchmark/Dockerfile` | New/Modified | Hermes agent Docker image |
| `tinycua-benchmark/docker-compose.yml` | Modified | Add Hermes service |
| `tinycua-benchmark/scripts/` | New | Hermes build/run scripts |

---

## Data Model

### HermesConfig

```python
# Configuration for Hermes agent run
HermesConfig:
    model: str               # Model name/path (e.g., "gpt-4", "claude-3")
    api_base: str            # API endpoint URL
    api_key_env: str         # Env var name for API key (not the key itself)
    temperature: float       # Sampling temperature (default: 0.0)
    max_tokens: int          # Max tokens per response (default: 4096)
    timeout: int             # Request timeout in seconds (default: 120)
```

### Config File Format (YAML)

```yaml
# hermes-config.yaml
model: "gpt-4"
api_base: "https://api.openai.com/v1"
api_key_env: "HERMES_API_KEY"
temperature: 0.0
max_tokens: 4096
timeout: 120
```

---

## API / Interface Contracts

### HermesAgent Adapter

The HermesAgent adapter implements the same `BaseAgent` ABC from `tinycua.wildclawbench.base_agent`:

```python
class HermesAgent(BaseAgent):
    expects_gateway: bool = False
    transcript_container_path: str = "/workspace/transcript.jsonl"

    def run_task(self, spec: AgentTaskSpec) -> AgentExecution:
        """
        Build Hermes Docker image if needed, run container with Hermes config,
        capture transcript and usage.
        """

    def collect_usage(self, spec: AgentTaskSpec, exec: AgentExecution) -> dict:
        """
        Collect token usage and cost from Hermes run logs.
        """
```

### CLI Interface

```bash
# Run benchmark with Hermes agent
python -m tinycua.benchmark \
    --agent-backend hermesagent \
    --hermes-config ./hermes-config.yaml \
    --tasks tasks.json
```

### Error Handling

| Error Case | Response | Notes |
|------------|----------|-------|
| Missing API key env var | Log error, skip Hermes tasks | Check `os.environ` before docker run |
| Docker image build fails | Log build error, skip Hermes tasks | Catch subprocess.CalledProcessError |
| Hermes container timeout | Log timeout, mark task as timeout | Same as TinyCUA timeout handler |
| Malformed transcript | Grade returns error, include in report | Do not crash pipeline |

---

## Implementation Phases

### Phase 1 — MVP

- [ ] Create `HermesAgent` adapter class implementing `BaseAgent`
- [ ] Wire `hermesagent` into `--agent-backend` CLI choices
- [ ] Build Hermes Docker image (Dockerfile based on upstream)
- [ ] Implement Hermes config loading (YAML file)
- [ ] Run smoke test (1-3 tasks) and verify transcript output
- [ ] Write unit tests for config validation and command construction

### Phase 2 — Enhancements

- [ ] Add side-by-side result reporting (TinyCUA vs Hermes)
- [ ] Document full setup guide (README)
- [ ] Add integration test with CI
- [ ] Support multiple Hermes config profiles

---

## Technical Decisions

1. **Decision**: Hermes runs exclusively in Docker (no local mode)
   - **Reason**: WildClawBench contract requires Docker isolation; Hermes has external dependencies (model API) that Docker manages cleanly
   - **Alternatives Considered**: Local subprocess — rejected because Hermes has Python dependency conflicts with TinyCUA

2. **Decision**: Use YAML config file for Hermes settings
   - **Reason**: Matches upstream Hermes convention (`hermes.yaml`); easy to version control and document
   - **Alternatives Considered**: CLI flags — rejected because config grows with model/endpoint fields

3. **Decision**: Reuse existing WildClawBench grading pipeline as-is
   - **Reason**: Same grading criteria for fair comparison; no need to duplicate
   - **Alternatives Considered**: Custom grading — rejected because it would break comparability

4. **Decision**: API key via env var (never in config file)
   - **Reason**: Security best practice; config file may be committed to version control
   - **Alternatives Considered**: Config file field — rejected for security

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hermes Docker image is large (>5GB) | Medium | Medium | Multi-stage build, document expected size |
| Hermes API dependency (external model) | High | High | Document required env vars; fail fast with clear error |
| Transcript format mismatch | Low | Medium | Validate transcript after Hermes run; compare against OpenClaw schema |
| Grading incompatibility | Low | Medium | Run smoke test with known scores to verify |

---

## Open Questions _(optional)_

1. **Which Hermes agent version to pin?**
   - Current thinking: Pin to the upstream WildClawBench commit used in adapter contract (`86d7144`). Update as needed.

---

## References

- Spec: `specs/hermes-benchmarks/spec.md`
- Adapter Contract: `specs/wildclawbench-adapter/adapter-contract.md`
- Upstream Hermes Agent: `https://github.com/InternLM/WildClawBench/tree/main/src/agents/hermesagent`
- TinyCUA Agent Adapter: `src/tinycua/tinycua/wildclawbench/agent.py`
- BaseAgent ABC: `src/tinycua/tinycua/wildclawbench/base_agent.py`
