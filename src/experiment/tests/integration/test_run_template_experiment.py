"""Integration tests for controlled template experiments with a stub Docker CLI."""

import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "experiment-fixtures" / "experiments-list"
VOLUME_TRANSFER_STUB = (
    "if args[:1] == ['cp']:\n"
    "    source, destination = args[1:3]\n"
    "    volume_state = Path(os.environ['DOCKER_VOLUMES'])\n"
    "    if ':' not in source:\n"
    "        volume_state.write_text(source)\n"
    "    else:\n"
    "        shutil.copytree(volume_state.read_text(), destination, dirs_exist_ok=True)\n"
    "    sys.exit(0)\n"
)


def test_experiment_one_evaluator_rejects_seed_and_accepts_correct_submission(
    tmp_path: Path,
) -> None:
    """The representative evaluator distinguishes an incorrect response."""
    fixture = FIXTURES / "experiment-1"
    incorrect_output = tmp_path / "incorrect"
    correct_output = tmp_path / "correct"
    incorrect_output.mkdir()
    correct_output.mkdir()
    (incorrect_output / "agent.stdout.log").write_text(
        '{"type":"text","part":{"text":"Hi"}}\n'
    )
    (correct_output / "agent.stdout.log").write_text(
        '{"type":"text","part":{"text":"Hello Reply"}}\n'
    )

    exit_codes = []
    scores = []
    for output in (incorrect_output, correct_output):
        result_directory = tmp_path / f"result-{output.name}"
        result_directory.mkdir()
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{(fixture / 'workdir').resolve()}:/submission:ro",
                "-v",
                f"{(fixture / 'eval').resolve()}:/eval:ro",
                "-v",
                f"{output.resolve()}:/agent-output:ro",
                "-v",
                f"{result_directory.resolve()}:/result",
                "busybox:1.36",
                "sh",
                "/eval/run.sh",
                "/submission",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        exit_codes.append(completed.returncode)
        scores.append(json.loads((result_directory / "score.json").read_text()))

    assert exit_codes[0] != 0
    assert exit_codes[1] == 0
    assert [score["total"] for score in scores] == [0, 1]


