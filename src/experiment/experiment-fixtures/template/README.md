# Controlled Experiment Template

Create an experiment by copying this directory into `../experiments-list/`:

```sh
cp -R template ../experiments-list/my-experiment
```

Then replace every placeholder below.

## `manifest.yaml`

The runner sends `prompt` to every selected harness. The evaluator runs
`eval_command` in `eval_image` after the harness finishes.

```yaml
prompt: |
  Read TASK.md in your workdir and complete the task.
outcome_group: coding
eval_image: python:3.12-alpine
eval_command: ["sh", "/eval/run.sh", "/submission"]
```

`eval_command` must exit `0` only when the submission passes. Its exit status
is the experiment pass/fail result. An evaluator can additionally write
`/result/score.json`; `/result` is writable only for the evaluator and is not
mounted into the harness or submission.

The optional score file has this exact schema. The runner validates it and
embeds it under `score` in the pair's `result.json`; a scored pair passes only
when the evaluator exits `0`, `total >= pass_threshold`, and every named
critical category earns its full points with non-empty evidence. Prefer one
binary category per observable check (`0/1`), a partial pass threshold, and a
short critical-category list for requirements that cannot be compensated by
other points. For coding fixtures, every mandatory behavior must be a critical
category so the result measures Pass@1 functional correctness. Fixtures that
do not write a score keep exit-status-only behavior.

```json
{
  "categories": {
    "frontend": {
      "points": 1,
      "max_points": 1,
      "evidence": ["Chromium rendered the saved item"]
    }
  },
  "total": 1,
  "pass_threshold": 1,
  "critical_categories": ["frontend"],
  "metrics": {"rouge_l_f1": 42.75}
}
```

`points` must be between zero and `max_points`; `total` must equal the category
points; `pass_threshold` must be within the category maximum; and every
critical category must name a defined category. Use evaluator-owned
`eval/requirements.txt` for evaluator tools rather than relying on submission
dependencies. Optional finite numeric `metrics` are reporting-only and never
affect pass/fail.

## `workdir/`

This is the only fixture content mounted into the harness container. Leave it
empty for a from-scratch task, or add starter files for the harness to edit.

Put task instructions and success criteria in `TASK.md`. Do not put evaluator
checks here.

If an evaluator expects a fixed path such as `app.py`, `src/app.py`, or
`frontend/index.html`, name that exact layout in `TASK.md`. If the task is
intentionally free-form, document one entrypoint for the evaluator to invoke
instead of assuming undocumented files.

Set `outcome_group` to `coding`, `research`, or `conversation`; controlled run
summaries keep these groups separate and never compute a cross-task average.
Use `eval_dockerfile` to build one fixed evaluator image shared by every
candidate for that fixture.

## `eval/`

This directory is mounted only into the separate evaluator container as
`/eval`; the submission is mounted there as `/submission`.

Replace `eval/run.sh` with deterministic checks. For example, a Python check
can import code from `/submission`, run a command, or compare generated files.
Place Python dependencies in `eval/requirements.txt` or `eval/pyproject.toml`;
submission dependencies may likewise use `workdir/requirements.txt` or
`workdir/pyproject.toml`. The runner installs these only in the ephemeral
evaluator container before `eval_command`. Any such manifest requires Python
and pip in `eval_image`; manifest-free evaluators can remain BusyBox.

Nested submission manifests are rejected unless the fixture explicitly allows
them in `manifest.yaml`. List safe relative paths in deterministic order:

```yaml
submission_dependency_files:
  - backend/requirements.txt
  - packages/client/pyproject.toml
```

The runner always installs the top-level submission manifests when present. A
free-form entrypoint may instead own dependency installation and nested layouts:

```yaml
entrypoint_manages_dependencies: true
```

This skips submission-manifest installation and nested-manifest validation; it
does not skip evaluator dependencies.

## Submission Dockerfile

To require that the completed submission builds, declare its safe relative
Dockerfile path:

```yaml
submission_dockerfile: Dockerfile
```

After the agent finishes, the host runner runs a bounded `docker build` using
the copied `workdir/` as context. Its output is stored under a
`submission-build` header in the pair's `stdout.log` and `stderr.log`; a failed
build skips the evaluator and fails the pair. This remains host-owned even
though the agent runs in Docker, so neither the agent nor evaluator receives
Docker access.

## `docker/Dockerfile`

This optional common layer adds task prerequisites to every existing harness
image. Keep its first two lines unchanged:

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
```

Add only task dependencies after `FROM`. The build context is this `docker/`
directory, so it cannot copy `workdir/` or hidden `eval/` files into the agent
image.

## Run

From `src/experiment`:

```sh
uv run python run_template_experiment.py \
  --fixtures my-experiment \
  --agents tinycua
```

Reusing the same output root resumes complete pairs; `--overwrite` replaces
only selected pairs. Results contain schema-v2 `result.json`, consolidated
`stdout.log` and `stderr.log`, `environment.json`, and a cleaned `workdir/`.
Optional evaluator scores are embedded in `result.json`; evaluator scratch is
removed.
