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
DEFAULT_FROM = os.getenv("WAITLIST_FROM_EMAIL", "skubase <hello@skubase.io>")
DEFAULT_REPLY_TO = os.getenv("WAITLIST_REPLY_TO", "hello@skubase.io")
MAGIC_LINK_FROM = os.getenv("MAGIC_LINK_FROM_EMAIL", DEFAULT_FROM)
MAGIC_LINK_REPLY_TO = os.getenv("MAGIC_LINK_REPLY_TO", DEFAULT_REPLY_TO)
DEFAULT_PRODUCT_URL = os.getenv("PRODUCT_URL", "https://skubase.io")


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:2]}***@{domain}"


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
          <p style="margin:0 0 8px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">skubase</p>
          <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#0f172a;">You&rsquo;re on the list.</h1>
          <p style="margin:0 0 16px;color:#334155;font-size:16px;line-height:1.6;">
            Thanks for signing up at <a href="{DEFAULT_PRODUCT_URL}" style="color:#0f172a;">skubase.io</a>.
            We&rsquo;re a Shopify-first inventory tool that ranks every SKU by what to do today &mdash;
            forecast, supplier scorecards, dead-stock plans, in one product.
          </p>
          {domain_block}
          <p style="margin:0 0 16px;color:#334155;font-size:16px;line-height:1.6;">
            We&rsquo;ll send your invite when paid plans launch. In the meantime,
            the live demo is up at <a href="{DEFAULT_PRODUCT_URL}/dashboard" style="color:#0f172a;">skubase.io/dashboard</a> &mdash;
            it runs on example data so you can poke around without connecting your store.
          </p>
          <p style="margin:24px 0 0;color:#334155;font-size:16px;line-height:1.6;">
            Just hit reply if you want to tell us about your stack &mdash; what you use today,
            what&rsquo;s broken about it, what you&rsquo;d need to switch. The first hundred
            replies shape the roadmap.
          </p>
          <p style="margin:24px 0 0;color:#475569;font-size:14px;">&mdash; Rainer, skubase</p>
        </td></tr>
      </table>
      <p style="margin:16px 0 0;color:#94a3b8;font-size:12px;line-height:1.6;">
        You&rsquo;re receiving this because you signed up at skubase.io with {email}.<br>
        skubase &middot; Independent &middot; Founder-led &middot; Prices locked at renewal
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
        "You're on the skubase waitlist.\n\n"
        f"Thanks for signing up at {DEFAULT_PRODUCT_URL}. skubase is a Shopify-first inventory tool that "
        "ranks every SKU by what to do today — forecast, supplier scorecards, dead-stock plans, in one product.\n\n"
        f"{domain_line}"
        f"We'll send your invite when paid plans launch. In the meantime, the live demo is up at {DEFAULT_PRODUCT_URL}/dashboard — "
        "it runs on example data so you can poke around without connecting your store.\n\n"
        "Just hit reply if you want to tell us about your stack — what you use today, what's broken about it, "
        "what you'd need to switch. The first hundred replies shape the roadmap.\n\n"
        "— Rainer, skubase\n\n"
        "---\n"
        f"You're receiving this because you signed up at skubase.io with {email}.\n"
        "skubase · Independent · Founder-led · Prices locked at renewal\n"
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
            "subject": "You're on the skubase waitlist",
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
          <p style="margin:0 0 8px;font-size:13px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">skubase</p>
          <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#0f172a;">Your Skubase sign-in link</h1>
          <p style="margin:0 0 24px;color:#334155;font-size:16px;line-height:1.6;">
            Use the secure link below to sign in to Skubase. This link expires soon and can only be used once.
          </p>
          <p style="margin:0 0 24px;">
            <a href="{link}" style="display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;font-weight:600;padding:14px 28px;border-radius:10px;font-size:15px;">Sign in to Skubase</a>
          </p>
          <p style="margin:0 0 8px;color:#64748b;font-size:13px;line-height:1.6;">
            Or paste this URL into your browser:
          </p>
          <p style="margin:0 0 24px;color:#334155;font-size:13px;line-height:1.6;word-break:break-all;">
            <a href="{link}" style="color:#334155;">{link}</a>
          </p>
          <p style="margin:24px 0 0;color:#64748b;font-size:13px;line-height:1.6;">
            If you did not request this email, you can ignore it.
          </p>
        </td></tr>
      </table>
      <p style="margin:16px 0 0;color:#94a3b8;font-size:12px;line-height:1.6;">
        Sent to {email} &middot; skubase
      </p>
    </td></tr>
  </table>
