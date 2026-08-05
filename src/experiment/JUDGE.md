# Hermes Judge

AI judge for evaluating agent submissions using Hermes Agent inside Docker.

## Prerequisites

- Docker

## Quick Start

```bash
cd src/experiment
bash scripts/setup_judge.sh
```

The setup script will:

1. Build the judge Docker image (Hermes Agent + judge profile)
2. Start the judge container (persistent, like searxng)
3. Launch the Hermes setup wizard inside the container
4. You pick your LLM provider and enter credentials interactively
5. Verify the judge responds correctly

## Usage

The judge container runs persistently. Use the semantic judge after a controlled
template run:

```bash
# Qualitatively cross-judge every completed submission for one fixture.
uv run python judge.py --fixture experiment-4

# Batch multiple fixtures. The submission count is discovered dynamically.
uv run python judge.py --fixture experiment-4,experiment-5
```

Semantic mode reads `fixtures-results/<fixture>/<agent>/`, anonymizes every
completed submission as `A`, `B`, and so on, and writes its verdict to
`fixtures-results/<fixture>/cross_verdict/`. It sees deterministic evaluator
outcomes as context, then compares qualitative strengths and weaknesses rather
than acting as the primary correctness judge. Submission workdir, stdout, and
environment locations come from `result.json`; schema-v1 artifact names remain
supported as a fallback. For schema-v2 conversational submissions, only the
`agent` stage is copied from consolidated `stdout.log`.

Legacy judging remains available only when explicitly requested with `--num`.
Use `docker compose exec` to run ad-hoc legacy-profile commands:

```bash
# Evaluate a submission
docker compose exec judge hermes -p judge -z \
  "Evaluate the submission at /workspace/results/opencode/experiment-1/workdir"

# Quick test
docker compose exec judge hermes -z "say hello"
```

## How It Works

- Hermes Agent runs inside a **persistent Docker container** (like searxng)
- The judge profile is a plain, minimal profile — no custom skills or tooling
- Model and provider are configured via `hermes setup model` (interactive TUI)
- Provider credentials persist in the `judge-hermes-home` Docker volume
- The current directory is mounted at `/workspace` inside the container
- `host.docker.internal` is available for accessing services on the host

### Judge Profiles

| Profile | Use | Location |
|---------|-----|----------|
| `semantic` | Default qualitative fixtures-results cross-judge | `judge/profiles/semantic/` |
| `judge` | Optional legacy correctness-oriented result judge | `judge/profiles/judge/` |

Each profile contains:

| File          | Purpose                                    |
|---------------|--------------------------------------------|
| `SOUL.md`     | Judge persona, scoring criteria, rules     |
| `config.yaml` | Minimal config — model, toolsets, browser  |
| `profile.yaml`| Profile description                        |

### Tools Available to the Judge

| Tool      | Purpose                                      |
|-----------|----------------------------------------------|
| terminal  | Run Docker containers for code testing       |
| file      | Read submission files                        |
| browser   | Verify HTML/web submissions visually         |

### Container Lifecycle

```bash
# Start (first time or after rebuild)
docker compose up -d judge

# Stop
docker compose stop judge

# Restart
docker compose restart judge

# Rebuild (after profile changes)
docker compose build judge
docker compose up -d judge
```

## Reconfiguration

```bash
# Re-run provider setup
docker compose exec judge hermes setup model
```

## Customization

Edit the selected profile's `SOUL.md` to change its judging criteria or persona.
Then rebuild:

```bash
docker compose build judge
docker compose up -d judge
```

## Data Persistence

The `judge-hermes-home` Docker volume stores:

- `.env` — provider API keys / credentials
- `config.yaml` — model and provider settings
- `auth.json` — OAuth tokens (if using Codex)

This data **survives container restarts and rebuilds**.
To wipe and reconfigure from scratch, run the cleanup script:

```bash
bash scripts/cleanup_judge.sh
```

Then set up again:

```bash
bash scripts/setup_judge.sh
```

## Troubleshooting

### "model not configured" or empty response

```bash
docker compose exec judge hermes setup model
```

### Container can't reach host services

The `host.docker.internal` DNS entry is configured. Use it to access
services running on the host (e.g., LLM server at `http://host.docker.internal:1234/v1`).

### Rebuild after profile changes

```bash
docker compose build --no-cache judge
docker compose up -d judge
```
