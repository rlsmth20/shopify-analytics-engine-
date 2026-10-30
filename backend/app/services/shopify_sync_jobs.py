"""Run Shopify syncs off the request path, one at a time per shop.

The Store Sync button used to run the whole catalog and order traversal
inside the HTTP request: a large store exceeded proxy timeouts, a retry in a
second tab raced the first run into the inventory unique constraint, and the
browser had no way to learn how it ended. Now a request only creates a
ShopifySyncRun row and returns 202; the traversal happens on a worker thread
and the page polls the run.

The row is also the per-shop lock. It is created under the per-shop
connection lock (a thread lock plus a Postgres transaction advisory lock), so
two workers cannot both find no active run and start one each.

The same machinery drives the automatic refresh: a loop started from the app
lifespan syncs every installed store whose newest run is older than
SHOPIFY_AUTO_SYNC_INTERVAL_SECONDS, so alerts and the action queue no longer
depend on a merchant remembering to click Sync now.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import suppress
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session as DbSession

from app.db.models import ShopifyConnection, ShopifySyncRun
from app.db.session import SessionLocal
from app.services.shopify_oauth import shopify_connection_lock
from app.services.shopify_sync import _friendly_sync_error, sync_shop_now

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")
IN_PROGRESS_MESSAGE = "A sync for this store is already running. Wait for it to finish."
ABANDONED_MESSAGE = "The sync did not finish within the expected time. Run it again."
INTERRUPTED_MESSAGE = "The sync was interrupted by a server restart. Run it again."
FULL_ORDER_WINDOW_DAYS = 60
MIN_ORDER_WINDOW_DAYS = 3

_task: asyncio.Task[None] | None = None


class SyncInProgress(RuntimeError):
    """Another run for this shop is queued or running."""


def _env_int(name: str, default: int, *, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, os.getenv(name), default)
        return default


def lease_seconds() -> int:
    """How long a queued/running row keeps its claim before it counts as abandoned."""
    return _env_int("SHOPIFY_SYNC_LEASE_SECONDS", 3600, minimum=60)


def auto_sync_enabled() -> bool:
    return os.getenv("SHOPIFY_AUTO_SYNC_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def auto_sync_interval_seconds() -> int:
    """A store is due when its newest run (any outcome) is older than this."""
    return _env_int("SHOPIFY_AUTO_SYNC_INTERVAL_SECONDS", 6 * 60 * 60, minimum=15 * 60)


def auto_sync_check_seconds() -> int:
    return _env_int("SHOPIFY_AUTO_SYNC_CHECK_SECONDS", 15 * 60, minimum=60)


def auto_sync_batch_size() -> int:
    return _env_int("SHOPIFY_AUTO_SYNC_MAX_SHOPS_PER_TICK", 10, minimum=1)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def active_run(db: DbSession, shop_id: int) -> ShopifySyncRun | None:
    """The queued or running run that currently owns this shop's sync, if any."""
    return db.scalar(
        select(ShopifySyncRun)
        .where(ShopifySyncRun.shop_id == shop_id, ShopifySyncRun.status.in_(ACTIVE_STATUSES))
        .order_by(ShopifySyncRun.id.desc())
        .limit(1)
    )


def _expire_abandoned_runs(db: DbSession, shop_id: int) -> None:
    """A run whose process died keeps its row; stop it blocking after the lease."""
    cutoff = _utcnow() - timedelta(seconds=lease_seconds())
    expired = db.execute(
        update(ShopifySyncRun)
        .where(
            ShopifySyncRun.shop_id == shop_id,
            ShopifySyncRun.status.in_(ACTIVE_STATUSES),
            ShopifySyncRun.started_at < cutoff,
        )
        .values(status="failed", error_message=ABANDONED_MESSAGE, finished_at=_utcnow())
        # Rows only; evaluating the date filter against loaded objects mixes
        # naive and aware datetimes on SQLite.
        .execution_options(synchronize_session=False)
    ).rowcount
    db.commit()
    if expired:
        logger.warning("Expired %s abandoned Shopify sync run(s) for shop_id=%s", expired, shop_id)


