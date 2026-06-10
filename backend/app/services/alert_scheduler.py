"""Background alert evaluation loop."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress

from sqlalchemy import select

from app.db.models import User
from app.db.session import SessionLocal
from app.services.alert_evaluation import evaluate_shop_alerts, user_has_active_access
from app.services.inventory_value import capture_all_inventory_snapshots
from app.services.weekly_digest import run_weekly_digests_once

logger = logging.getLogger(__name__)

_task: asyncio.Task[None] | None = None
_last_snapshot_date: str | None = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, os.getenv(name), default)
        return default


def run_alert_evaluation_once(*, cooldown_seconds: int) -> int:
    """Evaluate enabled alert rules once for every active shop.

    Returns the number of alert events created. Delivery is handled by the rule
    engine, respecting configured channels, plan entitlements, and cooldowns.
    """
    total_events = 0
    seen_shop_ids: set[int] = set()

    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.shop_id, User.id)).all()
        for user in users:
            if user.shop_id in seen_shop_ids:
                continue
            seen_shop_ids.add(user.shop_id)

            if not user_has_active_access(db, user):
                continue

            try:
                events = evaluate_shop_alerts(
                    db,
                    user,
                    dry_run=False,
                    cooldown_seconds=cooldown_seconds,
                )
            except Exception:
                logger.exception("Automatic alert evaluation failed for shop_id=%s", user.shop_id)
                continue

            total_events += len(events)

    return total_events


def _run_daily_jobs() -> None:
    """Once-per-UTC-day jobs piggybacking on the alert scheduler tick."""
    global _last_snapshot_date
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _last_snapshot_date == today:
        return
    _last_snapshot_date = today
    captured = capture_all_inventory_snapshots()
    if captured:
        logger.info("Captured inventory value snapshots for %s shop(s)", captured)
    sent = run_weekly_digests_once()
    if sent:
        logger.info("Sent %s weekly buy-list digest(s)", sent)


async def _scheduler_loop(interval_seconds: int, cooldown_seconds: int) -> None:
    logger.info(
        "Automatic alert evaluation enabled; interval=%ss cooldown=%ss",
        interval_seconds,
        cooldown_seconds,
    )
    while True:
        try:
            count = await asyncio.to_thread(
                run_alert_evaluation_once,
                cooldown_seconds=cooldown_seconds,
            )
            if count:
                logger.info("Automatic alert evaluation created %s event(s)", count)
            await asyncio.to_thread(_run_daily_jobs)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic alert scheduler tick failed")
        await asyncio.sleep(interval_seconds)


def start_alert_scheduler() -> None:
    global _task
    if not _env_bool("ALERT_AUTO_EVALUATION_ENABLED", True):
        logger.info("Automatic alert evaluation disabled by env")
        return
    if _task is not None and not _task.done():
        return

    interval_seconds = _env_int("ALERT_EVALUATION_INTERVAL_SECONDS", 900)
    cooldown_seconds = _env_int("ALERT_DELIVERY_COOLDOWN_SECONDS", 21600)
    _task = asyncio.create_task(_scheduler_loop(interval_seconds, cooldown_seconds))


async def stop_alert_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    with suppress(asyncio.CancelledError):
        await _task
    _task = None
