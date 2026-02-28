"""
tools/email_tool.py
--------------------
Implements the ``send_email`` tool and registers it with the global registry.

Architecture
------------
                 ┌──────────────────────────┐
  LLM output ──▶ │    dispatcher.execute_tool │
                 └────────────┬─────────────┘
                              │ validated kwargs
                              ▼
                    send_email(to, subject, body)
                              │
                 ┌────────────▼─────────────┐
                 │   smtplib.SMTP_SSL        │
                 │   (credentials from env)  │
                 └──────────────────────────┘

Environment Variables Required
-------------------------------
    SMTP_HOST      – SMTP server hostname  (default: smtp.gmail.com)
    SMTP_PORT      – SMTP port             (default: 465 for SSL)
    SMTP_USER      – Sender email address
    SMTP_PASSWORD  – SMTP password / app-password
    EMAIL_FROM     – Display name / from address (falls back to SMTP_USER)

Security Note
-------------
Credentials are NEVER hard-coded.  All secrets are read from environment
variables at call time so they can be injected via .env, Docker secrets, or
a secrets manager without touching source code.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from pydantic import BaseModel, EmailStr, field_validator

from registry import registry

# ---------------------------------------------------------------------------
# Pydantic parameter model
# ---------------------------------------------------------------------------


class SendEmailParams(BaseModel):
    """
    Validates the parameters the LLM passes to ``send_email``.

    Using Pydantic here means:
    - Bad email addresses are rejected before hitting the network.
    - Missing required fields raise a clear ValidationError.
    - The dispatcher can convert raw JSON → typed Python in one call.
    """

    to: EmailStr
    subject: str
    body: str

    @field_validator("subject", "body")
    @classmethod
    def must_not_be_blank(cls, v: str, info) -> str:
        if not v.strip():
            raise ValueError(f"'{info.field_name}' must not be blank.")
        return v


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


def _build_message(from_addr: str, to: str, subject: str, body: str) -> MIMEMultipart:
    """Construct a MIME email message."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.attach(MIMEText(body, "plain"))
    return msg


def _send_via_smtp(to: str, subject: str, body: str) -> None:
    """
    Send an email using smtplib over SSL.

    All connection parameters come from environment variables so no secrets
    are ever present in source code.

    Raises
    ------
    smtplib.SMTPAuthenticationError
        When SMTP credentials are invalid.
    smtplib.SMTPException
        For any other SMTP-layer error.
    EnvironmentError
        When required env vars (SMTP_USER, SMTP_PASSWORD) are missing.
    """
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("EMAIL_FROM", user)

    if not user or not password:
        raise EnvironmentError(
            "SMTP_USER and SMTP_PASSWORD environment variables must be set."
        )

    msg = _build_message(from_addr, to, subject, body)
    ssl_context = ssl.create_default_context()

    with smtplib.SMTP_SSL(host, port, context=ssl_context) as server:
        server.login(user, password)
        server.sendmail(from_addr, to, msg.as_string())


# ---------------------------------------------------------------------------
# Registered tool function
# ---------------------------------------------------------------------------


@registry.register(
    description=(
        "Send an email to a single recipient. "
        "Use this when the user explicitly asks to send, draft-and-send, "
        "or forward an email message."
    ),
    parameters={
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address (e.g. alice@example.com).",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line.",
            },
            "body": {
                "type": "string",
                "description": "Plain-text body of the email.",
            },
        },
        "required": ["to", "subject", "body"],
    },
)
def send_email(to: str, subject: str, body: str) -> str:
    """
    Send a plain-text email.

    This function is intentionally kept thin — it validates its inputs via
    the Pydantic model and delegates to ``_send_via_smtp``.  Any transport
    (SendGrid, Resend, SES) can be swapped in by replacing ``_send_via_smtp``
    without touching this function or the registry schema.

    Parameters
    ----------
    to:
        Recipient email address.
    subject:
        Email subject line.
    body:
        Plain-text email body.

    Returns
    -------
    str
        A human-readable observation string suitable for feeding back to the
        LLM in the next turn (the "observation" step of the ReAct loop).
    """
    # --- Validate inputs ---------------------------------------------------
    # Raises pydantic.ValidationError on bad data; caught by the dispatcher.
    params = SendEmailParams(to=to, subject=subject, body=body)

    # --- Send ---------------------------------------------------------------
    _send_via_smtp(params.to, params.subject, params.body)

    return f"Success: Email sent to '{params.to}' with subject '{params.subject}'."
