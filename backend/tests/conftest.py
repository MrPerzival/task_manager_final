"""
tests/conftest.py
-----------------
Shared pytest fixtures.

Strategy
--------
• In-memory SQLite DB — no external services required, CI-friendly.
• Overrides get_db dependency so every route uses the test session.
• reset_db autouse fixture wipes tables between tests for full isolation.
• make_task factory fixture for DRY task creation in test bodies.
• no_sleep fixture patches asyncio.sleep to skip the 2-second delay.
"""

import sys
import os
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import Base, get_db
from main import app

# ── In-memory SQLite engine ───────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///:memory:"

_test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_test_engine,
)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all ORM tables once per test session."""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture(autouse=True)
def reset_db():
    """Truncate all tables before each test for full isolation."""
    with _test_engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.commit()
    yield


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    """Synchronous HTTP test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Skip the 2-second async delay in all tests."""
    monkeypatch.setattr("main.asyncio.sleep", AsyncMock(return_value=None))


def make_task_payload(
    title: str = "Test Task",
    description: str = "",
    due_date: str | None = None,
    status: str = "To-Do",
    blocked_by: int | None = None,
    recurring: str = "None",
) -> dict:
    payload: dict = {
        "title": title,
        "description": description,
        "status": status,
        "recurring": recurring,
    }
    if due_date:
        payload["due_date"] = due_date
    if blocked_by is not None:
        payload["blocked_by"] = blocked_by
    return payload


@pytest.fixture
def make_task(client):
    """Factory fixture — creates a task via POST and returns the response JSON."""
    def _factory(**kwargs) -> dict:
        resp = client.post("/tasks", json=make_task_payload(**kwargs))
        assert resp.status_code == 201, f"make_task failed: {resp.json()}"
        return resp.json()
    return _factory
