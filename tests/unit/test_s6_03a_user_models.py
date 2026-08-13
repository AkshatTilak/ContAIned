
import pytest
pytestmark = pytest.mark.unit
"""Unit tests for S6-03a: User, Identity & Invite Models + Schemas."""

import pytest
from common.models.database import User, UserIdentity, UserInvite
from common.schemas.api import UserDetail


def test_user_detail_schema_excludes_password_hash():
    """Verify UserDetail never declares password_hash field."""
    assert "password_hash" not in UserDetail.model_fields, "UserDetail must not expose password_hash"


def test_user_model_defaults_and_validations():
    """Test User model default values and validation hooks."""
    user = User(
        email="test@example.com",
        platform_role="member",
        status="pending",
    )
    assert user.email == "test@example.com"
    assert user.platform_role == "member"
    assert user.status == "pending"

    with pytest.raises(ValueError, match="Invalid platform_role"):
        User(email="invalid@example.com", platform_role="superadmin")

    with pytest.raises(ValueError, match="Invalid status"):
        User(email="invalid@example.com", status="unknown_status")


def test_user_identity_validation():
    """Test UserIdentity validation hook."""
    identity = UserIdentity(
        provider="google",
        provider_id="12345",
        email="google@example.com",
    )
    assert identity.provider == "google"

    with pytest.raises(ValueError, match="Invalid provider"):
        UserIdentity(provider="twitter", provider_id="123", email="tw@example.com")


def test_user_invite_validation():
    """Test UserInvite validation hook."""
    invite = UserInvite(
        email="invitee@example.com",
        token_hash="hash123",
        status="pending",
    )
    assert invite.status == "pending"

    with pytest.raises(ValueError, match="Invalid status"):
        UserInvite(email="a@b.com", token_hash="x", status="cancelled")
