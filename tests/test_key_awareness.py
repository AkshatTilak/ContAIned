"""Unit tests for GuardRoute API Key Awareness & Status Flags (sub_08_02)."""

import pytest
from projects.guardroute.src.services.key_inspector import APIKeyInspector


def test_key_inspector_returns_dict():
    keys = APIKeyInspector.inspect_keys()
    assert isinstance(keys, dict)
    assert "gemini" in keys
    assert "openai" in keys
    assert "groq" in keys


def test_get_model_status_flag_local():
    flag = APIKeyInspector.get_model_status_flag("huggingface", "local")
    assert flag == "local_only"


def test_get_model_status_flag_missing():
    flag = APIKeyInspector.get_model_status_flag("nonexistent_provider", "cloud")
    assert flag == "missing_key"
