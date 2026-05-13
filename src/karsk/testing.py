"""Utilities for testing Karsk packages using pytest"""

from __future__ import annotations
import pytest

from karsk.context import Context


_CONTEXT: Context | None = None


@pytest.fixture
def karsk() -> Context:
    if _CONTEXT is None:
        raise RuntimeError(
            "Karsk context not initialised. Run tests via 'karsk test'."
        )
    return _CONTEXT
