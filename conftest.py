"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values


def _ensure_test_openrouter_key():
    """Provide a dummy key for mocked tests without shadowing a real .env key."""
    if os.getenv("OPENROUTER_API_KEY"):
        return

    env_path = Path(__file__).resolve().parent / ".env"
    file_key = (
        dotenv_values(env_path).get("OPENROUTER_API_KEY") if env_path.exists() else None
    )
    if file_key:
        os.environ["OPENROUTER_API_KEY"] = file_key
    else:
        os.environ["OPENROUTER_API_KEY"] = "pytest-dummy-key"


_ensure_test_openrouter_key()


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests with fake external services"
    )
    config.addinivalue_line(
        "markers", "live: Tests requiring live OpenRouter API access"
    )
    config.addinivalue_line("markers", "slow: Slow running tests")


# Optional: Add command line options for filtering tests
def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests",
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers and options."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="Need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
