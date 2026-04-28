"""Test Runner for Integration Tests.

This script runs all integration tests and provides a summary.

Usage:
    python tests/run_integration_tests.py
"""

import pytest
import sys
import os
import logging


def run_tests():
    """Run all integration tests."""
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_package = os.path.join(test_dir, "integration")

    # Run tests
    exit_code = pytest.main(
        [
            test_package,
            "-v",
            "--tb=short",
            "--color=yes",
            "--log-cli-level=INFO",
            "--log-cli-format=%(levelname)s: %(message)s",
            "--log-cli-date-format=%H:%M:%S",
        ]
    )

    return exit_code


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting TINYCUA SDK Integration Tests")
    logger.info(f"LLM endpoint: {os.getenv('TINYCUA_BASE_URL', 'http://localhost:1234/v1')}")
    logger.info(f"Model: {os.getenv('TINYCUA_MODEL', 'qwen/qwen3.5-9b')}")
    logger.info("=" * 70)

    exit_code = run_tests()

    logger.info("=" * 70)
    if exit_code == 0:
        logger.info("All tests passed!")
    else:
        logger.error("Some tests failed!")
    logger.info("=" * 70)

    sys.exit(exit_code)