def test_clock_evaluator_browser_executes_time_derived_hands(tmp_path: Path) -> None:
    """The clock passes only when Chromium observes correct hand geometry."""
    fixture = FIXTURES / "experiment-3"
    submission = tmp_path / "submission"
    result_directory = tmp_path / "result"
    submission.mkdir()
    result_directory.mkdir()
    (submission / "clock.html").write_text(
        """<!doctype html><html><body><canvas width="300" height="300"></canvas>
<script>
const canvas = document.querySelector('canvas');
const context = canvas.getContext('2d');
function hand(angle, length) {
  const radians = angle * Math.PI / 180;
  context.beginPath();
  context.moveTo(150, 150);
  context.lineTo(150 + Math.sin(radians) * length, 150 - Math.cos(radians) * length);
  context.stroke();
}
function draw() {
  const now = new Date();
  context.clearRect(0, 0, 300, 300);
  hand(now.getSeconds() * 6, 120);
  hand(now.getMinutes() * 6, 100);
  hand((now.getHours() % 12) * 30, 70);
}
draw();
setInterval(draw, 1000);
</script></body></html>"""
    )
    image = "tinycua-test-browser-evaluator"
    build = subprocess.run(
        [
            "docker",
            "build",
            "--tag",
            image,
            "--build-arg",
            "BASE_IMAGE=python:3.12-slim",
            "--file",
            str(fixture / "eval" / "Dockerfile"),
            str(fixture / "eval"),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert build.returncode == 0, build.stderr
    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{submission.resolve()}:/submission:ro",
            "-v",
            f"{(fixture / 'eval').resolve()}:/eval:ro",
            "-v",
            f"{result_directory.resolve()}:/result",
            image,
            "sh",
            "/eval/run.sh",
            "/submission",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    score = json.loads((result_directory / "score.json").read_text())
    assert completed.returncode == 0, completed.stderr
    assert score["total"] == len(score["categories"])
    assert set(score["critical_categories"]) == set(score["categories"])


def test_research_evaluator_uses_exact_snapshot_model_for_relevancy(
    tmp_path: Path,
) -> None:
    """Research freshness requires a model from the bundled snapshot."""
    fixture = FIXTURES / "experiment-2"
    cases = (
        ("model-only", "", "GPT-5.6-Sol"),
        ("missing-model", "2026-07-22", ""),
        ("later", "2026-07-23", "GPT-5.6-Sol"),
    )
    for name, date_text, model in cases:
        submission = tmp_path / name
        submission.mkdir()
        shutil.copy(fixture / "workdir" / "TASK.md", submission / "TASK.md")
        (submission / "report.md").write_text(
            f"# Frontier LLM Report\n\nSnapshot date: {date_text}\n\n{model}\n"
        )
        (tmp_path / f"{name}-result").mkdir()

    completed = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{tmp_path.resolve()}:/cases",
            "-v",
            f"{(fixture / 'eval').resolve()}:/eval:ro",
            "tinycua-template-tinycua-base",
            "sh",
            "-c",
            "python -m pip install -q -r /eval/requirements.txt && "
            "python /eval/check.py /cases/model-only "
            "/cases/model-only-result || true; "
            "python /eval/check.py /cases/missing-model "
            "/cases/missing-model-result || true; "
            "python /eval/check.py /cases/later /cases/later-result || true",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    model_only = json.loads((tmp_path / "model-only-result" / "score.json").read_text())
    missing_model = json.loads(
        (tmp_path / "missing-model-result" / "score.json").read_text()
    )
    later = json.loads((tmp_path / "later-result" / "score.json").read_text())
    assert "latest_relevancy" in model_only["critical_categories"]
    assert model_only["categories"]["latest_relevancy"]["points"] == 1
    assert missing_model["categories"]["latest_relevancy"]["points"] == 0
    assert later["categories"]["latest_relevancy"]["points"] == 1
    assert 0 < model_only["metrics"]["rouge_l_f1"] <= 100
    assert 0 < model_only["metrics"]["bleu"] <= 100


def test_experiment_four_wrapper_runs_app_with_uv_and_prints_pid(
    tmp_path: Path,
) -> None:
    """The supplied wrapper exposes the live background app PID."""
    fixture = FIXTURES / "experiment-4"
    shutil.copy(fixture / "workdir" / "run.sh", tmp_path / "run.sh")
    shutil.copy(fixture / "workdir" / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "app.py").write_text("import time\ntime.sleep(60)\n")
    uv = tmp_path / "uv"
    uv.write_text(
        '#!/bin/sh\nif [ "$1" = sync ]; then exit 0; fi\n'
        'shift\nshift\nexec python "$@"\n'
    )
    uv.chmod(uv.stat().st_mode | stat.S_IXUSR)
    process = subprocess.Popen(
        ["sh", "run.sh"],
        cwd=tmp_path,
        env=os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    pid_text = process.stdout.readline().strip()

    try:
        app_pid = int(pid_text)
        os.kill(app_pid, 0)
    finally:
        process.terminate()
        process.wait(timeout=5)

    for _ in range(20):
        try:
            os.kill(app_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("run.sh did not terminate its background app")


@pytest.mark.parametrize(
    ("agent_code", "evaluator_code", "eval_image", "eval_command"),
    [
        (
            0,
            0,
            "tinycua-template-browser-evaluator",
            ("python", "/eval/check.py", "/submission"),
        ),
        (0, 3, "busybox:1.36", ("sh", "/eval/run.sh", "/submission")),
        (7, 0, "busybox:1.36", ("sh", "/eval/run.sh", "/submission")),
    ],
    ids=(
        "agent_zero_evaluator_zero",
        "agent_zero_evaluator_nonzero",
        "agent_nonzero_evaluator_zero",
    ),
)
def test_controlled_runner_records_agent_telemetry_before_delayed_evaluation(
    tmp_path: Path,
    agent_code: int,
    evaluator_code: int,
    eval_image: str,
    eval_command: tuple[str, ...],
) -> None:
    """The stub proves image build, agent isolation, and evaluator result mapping."""
    fixture = FIXTURES / "test-controlled-runner"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "docker").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\n"
        "outcome_group: coding\n"
        f"eval_image: {eval_image}\n"
        "eval_dockerfile: eval/Dockerfile\n"
        f"eval_command: {list(eval_command)}\n"
    )
    (fixture / "workdir" / "answer.txt").write_text("seed\n")
    (fixture / "eval" / "check.py").write_text("print('ok')\n")
    (fixture / "eval" / "Dockerfile").write_text("ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n")
    (fixture / "docker" / "Dockerfile").write_text(
        "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n"
    )
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, shutil, sys, time\n"
        "from pathlib import Path\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n" + VOLUME_TRANSFER_STUB + "if args[:1] == ['run']:\n"
        "    time.sleep(1)\n"
        "    sys.exit(int(os.environ['EVALUATOR_CODE']))\n"
        "if args[:1] == ['compose']:\n"
        "    sys.exit(int(os.environ['AGENT_CODE']))\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
        "AGENT_CODE": str(agent_code),
        "EVALUATOR_CODE": str(evaluator_code),
        "DOCKER_VOLUMES": str(tmp_path / "volumes.json"),
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-controlled-runner",
                "--agents",
                "opencode",
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    assert result.returncode == bool(evaluator_code)
    commands = [
        command
        for line in calls.read_text().splitlines()
        if (command := json.loads(line))[:2] != ["image", "inspect"]
    ]
    assert commands[0][:2] == ["build", "--tag"]
    assert commands[1][:3] == ["build", "--tag", "tinycua-template-tinycua-base"]
    assert commands[2][:3] == ["build", "--tag", eval_image]
    assert commands[3][:2] == ["build", "--tag"]
    agent = next(command for command in commands if command[:1] == ["compose"])
    evaluator = next(command for command in commands if command[:1] == ["run"])
    transfers = [command for command in commands if command[:1] == ["cp"]]
    assert len(transfers) == 2
    assert commands.index(agent) < commands.index(evaluator)
    assert (
        len(
            [
                command
                for command in commands
                if command[:3] == ["volume", "rm", "--force"]
            ]
        )
        == 2
    )
    assert str(
        output / "test-controlled-runner" / "opencode" / "workdir"
    ) not in " ".join(agent)
    assert agent[0] == "compose"
    assert "eval" not in " ".join(agent)
    assert evaluator[0] == "run"
    assert any(mount.endswith(":/submission:ro") for mount in evaluator)
    assert any(mount.endswith(":/eval:ro") for mount in evaluator)
    assert evaluator[-(len(eval_command) + 1) :] == [
        eval_image,
        *eval_command,
    ]
    run_root = output / "test-controlled-runner" / "opencode"
    pair_result = json.loads((run_root / "result.json").read_text())
    assert pair_result["agent_exit_code"] == agent_code
    assert pair_result["evaluator_exit_code"] == evaluator_code
    assert pair_result["evaluator_outcome"] == (
        "passed" if evaluator_code == 0 else "failed"
    )
    assert pair_result["passed"] is (evaluator_code == 0)
    assert pair_result["stdout_path"] == "agent.stdout.log"
    assert pair_result["stderr_path"] == "agent.stderr.log"
    assert (run_root / pair_result["sanitized_environment"]).is_file()
    assert "--name" in agent
    assert "--name" in evaluator
    metadata = json.loads((output / "run_metadata.json").read_text())
    assert metadata["result_generation_commit"]
    assert metadata["trial_policy"] == {
        "pass_at_k": 1,
        "trials_per_pair": 1,
        "retries": 0,
        "execution_order": "sequential",
    }
    assert metadata["fixtures"]["test-controlled-runner"]["fixture_revision"]
    assert metadata["fixtures"]["test-controlled-runner"]["evaluator_revision"]
    assert (
        metadata["images"]["candidates"]["test-controlled-runner"]["opencode"][
            "reference"
        ]
        == "tinycua-template-test-controlled-runner-opencode"
    )
    outcomes = json.loads((output / "outcomes.json").read_text())
    assert set(outcomes) == {"coding", "research", "conversation"}
    assert outcomes["research"] == {}
    assert outcomes["coding"]["test-controlled-runner"]["opencode"]["passed"] is (
        evaluator_code == 0
    )


def test_controlled_runner_records_fixture_image_build_failure(tmp_path: Path) -> None:
    """A failed fixture image build still produces a complete pair result."""
    fixture = FIXTURES / "test-fixture-build-failure"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "docker").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    (fixture / "docker" / "Dockerfile").write_text(
        "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n"
    )
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:1] == ['build'] and 'tinycua-template-test-fixture-build-failure-opencode' in args:\n"
        "    sys.exit(7)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"}
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-fixture-build-failure",
                "--agents",
                "opencode",
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    run_root = output / "test-fixture-build-failure" / "opencode"
    pair_result = json.loads((run_root / "result.json").read_text())
    assert completed.returncode == 1
    assert pair_result["agent_exit_code"] == 125
    assert pair_result["evaluator_exit_code"] == 125
    assert pair_result["passed"] is False
    assert "fixture image build failed exit_code=7" in completed.stdout