</body></html>"""


def _magic_link_text(email: str, link: str) -> str:
    return (
        "Your Skubase sign-in link\n\n"
        "Use the secure link below to sign in to Skubase. This link expires soon and can only be used once.\n\n"
        f"Sign in to Skubase: {link}\n\n"
        "If you did not request this email, you can ignore it.\n\n"
        f"Sent to {email}\n"
    )


def send_contact_notification(
    name: str,
    email: str,
    contact_type: str,
    message: str,
) -> bool:
    """Forward a contact form submission to Rainer. Never raises."""
    client = _client()
    if client is None:
        return False

    OWNER_EMAIL = os.getenv("OWNER_EMAIL", "rlsmth20@gmail.com")
    label = contact_type.capitalize()
    subject = f"[skubase {label}] from {name} <{email}>"
    html = f"""<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:32px 16px;">
  <table role="presentation" width="560" style="max-width:560px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;margin:0 auto;">
    <tr><td>
      <p style="margin:0 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;">skubase · {label}</p>
      <h2 style="margin:0 0 20px;font-size:20px;color:#0f172a;">{name}</h2>
      <p style="margin:0 0 4px;font-size:13px;color:#64748b;">From</p>
      <p style="margin:0 0 16px;font-size:15px;color:#0f172a;"><a href="mailto:{email}" style="color:#0f172a;">{email}</a></p>
      <p style="margin:0 0 4px;font-size:13px;color:#64748b;">Message</p>
      <p style="margin:0;font-size:15px;color:#334155;white-space:pre-wrap;line-height:1.6;">{message}</p>
    </td></tr>
  </table>
