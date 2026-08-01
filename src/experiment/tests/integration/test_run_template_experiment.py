"""Integration tests for controlled template experiments with a stub Docker CLI."""

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
import run_template_experiment as runner


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "experiment-fixtures" / "experiments-list"
VOLUME_TRANSFER_STUB = (
    "import hashlib\n"
    "volume_root = Path(os.environ['DOCKER_VOLUMES'])\n"
    "volume_root.mkdir(parents=True, exist_ok=True)\n"
    "containers_file = volume_root / 'containers.json'\n"
    "containers = json.loads(containers_file.read_text()) if containers_file.exists() else {}\n"
    "def volume_path(name):\n"
    "    return volume_root / hashlib.sha256(name.encode()).hexdigest()\n"
    "if args[:1] == ['create']:\n"
    "    name = args[args.index('--name') + 1]\n"
    "    mount = args[args.index('-v') + 1]\n"
    "    containers[name] = mount.split(':', 1)[0]\n"
    "    containers_file.write_text(json.dumps(containers))\n"
    "    sys.exit(0)\n"
    "if args[:1] == ['cp']:\n"
    "    source, destination = args[1:3]\n"
    "    if ':' not in source:\n"
    "        container = destination.split(':', 1)[0]\n"
    "        shutil.copytree(source, volume_path(containers[container]), dirs_exist_ok=True)\n"
    "    else:\n"
    "        container = source.split(':', 1)[0]\n"
    "        shutil.copytree(volume_path(containers[container]), destination, dirs_exist_ok=True)\n"
    "    sys.exit(0)\n"
    "if args[:1] == ['run']:\n"
    "    for mount in (arg for arg in args if ':/' in arg):\n"
    "        source = mount.split(':', 1)[0]\n"
    "        if not source.startswith('/'):\n"
    "            volume_path(source).mkdir(parents=True, exist_ok=True)\n"
)
IMAGE_INSPECT_STUB = (
    "if args[:2] == ['image', 'inspect']:\n"
    "    print(json.dumps({'Id': 'sha256:' + args[2], 'RepoDigests': []}))\n"
    "    sys.exit(0)\n"
)
SEARXNG_READY_COMMAND = [
    "compose",
    "up",
    "-d",
    "--wait",
    "searxng",
]


