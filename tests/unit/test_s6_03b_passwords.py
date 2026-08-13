
import pytest
pytestmark = pytest.mark.unit
"""Unit tests for S6-03b: Local Password Authentication primitives and policy rules."""

import pytest
from common.observability.exceptions import PasswordPolicyError
from gateway.auth.passwords import (
    hash_password,
    verify_password,
    needs_rehash,
    validate_password_policy,
)


def test_hash_and_verify_password():
    """Test Argon2id password hashing and verification."""
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)
    assert isinstance(hashed, str)
    assert hashed.startswith("$argon2id$")

    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_verify_password_dummy_timing():
    """Test dummy verification for None hash to prevent timing attacks."""
    plain = "SomePassword123!"
    assert verify_password(plain, None) is False


def test_needs_rehash():
    """Test needs_rehash check."""
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)
    assert needs_rehash(hashed) is False


def test_password_policy_validation():
    """Test password policy length, username inclusion, and common password denylist rules."""
    email = "john.doe@example.com"

    # Valid password
    validate_password_policy("SuperValidPassword123!", email)

    # Short password (<12 chars)
    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_password_policy("Short1!", email)
    assert "at least 12 characters" in str(exc_info.value.details.get("rules", []))

    # Username inclusion
    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_password_policy("john.doe123456", email)
    assert "must not contain your email username" in str(exc_info.value.details.get("rules", []))

    # Common password denylist check
    with pytest.raises(PasswordPolicyError) as exc_info:
        validate_password_policy("password12345", email)
    assert "too common" in str(exc_info.value.details.get("rules", []))
