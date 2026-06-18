# Agent harness experiment

```bash
cp .env.example .env
docker compose build
uv run python run_experiment.py --num 1 --prompt "Make me a simple clock animation app in a single HTML file"
```

Results land under `results/<agent>/experiment-<num>/` with `prompt.txt`, `container.env`, `stdout.log`, `stderr.log`, and `metadata.json`.

If containers cannot reach a host LLM on `localhost`, set `EXPERIMENT_LLM_BASE_URL=http://host.docker.internal:1234/v1` in `.env`.
