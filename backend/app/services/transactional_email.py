"""Transactional email — Resend-backed, fire-and-forget friendly.

Designed to never crash a request: every public function logs and swallows
errors so the caller (e.g. a FastAPI BackgroundTask) does not need a
try/except. We log enough to debug a misconfigured RESEND_API_KEY without
leaking the API key itself.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults are safe to ship. Override via env vars on Railway.
DEFAULT_FROM = os.getenv("WAITLIST_FROM_EMAIL", "slelfly <hello@slelfly.com>")
DEFAULT_REPLY_TO = os.getenv("WAITLIST_REPLY_TO", "hello@slelfly.com")
DEFAULT_PRODUCT_URL = os.getenv("PRODUCT_URL", "https://slelfly.com")


def _client():
    """Return a configured Resend module, or None if the API key is missing.

    Importing inside the function keeps the dependency optional — local dev
    without RESEND_API_KEY simply skips email sending and logs a warning.
    """
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY not set — skipping transactional email")
        return None
    try:
        import resend  # type: ignore
    except ImportError:
        logger.error("resend package not installed — add it to requirements.txt")
        return None
    resend.api_key = api_key
    return resend


def _waitlist_html(email: str, shopify_domain: Optional[str]) -> str:
    domain_block = (
        f'<p style="margin:0 0 16px;color:#475569;">We have your store noted as '
        f'<strong>{shopify_domain}</strong> — we&rsquo;ll prioritise your invite '
        f'when we open up Shopify connections.</p>'
        if shopify_domain
        else ""
    )
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 8px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">slelfly</p>
          <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#0f172a;">You&rsquo;re on the list.</h1>
          <p style="margin:0 0 16px;color:#334155;font-size:16px;line-height:1.6;">
            Thanks for signing up at <a href="{DEFAULT_PRODUCT_URL}" style="color:#0f172a;">slelfly.com</a>.
            We&rsquo;re a Shopify-first inventory tool that ranks every SKU by what to do today &mdash;
            forecast, supplier scorecards, dead-stock plans, in one product.
          </p>
          {domain_block}
          <p style="margin:0 0 16px;color:#334155;font-size:16px;line-height:1.6;">
            We&rsquo;ll send your invite when paid plans launch. In the meantime,
            the live demo is up at <a href="{DEFAULT_PRODUCT_URL}/dashboard" style="color:#0f172a;">slelfly.com/dashboard</a> &mdash;
            it runs on example data so you can poke around without connecting your store.
          </p>
          <p style="margin:24px 0 0;color:#334155;font-size:16px;line-height:1.6;">
            Just hit reply if you want to tell us about your stack &mdash; what you use today,
            what&rsquo;s broken about it, what you&rsquo;d need to switch. The first hundred
            replies shape the roadmap.
          </p>
          <p style="margin:24px 0 0;color:#475569;font-size:14px;">&mdash; Rainer, slelfly</p>
        </td></tr>
      </table>
      <p style="margin:16px 0 0;color:#94a3b8;font-size:12px;line-height:1.6;">
        You&rsquo;re receiving this because you signed up at slelfly.com with {email}.<br>
        slelfly &middot; Independent &middot; Founder-led &middot; Prices locked at renewal
      </p>
    </td></tr>
  </table>
</body></html>"""


def _waitlist_text(email: str, shopify_domain: Optional[str]) -> str:
    domain_line = (
        f"We have your store noted as {shopify_domain} — we'll prioritise your invite when we open up Shopify connections.\n\n"
        if shopify_domain
        else ""
    )
    return (
        "You're on the slelfly waitlist.\n\n"
        f"Thanks for signing up at {DEFAULT_PRODUCT_URL}. slelfly is a Shopify-first inventory tool that "
        "ranks every SKU by what to do today — forecast, supplier scorecards, dead-stock plans, in one product.\n\n"
        f"{domain_line}"
        f"We'll send your invite when paid plans launch. In the meantime, the live demo is up at {DEFAULT_PRODUCT_URL}/dashboard — "
        "it runs on example data so you can poke around without connecting your store.\n\n"
        "Just hit reply if you want to tell us about your stack — what you use today, what's broken about it, "
        "what you'd need to switch. The first hundred replies shape the roadmap.\n\n"
        "— Rainer, slelfly\n\n"
        "---\n"
        f"You're receiving this because you signed up at slelfly.com with {email}.\n"
        "slelfly · Independent · Founder-led · Prices locked at renewal\n"
    )


