# Agent harness experiment

```bash
scripts/setup.sh
scripts/run.sh 1 "Make me a simple clock animation app in a single HTML file"
```

Results land under `results/<agent>/experiment-<num>/` with `prompt.txt`, `container.env`, `stdout.log`, `stderr.log`, and `metadata.json`.
Logs are written while each harness runs, and each harness is killed after `EXPERIMENT_TIMEOUT_SECONDS` (default `3600`).

If containers cannot reach a host LLM on `localhost`, set `EXPERIMENT_LLM_BASE_URL=http://host.docker.internal:1234/v1` in `.env`.
