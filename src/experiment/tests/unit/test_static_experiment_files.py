"""Static checks for compose and agent image setup."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_defines_four_services_and_volumes() -> None:
    """Compose defines the four harness services."""
    compose = (ROOT / "docker-compose.yml").read_text()

    for service in ["opencode", "hermes", "openclaw", "tinycua"]:
        assert f"  {service}:" in compose
        assert "env_file:\n      - .env" in compose
    assert "  searxng:" in compose
    assert "docker.io/searxng/searxng:latest" in compose
    assert "${EXPERIMENT_SEARXNG_HOST_PORT:-18080}:8080" in compose
    assert "host.docker.internal:host-gateway" in compose


def test_tinycua_dockerfile_installs_local_packages() -> None:
    """TINYCUA image uses this branch's code."""
    dockerfile = (ROOT / "docker" / "tinycua.Dockerfile").read_text()

    assert "COPY src/tinycua-sdk /app/tinycua-sdk" in dockerfile
    assert "COPY src/tinycua /app/tinycua" in dockerfile
    assert "uv pip install --no-cache-dir --system ./tinycua-sdk" in dockerfile
    assert "uv pip install --no-cache-dir --system ./tinycua" in dockerfile
    assert "tinycua run" in dockerfile
    assert "--dir" in dockerfile
    assert "EXPERIMENT_TINYCUA_NO_DIGEST" in dockerfile
    assert "EXPERIMENT_TINYCUA_NO_REVIEW" in dockerfile
    assert "--no-digest" in dockerfile
    assert "--no-review" in dockerfile


def test_agent_dockerfiles_expose_harness_commands() -> None:
    """Agent commands stay visible and fail loud."""
    expected = {
        "opencode.Dockerfile": [
            "npm install -g opencode-ai@1.18.4",
            "--pure",
            "--print-logs",
            "--thinking",
            "--dangerously-skip-permissions",
            "opencode run",
        ],
        "openclaw.Dockerfile": [
            "npm install -g openclaw@2026.7.1-2",
            r"\"profile\":\"full\"",
            "--verbose on",
            "openclaw agent",
        ],
        "hermes.Dockerfile": [
            "pip install",
            "hermes-agent==0.16.0",
            "hermes chat",
            "--verbose",
            "--yolo",
            "SEARXNG_URL",
        ],
    }

    for name, snippets in expected.items():
        text = (ROOT / "docker" / name).read_text()
        for snippet in snippets:
            assert snippet in text


def test_agent_images_share_common_cli_tools() -> None:
    """Every harness can use the same basic research and coding commands."""
    for name in ("opencode", "hermes", "openclaw", "tinycua"):
        dockerfile = (ROOT / "docker" / f"{name}.Dockerfile").read_text()
        for package in ("curl", "wget", "jq", "git", "ripgrep"):
            assert package in dockerfile


def test_harnesses_receive_searxng_config() -> None:
    """Harnesses with web search get SearXNG env/config aliases."""
    compose = (ROOT / "docker-compose.yml").read_text()
    env = (ROOT / ".env.example").read_text()
    openclaw = (ROOT / "docker" / "openclaw.Dockerfile").read_text()
    searxng_settings = (ROOT / "docker" / "searxng" / "settings.yml").read_text()

    assert "EXPERIMENT_SEARXNG_HOST_PORT=18080" in env
    assert "EXPERIMENT_SEARXNG_BASE_URL=http://searxng:8080" in env
    assert "TINYCUA_SEARXNG_URL=http://searxng:8080/search" in env
    assert (
        "SEARXNG_URL: ${EXPERIMENT_SEARXNG_BASE_URL:-http://searxng:8080}"
    ) in compose
    assert (
        "SEARXNG_BASE_URL: ${EXPERIMENT_SEARXNG_BASE_URL:-http://searxng:8080}"
    ) in compose
    assert (
        "TINYCUA_SEARXNG_URL: ${TINYCUA_SEARXNG_URL:-http://searxng:8080/search}"
    ) in compose
    assert "depends_on:" in compose
    assert "./docker/searxng/settings.yml:/etc/searxng/settings.yml:ro" in compose
    assert '\\"provider\\":\\"searxng\\"' in openclaw
    assert '\\"baseUrl\\":\\"' in openclaw
    assert "%/search" in openclaw
    assert "formats:" in searxng_settings
    assert "- json" in searxng_settings


