from __future__ import annotations

from collections.abc import Iterator

import pytest

import breakdown.indexer.registry as _registry_module


@pytest.fixture(autouse=True)
def clear_language_cache() -> Iterator[None]:
    """Clear the module-level language cache after each integration test."""
    yield
    _registry_module._LANGUAGE_CACHE.clear()