def start_run(db: DbSession, *, shop_id: int, triggered_by: str = "manual") -> ShopifySyncRun:
    """Create the run row that owns this shop's next sync and commit it.

    Raises SyncInProgress when a live run exists and RuntimeError when the
    shop has no usable Shopify connection.
    """
    conn = db.scalar(select(ShopifyConnection).where(ShopifyConnection.shop_id == shop_id))
    if conn is None or not conn.access_token or conn.uninstalled_at is not None:
        raise RuntimeError("No active Shopify connection for this workspace.")
    _expire_abandoned_runs(db, shop_id)
    with shopify_connection_lock(db, conn.shopify_domain):
        if active_run(db, shop_id) is not None:
            raise SyncInProgress(IN_PROGRESS_MESSAGE)
        run = ShopifySyncRun(shop_id=shop_id, status="queued", triggered_by=triggered_by)
        db.add(run)
        db.commit()
    db.refresh(run)
    return run


def execute_run(run_id: int, *, factory=SessionLocal, order_days_back: int = FULL_ORDER_WINDOW_DAYS) -> dict | None:
    """Perform a queued run in its own session. Never raises; failures live on the row."""
    with factory() as db:
        run = db.get(ShopifySyncRun, run_id)
        if run is None or run.status != "queued":
            return None
        shop_id = run.shop_id
        try:
            return sync_shop_now(db, shop_id=shop_id, run=run, order_days_back=order_days_back)
        except Exception as exc:
            db.rollback()
            # sync_shop_now records product-stage failures itself; anything
            # that escaped (token refresh, database errors) must still close
            # the run, or the shop stays locked until the lease expires.
            run = db.get(ShopifySyncRun, run_id)
            if run is not None and run.status in ACTIVE_STATUSES:
                run.status = "failed"
                run.error_message = _friendly_sync_error(exc)[:1000]
                run.finished_at = _utcnow()
                db.commit()
            logger.exception("Shopify sync run %s failed for shop_id=%s", run_id, shop_id)
            return None


def run_in_background(run_id: int) -> threading.Thread:
    """Execute a queued run on a daemon thread so the HTTP request can return."""
    thread = threading.Thread(
        target=execute_run, args=(run_id,), name=f"shopify-sync-{run_id}", daemon=True
    )
    thread.start()
    return thread


def recover_interrupted_sync_runs(factory=SessionLocal) -> int:
    """Close runs left queued or running by a previous process.

    Called at startup. The API runs as one Railway instance, so an active row
    at this point belongs to a process that no longer exists; without this a
    merchant would be told a sync is running for the rest of the lease.
    """
    with factory() as db:
        count = db.execute(
            update(ShopifySyncRun)
            .where(ShopifySyncRun.status.in_(ACTIVE_STATUSES))
            .values(status="failed", error_message=INTERRUPTED_MESSAGE, finished_at=_utcnow())
            .execution_options(synchronize_session=False)
        ).rowcount
        db.commit()
    return int(count or 0)


def find_run(db: DbSession, *, shop_id: int, run_id: int | None = None) -> ShopifySyncRun | None:
    """A specific run, or the latest one, belonging to this shop only."""
    query = select(ShopifySyncRun).where(ShopifySyncRun.shop_id == shop_id)
    if run_id is not None:
        query = query.where(ShopifySyncRun.id == run_id)
    return db.scalar(query.order_by(ShopifySyncRun.id.desc()).limit(1))


def serialize_run(run: ShopifySyncRun) -> dict:
    return {
        "run_id": run.id,
        "status": run.status,
        "triggered_by": run.triggered_by,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error_message": run.error_message,
        # The dict the Store Sync page renders, present once the run finished.
        "result": run.summary,
    }


# ---------- Automatic refresh ----------