</body></html>"""
    text = f"[skubase {label}]\nFrom: {name} <{email}>\n\n{message}\n"

    try:
        params = {
            "from": DEFAULT_FROM,
            "to": [OWNER_EMAIL],
            "reply_to": email,
            "subject": subject,
            "html": html,
            "text": text,
            "tags": [{"name": "category", "value": "contact_form"}],
        }
        result = client.Emails.send(params)
        logger.info("contact notification sent: id=%s from=%s", result.get("id"), email)
        return True
    except Exception as exc:
        logger.exception("failed to send contact notification from %s: %s", email, exc)
        return False


def send_alert_email(
    *,
    to: str,
    subject: str,
    body: str,
) -> bool:
    """Send an inventory alert email via Resend. Never raises."""
    client = _client()
    if client is None:
        return False

    safe_body = body.replace("\n", "<br>")
    html = f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 8px;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">skubase alert</p>
          <h2 style="margin:0 0 16px;font-size:20px;line-height:1.3;color:#0f172a;">{subject}</h2>
          <p style="margin:0 0 24px;color:#334155;font-size:15px;line-height:1.6;">{safe_body}</p>
          <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
          <p style="margin:0;font-size:12px;color:#94a3b8;">skubase &middot; automated inventory alert</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""

    try:
        params = {
            "from": DEFAULT_FROM,
            "to": [to],
            "reply_to": DEFAULT_REPLY_TO,
            "subject": subject,
            "html": html,
            "text": f"{subject}\n\n{body}\n\n--\nskubase automated alert",
            "tags": [{"name": "category", "value": "alert"}],
        }
        result = client.Emails.send(params)
        logger.info("alert email sent: id=%s to=%s", result.get("id"), to)
        return True
    except Exception as exc:
        logger.exception("failed to send alert email to %s: %s", to, exc)
        return False


def send_magic_link_email(email: str, link: str) -> bool:
    """Send a sign-in link. Returns True on success, False on any failure.

    Designed for use as a FastAPI BackgroundTask: never raises.
    """
    client = _client()
    if client is None:
        return False
    try:
        params = {
            "from": MAGIC_LINK_FROM,
            "to": [email],
            "reply_to": MAGIC_LINK_REPLY_TO,
            "subject": "Your Skubase sign-in link",
            "html": _magic_link_html(email, link),
            "text": _magic_link_text(email, link),
            "tags": [
                {"name": "category", "value": "magic_link"},
            ],
        }
        result = client.Emails.send(params)
        logger.info(
            "magic-link email sent: id=%s to=%s from=%s reply_to=%s",
            result.get("id"),
            _mask_email(email),
            MAGIC_LINK_FROM,
            MAGIC_LINK_REPLY_TO,
        )
        return True
    except Exception as exc:
        logger.exception("failed to send magic-link to %s: %s", _mask_email(email), exc)
        return False


def send_buy_list_email(
    *,
    email: str,
    items: list[dict],
    total_cost: float,
    vendor_totals: dict[str, float],
) -> bool:
    """Send the weekly Monday Buy List digest. Never raises."""
    client = _client()
    if client is None:
        return False

    rows = "".join(
        f"""<tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:14px;">{item['name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#475569;font-size:13px;">{item['vendor'] or '-'}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:14px;text-align:right;">{item['qty']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:14px;text-align:right;">${item['cost']:,.0f}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:{'#b91c1c' if item['stockout_prob'] >= 0.5 else '#475569'};font-size:13px;text-align:right;">{item['stockout_prob']:.0%}</td>
        </tr>"""
        for item in items
    )
    vendor_lines = "".join(
        f'<li style="margin:0 0 4px;color:#475569;font-size:13px;">{vendor or "Unassigned"}: <strong>${amount:,.0f}</strong></li>'
        for vendor, amount in sorted(vendor_totals.items(), key=lambda kv: kv[1], reverse=True)
    )
    text_lines = "\n".join(
        f"- {item['name']} ({item['vendor'] or '-'}): order {item['qty']} (~${item['cost']:,.0f}, "
        f"stockout risk {item['stockout_prob']:.0%}, lead time {item['lead_time_days']}d)"
        for item in items
    )

    html = f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;">
        <tr><td>
          <p style="margin:0 0 8px;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;">skubase weekly buy list</p>
          <h1 style="margin:0 0 8px;font-size:22px;line-height:1.3;color:#0f172a;">What to order this week.</h1>
          <p style="margin:0 0 20px;color:#334155;font-size:15px;line-height:1.6;">
            Your top {len(items)} reorders, ranked by stockout risk. Total cash required:
            <strong>${total_cost:,.0f}</strong>.
          </p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <th style="padding:8px 12px;border-bottom:2px solid #0f172a;color:#64748b;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;text-align:left;">Product</th>
              <th style="padding:8px 12px;border-bottom:2px solid #0f172a;color:#64748b;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;text-align:left;">Vendor</th>
              <th style="padding:8px 12px;border-bottom:2px solid #0f172a;color:#64748b;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;text-align:right;">Qty</th>
              <th style="padding:8px 12px;border-bottom:2px solid #0f172a;color:#64748b;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;text-align:right;">Cost</th>
              <th style="padding:8px 12px;border-bottom:2px solid #0f172a;color:#64748b;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;text-align:right;">Risk</th>
            </tr>
            {rows}
          </table>
          <p style="margin:20px 0 8px;color:#0f172a;font-size:14px;font-weight:600;">Cash by vendor</p>
          <ul style="margin:0 0 20px;padding-left:18px;">{vendor_lines}</ul>
          <p style="margin:0 0 24px;">
            <a href="{DEFAULT_PRODUCT_URL}/purchase-orders" style="display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;font-size:14px;font-weight:600;padding:10px 18px;border-radius:10px;">Open PO drafts</a>
          </p>
          <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
          <p style="margin:0;font-size:12px;color:#94a3b8;">
            skubase &middot; weekly buy list &middot; manage this email on the
            <a href="{DEFAULT_PRODUCT_URL}/reports" style="color:#64748b;">Reports page</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""

    try:
        params = {
            "from": DEFAULT_FROM,
            "to": [email],
            "reply_to": DEFAULT_REPLY_TO,
            "subject": f"Your Monday buy list - {len(items)} reorders, ${total_cost:,.0f} required",
            "html": html,
            "text": (
                f"Your weekly skubase buy list ({len(items)} reorders, ${total_cost:,.0f} total):\n\n"
                f"{text_lines}\n\nOpen PO drafts: {DEFAULT_PRODUCT_URL}/purchase-orders\n"
                f"Manage this email: {DEFAULT_PRODUCT_URL}/reports\n"
            ),
            "tags": [{"name": "category", "value": "weekly_buy_list"}],
        }
        result = client.Emails.send(params)
        logger.info("buy list email sent: id=%s to=%s", result.get("id"), _mask_email(email))
        return True
    except Exception as exc:
        logger.exception("failed to send buy list email to %s: %s", _mask_email(email), exc)
        return False