def _run_controlled(
    output: Path,
    fixture: str,
    agents: str,
    env: dict[str, str],
    *,
    cwd: Path = ROOT,
    overwrite: bool = False,
    order_by: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "run_template_experiment.py"),
        "--fixtures",
        fixture,
        "--agents",
        agents,
        "--output-root",
        str(output),
    ]
    if overwrite:
        command.append("--overwrite")
    if order_by is not None:
        command.extend(("--order-by", order_by))
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_controlled_campaign_resumes_aggregates_and_keeps_compact_artifacts(
    tmp_path: Path,
) -> None:
    """Disjoint stub-Docker invocations safely extend one durable campaign."""
    fixture_name = "test-resumable-campaign"
    fixture = FIXTURES / fixture_name
    (fixture / "workdir" / ".venv" / "bin").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "docker").mkdir()
    (fixture / "workdir" / "app.py").write_text("pass\n")
    (fixture / "workdir" / ".venv" / "bin" / "python").write_text("generated\n")
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\n"
        "outcome_group: coding\n"
        "eval_image: busybox:1.36\n"
        "eval_command: ['true']\n"
    )
    (fixture / "docker" / "Dockerfile").write_text(
        "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n"
    )
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    images = tmp_path / "images.json"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, shutil, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(args) + '\\n')\n"
        "image_file = Path(os.environ['DOCKER_IMAGES'])\n"
        "image_ids = json.loads(image_file.read_text()) if image_file.exists() else {}\n"
        "if args[:2] == ['image', 'inspect']:\n"
        "    identity = image_ids.get(args[2])\n"
        "    if identity:\n"
        "        print(json.dumps({'Id': identity, 'RepoDigests': []}))\n"
        "        sys.exit(0)\n"
        "    sys.exit(1)\n"
        "if args[:1] == ['build']:\n"
        "    tag = args[args.index('--tag') + 1]\n"
        "    if os.environ.get('FAIL_DECORATOR') == '1' and 'test-resumable-campaign-opencode' in tag:\n"
        "        sys.exit(9)\n"
        "    image_ids[tag] = 'sha256:' + tag\n"
        "    image_file.write_text(json.dumps(image_ids))\n"
        "    print('built ' + tag)\n"
        "    sys.exit(0)\n"
        "if args[:1] == ['pull']:\n"
        "    image_ids[args[1]] = 'sha256:' + args[1]\n"
        "    image_file.write_text(json.dumps(image_ids))\n"
        "    sys.exit(0)\n"
        + VOLUME_TRANSFER_STUB
        + "if args[:1] == ['run']:\n"
        "    result_mount = next((arg[:-8] for arg in args if arg.endswith(':/result')), None)\n"
        "    if result_mount:\n"
        "        result_dir = volume_path(result_mount)\n"
        "        result_dir.mkdir(parents=True, exist_ok=True)\n"
        "        Path(result_dir, 'score.json').write_text(json.dumps({\n"
        "            'categories': {'check': {'points': 1, 'max_points': 1, 'evidence': ['ok']}},\n"
        "            'total': 1, 'pass_threshold': 1, 'critical_categories': ['check']}))\n"
        "    if os.environ.get('FAIL_EVALUATOR') == '1':\n"
        "        sys.exit(8)\n"
        "    sys.exit(0)\n"
        "sys.exit(0)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "campaign"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
        "DOCKER_IMAGES": str(images),
        "DOCKER_VOLUMES": str(tmp_path / "volumes.txt"),
    }
    (tmp_path / ".env").write_text(
        "EXPERIMENT_LLM_BASE_URL=http://model/v1\n"
        "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY=markdown_synthesis\n"
        "JUDGE_MODEL=judge-a\n"
    )
    try:
        first = _run_controlled(output, fixture_name, "tinycua", env, cwd=tmp_path)
        first_calls = [json.loads(line) for line in calls.read_text().splitlines()]
        second = _run_controlled(
            output,
            fixture_name,
            "opencode",
            env,
            cwd=tmp_path,
            order_by="agent",
        )
        second_calls = [json.loads(line) for line in calls.read_text().splitlines()]

        assert first.returncode == second.returncode == 0
        metadata = json.loads((output / "run_metadata.json").read_text())
        assert metadata["schema_version"] == 2
        UUID(metadata["campaign_id"])
        assert metadata["selected_agents"] == ["opencode", "tinycua"]
        assert metadata["pairs"] == [
            {"fixture": fixture_name, "agent": "opencode"},
            {"fixture": fixture_name, "agent": "tinycua"},
        ]
        assert len(metadata["invocations"]) == 2
        assert [
            invocation["order_by"] for invocation in metadata["invocations"]
        ] == ["fixture", "agent"]
        assert all(
            set(invocation) >= {"ended_at", "status", "exit_code"}
            for invocation in metadata["invocations"]
        )
        outcomes = json.loads((output / "outcomes.json").read_text())
        assert set(outcomes["coding"][fixture_name]) == {"opencode", "tinycua"}
        assert set(path.name for path in output.iterdir()) == {
            "run_metadata.json",
            "outcomes.json",
            "stdout.log",
            "stderr.log",
            fixture_name,
        }
        for agent in ("opencode", "tinycua"):
            pair = output / fixture_name / agent
            assert set(path.name for path in pair.iterdir()) == {
                "result.json",
                "stdout.log",
                "stderr.log",
                "environment.json",
                "workdir",
            }
            assert (pair / "workdir" / "app.py").is_file()
            assert not (pair / "workdir" / ".venv").exists()

        tinycua_state = (
            f"tinycua-template-{metadata['campaign_id']}-"
            f"{fixture_name.encode().hex()}-{b'tinycua'.hex()}"
        )
        assert sum(
            command == ["volume", "rm", "--force", tinycua_state]
            for command in first_calls
        ) == 2
        assert not any(tinycua_state in command for command in second_calls[len(first_calls) :])

        complete_calls = len(second_calls)
        skipped = _run_controlled(
            output, fixture_name, "opencode", env, cwd=tmp_path
        )
        assert skipped.returncode == 0
        assert len(calls.read_text().splitlines()) == complete_calls

        result_path = output / fixture_name / "opencode" / "result.json"
        old_opencode = result_path.read_bytes()
        tinycua_result = output / fixture_name / "tinycua" / "result.json"
        old_tinycua = tinycua_result.read_bytes()
        replacement = _run_controlled(
            output,
            fixture_name,
            "opencode",
            env,
            cwd=tmp_path,
            overwrite=True,
        )
        assert replacement.returncode == 0
        assert result_path.read_bytes() != old_opencode
        assert tinycua_result.read_bytes() == old_tinycua
        assert not list((output / fixture_name).glob(".opencode.*"))
        complete_calls = len(calls.read_text().splitlines())

        failed_result = json.loads(result_path.read_text())
        failed_result.update(
            {
                "passed": False,
                "status": "failed",
                "evaluator_outcome": "failed",
                "evaluator_exit_code": 1,
            }
        )
        result_path.write_text(json.dumps(failed_result))
        skipped_failure = _run_controlled(
            output, fixture_name, "opencode", env, cwd=tmp_path
        )
        assert skipped_failure.returncode == 1
        assert len(calls.read_text().splitlines()) == complete_calls

        result_path.unlink()
        (result_path.parent / "partial.tmp").write_text("interrupted")
        rerun = _run_controlled(output, fixture_name, "opencode", env, cwd=tmp_path)
        assert rerun.returncode == 0
        rerun_calls = [json.loads(line) for line in calls.read_text().splitlines()][
            complete_calls:
        ]
        assert not any(command[:1] == ["build"] for command in rerun_calls)
        assert not (result_path.parent / "partial.tmp").exists()
        assert result_path.is_file()
        assert [command for command in first_calls if command[:1] == ["pull"]] == [
            ["pull", "busybox:1.36"]
        ]

        old_result = result_path.read_bytes()
        previous = result_path.parent.with_name(".opencode.previous")
        staging = result_path.parent.with_name(".opencode.staging")
        tinycua_previous = tinycua_result.parent.with_name(".tinycua.previous")
        result_path.parent.replace(previous)
        tinycua_result.parent.replace(tinycua_previous)
        staging.mkdir()
        (staging / "partial.tmp").write_text("interrupted replacement")
        image_ids = json.loads(images.read_text())
        external_id = image_ids.pop("busybox:1.36")
        images.write_text(json.dumps(image_ids))
        before_recovery = len(calls.read_text().splitlines())

        recovered = _run_controlled(
            output, fixture_name, "opencode", env, cwd=tmp_path
        )

        recovery_calls = [
            json.loads(line)
            for line in calls.read_text().splitlines()[before_recovery:]
        ]
        assert recovered.returncode == 0
        assert result_path.read_bytes() == old_result
        assert tinycua_result.is_file()
        assert not previous.exists()
        assert not tinycua_previous.exists()
        assert not staging.exists()
        assert not any(
            command[:1] == ["compose"] and "run" in command
            for command in recovery_calls
        )
        image_ids["busybox:1.36"] = external_id
        images.write_text(json.dumps(image_ids))

        before_mismatch = len(calls.read_text().splitlines())
        (tmp_path / ".env").write_text(
            "EXPERIMENT_LLM_BASE_URL=http://model/v1\n"
            "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY=markdown_synthesis\n"
            "JUDGE_MODEL=judge-b\n"
        )
        judge_only = _run_controlled(
            output, fixture_name, "opencode", env, cwd=tmp_path
        )
        assert judge_only.returncode == 0
        assert len(calls.read_text().splitlines()) == before_mismatch

        (tmp_path / ".env").write_text(
            "EXPERIMENT_LLM_BASE_URL=http://different-model/v1\n"
            "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY=markdown_synthesis\n"
            "JUDGE_MODEL=judge-b\n"
        )
        mismatch = _run_controlled(
            output, fixture_name, "opencode", env, cwd=tmp_path, overwrite=True
        )
        assert mismatch.returncode == 2
        assert "model_settings" in mismatch.stderr
        assert len(calls.read_text().splitlines()) == before_mismatch
        assert result_path.is_file()

        (tmp_path / ".env").write_text(
            "EXPERIMENT_LLM_BASE_URL=http://model/v1\n"
            "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY=full_replay\n"
            "JUDGE_MODEL=judge-b\n"
        )
        recovery_mismatch = _run_controlled(
            output, fixture_name, "opencode", env, cwd=tmp_path, overwrite=True
        )
        assert recovery_mismatch.returncode == 2
        assert len(calls.read_text().splitlines()) == before_mismatch

        (tmp_path / ".env").write_text(
            "EXPERIMENT_LLM_BASE_URL=http://model/v1\n"
            "EXPERIMENT_TINYCUA_RECOVERY_STRATEGY=markdown_synthesis\n"
            "JUDGE_MODEL=judge-b\n"
        )
        image_ids = json.loads(images.read_text())
        external_id = image_ids.pop("busybox:1.36")
        images.write_text(json.dumps(image_ids))
        old_result_before_image_failure = result_path.read_bytes()

        unavailable_image = _run_controlled(
            output,
            fixture_name,
            "opencode",
            env,
            cwd=tmp_path,
            overwrite=True,
        )

        assert unavailable_image.returncode == 2
        assert result_path.read_bytes() == old_result_before_image_failure
        assert not list((output / fixture_name).glob(".opencode.*"))
        image_ids["busybox:1.36"] = external_id
        images.write_text(json.dumps(image_ids))

        old_pair_before_execution_failure = {
            path.relative_to(result_path.parent): path.read_bytes()
            for path in result_path.parent.rglob("*")
            if path.is_file()
        }
        execution_failure = _run_controlled(
            output,
            fixture_name,
            "opencode",
            env | {"FAIL_EVALUATOR": "1"},
            cwd=tmp_path,
            overwrite=True,
        )
        assert execution_failure.returncode == 1
        assert old_pair_before_execution_failure == {
            path.relative_to(result_path.parent): path.read_bytes()
            for path in result_path.parent.rglob("*")
            if path.is_file()
        }
        assert not list((output / fixture_name).glob(".opencode.*"))

        image_ids.pop(f"tinycua-template-{fixture_name}-opencode")
        images.write_text(json.dumps(image_ids))
        old_pair = {
            path.relative_to(result_path.parent): path.read_bytes()
            for path in result_path.parent.rglob("*")
            if path.is_file()
        }

        overwrite_failure = _run_controlled(
            output,
            fixture_name,
            "opencode",
            env | {"FAIL_DECORATOR": "1"},
            cwd=tmp_path,
            overwrite=True,
        )

        assert overwrite_failure.returncode == 1
        assert old_pair == {
            path.relative_to(result_path.parent): path.read_bytes()
            for path in result_path.parent.rglob("*")
            if path.is_file()
        }
        assert not list((output / fixture_name).glob(".opencode.*"))
        final_metadata = json.loads((output / "run_metadata.json").read_text())
        assert final_metadata["invocations"][-1]["status"] == "failed"
        assert final_metadata["invocations"][-1]["exit_code"] == 1
        assert all(
            set(invocation) >= {"ended_at", "status", "exit_code"}
            for invocation in final_metadata["invocations"]
        )
    finally:
        shutil.rmtree(fixture)


