"""Main gate orchestrator for architecture verification.

Runs all 12 architecture paths and produces an aggregate pass/fail verdict.
Single entry point for the verification gate.
"""

from __future__ import annotations

import logging

from tests.verification.config import GateConfig
from tests.verification.executor import PathExecutor
from tests.verification.paths import ALL_PATHS, ArchitecturePath, get_path
from tests.verification.reporter import (
    PathResult,
    VerificationReport,
    build_report,
    create_error_result,
)

logger = logging.getLogger(__name__)


class VerificationGate:
    """Main orchestrator for architecture verification.

    Runs all paths (or selected paths) against a local LLM and produces
    an aggregate pass/fail verdict with detailed per-path results.
    """

    def __init__(self, config: GateConfig) -> None:
        """Initialize with LLM endpoint and timeout configuration.

        Args:
            config: Verification gate configuration.
        """
        self._config = config
        self._executor = PathExecutor(config)

    def run_all(self) -> VerificationReport:
        """Run all 12 paths and produce aggregate report.

        Executes paths sequentially, captures results, and produces
        a VerificationReport with overall pass/fail status.

        Returns:
            VerificationReport with all path results.
        """
        logger.info("Starting verification gate — running all 12 paths")
        path_results: list[PathResult] = []

        for path in ALL_PATHS:
            logger.info("Executing path: %s", path.name)
            try:
                result = self._executor.execute(path)
                path_results.append(result)
                logger.info(
                    "Path '%s' completed with status: %s (%.1fs)",
                    path.name,
                    result.status,
                    result.duration_seconds,
                )
            except Exception as e:
                logger.error("Path '%s' raised unexpected exception: %s", path.name, e)
                path_results.append(create_error_result(path.name, e))

        report = build_report(path_results, self._config.model_name)
        logger.info(
            "Verification gate complete: %s (passed=%d, failed=%d, "
            "timed_out=%d, errored=%d)",
            report.overall_status.upper(),
            report.passed,
            report.failed,
            report.timed_out,
            report.errored,
        )
        return report

    def run_path(self, path_name: str) -> PathResult:
        """Run a single path by name.

        Args:
            path_name: The name of the path to execute.

        Returns:
            PathResult for the executed path.

        Raises:
            KeyError: If no path with the given name exists.
        """
        path = get_path(path_name)
        logger.info("Executing single path: %s", path.name)
        return self._executor.execute(path)

    def run_paths(self, path_names: list[str]) -> VerificationReport:
        """Run specific paths and produce report.

        Args:
            path_names: List of path names to execute.

        Returns:
            VerificationReport with results for the specified paths.

        Raises:
            KeyError: If any path name does not exist.
        """
        paths = [get_path(name) for name in path_names]
        logger.info("Running %d selected paths: %s", len(paths), path_names)

        path_results: list[PathResult] = []
        for path in paths:
            try:
                result = self._executor.execute(path)
                path_results.append(result)
            except Exception as e:
                logger.error("Path '%s' raised unexpected exception: %s", path.name, e)
                path_results.append(create_error_result(path.name, e))

        return build_report(path_results, self._config.model_name)