def test_searxng_enables_broad_engine_coverage() -> None:
    """SearXNG runs enough engines that a few dead upstreams still return results."""
    import json

    settings = (ROOT / "docker" / "searxng" / "settings.yml").read_text()
    for engine in (
        "google", "bing", "brave", "duckduckgo", "startpage",
        "mojeek", "qwant", "wikipedia", "arxiv", "stackoverflow",
        "github", "bing news", "google news",
    ):
        assert f"name: {engine}" in settings, f"engine '{engine}' not enabled"
    assert "name: wikidata" in settings
    assert "enabled: false" in settings.split("name: wikidata", 1)[1].split(
        "name:", 1
    )[0], "wikidata must be disabled (403s on init)"
    _ = json  # keep import alive for the assertion surface


def test_research_fixture_hides_evaluator_models_and_snapshot_framing() -> None:
    """Experiment 2 hides evaluator data and omits snapshot/date framing."""
    import json

    fixtures = ROOT / "experiment-fixtures" / "experiments-list"
    fixture = fixtures / "experiment-2"
    evidence = json.loads((fixture / "eval" / "evidence.json").read_text())
    task = (fixture / "workdir" / "TASK.md").read_text()
    manifest = (fixture / "manifest.yaml").read_text()
    agent_visible = f"{task}\n{manifest}".lower()
    for model in evidence["models"]:
        assert model not in task, f"TASK.md leaks evaluator model name: {model}"
        assert model.lower() not in task.lower(), (
            f"TASK.md leaks evaluator model name (case-insensitive): {model}"
        )
    for marker in ("frozen", "snapshot", "22 july 2026", "2026-07-22"):
        assert marker not in agent_visible
    assert "## scope" in task.lower()
    assert "## snapshot scope" not in task.lower()

    evaluator = (fixture / "eval" / "check.py").read_text().lower()
    reference = (fixture / "eval" / "reference.md").read_text().lower()
    assert "frozen" not in evaluator
    assert "snapshot" not in evaluator
    assert "2026-07-22" not in (fixture / "eval" / "evidence.json").read_text()
    assert "22 july 2026" not in reference


def test_browser_fixtures_share_one_evaluator_image_and_toolset() -> None:
    """Clock and web-app candidates share browser evaluation and agent tools."""
    fixtures = ROOT / "experiment-fixtures" / "experiments-list"
    experiment_3 = fixtures / "experiment-3"
    experiment_4 = fixtures / "experiment-4"

    for fixture in (experiment_3, experiment_4):
        manifest = (fixture / "manifest.yaml").read_text()
        assert "eval_image: tinycua-template-browser-evaluator" in manifest
        assert "eval_dockerfile: eval/Dockerfile" in manifest
    assert (experiment_3 / "eval" / "Dockerfile").read_bytes() == (
        experiment_4 / "eval" / "Dockerfile"
    ).read_bytes()
    assert (experiment_3 / "docker" / "Dockerfile").read_bytes() == (
        experiment_4 / "docker" / "Dockerfile"
    ).read_bytes()
    for fixture in (experiment_3, experiment_4):
        workdir = fixture / "workdir"
        task = workdir / "TASK.md"
        browser = workdir / ".agent_scripts" / "browser.py"
        assert (workdir / ".agent_scripts" / "browser.sh").is_file()
        assert browser.is_file()
        assert "--click" in browser.read_text()
        assert "--click-at" in browser.read_text()
        assert "browser.sh" in task.read_text()


def test_research_fixtures_report_bleu_and_rouge_metrics() -> None:
    """Both research evaluators expose the same secondary text metrics."""
    fixtures = ROOT / "experiment-fixtures" / "experiments-list"
    for name in ("experiment-2", "experiment-5"):
        evaluator = (fixtures / name / "eval" / "check.py").read_text()
        assert '"bleu":' in evaluator
        assert '"rouge_l_f1":' in evaluator


def test_study_guide_fixture_prioritizes_content_over_fixed_outline() -> None:
    """Experiment 5 guides Markdown organization without prescribing headings."""
    fixture = ROOT / "experiment-fixtures" / "experiments-list" / "experiment-5"
    evaluator = (fixture / "eval" / "check.py").read_text()
    task = " ".join((fixture / "workdir" / "TASK.md").read_text().lower().split())
    critical = evaluator.split("CRITICAL_CATEGORIES = (", 1)[1].split(")", 1)[0]

    assert "heading names and order are your choice" in task
    assert '"organized_sections"' in critical
    for category in ("exact_title", "toc_placement", "required_chapters"):
        assert f'"{category}"' not in evaluator
    assert '"reference_coverage"' not in evaluator
    assert '"bleu":' in evaluator
    assert '"rouge_l_f1":' in evaluator