def test_controlled_campaign_upgrades_valid_schema_v1_metadata(tmp_path: Path) -> None:
    """A real legacy layout is compacted once without rerunning its pair."""
    fixture_name = "test-campaign-v1"
    fixture = FIXTURES / fixture_name
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Reply.\neval_image: busybox:1.36\neval_command: ['true']\n"
    )
    output = tmp_path / "campaign"
    run_root = output / fixture_name / "tinycua"
    (run_root / "workdir" / ".venv" / "bin").mkdir(parents=True)
    (run_root / "workdir" / "answer.txt").write_text("done\n")
    (run_root / "workdir" / ".venv" / "bin" / "python").write_text("cache\n")
    (run_root / "agent.stdout.log").write_text("legacy answer\n")
    (run_root / "agent.stderr.log").write_text("legacy agent warning\n")
    (run_root / "eval.stdout.log").write_text("legacy evaluator output\n")
    (run_root / "eval.stderr.log").write_text("")
    (run_root / "workspace-seed.stdout.log").write_text("legacy transfer\n")
    (run_root / "workspace-seed.stderr.log").write_text("")
    (run_root / "container_environment.json").write_text(
        json.dumps({"EXPERIMENT_PROMPT": "Reply."})
    )
    (run_root / "evaluator-result").mkdir()
    score = {
        "categories": {
            "check": {"points": 1, "max_points": 1, "evidence": ["ok"]}
        },
        "total": 1,
        "pass_threshold": 1,
        "critical_categories": ["check"],
    }
    (run_root / "evaluator-result" / "score.json").write_text(json.dumps(score))
    (run_root / "result.json").write_text(
        json.dumps(
            {
                "fixture": fixture_name,
                "agent": "tinycua",
                "state_volume": "legacy-state",
                "started_at": "2026-07-01T00:00:00+00:00",
                "ended_at": "2026-07-01T00:00:01+00:00",
                "elapsed_prompt_to_finish_seconds": 1.0,
                "stdout_path": "agent.stdout.log",
                "stderr_path": "agent.stderr.log",
                "agent_exit_code": 0,
                "sanitized_environment": "container_environment.json",
                "evaluator_exit_code": 0,
                "evaluator_outcome": "passed",
                "passed": True,
                "score": score,
            }
        )
    )
    output.mkdir(exist_ok=True)
    (output / "tinycua-build.stdout.log").write_text("legacy build output\n")
    (output / "tinycua-build.stderr.log").write_text("")
    (tmp_path / ".env").write_text("JUDGE_MODEL=ignored\n")
    _, effective_environment = runner._agent_compose_environments(
        tmp_path / ".env", ""
    )
    (output / "run_metadata.json").write_text(
        json.dumps(
            {
                "result_generation_commit": "legacy-commit",
                "working_tree_dirty": False,
                "selected_fixtures": [fixture_name],
                "selected_agents": ["tinycua"],
                "agent_configurations": {
                    "tinycua": {
                        "service": "tinycua",
                        "no_digest": False,
                        "no_review": False,
                    }
                },
                "fixtures": {
                    fixture_name: {
                        "outcome_group": "coding",
                        "fixture_revision": runner.tree_revision(fixture),
                        "evaluator_revision": runner.tree_revision(fixture / "eval"),
                    }
                },
                "images": {
                    "harnesses": {},
                    "evaluators": {},
                    "candidates": {},
                },
                "harness_versions": {},
                "model_settings": runner._model_settings(effective_environment),
                "sampling_settings": {
                    "temperature": None,
                    "top_p": None,
                    "seed": None,
                },
                "timeout_seconds": 14_400,
                "trial_policy": runner.TRIAL_POLICY,
                "overwrite": False,
                "state_reset_on_overwrite": False,
            }
        )
    )
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    docker.write_text(
        "#!/bin/sh\n"
        f"touch '{calls}'\n"
        "exit 99\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"}
    try:
        resumed = _run_controlled(
            output, fixture_name, "tinycua", env, cwd=tmp_path
        )

        metadata_path = output / "run_metadata.json"
        upgraded = json.loads(metadata_path.read_text())
        pair_result = json.loads((run_root / "result.json").read_text())
        assert resumed.returncode == 0
        assert upgraded["schema_version"] == 2
        UUID(upgraded["campaign_id"])
        assert upgraded["pairs"] == [{"fixture": fixture_name, "agent": "tinycua"}]
        assert upgraded["invocations"][-1]["agents"] == ["tinycua"]
        assert upgraded["invocations"][-1]["status"] == "passed"
        assert not calls.exists()
        assert set(path.name for path in output.iterdir()) == {
            "run_metadata.json",
            "outcomes.json",
            "stdout.log",
            "stderr.log",
            fixture_name,
        }
        assert set(path.name for path in run_root.iterdir()) == {
            "result.json",
            "stdout.log",
            "stderr.log",
            "environment.json",
            "workdir",
        }
        assert "legacy build output" in (output / "stdout.log").read_text()
        assert "legacy answer" in (run_root / "stdout.log").read_text()
        assert "legacy evaluator output" in (run_root / "stdout.log").read_text()
        assert not (run_root / "workdir" / ".venv").exists()
        assert pair_result["schema_version"] == 2
        assert pair_result["stdout_path"] == "stdout.log"
        assert pair_result["sanitized_environment"] == "environment.json"
        first_stdout = (run_root / "stdout.log").read_text()

        resumed_again = _run_controlled(
            output, fixture_name, "tinycua", env, cwd=tmp_path
        )

        assert resumed_again.returncode == 0
        assert (run_root / "stdout.log").read_text() == first_stdout
        assert not calls.exists()
    finally:
        shutil.rmtree(fixture)


