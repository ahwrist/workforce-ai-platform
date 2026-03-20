"""pytest configuration for the backend test suite.

Uses a session-scoped event loop so the SQLAlchemy asyncpg connection pool
(created at module import time in core/database/postgres.py) is not invalidated
between test functions.  Without this, tests that share the FastAPI ASGI app
fail with "Future attached to a different loop".
"""
import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop shared by all async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
