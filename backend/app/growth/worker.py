"""python -m app.growth.worker [--once]; supervised process or opt-in API task."""
import argparse
import asyncio
import logging
import os
import signal
import threading
import time
from sqlalchemy import text

from app.db.base import Base
from app.db.session import SessionLocal, engine
from .engine import bootstrap, run_once
from . import models  # Register growth tables without running product migrations.

_task = None


def initialize():
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("SELECT pg_advisory_xact_lock(739201601)"))
        Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables if t.name.startswith("growth_")])
    bootstrap(SessionLocal)


async def loop():
    while True:
        try:
            await asyncio.to_thread(initialize)
            break
        except Exception:
            logging.error("Growth initialization failed; retrying in 30 seconds")
            await asyncio.sleep(30)
    while True:
        try:
            worked = await asyncio.to_thread(run_once, SessionLocal)
        except Exception:
            logging.exception("Growth worker wake failed")
            worked = False
        await asyncio.sleep(1 if worked else 30)


def start():
    global _task
    if os.getenv("GROWTH_ENABLED") == "true" and (_task is None or _task.done()):
        _task = asyncio.create_task(loop())


async def stop():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    initialize()
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    while not stopped.is_set():
        try:
            worked = run_once(SessionLocal)
        except Exception:
            logging.exception("Growth worker wake failed")
            worked = False
        if args.once:
            break
        stopped.wait(1 if worked else 30)


if __name__ == "__main__":
    main()
