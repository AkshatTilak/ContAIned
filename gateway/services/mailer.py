"""Outbound email service abstraction, SMTPMailer, NullMailer fallback, and Jinja2 templates (S6-03e)."""

import asyncio
import email.message
import logging
import os
from functools import lru_cache
from typing import Any, Optional, Protocol

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from common.config.settings import get_settings

logger = logging.getLogger("gateway.services.mailer")


class Mailer(Protocol):
    """Protocol defining the platform outbound mailer interface."""

    async def send(self, to: str, subject: str, html: str, text: str) -> bool:
        """Send an email to a recipient. Returns True if delivered, False otherwise."""
        ...


class SMTPMailer:
    """Outbound SMTP mailer using aiosmtplib."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        user: Optional[str] = None,
        password: Optional[str] = None,
        sender: str = "ContAIned <no-reply@contained.local>",
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.use_tls = use_tls

    async def send(self, to: str, subject: str, html: str, text: str) -> bool:
        """Send email via SMTP with a 10-second non-blocking timeout.

        Returns False on any delivery failure without raising.
        """
        msg = email.message.EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        # Determine TLS mode
        start_tls = self.use_tls if self.port != 465 else False
        use_tls_implicit = self.use_tls if self.port == 465 else False

        try:
            async with asyncio.timeout(10.0):
                await aiosmtplib.send(
                    msg,
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    start_tls=start_tls,
                    use_tls=use_tls_implicit,
                )
            logger.info("Email delivered to %s (subject=%s)", to, subject)
            return True
        except (aiosmtplib.SMTPException, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("SMTP delivery failed for recipient %s (subject=%s): %s", to, subject, exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected error sending email to %s: %s", to, exc)
            return False


class NullMailer:
    """No-op mailer used when SMTP_HOST is unconfigured."""

    async def send(self, to: str, subject: str, html: str, text: str) -> bool:
        logger.warning("SMTP not configured; email to %s dropped (subject=%s)", to, subject)
        return False


@lru_cache(maxsize=1)
def get_mailer() -> Mailer:
    """Fetch singleton Mailer instance (SMTPMailer if SMTP_HOST is set, else NullMailer)."""
    settings = get_settings()
    host = getattr(settings, "SMTP_HOST", None)
    if host and host.strip():
        return SMTPMailer(
            host=host.strip(),
            port=getattr(settings, "SMTP_PORT", 587),
            user=getattr(settings, "SMTP_USER", None),
            password=getattr(settings, "SMTP_PASSWORD", None),
            sender=getattr(settings, "SMTP_FROM", "ContAIned <no-reply@contained.local>"),
            use_tls=getattr(settings, "SMTP_USE_TLS", True),
        )
    return NullMailer()


@lru_cache(maxsize=1)
def _get_jinja_env() -> Environment:
    """Initialize sandboxed Jinja2 environment for email templates."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    templates_dir = os.path.join(base_dir, "templates", "email")
    return Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )


async def send_template(to: str, template: str, subject: str, **context: Any) -> bool:
    """Render and send an HTML + plain text email template.

    Injects app_url into every template context.
    Returns True if delivered, False if unconfigured or failed.
    """
    settings = get_settings()
    public_url = getattr(settings, "APP_PUBLIC_URL", "http://localhost:5173")

    ctx = dict(context)
    ctx.setdefault("app_url", public_url)

    env = _get_jinja_env()

    html_template_name = f"{template}.html"
    text_template_name = f"{template}.txt"

    html_content = env.get_template(html_template_name).render(**ctx)
    text_content = env.get_template(text_template_name).render(**ctx)

    mailer = get_mailer()
    return await mailer.send(to=to, subject=subject, html=html_content, text=text_content)