def test_controlled_runner_embeds_valid_evaluator_score(tmp_path: Path) -> None:
    """A score written to the evaluator-only mount is validated and retained."""
    fixture = FIXTURES / "test-controlled-score"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, shutil, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n" + VOLUME_TRANSFER_STUB + "if args[:1] == ['run']:\n"
        "    result = next(arg[:-8] for arg in args if arg.endswith(':/result'))\n"
        "    Path(result, 'score.json').write_text(json.dumps({\n"
        "        'categories': {'checks': {'points': 100, 'max_points': 100, 'evidence': ['stub passed']}},\n"
        "        'total': 100, 'pass_threshold': 80, 'critical_categories': ['checks']\n"
        "    }))\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_VOLUMES": str(tmp_path / "volumes.txt"),
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-controlled-score",
                "--agents",
                "opencode",
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    pair_result = json.loads(
        (output / "test-controlled-score" / "opencode" / "result.json").read_text()
    )
    assert result.returncode == 0
    assert pair_result["passed"] is True
    assert pair_result["score"]["total"] == 100
    assert pair_result["score"]["pass_threshold"] == 80
    assert pair_result["score"]["categories"]["checks"]["evidence"] == ["stub passed"]


@pytest.mark.parametrize("build_code", (0, 7), ids=("passes", "fails"))
def test_controlled_runner_builds_submission_on_host_before_evaluation(
    tmp_path: Path, build_code: int
) -> None:
    """A declared submission Dockerfile gates evaluation from the host runner."""
    fixture = FIXTURES / "test-submission-dockerfile"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\n"
        "eval_image: busybox\n"
        "eval_command: ['true']\n"
        "submission_dockerfile: Dockerfile\n"
    )
    (fixture / "workdir" / "Dockerfile").write_text("FROM scratch\n")
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, shutil, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(args) + '\\n')\n"
        + VOLUME_TRANSFER_STUB
        + "if args[:1] == ['build'] and os.environ['SUBMISSION_DOCKERFILE'] in args:\n"
        "    print('submission build output')\n"
        "    print('submission build error', file=sys.stderr)\n"
        "    sys.exit(int(os.environ['BUILD_CODE']))\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
        "BUILD_CODE": str(build_code),
        "DOCKER_VOLUMES": str(tmp_path / "volumes.txt"),
        "SUBMISSION_DOCKERFILE": str(
            output
            / "test-submission-dockerfile"
            / "opencode"
            / "workdir"
            / "Dockerfile"
        ),
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-submission-dockerfile",
                "--agents",
                "opencode",
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    run_root = output / "test-submission-dockerfile" / "opencode"
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    submission_build = next(
        command
        for command in commands
        if command[:1] == ["build"] and env["SUBMISSION_DOCKERFILE"] in command
    )
    assert submission_build[-1] == str(run_root / "workdir")
    assert (
        run_root / "submission-build.stdout.log"
    ).read_text() == "submission build output\n"
    assert (
        run_root / "submission-build.stderr.log"
    ).read_text() == "submission build error\n"
    pair_result = json.loads((run_root / "result.json").read_text())
    assert result.returncode == int(build_code != 0)
    assert pair_result["passed"] is (build_code == 0)
    if build_code:
        assert pair_result["evaluator_exit_code"] == 125
        assert not any(command[:1] == ["run"] for command in commands)
    else:
        assert pair_result["evaluator_exit_code"] == 0
        assert commands.index(submission_build) < next(
            index for index, command in enumerate(commands) if command[:1] == ["run"]
        )


