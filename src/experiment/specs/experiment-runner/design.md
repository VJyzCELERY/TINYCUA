# Design Document: Experiment Runner

**Spec**: `./spec.md`
**Status**: Complete
**Last Updated**: 2026-06-19

---

## Overview

Add one small batch CLI in `src/experiment` that parses a prompt manifest, invokes the existing experiment runner sequentially, invokes the existing judge per experiment, then moves the judged experiment folders into a timestamped archive. Add a narrow Hermes guard for background process polling deadlocks. Pass SearXNG web search configuration to harnesses that support it.

---

## Architecture

### Component Overview

```
prompt manifest -> run_batch_experiments.py
                 -> run_experiment.py --num N --prompt ... --overwrite
                 -> judge.py --num N
                 -> archives/<timestamp>/results/<agent>/experiment-N

Hermes run_experiment output -> detect unresolved process poll -> exit 124
.env SearXNG values -> bundled searxng service -> harness web_search tools
container result -> permission repair -> artifact sanitation -> judge/archive
```

### Affected Components

| Component | Change Type | Notes |
|-----------|-------------|-------|
| `run_batch_experiments.py` | New | Batch orchestration only. |
| `run_experiment.py` | Modified | Hermes process-poll deadlock guard. |
| `judge.py` | Modified | Defense-in-depth skip for harness artifacts. |
| `docker-compose.yml` / harness Dockerfiles | Modified | SearXNG env aliases and OpenClaw provider config. |
| `tests/unit/test_run_batch_experiments.py` | New | Parser and archive helper checks. |
| `README.md` | Modified | Shows manifest format and command. |

---

## Data Model

### New Entities _(if applicable)_

- Prompt manifest line: `Experiment_<number>: <prompt>`
- Archive folder: `archives/<UTC timestamp>/`

### Schema Changes _(if applicable)_

- None.

---

## API / Interface Contracts

### New / Modified Endpoints or Functions

- CLI: `uv run python run_batch_experiments.py --manifest tmp/experiment_prompts.txt`
- Optional flags: `--output-root`, `--archive-root`, `--fail-fast`, `--dry-run`.
- Compose service: `searxng`, exposed on `EXPERIMENT_SEARXNG_HOST_PORT` (default `18080`).
- Env: `EXPERIMENT_SEARXNG_BASE_URL` for harnesses expecting a SearXNG instance root.
- Env: `TINYCUA_SEARXNG_URL` for TinyCUA's `/search` endpoint.

### Error Handling

| Error Case | Exception / Response | Notes |
|------------|---------------------|-------|
| Empty manifest | Exit 2 | No experiment starts. |
| Bad line | Exit 2 | Points to line number. |
| Command failure | Exit 1 | Continues by default; stops with `--fail-fast`. |
| Hermes process poll hang | Exit 124 | Guard applies only to Hermes `process poll`; full timeout remains for other long work. |
| Root-owned result files | Best-effort permission repair | Uses a short-lived helper container. |

---

## Implementation Phases

### Phase 1 — MVP _(required for initial release)_

- [x] Add parser and archive unit tests.
- [x] Add batch runner CLI.
- [x] Update README with prompt-list usage.
- [x] Add Hermes process-poll guard.
- [x] Add shared SearXNG config wiring.
- [x] Add result sanitation and permission repair.

---

## Technical Decisions

1. **Decision**: Reuse `run_experiment.py` and `judge.py` via subprocess.
   - **Reason**: Keeps hotfix small and honors current CLIs.
   - **Alternatives Considered**: Importing internals — rejected because subprocess matches real usage.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Long LLM/Docker runs fail midway | Med | Med | Record failures and archive partial results. |
| Archiving wrong results | Low | High | Move only requested experiment numbers per agent. |
| Hermes background server poll never returns | Med | Med | Kill only that known stuck poll after its own timeout. |
| Harnesses use different SearXNG env names | Med | Low | Provide common aliases in compose. |
| Harness artifacts leak identity to judge | Med | High | Remove known artifacts before judging and skip them in judge copy. |

---

## References

- Spec: `./spec.md`