def test_web_app_fixture_uses_a_free_form_start_contract() -> None:
    """The web-app fixture scores behavior without prescribing implementation."""
    fixture = ROOT / "experiment-fixtures" / "experiments-list" / "experiment-4"
    evaluator = (fixture / "eval" / "check.py").read_text()
    task = (fixture / "workdir" / "TASK.md").read_text().lower()
    manifest = (fixture / "manifest.yaml").read_text()
    normalized_task = " ".join(task.split())

    assert "entrypoint_manages_dependencies: true" in manifest
    assert not (fixture / "workdir" / "run.sh").exists()
    assert not (fixture / "workdir" / "pyproject.toml").exists()
    assert "start.sh" in normalized_task
    assert "foreground" in normalized_task
    assert "create, edit, and delete" in normalized_task
    assert "restart" in normalized_task
    assert "app.py" not in normalized_task
    assert "`/health`" not in task
    assert "`/blocks`" not in task
    assert "#block-text" not in task
    assert "#add-block" not in task
    assert "start.sh" in evaluator
    assert "os.killpg(server.process.pid" in evaluator
    assert '"/blocks"' not in evaluator
    assert '"/health"' not in evaluator
    assert "ruff" not in evaluator
    assert "coverage" not in evaluator


def test_all_fixtures_share_ignored_agent_scripts() -> None:
    """Every fixture gives agents identical helpers that evaluators ignore."""
    fixtures = ROOT / "experiment-fixtures" / "experiments-list"
    scripts = []
    readmes = []
    for name in (*(f"experiment-{number}" for number in range(1, 6)), "smoke-test"):
        scripts_dir = fixtures / name / "workdir" / ".agent_scripts"
        scripts.append((scripts_dir / "search.sh").read_bytes())
        readmes.append((scripts_dir / "README.md").read_bytes())
    for number in range(2, 6):
        task = (fixtures / f"experiment-{number}" / "workdir" / "TASK.md").read_text()
        assert 'sh .agent_scripts/search.sh "query"' in task
        assert "curl" in task
    assert len(set(scripts)) == 1
    assert len(set(readmes)) == 1
    assert b"SEARXNG_URL" in scripts[0]
    assert b"curl" in scripts[0]
    assert b"jq" in scripts[0]
    evaluator = (fixtures / "experiment-4" / "eval" / "check.py").read_text()
    assert '".agent_scripts"' in evaluator
    assert '".venv"' in evaluator


def test_helper_scripts_wrap_setup_and_runner() -> None:
    """Shell helpers keep common commands one step."""
    setup = (ROOT / "scripts" / "setup.sh").read_text()
    run = (ROOT / "scripts" / "run.sh").read_text()

    assert "cp .env.example .env" in setup
    assert "docker compose build" in setup
    assert "docker compose pull searxng" in setup
    assert "docker pull python:3.12-alpine" in setup
    assert "uv run python" in run
    assert "run_experiment.py" in run
    assert "--num" in run
    assert "--prompt" in run


def test_semantic_judge_profile_exists_and_documents_qualitative_role() -> None:
    """The semantic judge profile exists with the expected files and role."""
    profile_dir = ROOT / "judge" / "profiles" / "semantic"
    assert (profile_dir / "SOUL.md").is_file()
    assert (profile_dir / "config.yaml").is_file()
    assert (profile_dir / "profile.yaml").is_file()
    soul = (profile_dir / "SOUL.md").read_text().lower()
    # Illustrative category types guide the judge without fixing a menu.
    for marker in ("qualitative", "category", "strength", "weakness"):
        assert marker in soul


def test_judge_py_exposes_semantic_mode_and_legacy_unchanged() -> None:
    """judge.py defines semantic helpers and keeps legacy --num mode."""
    import inspect

    from judge import (
        build_cross_judge_prompt,
        build_judge_prompt,
        build_semantic_judge_prompt,
        discover_submissions,
        semantic_judge_fixture,
    )

    # Legacy helpers keep their signatures.
    assert "task_prompt" in inspect.signature(build_judge_prompt).parameters
    assert "submissions" in inspect.signature(build_cross_judge_prompt).parameters
    # New semantic helpers are callable with the documented parameters.
    assert "submissions" in inspect.signature(build_semantic_judge_prompt).parameters
    assert "fixture_name" in inspect.signature(discover_submissions).parameters
    assert "output_root" in inspect.signature(discover_submissions).parameters
    assert "fixture_name" in inspect.signature(semantic_judge_fixture).parameters

    judge_src = (ROOT / "judge.py").read_text()
    assert "--fixture" in judge_src
    assert "--num" in judge_src
    # Legacy prose rubric still in judge/profiles/judge/SOUL.md.
    legacy_soul = (
        ROOT / "judge" / "profiles" / "judge" / "SOUL.md"
    ).read_text()
    assert "Task Completion" in legacy_soul
    assert "Correctness" in legacy_soul
