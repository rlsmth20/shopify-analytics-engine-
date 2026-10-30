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
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
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


class SyncInProgress(RuntimeError):
    """Another run for this shop is queued or running."""


def lease_seconds() -> int:
    """How long a queued/running row keeps its claim before it counts as abandoned."""
    try:
        return max(60, int(os.getenv("SHOPIFY_SYNC_LEASE_SECONDS", "3600")))
    except ValueError:
        return 3600


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


def execute_run(run_id: int, *, factory=SessionLocal) -> dict | None:
    """Perform a queued run in its own session. Never raises; failures live on the row."""
    with factory() as db:
        run = db.get(ShopifySyncRun, run_id)
        if run is None or run.status != "queued":
            return None
        shop_id = run.shop_id
        try:
            return sync_shop_now(db, shop_id=shop_id, run=run)
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
