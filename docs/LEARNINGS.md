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

---

## Phase 1c — Synthesizer Agent / Pipeline Agent (2026-03-20)

### Patching a lazily-imported function in tests
`run_extraction()` called `from agents.synthesizer.embedder import embed_and_store` inside the
function body to avoid circular imports. This made the name unavailable at module level, so
`patch("agents.synthesizer.extractor.embed_and_store")` raised `AttributeError`.
Fix: move the import to module level (no circular import exists since embedder does not import
extractor). The patchable attribute is then `agents.synthesizer.extractor.embed_and_store`.

### pg_insert on_conflict_do_nothing — always query back for the ID
After `pg_insert(...).on_conflict_do_nothing()`, the RETURNING clause is suppressed and the
execute result has no `inserted_primary_key`. Always follow with an explicit `SELECT` on the
unique column to retrieve the ID whether the row was inserted or already existed.

---

## Phase 1b — Harvester Agent / Pipeline Agent (2026-03-20)

### Scheduler must dispatch Celery tasks, not call agents directly
The original `scheduler.py` stub referenced `pipelines.skill_pipeline:harvest_new_postings` as a
string, which APScheduler would interpret as a dotted import path for a function. This would call
the function inline in the scheduler process rather than dispatching it to the Celery worker.
Fix: define thin `_dispatch_*()` functions that call `task.delay()` to properly enqueue the work.
The scheduler process stays lightweight; the worker handles execution and retries.

### robots.txt RobotFileParser requires pre-parsing
`urllib.robotparser.RobotFileParser` must have `.parse()` called on it explicitly — setting
`allow_all = True` on an instance is not a standard attribute, but it works as a sentinel we check
in `_is_allowed()`. For parsed robots.txt content use `.parse(lines)`. For the "allow all" fallback
(no robots.txt or fetch error) simply set `rp.allow_all = True` and guard in `_is_allowed()`.

### Admin endpoint 503 vs 200 in tests
When Celery broker (Redis) is unreachable in the test environment, `task.delay()` raises a
connection error and the admin endpoint returns 503. The harvester tests only assert on the 403
(bad key) and 422 (missing header) paths — they do not test the success 200 path — so tests pass
regardless of whether Redis is available in CI. Document this: the 200 path is verified manually
via `docker compose exec api` with a running Celery worker.

### IntegrityError race condition in _insert_new_postings
URL-level dedup via `SELECT ... WHERE url = $url` + `session.flush()` has a TOCTOU race window if
multiple workers run concurrently. Guard with `except IntegrityError → rollback + skip` so the
unique constraint on `job_postings.url` is the final arbiter. Always call `await session.rollback()`
before continuing the loop after an IntegrityError — SQLAlchemy async sessions are not usable after
an unhandled exception without a rollback.