def test_controlled_runner_rejects_undeclared_nested_submission_dependencies(
    tmp_path: Path,
) -> None:
    """Nested manifests require explicit fixture approval before evaluation."""
    fixture = FIXTURES / "test-nested-submission-dependency"
    (fixture / "workdir" / "package").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    (fixture / "workdir" / "package" / "requirements.txt").write_text("requests\n")
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, shutil, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(args) + '\\n')\n" + VOLUME_TRANSFER_STUB
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
        "DOCKER_VOLUMES": str(tmp_path / "volumes.txt"),
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-nested-submission-dependency",
                "--agents",
                "opencode",
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    run_root = output / "test-nested-submission-dependency" / "opencode"
    pair_result = json.loads((run_root / "result.json").read_text())
    assert result.returncode == 1
    assert pair_result["evaluator_exit_code"] == 125
    assert pair_result["passed"] is False
    assert (
        "undeclared nested submission dependency manifest"
        in (run_root / "eval.stderr.log").read_text()
    )
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    assert not any(command[:1] == ["run"] for command in commands)


@pytest.mark.parametrize("timed_out", ["agent", "evaluator"])
def test_controlled_runner_records_agent_and_evaluator_timeouts(
    tmp_path: Path, timed_out: str
) -> None:
    """Timed-out Docker runs retain diagnostics and a deterministic result."""
    fixture = FIXTURES / "test-controlled-timeout"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    (fixture / "workdir" / "answer.txt").write_text("seed\n")
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "mode = os.environ['TIMEOUT_MODE']\n"
        "is_agent = sys.argv[1:2] == ['compose']\n"
        "is_evaluator = sys.argv[1:2] == ['run']\n"
        "if (mode == 'agent' and is_agent) or (mode == 'evaluator' and is_evaluator):\n"
        "    print(f'TOKEN={os.environ[\"TIMEOUT_SECRET\"]}')\n"
        "    print(f'TOKEN={os.environ[\"TIMEOUT_SECRET\"]}', file=sys.stderr)\n"
        "    time.sleep(2)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    secret = "timeout-configured-secret"
    (tmp_path / ".env").write_text(f"EXPERIMENT_LLM_API_KEY={secret}\n")
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "TIMEOUT_MODE": timed_out,
        "DOCKER_CALLS": str(tmp_path / "calls.jsonl"),
        "TIMEOUT_SECRET": secret,
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-controlled-timeout",
                "--agents",
                "opencode",
                "--timeout-seconds",
                "1",
                "--output-root",
                str(output),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    run_root = output / "test-controlled-timeout" / "opencode"
    result_json = json.loads((run_root / "result.json").read_text())
    assert result.returncode == int(timed_out == "evaluator")
    assert result_json[f"{timed_out}_exit_code"] == 124
    assert result_json["passed"] is (timed_out == "agent")
    log_name = "eval" if timed_out == "evaluator" else timed_out
    assert (
        "Timed out after 1 seconds" in (run_root / f"{log_name}.stderr.log").read_text()
    )
    assert secret not in (run_root / f"{log_name}.stdout.log").read_text()
    assert secret not in (run_root / f"{log_name}.stderr.log").read_text()
    commands = [
        json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    timed_out_index = next(
        index
        for index, command in enumerate(commands)
        if command[0] == ("compose" if timed_out == "agent" else "run")
    )
    timed_out_name = commands[timed_out_index][
        commands[timed_out_index].index("--name") + 1
    ]
    cleanup_index = commands.index(["rm", "--force", timed_out_name])
    assert cleanup_index == timed_out_index + 1
    if timed_out == "agent":
        assert commands[cleanup_index + 1][:2] == ["container", "ls"]
        assert any(command[0] == "run" for command in commands[cleanup_index + 2 :])


@pytest.mark.parametrize("cleanup_mode", ("failed", "hung"))
def test_controlled_runner_stops_after_failed_or_hung_timeout_cleanup(
    tmp_path: Path, cleanup_mode: str
) -> None:
    """A failed timed-out-container cleanup blocks evaluation and later pairs."""
    fixture = FIXTURES / "test-controlled-cleanup-failure"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    (fixture / "workdir" / "answer.txt").write_text("seed\n")
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys, time\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['rm', '--force'] and 'workspace-' not in sys.argv[3]:\n"
        "    if os.environ['CLEANUP_MODE'] == 'failed':\n"
        "        sys.exit(1)\n"
        "    time.sleep(2)\n"
        "if sys.argv[1:2] == ['compose']:\n"
        "    time.sleep(2)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
        "CLEANUP_MODE": cleanup_mode,
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-controlled-cleanup-failure",
                "--agents",
                "opencode,hermes",
                "--timeout-seconds",
                "1",
                "--output-root",
                str(output),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    run_root = output / "test-controlled-cleanup-failure" / "opencode"
    result_json = json.loads((run_root / "result.json").read_text())
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    assert result.returncode == 1
    assert result_json["agent_exit_code"] == 124
    assert result_json["evaluator_exit_code"] == 125
    assert result_json["passed"] is False
    assert "cleanup" in (run_root / "agent.stderr.log").read_text().lower()
    assert not any(command[0] == "run" for command in commands)
    assert sum(command[0] == "compose" for command in commands) == 1


def test_controlled_runner_redacts_configured_secret_from_all_pair_artifacts(
    tmp_path: Path,
) -> None:
    """Stub agent and evaluator output cannot persist a configured .env secret."""
    fixture = FIXTURES / "test-controlled-redaction"
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    (fixture / "workdir" / "answer.txt").write_text("seed\n")
    secret = "stub-emitted-env-secret"
    (tmp_path / ".env").write_text(
        f"COMPOSE_BASE_SECRET={secret} # local comment\n"
        "EXPERIMENT_LLM_API_KEY=${COMPOSE_BASE_SECRET}\n"
    )
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:2] in (['compose'], ['run']):\n"
        "    print(os.environ['STUB_SECRET'])\n"
        "    print(os.environ['STUB_SECRET'], file=sys.stderr)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "results"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "STUB_SECRET": secret,
    }
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                "test-controlled-redaction",
                "--agents",
                "opencode",
                "--output-root",
                str(output),
            ],
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(fixture)

    assert result.returncode == 0
    run_root = output / "test-controlled-redaction" / "opencode"
    assert all(
        secret not in path.read_text() for path in run_root.rglob("*") if path.is_file()
    )
