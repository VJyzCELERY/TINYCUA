"""Pytest entry point for the architecture verification gate.

Parameterized tests that run the verification gate against a local LLM.
Tests are marked with @pytest.mark.integration and skip when the LLM
server is unreachable.
"""

from __future__ import annotations

import json
import os

import pytest

from tests.verification.config import GateConfig
from tests.verification.gate import VerificationGate
from tests.verification.paths import ALL_PATHS, list_paths
from tests.verification.reporter import ReportGenerator


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def gate_config() -> GateConfig:
    """Create GateConfig from environment variables."""
    return GateConfig.from_env()


@pytest.fixture(scope="module")
def gate(gate_config: GateConfig) -> VerificationGate:
    """Create a VerificationGate instance."""
    return VerificationGate(config=gate_config)


# ── Individual Path Tests ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path_def",
    ALL_PATHS,
    ids=[p.name for p in ALL_PATHS],
)
def test_gate_individual_path(gate: VerificationGate, path_def):
    """Verify a single path can be run by name."""
    result = gate.run_path(path_def.name)
    assert result.path_name == path_def.name
    assert result.status in ("pass", "fail", "timeout", "error")
    assert result.duration_seconds >= 0


# ── Aggregate Tests ──────────────────────────────────────────────────────


@pytest.mark.timeout(600)
def test_gate_all_paths_pass(gate: VerificationGate):
    """Verify all 12 architecture paths pass against local LLM."""
    if os.environ.get("TINYCUA_STRICT_VERIFICATION") != "1":
        pytest.skip("Set TINYCUA_STRICT_VERIFICATION=1 for live all-path gate")
    report = gate.run_all()
    assert report.overall_status == "pass"
    assert report.passed == 12
    assert report.failed == 0
    assert report.total_paths == 12


@pytest.mark.timeout(600)
def test_gate_report_json_output(gate: VerificationGate):
    """Verify JSON report is well-formed and contains all fields."""
    report = gate.run_all()
    json_output = ReportGenerator().generate_json(report)
    data = json.loads(json_output)
    assert "overall_status" in data
    assert "path_results" in data
    assert len(data["path_results"]) == 12
    assert "passed" in data
    assert "failed" in data
    assert "timed_out" in data
    assert "timestamp" in data
    assert "llm_model" in data


@pytest.mark.timeout(600)
def test_gate_human_readable_summary(gate: VerificationGate):
    """Verify human-readable summary is generated."""
    report = gate.run_all()
    summary = ReportGenerator().generate_summary(report)
    assert len(summary) > 0
    assert "PASS" in summary or "FAIL" in summary


def test_gate_paths_capture_llm_interaction_logs(gate: VerificationGate):
    """Verify paths capture LLM interaction logs.

    Per design.md:346-347, interaction logs are captured for all paths
    to enable post-hoc analysis even for passing paths.
    """
    result = gate.run_path("passthrough_simple")
    # The result should have node outputs (LLM interactions are captured
    # in the session's chat_history, which is reflected in node_outputs)
    assert result.node_outputs is not None


def test_gate_timeout_handling(gate_config: GateConfig):
    """Verify per-path timeouts are respected."""
    config = GateConfig.from_env()
    config.default_timeout_seconds = 1  # Very short timeout
    gate = VerificationGate(config=config)
    # This should timeout or pass quickly
    result = gate.run_path("passthrough_simple")
    assert result.status in ("pass", "timeout")


def test_gate_llm_unavailable_fails_gracefully(gate_config: GateConfig):
    """Verify gate fails gracefully when LLM endpoint is unreachable."""
    from tinycua.config.local_model import LocalModelConfig

    config = GateConfig(
        local_model_config=LocalModelConfig(
            base_url="http://localhost:99999/v1",
            model="nonexistent-model",
            api_key="not-needed",
        ),
    )
    gate = VerificationGate(config=config)
    report = gate.run_all()
    assert report.overall_status == "fail"
    assert report.failed > 0 or report.errored > 0


def test_gate_path_count():
    """Verify exactly 12 paths are defined."""
    assert len(ALL_PATHS) == 12
    assert len(list_paths()) == 12
