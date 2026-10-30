"""Shared-secret admin gate with brute-force lockout.

Admin routes are still protected by the static ADMIN_BOOTSTRAP_TOKEN header.
Compare it in constant time and lock an address out after repeated failures
so the token cannot be guessed online.
"""
from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import HTTPException, Request, status

from app.services import rate_limit

LOCKOUT_DETAIL = "Too many failed admin attempts from this address. Try again later."


def require_admin_token(request: Request, token: Optional[str], *, disabled_detail: str) -> None:
    expected = os.getenv("ADMIN_BOOTSTRAP_TOKEN")
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=disabled_detail)
    address = rate_limit.client_ip(request)
    wait = rate_limit.retry_after("admin_token_ip", address)
    if wait is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=LOCKOUT_DETAIL,
            headers={"Retry-After": str(wait)},
        )
    if not token or not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        # Only failures count, so a legitimate operator is never throttled.
        rate_limit.record("admin_token_ip", address)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token.")
