"""EmailPal transport only; eligibility and durable state belong to outreach_email.

The official contract is https://www.emailpal.io/api/public/v1/openapi.json.
Queue acceptance is deliberately distinct from provider-confirmed sending.
"""
import hashlib
import hmac
import json
import os
import re
import time
from email.utils import parseaddr

import requests

from .policy import GrowthError


BASE_URL = "https://www.emailpal.io/api/public/v1"
MAX_RESPONSE_BYTES = 256_000
MAX_WEBHOOK_BYTES = 64_000
RESOURCE_ID = re.compile(r"[A-Za-z0-9_-]{1,200}\Z")


class ProviderRejected(GrowthError):
    """Known no-send result; it is safe to release this attempt's reservation."""
    definitive = True

    def __init__(self, message, category="permanent", *, retry_after=None):
        super().__init__(message, category)
        self.retry_after = retry_after


def _configuration():
    if os.getenv("OUTREACH_PROVIDER", "").lower() != "emailpal":
        raise ProviderRejected("Dedicated outreach provider is not configured", "configuration")
    token = os.getenv("OUTREACH_EMAILPAL_API_KEY", "").strip()
    if not token or "\r" in token or "\n" in token:
        raise ProviderRejected("Dedicated outreach API key is missing or invalid", "configuration")
    return token


def _id(value):
    if not isinstance(value, str) or not RESOURCE_ID.fullmatch(value):
        raise ProviderRejected("Invalid provider resource identifier")
    return value