def test_controlled_campaign_rejects_pair_dirs_without_metadata(tmp_path: Path) -> None:
    """An ambiguous result root fails before invoking Docker."""
    output = tmp_path / "campaign"
    (output / "smoke-test" / "tinycua").mkdir(parents=True)
    docker = tmp_path / "docker"
    marker = tmp_path / "docker-called"
    docker.write_text(
        "#!/bin/sh\n"
        f"touch '{marker}'\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    env = os.environ | {"PATH": f"{tmp_path}:{os.environ['PATH']}"}

    completed = _run_controlled(output, "smoke-test", "tinycua", env)

    assert completed.returncode == 2
    assert "run_metadata.json" in completed.stderr
    assert not marker.exists()


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


@pytest.mark.parametrize(
    (
        "angle_offset",
        "time_source",
        "expected_exit_code",
        "expected_second",
        "expected_hour_update",
    ),
    (
        (0, "new Date()", 0, 1, 1),
        (90, "new Date()", 1, 0, 0),
        (0, "fixedNow", 1, 0, 0),
    ),
    ids=("upright_clock", "clock_rotated_clockwise", "static_clock"),
)
def test_clock_evaluator_browser_executes_time_derived_hands(
    tmp_path: Path,
    angle_offset: int,
    time_source: str,
    expected_exit_code: int,
    expected_second: int,
    expected_hour_update: int,
) -> None:
    """The evaluator tracks each upright hand across browser time samples."""
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
  const radians = (angle + ANGLE_OFFSET) * Math.PI / 180;
  context.beginPath();
  context.moveTo(150, 150);
  context.lineTo(150 + Math.sin(radians) * length, 150 - Math.cos(radians) * length);
  context.stroke();
}
const fixedNow = new Date();
function draw() {
  const now = TIME_SOURCE;
  context.clearRect(0, 0, 300, 300);
  hand(now.getSeconds() * 6, 120);
  hand(now.getMinutes() * 6, 100);
  hand((now.getHours() % 12) * 30, 70);
}
draw();
setInterval(draw, 1000);
</script></body></html>"""
        .replace("ANGLE_OFFSET", str(angle_offset))
        .replace("TIME_SOURCE", time_source)
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
    assert completed.returncode == expected_exit_code, completed.stderr
    assert score["categories"]["second_hand"]["points"] == expected_second
    assert score["categories"]["hour_updates_clockwise"]["points"] == expected_hour_update
    if expected_exit_code == 0:
        assert score["total"] == len(score["categories"])
        assert set(score["critical_categories"]) == set(score["categories"])


def test_research_evaluator_accepts_model_name_variants(
    tmp_path: Path,
) -> None:
    """Research relevancy accepts natural model-name formatting variants."""
    fixture = FIXTURES / "experiment-2"
    cases = (
        ("exact-hyphen", "GPT-5.6-Sol"),
        ("missing-model", ""),
        ("all-spaces", "GPT 5.6 Sol"),
        ("mixed-sep", "GPT-5.6 Sol"),
        ("no-claude-opus", "Opus 4.8"),
        ("no-claude-fable", "Fable 5"),
        ("trailing-period", "Claude Fable 5."),
        ("all-spaces-terra", "GPT 5.6 Terra"),
    )
    for name, model in cases:
        submission = tmp_path / name
        submission.mkdir()
        shutil.copy(fixture / "workdir" / "TASK.md", submission / "TASK.md")
        (submission / "report.md").write_text(
            f"# Frontier LLM Report\n\n{model}\n"
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
            "python /eval/check.py /cases/exact-hyphen "
            "/cases/exact-hyphen-result || true; "
            "python /eval/check.py /cases/missing-model "
            "/cases/missing-model-result || true; "
            "python /eval/check.py /cases/all-spaces "
            "/cases/all-spaces-result || true; "
            "python /eval/check.py /cases/mixed-sep "
            "/cases/mixed-sep-result || true; "
            "python /eval/check.py /cases/no-claude-opus "
            "/cases/no-claude-opus-result || true; "
            "python /eval/check.py /cases/no-claude-fable "
            "/cases/no-claude-fable-result || true; "
            "python /eval/check.py /cases/trailing-period "
            "/cases/trailing-period-result || true; "
            "python /eval/check.py /cases/all-spaces-terra "
            "/cases/all-spaces-terra-result || true",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr

    def score(name: str) -> dict[str, object]:
        return json.loads(
            (tmp_path / f"{name}-result" / "score.json").read_text()
        )

    assert "model_relevancy" in score("exact-hyphen")["critical_categories"]
    assert score("exact-hyphen")["categories"]["model_relevancy"]["points"] == 1
    assert score("missing-model")["categories"]["model_relevancy"]["points"] == 0
    for variant in (
        "all-spaces",
        "mixed-sep",
        "no-claude-opus",
        "no-claude-fable",
        "trailing-period",
        "all-spaces-terra",
    ):
        assert score(variant)["categories"]["model_relevancy"]["points"] == 1, (
            f"variant '{variant}' should pass model_relevancy"
        )
    assert 0 <= score("exact-hyphen")["metrics"]["rouge_l_f1"] <= 100
    assert 0 <= score("exact-hyphen")["metrics"]["bleu"] <= 100


def test_experiment_four_leaves_startup_and_dependencies_to_the_submission() -> None:
    """The free-form fixture provides no implementation-specific launcher."""
    fixture = FIXTURES / "experiment-4"
    task = (fixture / "workdir" / "TASK.md").read_text()

    assert not (fixture / "workdir" / "run.sh").exists()
    assert not (fixture / "workdir" / "pyproject.toml").exists()
    assert "root `start.sh`" in task
    assert "`start.sh` owns dependency installation" in task


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
        "args = sys.argv[1:]\n"
        + IMAGE_INSPECT_STUB
            + VOLUME_TRANSFER_STUB
            + "if args[:1] == ['run']:\n"
            "    time.sleep(1)\n"
            "    sys.exit(int(os.environ['EVALUATOR_CODE']))\n"
            "if args[:2] == ['compose', 'up']:\n"
            "    sys.exit(0)\n"
            "if args[:1] == ['compose']:\n"
        "    print('agent-only-output')\n"
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
    resolved_eval_image = f"{eval_image}-test-controlled-runner"
    assert commands.pop(0) == SEARXNG_READY_COMMAND
    assert commands[0][:2] == ["build", "--tag"]
    assert commands[1][:3] == ["build", "--tag", "tinycua-template-tinycua-base"]
    assert commands[2][:4] == [
        "build",
        "--provenance=false",
        "--tag",
        resolved_eval_image,
    ]
    assert commands[3][:2] == ["build", "--provenance=false"]
    agent = next(command for command in commands if command[:1] == ["compose"])
    evaluator = next(command for command in commands if command[:1] == ["run"])
    transfers = [command for command in commands if command[:1] == ["cp"]]
    assert len(transfers) == 4
    assert commands.index(agent) < commands.index(evaluator)
    assert (
        len(
            [
                command
                for command in commands
                if command[:3] == ["volume", "rm", "--force"]
            ]
        )
        == 6
    )
    assert str(
        output / "test-controlled-runner" / "opencode" / "workdir"
    ) not in " ".join(agent)
    assert agent[0] == "compose"
    assert "eval" not in " ".join(agent)
    assert evaluator[0] == "run"
    assert any(mount.endswith(":/submission:ro") for mount in evaluator)
    assert any(mount.endswith("-evaluator-input:/eval:ro") for mount in evaluator)
    assert any(
        mount.endswith("-evaluator-input:/agent-output:ro") for mount in evaluator
    )
    assert any(mount.endswith("-evaluator-result:/result") for mount in evaluator)
    assert str(output) not in " ".join(evaluator)
    assert evaluator[-(len(eval_command) + 1) :] == [
        resolved_eval_image,
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
    assert pair_result["schema_version"] == 2
    assert pair_result["stdout_path"] == "stdout.log"
    assert pair_result["stderr_path"] == "stderr.log"
    assert pair_result["sanitized_environment"] == "environment.json"
    assert (run_root / pair_result["sanitized_environment"]).is_file()
    assert "=== agent ===\nagent-only-output\n" in (
        run_root / "stdout.log"
    ).read_text()
    assert not (run_root / ".agent.stdout.log").exists()
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
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        + IMAGE_INSPECT_STUB
        + "if args[:1] == ['build'] and 'tinycua-template-test-fixture-build-failure-opencode' in args:\n"
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
    assert (run_root / "workdir").is_dir()
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
        "args = sys.argv[1:]\n"
        + IMAGE_INSPECT_STUB
        + VOLUME_TRANSFER_STUB
        + "if args[:1] == ['run']:\n"
        "    result = next(arg[:-8] for arg in args if arg.endswith(':/result'))\n"
        "    result_dir = volume_path(result)\n"
        "    result_dir.mkdir(parents=True, exist_ok=True)\n"
        "    Path(result_dir, 'score.json').write_text(json.dumps({\n"
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
        + IMAGE_INSPECT_STUB
        + "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
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
    assert "=== submission-build ===\nsubmission build output\n" in (
        run_root / "stdout.log"
    ).read_text()
    assert "=== submission-build ===\nsubmission build error\n" in (
        run_root / "stderr.log"
    ).read_text()
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
        + IMAGE_INSPECT_STUB
        + "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
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
        in (run_root / "stderr.log").read_text()
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
        "args = sys.argv[1:]\n"
        + IMAGE_INSPECT_STUB
        + "mode = os.environ['TIMEOUT_MODE']\n"
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
    assert "Timed out after 1 seconds" in (run_root / "stderr.log").read_text()
    assert secret not in (run_root / "stdout.log").read_text()
    assert secret not in (run_root / "stderr.log").read_text()
    commands = [
        json.loads(line)
        for line in (tmp_path / "calls.jsonl").read_text().splitlines()
    ]
    assert commands.pop(0) == SEARXNG_READY_COMMAND
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


def test_evaluator_timeout_cleanup_failure_stops_before_later_pairs(
    tmp_path: Path,
) -> None:
    """Unsafe evaluator cleanup is retained in the result and halts the campaign."""
    fixture_name = "test-evaluator-cleanup-stop"
    fixture = FIXTURES / fixture_name
    (fixture / "workdir").mkdir(parents=True)
    (fixture / "eval").mkdir()
    (fixture / "manifest.yaml").write_text(
        "prompt: Make the change.\neval_image: busybox\neval_command: ['true']\n"
    )
    docker = tmp_path / "docker"
    calls = tmp_path / "calls.jsonl"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, shutil, sys, time\n"
        "from pathlib import Path\n"
        "with open(os.environ['DOCKER_CALLS'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['image', 'inspect']:\n"
        "    print(json.dumps({'Id': 'sha256:' + args[2], 'RepoDigests': []}))\n"
        "    sys.exit(0)\n"
        + VOLUME_TRANSFER_STUB
        + "if args[:1] == ['run']:\n"
        "    time.sleep(2)\n"
        "if args[:2] == ['rm', '--force'] and '-evaluator-' in args[2] "
        "and '-evaluator-input-' not in args[2] and '-evaluator-result-' not in args[2]:\n"
        "    sys.exit(1)\n"
        "sys.exit(0)\n"
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    output = tmp_path / "campaign"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DOCKER_CALLS": str(calls),
        "DOCKER_VOLUMES": str(tmp_path / "volumes"),
    }
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run_template_experiment.py"),
                "--fixtures",
                fixture_name,
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

    result = json.loads(
        (output / fixture_name / "opencode" / "result.json").read_text()
    )
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    agent_runs = [
        command
        for command in commands
        if command[:1] == ["compose"] and "run" in command
    ]
    assert completed.returncode == 1
    assert result["evaluator_exit_code"] == 124
    assert result["failure_stage"] == "evaluator_cleanup"
    assert len(agent_runs) == 1
    assert agent_runs[0][-1] == "opencode"


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
        "args = sys.argv[1:]\n"
        + IMAGE_INSPECT_STUB
        + "if sys.argv[1:3] == ['rm', '--force'] and 'workspace-' not in sys.argv[3]:\n"
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
    assert commands.pop(0) == SEARXNG_READY_COMMAND
    assert result.returncode == 1
    assert result_json["agent_exit_code"] == 124
    assert result_json["evaluator_exit_code"] == 125
    assert result_json["passed"] is False
    assert "cleanup" in (run_root / "stderr.log").read_text().lower()
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
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        + IMAGE_INSPECT_STUB
        + "if sys.argv[1:2] in (['compose'], ['run']):\n"
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
