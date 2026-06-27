from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker


def get_db_url() -> str:
    return os.environ.get("CYBERGUARD_DB_URL", "sqlite:///./cyberguard-dev.db")


def make_engine(url: str | None = None) -> sa.Engine:
    db_url = url or get_db_url()
    connect_args: dict = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return sa.create_engine(db_url, connect_args=connect_args)


@contextmanager
def get_session(db_url: str | None = None) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy Session, committing on clean exit and rolling back on error."""
    engine = make_engine(db_url)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