def request(path, *, method="GET", data=None, idempotency_key=None, params=None):
    """Bounded fixed-origin request. No redirects, retries, or provider text in errors."""
    token = _configuration()
    if not isinstance(path, str) or not re.fullmatch(r"/[A-Za-z0-9_/-]+", path) or "//" in path:
        raise ProviderRejected("Invalid provider request path")
    if method not in {"GET", "POST", "PATCH", "DELETE"}:
        raise ProviderRejected("Invalid provider request method")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json",
               "Content-Type": "application/json", "User-Agent": "SkubaseGrowth/1.0"}
    if idempotency_key is not None:
        if not isinstance(idempotency_key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", idempotency_key):
            raise ProviderRejected("Invalid outreach idempotency key")
        headers["Idempotency-Key"] = idempotency_key
    try:
        with requests.request(method, BASE_URL + path, json=data, params=params, headers=headers,
                              timeout=20, stream=True, allow_redirects=False) as response:
            status = response.status_code
            if status in {400, 401, 403, 404, 409, 422, 429}:
                category = "configuration" if status in {401, 403} else "transient" if status == 429 else "permanent"
                retry = response.headers.get("Retry-After", "")
                retry_after = min(int(retry), 86400) if retry.isdigit() else None
                raise ProviderRejected(f"Outreach provider rejected request (HTTP {status})", category,
                                       retry_after=retry_after)
            if status < 200 or status >= 300:
                raise GrowthError(f"Outreach provider result unresolved (HTTP {status})", "ambiguous")
            raw = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise GrowthError("Outreach provider response exceeds bounded read", "ambiguous")
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise GrowthError("Outreach provider response is invalid", "ambiguous")
            return {"status_code": status, "data": body}
    except (requests.RequestException, TimeoutError, ValueError, OSError):
        raise GrowthError("Outreach provider transport result unknown", "ambiguous") from None


def _address(value):
    if not isinstance(value, str) or len(value) > 320 or any(c in value for c in "\r\n"):
        raise ProviderRejected("Invalid outreach email address")
    address = parseaddr(value)[1]
    if address != value.strip() or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", address):
        raise ProviderRejected("Invalid outreach email address")
    return address.lower()


def send_message(payload):
    """Verify sender, then submit exactly once. HTTP 202 remains queued."""
    _configuration()
    mailbox_id = _id(os.getenv("OUTREACH_EMAILPAL_MAILBOX_ID", ""))
    sender = _address(payload.get("sender"))
    recipient = _address(payload.get("recipient"))
    if _address(payload.get("reply_to")) != sender:
        raise ProviderRejected("EmailPal replies must use the configured sending mailbox", "configuration")
    subject, body = payload.get("subject"), payload.get("body")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 500 or any(c in subject for c in "\r\n"):
        raise ProviderRejected("Invalid outreach subject")
    if not isinstance(body, str) or not 1 <= len(body) <= 50_000:
        raise ProviderRejected("Invalid outreach body")
    key = payload.get("idempotency_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", key):
        raise ProviderRejected("A stable outreach idempotency key is required")
    try:
        mailbox = request("/mailboxes/" + mailbox_id)["data"]
    except GrowthError as exc:
        # Only a read has happened; a preflight failure cannot have sent the message.
        raise ProviderRejected("Could not verify outreach sender mailbox", exc.category) from None
    if mailbox.get("id") != mailbox_id or _address(mailbox.get("email")) != sender:
        raise ProviderRejected("Provider mailbox does not match configured sender", "configuration")
    sender_name = payload.get("sender_name", "")
    if sender_name and mailbox.get("display_name") != sender_name:
        raise ProviderRejected("Provider sender display name must match configured identity", "configuration")
    if mailbox.get("status") in {"suspended", "failed", "deleted", "provisioning", "pending"}:
        raise ProviderRejected("Provider mailbox is not available for sending", "configuration")
    data = {"mailbox_id": mailbox_id, "to": [recipient], "subject": subject, "body": body}
    if payload.get("parent_provider_id"):
        data["reply_to_id"] = _id(payload["parent_provider_id"])
    elif payload.get("parent_rfc_message_id"):
        parent = payload["parent_rfc_message_id"]
        if not isinstance(parent, str) or not 3 <= len(parent) <= 998 or any(c in parent for c in "\r\n"):
            raise ProviderRejected("Invalid parent RFC message identifier")
        data["in_reply_to"] = parent
        data["references"] = [parent]
    result = request("/inbox/send", method="POST", data=data, idempotency_key=key)
    response = result["data"]
    if result["status_code"] != 202 or not RESOURCE_ID.fullmatch(str(response.get("id", ""))) or not RESOURCE_ID.fullmatch(str(response.get("job_id", ""))):
        raise GrowthError("Outreach provider submission receipt is incomplete", "ambiguous")
    return {"provider_id": response["id"], "queued": True, "job_id": response["job_id"]}


def read_send(provider_id):
    return request("/inbox/send/" + _id(provider_id))["data"]


def read_inbound(provider_id):
    result = request("/inbox/" + _id(provider_id))
    if result["status_code"] == 202:
        return {**result["data"], "status": "pending"}
    return result["data"]


def list_inbound(cursor=None):
    """One bounded page, including seen replies but excluding warming traffic."""
    mailbox_id = _id(os.getenv("OUTREACH_EMAILPAL_MAILBOX_ID", ""))
    params = {"mailbox_id": mailbox_id, "include_warming": "false", "limit": 50}
    if cursor is not None:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 200 or any(c in cursor for c in "\r\n"):
            raise ProviderRejected("Invalid inbox pagination cursor")
        params["cursor"] = cursor
    page = request("/inbox", params=params)["data"]
    if not isinstance(page.get("data"), list) or len(page["data"]) > 50 or not isinstance(page.get("has_more"), bool):
        raise GrowthError("Invalid inbox page response", "transient")
    next_cursor = page.get("next_cursor")
    if next_cursor is not None and (not isinstance(next_cursor, str) or not 1 <= len(next_cursor) <= 200):
        raise GrowthError("Invalid inbox pagination response", "transient")
    return page


def verify_webhook(raw, headers):
    """Authenticate raw bytes before parsing. Persistence layer deduplicates IDs."""
    secret = os.getenv("OUTREACH_EMAILPAL_WEBHOOK_SECRET", "")
    if not secret:
        raise GrowthError("Outreach webhook secret missing", "configuration")
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_WEBHOOK_BYTES:
        raise GrowthError("Invalid outreach webhook body", "permanent")
    header = next((v for k, v in headers.items() if k.lower() == "emailpal-signature"), "")
    try:
        parts = [part.strip().split("=", 1) for part in header.split(",")]
        if any(len(part) != 2 for part in parts) or len({part[0] for part in parts}) != len(parts):
            raise ValueError()
        signature = dict(parts)
        timestamp = signature["t"]
        if not re.fullmatch(r"\d{1,12}", timestamp) or abs(time.time() - int(timestamp)) > 300:
            raise ValueError()
        expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.get("v1", "")):
            raise ValueError()
        event = json.loads(raw)
        if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not event["id"] or len(event["id"]) > 200:
            raise ValueError()
        return event
    except (ValueError, KeyError, TypeError, AttributeError):
        raise GrowthError("Invalid outreach webhook signature or envelope", "permanent") from None


def setup_status(domain_id=None):
    """Read only: no billing, provisioning, warming, or DNS mutations."""
    account = request("/account")["data"]
    mailbox = request("/mailboxes/" + _id(os.getenv("OUTREACH_EMAILPAL_MAILBOX_ID", "")))["data"]
    result = {"provider": "emailpal", "account_status": account.get("status"),
              "enforcement": account.get("enforcement"), "plan": account.get("plan"),
              "mailbox": {k: mailbox.get(k) for k in ("id", "email", "display_name", "status", "warming", "health_score", "daily_limit")}}
    if domain_id:
        domain = request("/domains/" + _id(domain_id))["data"]
        result["domain"] = {k: domain.get(k) for k in ("id", "name", "customer_owned", "dns_method", "status", "dns")}
    return result
