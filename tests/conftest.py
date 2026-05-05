"""Shared test fixtures for unified-search tests."""

import pytest
from app.modules import auto_register
from app.engine import engine


@pytest.fixture(scope="session")
def setup_engine():
    """Register modules and load engine once for all tests."""
    auto_register()
    engine.load_modules()
    return engine
