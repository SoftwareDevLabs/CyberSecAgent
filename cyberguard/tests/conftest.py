"""Shared pytest fixtures for the CyberGuard test suite."""
from __future__ import annotations

import os

import pytest
from sqlalchemy.orm import sessionmaker

from pipeline.db.models import Base
from pipeline.db.session import make_engine


@pytest.fixture(scope="session", autouse=True)
def _set_test_db_url() -> None:
    """Point all tests at an in-memory SQLite database."""
    os.environ.setdefault("CYBERGUARD_DB_URL", "sqlite:///:memory:")


@pytest.fixture
def db_engine():
    """Create all tables in a fresh in-memory SQLite engine for each test."""
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """Yield a Session that rolls back after each test — no state leaks between tests."""
    factory = sessionmaker(bind=db_engine)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
