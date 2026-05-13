"""Pytest plugin for testing Karsk packages.

Usage: registered as a plugin via `karsk test`, which stores the Context
on pytest's Config stash before test collection begins.
"""

from __future__ import annotations

import pytest

from karsk.context import Context

_CONTEXT_KEY = pytest.StashKey[Context]()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "karsk: mark test as a karsk package test")


@pytest.fixture
def karsk(request: pytest.FixtureRequest) -> Context:
    try:
        return request.config.stash[_CONTEXT_KEY]
    except KeyError:
        raise RuntimeError(
            "Karsk context not initialised. Run tests via 'karsk test'."
        ) from None
