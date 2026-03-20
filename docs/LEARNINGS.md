# LEARNINGS.md

This file records debugging sessions, failure modes, and non-obvious decisions encountered
during development. Every agent must add an entry for any task that required iteration.

---

## Phase 1a — Database Agent (2026-03-20)

### `make up` fails — port conflicts and missing package-lock.json
`make up` (docker-compose up) fails for two reasons:
1. `frontend/package-lock.json` is missing — the frontend Docker build fails with `npm ci` because
   there is no lockfile. Fix: Infrastructure Agent must run `npm install` in `frontend/` first, or
   change the Dockerfile to use `npm install` instead of `npm ci`.
2. Ports 5432 (PostgreSQL) and 6379 (Redis) conflict with other projects already running on the host.
   Fix: Use `docker run` with `--network platform-net` to start backend services on a named bridge
   network, bypassing the host port bindings for local dev.

### `make test-backend` wrong path inside container
The Makefile runs `pytest backend/tests/` but the container's WORKDIR is `/app` and tests live at
`/app/tests/`. Run `pytest tests/ -v` directly instead of `make test-backend`.

### Alembic asyncpg → psycopg2 conversion
`data/migrations/env.py` converts the `asyncpg://` DATABASE_URL to `psycopg2://` for sync
migrations. `psycopg2-binary` must be installed in the container — it is listed in
`backend/requirements.txt` and installed in the Docker image.

---

## Phase 1b — API Agent (2026-03-20)

### pytest-asyncio + asyncpg "Future attached to a different loop"
**Symptom:** ~half the new API tests fail with `RuntimeError: Task ... got Future ... attached to a
different loop`. The failing tests are not predictable — they depend on which prior test first
established a pool connection.

**Root cause:** `core/database/postgres.py` creates the SQLAlchemy `AsyncEngine` (and its asyncpg
connection pool) at module import time. pytest-asyncio 0.24 defaults to function-scoped event loops,
so each test function runs in a fresh loop. When a test reuses a pooled connection established in an
earlier test's loop, asyncpg raises the "different loop" error.

**Fix:** Add `backend/tests/conftest.py` with a session-scoped `event_loop` fixture so all tests in
the session share one event loop. Also set `asyncio_default_fixture_loop_scope = "session"` in
`pyproject.toml`. The `event_loop` override is deprecated in pytest-asyncio 0.24 but remains
functional; it produces one deprecation warning per test session.

**Alternative (not taken):** Recreate the engine per-test (as test_models.py does) — but this
would require overriding `get_db` in the FastAPI app per test, which is more invasive.

### `/api/v1/domains/` route placement
Domains are semantically separate from skills but the task brief put them under `/api/v1/domains/`.
Created a new router file `backend/api/routers/domains.py` and registered it in `main.py`.
Do not nest domains under the skills router to keep prefix logic clean.

### taxonomy.yaml path inside container
`backend/agents/taxonomist/taxonomy.yaml` is at `/app/agents/taxonomist/taxonomy.yaml` inside the
container. The domains router resolves the path relative to `__file__` using `pathlib`:
`Path(__file__).parent.parent.parent / "agents" / "taxonomist" / "taxonomy.yaml"`.
This resolves correctly both inside the container (`/app/api/routers/domains.py` → `/app/agents/...`)
and in local development.

### Cursor pagination implementation
Used base64-encoded integer offset (not keyset pagination). This is simpler and sufficient for an
MVP with 32–hundreds of skills. If the skill table grows to tens of thousands, consider switching
to keyset pagination on `(canonical_name, id)` for stable ordering under concurrent inserts.
