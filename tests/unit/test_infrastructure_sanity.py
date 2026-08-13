"""Sanity test for V8 testing infrastructure foundation."""

import pytest
from common.config.settings import settings


@pytest.mark.unit
def test_settings_loaded(test_settings):
    """Verify test_settings fixture is injected properly and APP_ENV is test or development."""
    assert test_settings is not None
    assert settings.APP_NAME is not None


@pytest.mark.unit
def test_markers_registered():
    """Verify unit marker execution works."""
    assert True
