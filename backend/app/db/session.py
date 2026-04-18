import os
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_DATABASE_URL = "sqlite:///./shopify_analytics_engine.db"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def is_sqlite_database_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def create_sqlalchemy_engine(database_url: str | None = None):
    resolved_database_url = database_url or get_database_url()
    engine_kwargs = {
        "echo": os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
    }

    if is_sqlite_database_url(resolved_database_url):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["pool_pre_ping"] = True

    return create_engine(
        resolved_database_url,
        **engine_kwargs,
    )


engine = create_sqlalchemy_engine()


def create_session_factory(bind_engine=None):
    return sessionmaker(
        bind=bind_engine or engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


SessionLocal = create_session_factory()


def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
