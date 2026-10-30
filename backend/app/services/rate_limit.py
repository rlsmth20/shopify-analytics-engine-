"""In-process sliding-window rate limits for unauthenticated endpoints.

The public routes that send email (magic links, contact, waitlist) or store
submissions (snapshot leads) had no ceiling, so a loop could bomb a victim's
inbox, burn the Resend quota, and hurt sender reputation. This keeps that
bounded without a new dependency or table.

State lives in this process: a restart clears it and each uvicorn worker
counts separately. That is acceptable for a defence whose job is to stop
thousands of sends, not to meter exact quotas. Keys are per client address
and, where it matters more, per target email, which an attacker cannot
change by rotating addresses.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

# name -> (requests, seconds). Override one with RATE_LIMIT_<NAME>=requests/seconds.
# RATE_LIMITS_ENABLED=false turns every limit off (local load tests only).
DEFAULT_POLICIES: dict[str, tuple[int, int]] = {
    "magic_link_ip": (20, 15 * 60),
    "magic_link_email": (3, 15 * 60),
    "magic_link_email_daily": (10, 24 * 60 * 60),
    "contact_ip": (5, 10 * 60),
    "contact_email": (3, 60 * 60),
    "waitlist_ip": (10, 10 * 60),
    "lead_ip": (10, 60 * 60),
    "admin_token_ip": (10, 15 * 60),
}
RETRY_MESSAGE = "Too many requests. Please wait a few minutes and try again."
_SWEEP_INTERVAL = 300

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}
_last_sweep = 0.0
_clock = time.monotonic  # patched in tests


def enabled() -> bool:
    return os.getenv("RATE_LIMITS_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def policy(name: str) -> tuple[int, int]:
    limit, window = DEFAULT_POLICIES[name]
    raw = os.getenv(f"RATE_LIMIT_{name.upper()}", "").strip()
    if raw:
        try:
            limit_text, window_text = raw.split("/", 1)
            limit, window = max(1, int(limit_text)), max(1, int(window_text))
        except ValueError:
            # A typo must neither disable protection nor lock everyone out.
            pass
    return limit, window


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        # The proxy in front of this service (Railway's edge) appends the
        # connecting address last; earlier entries are client-supplied.
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last
    return request.client.host if request.client else "unknown"


def _sweep(now: float) -> None:
    """Drop idle keys so a scan from many addresses cannot grow memory without bound."""
    global _last_sweep
    if now - _last_sweep < _SWEEP_INTERVAL:
        return
    _last_sweep = now
    for key, bucket in list(_hits.items()):
        _, window = policy(key[0])
        if not bucket or bucket[-1] <= now - window:
            del _hits[key]


def _wait_seconds(name: str, key: str, now: float) -> int | None:
    """Seconds until another request is allowed, or None when within the limit. Caller holds _lock."""
    limit, window = policy(name)
    bucket = _hits.get((name, key))
    if bucket is None:
        return None
    cutoff = now - window
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()
    if len(bucket) < limit:
        return None
    return max(1, int(bucket[0] + window - now) + 1)


def retry_after(name: str, key: str) -> int | None:
    """Seconds until another request is allowed, or None when not limited."""
    if not enabled():
        return None
    now = _clock()
    with _lock:
        _sweep(now)
        return _wait_seconds(name, key, now)


def record(name: str, key: str) -> None:
    """Count one event (for example a failed admin token) without checking."""
    if not enabled():
        return
    with _lock:
        _hits.setdefault((name, key), deque()).append(_clock())


def enforce(request: Request, *checks: tuple[str, str | None], detail: object = None) -> None:
    """Reject with 429 when any check is exhausted, else count this request against all.

    ``checks`` are ``(policy_name, key)`` pairs; a ``None`` key means the
    client address. Every bucket is checked before any is counted, so a
    request blocked by one limit does not consume another: tripping the
    per-address limit cannot be used to exhaust a victim's per-email allowance.
    """
    if not enabled():
        return
    resolved = [(name, key if key is not None else client_ip(request)) for name, key in checks]
    now = _clock()
    with _lock:
        _sweep(now)
        waits = [wait for wait in (_wait_seconds(name, key, now) for name, key in resolved) if wait is not None]
        if waits:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=detail or RETRY_MESSAGE,
                headers={"Retry-After": str(max(waits))},
            )
        for name, key in resolved:
            _hits.setdefault((name, key), deque()).append(now)


def reset() -> None:
    """Forget every counter. Tests share one process and call this in setUp."""
    global _last_sweep
    with _lock:
        _hits.clear()
        _last_sweep = 0.0