def due_shop_ids(db: DbSession, *, now: datetime, interval: timedelta) -> list[int]:
    """Installed stores whose newest run started more than ``interval`` ago, or never.

    The newest run of any outcome counts, so a store whose sync keeps
    failing is retried once per interval rather than every tick. Oldest
    first, so a batch limit still reaches every store eventually.
    """
    latest = (
        select(ShopifySyncRun.shop_id, func.max(ShopifySyncRun.started_at).label("last_started"))
        .group_by(ShopifySyncRun.shop_id)
        .subquery()
    )
    rows = db.execute(
        select(ShopifyConnection.shop_id)
        .outerjoin(latest, latest.c.shop_id == ShopifyConnection.shop_id)
        .where(
            ShopifyConnection.access_token != "",
            ShopifyConnection.uninstalled_at.is_(None),
            or_(latest.c.last_started.is_(None), latest.c.last_started < now - interval),
        )
        .order_by(latest.c.last_started.asc().nulls_first(), ShopifyConnection.shop_id)
    ).all()
    return [int(shop_id) for (shop_id,) in rows]


def order_window_days(last_success: datetime | None, now: datetime) -> int:
    """Days of orders a scheduled run must re-read to stay complete.

    Imported lines are keyed by Shopify line id, so re-reading is safe but
    costs Shopify pages. After a recent successful run only the gap plus a
    two-day margin is needed; without one, the full window applies.
    """
    last_success = _as_aware(last_success)
    if last_success is None:
        return FULL_ORDER_WINDOW_DAYS
    gap_days = max(0, (now - last_success).days) + 2
    return max(MIN_ORDER_WINDOW_DAYS, min(FULL_ORDER_WINDOW_DAYS, gap_days))


def _last_successful_sync(db: DbSession, shop_id: int) -> datetime | None:
    return db.scalar(
        select(func.max(ShopifySyncRun.finished_at)).where(
            ShopifySyncRun.shop_id == shop_id, ShopifySyncRun.status == "succeeded"
        )
    )


def run_due_syncs(*, factory=SessionLocal, now: datetime | None = None) -> int:
    """Sync every due store in turn. Returns the number of runs executed."""
    now = now or _utcnow()
    interval = timedelta(seconds=auto_sync_interval_seconds())
    with factory() as db:
        shop_ids = due_shop_ids(db, now=now, interval=interval)[: auto_sync_batch_size()]
    executed = 0
    for shop_id in shop_ids:
        try:
            with factory() as db:
                days_back = order_window_days(_last_successful_sync(db, shop_id), now)
                run_id = start_run(db, shop_id=shop_id, triggered_by="scheduled").id
        except SyncInProgress:
            continue  # a merchant beat us to it; the lock did its job
        except RuntimeError as exc:
            logger.info("Automatic Shopify sync skipped shop_id=%s: %s", shop_id, exc)
            continue
        except Exception:
            logger.exception("Automatic Shopify sync could not start for shop_id=%s", shop_id)
            continue
        execute_run(run_id, factory=factory, order_days_back=days_back)
        executed += 1
    return executed


async def _scheduler_loop() -> None:
    logger.info(
        "Automatic Shopify sync enabled; per-store interval=%ss, checked every %ss",
        auto_sync_interval_seconds(),
        auto_sync_check_seconds(),
    )
    await asyncio.sleep(60)  # let startup and the health check settle first
    while True:
        try:
            count = await asyncio.to_thread(run_due_syncs)
            if count:
                logger.info("Automatic Shopify sync executed %s run(s)", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic Shopify sync tick failed")
        await asyncio.sleep(auto_sync_check_seconds())


def start_sync_scheduler() -> None:
    global _task
    if not auto_sync_enabled():
        logger.info("Automatic Shopify sync disabled by env")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_scheduler_loop())


async def stop_sync_scheduler() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    with suppress(asyncio.CancelledError):
        await _task
    _task = None
