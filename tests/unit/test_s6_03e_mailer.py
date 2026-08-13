
import pytest
pytestmark = pytest.mark.unit
"""Unit tests for S6-03e Mailer Abstraction, SMTP & Templates."""

import pytest
from gateway.services.mailer import (
    NullMailer,
    SMTPMailer,
    send_template,
    _get_jinja_env,
)


@pytest.mark.asyncio
async def test_null_mailer_fallback():
    """Test NullMailer when SMTP_HOST is None."""
    mailer = NullMailer()
    res = await mailer.send(
        to="test@example.com",
        subject="Test Subject",
        html="<p>Test</p>",
        text="Test",
    )
    assert res is False


@pytest.mark.asyncio
async def test_smtp_mailer_timeout_handling():
    """Test SMTPMailer gracefully catches connection errors and returns False."""
    # Point to invalid port/host to trigger non-blocking timeout
    mailer = SMTPMailer(host="127.0.0.1", port=59999, use_tls=False)
    res = await mailer.send(
        to="test@example.com",
        subject="Test Failure",
        html="<p>Fail</p>",
        text="Fail",
    )
    assert res is False


def test_jinja2_templates_rendering():
    """Test Jinja2 email templates render with autoescaping and context injection."""
    env = _get_jinja_env()

    # Invite template
    tmpl = env.get_template("invite.html")
    rendered = tmpl.render(
        inviter_name="<Admin & User>",
        platform_role="admin",
        hub_names=["Hub 1", "Hub 2"],
        invite_url="http://localhost:5173/auth/invite/raw123",
        expires_at="2026-08-01 00:00:00 UTC",
    )
    assert "&lt;Admin &amp; User&gt;" in rendered
    assert "Accept Invitation" in rendered

    # Approved template
    tmpl_app = env.get_template("approved.html")
    rendered_app = tmpl_app.render(display_name="John Doe", app_url="http://localhost:5173")
    assert "John Doe" in rendered_app
    assert "Log In Now" in rendered_app

    # Password reset template
    tmpl_pwd = env.get_template("password_reset.html")
    rendered_pwd = tmpl_pwd.render(display_name="Alice", reset_url="http://localhost:5173/reset?token=123", ttl_minutes=60)
    assert "Alice" in rendered_pwd
    assert "60 minutes" in rendered_pwd


@pytest.mark.asyncio
async def test_send_template_fallback():
    """Test send_template returns False when using NullMailer without raising exception."""
    res = await send_template(
        to="recipient@example.com",
        template="approved",
        subject="Your Account is Approved",
        display_name="Recipient User",
    )
    assert res is False
