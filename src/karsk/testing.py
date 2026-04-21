"""Utilities for testing Karsk packages using pytest"""

from __future__ import annotations
import pytest

from karsk.context import Context


_CONTEXT: Context | None = None


@pytest.fixture
def karsk() -> Context:
    assert _CONTEXT is not None
    return _CONTEXT