def send_waitlist_confirmation(
    email: str,
    shopify_domain: Optional[str] = None,
) -> bool:
    """Send the welcome email. Returns True on success, False on any failure.

    Designed for use as a FastAPI BackgroundTask: never raises.
    """
    client = _client()
    if client is None:
        return False

    try:
        params = {
            "from": DEFAULT_FROM,
            "to": [email],
            "reply_to": DEFAULT_REPLY_TO,
            "subject": "You're on the slelfly waitlist",
            "html": _waitlist_html(email, shopify_domain),
            "text": _waitlist_text(email, shopify_domain),
            "tags": [
                {"name": "category", "value": "waitlist_confirmation"},
            ],
        }
        result = client.Emails.send(params)
        logger.info("waitlist confirmation sent: id=%s to=%s", result.get("id"), email)
        return True
    except Exception as exc:  # pragma: no cover — best-effort send
        logger.exception("failed to send waitlist confirmation to %s: %s", email, exc)
        return False


def _magic_link_html(email: str, link: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 8px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">slelfly</p>
          <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#0f172a;">Sign in to slelfly</h1>
          <p style="margin:0 0 24px;color:#334155;font-size:16px;line-height:1.6;">
            Click the button below to sign in. The link is valid for 15 minutes and can only be used once.
          </p>
          <p style="margin:0 0 24px;">
            <a href="{link}" style="display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;font-weight:600;padding:14px 28px;border-radius:10px;font-size:15px;">Sign in to slelfly &rarr;</a>
          </p>
          <p style="margin:0 0 8px;color:#64748b;font-size:13px;line-height:1.6;">
            Or paste this URL into your browser:
          </p>
          <p style="margin:0 0 24px;color:#334155;font-size:13px;line-height:1.6;word-break:break-all;">
            <a href="{link}" style="color:#334155;">{link}</a>
          </p>
          <p style="margin:24px 0 0;color:#64748b;font-size:13px;line-height:1.6;">
            If you did not request this email, you can ignore it &mdash; nothing happens until the link is clicked.
          </p>
        </td></tr>
      </table>
      <p style="margin:16px 0 0;color:#94a3b8;font-size:12px;line-height:1.6;">
        Sent to {email} &middot; slelfly
      </p>
    </td></tr>
  </table>
</body></html>"""


def _magic_link_text(email: str, link: str) -> str:
    return (
        "Sign in to slelfly\n\n"
        f"Click this link to sign in: {link}\n\n"
        "The link is valid for 15 minutes and can only be used once.\n\n"
        "If you did not request this email, you can ignore it — nothing "
        "happens until the link is clicked.\n\n"
        f"Sent to {email}\n"
    )


def send_magic_link_email(email: str, link: str) -> bool:
    """Send a sign-in link. Returns True on success, False on any failure.

    Designed for use as a FastAPI BackgroundTask: never raises.
    """
    client = _client()
    if client is None:
        return False
    try:
        params = {
            "from": DEFAULT_FROM,
            "to": [email],
            "reply_to": DEFAULT_REPLY_TO,
            "subject": "Sign in to slelfly",
            "html": _magic_link_html(email, link),
            "text": _magic_link_text(email, link),
            "tags": [
                {"name": "category", "value": "magic_link"},
            ],
        }
        result = client.Emails.send(params)
        logger.info("magic-link email sent: id=%s to=%s", result.get("id"), email)
        return True
    except Exception as exc:
        logger.exception("failed to send magic-link to %s: %s", email, exc)
        return False
