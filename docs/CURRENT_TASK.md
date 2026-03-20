# CURRENT_TASK.md

## Phase: Phase 1b — Skills API
## Epic: Skills & Domains Endpoints (Epic 1.5)
## Status: COMPLETE
## Assigned To: API Agent
## Started: 2026-03-20
## Completed: 2026-03-20

---

## Objective
Implement all Skills API endpoints so the 32 seeded canonical skills are queryable via REST.

## Acceptance Criteria
- [x] GET /api/v1/skills/ returns 200 with 32 seeded skills, paginated (cursor-based)
- [x] GET /api/v1/domains/ returns 200 with all 6 domains and correct skill counts
- [x] GET /api/v1/skills/{valid-id} returns 200; GET /api/v1/skills/{bad-id} returns 404 with error envelope
- [x] GET /api/v1/skills/trending returns 200 (empty list acceptable — no harvested postings yet)
- [x] 21 tests pass (11 pre-existing + 10 new in test_skills_api.py)
- [x] `make migrate` still runs cleanly — no new migrations added

## Files Modified
- `backend/api/schemas/skills.py` — added PaginatedSkills, TrendingSkillItem, DomainResponse
- `backend/api/routers/skills.py` — implemented all 3 skills endpoints
- `backend/api/routers/domains.py` — new file, GET /api/v1/domains/ with taxonomy.yaml labels
- `backend/main.py` — registered domains router
- `backend/tests/test_skills_api.py` — new file, 10 API-level tests
- `backend/tests/conftest.py` — new file, session-scoped event loop fixture
- `backend/pyproject.toml` — added asyncio_default_fixture_loop_scope = "session"

---

## Previous Phase: Phase 1a — Foundation — COMPLETE (2026-03-20)

---

## Objective
Verify all SQLAlchemy ORM models are complete and correct, run Alembic migrations to create all tables, and seed the canonical skill taxonomy — so subsequent agents have a fully-populated, healthy database to build on.

## Acceptance Criteria
- [x] `make up` starts all services cleanly — NOTE: `make up` as written fails because (a) frontend/package-lock.json is missing (requires Infrastructure Agent to run `npm install` in `frontend/`) and (b) ports 5432/6379 conflict with other running projects on this machine. Backend services (postgres, api, qdrant, redis, worker) were started successfully via `docker run` on `platform-net`. See LEARNINGS.md for details.
- [x] `make migrate` runs `alembic upgrade head` with zero errors and creates all 7 tables: `users`, `job_postings`, `skills`, `job_posting_skills`, `survey_sessions`, `survey_messages`, `survey_extractions`
- [x] `make shell-db` → `\dt` shows all 7 tables present (verified via `docker exec ... psql`)
- [x] `make seed` runs `scripts/seed_taxonomy.py` without errors and logs all taxonomy domains — 32 anchor skills inserted across 6 domains
- [x] `make test-backend` passes all 11 tests in `backend/tests/` — NOTE: `make test-backend` uses path `backend/tests/` which is wrong inside the container (should be `tests/`). Tests were run directly with `pytest tests/ -v`. See LEARNINGS.md.

## Context Files to Read First
- `ARCHITECTURE.md` — section 6 (Database Schema) for table relationships
- `AGENT_ROLES.md` — Role 1–4 interface contracts (what each agent reads/writes)
- `backend/core/models/` — all four ORM model files
- `data/migrations/env.py` — Alembic async configuration
- `backend/alembic.ini` — migration script location config

## Known Risks (check LEARNINGS.md for detail)
- Alembic env.py converts `asyncpg` URL to `psycopg2` for sync migrations — verify psycopg2-binary is installed
- ARRAY and JSONB column types require PostgreSQL — will fail on SQLite
- Model imports in `data/migrations/env.py` use absolute path `/app` — only works inside the Docker container

## Scope — Files You May Modify
- `backend/core/models/*.py` — fix any ORM issues
- `data/migrations/env.py` — fix any Alembic config issues
- `data/migrations/versions/` — create initial migration revision if needed
- `backend/scripts/seed_taxonomy.py` — implement taxonomy seed logic
- `backend/tests/` — add model/migration smoke tests

## Do NOT Touch
- `docker-compose.yml`
- `infra/`
- `frontend/`
- `backend/main.py`
- `backend/api/`
- `backend/agents/`

## Handoff Instructions
When all criteria are checked:
1. Run `make test-backend` — all tests must pass
2. Run `make shell-db` and paste `\dt` output to confirm all 7 tables exist
3. Update this file: set Status to COMPLETE, add "Completed: [date]"
4. Add a LEARNINGS.md entry if anything required debugging or iteration
5. Commit: `git commit -m "feat(phase-1a): database models and migrations"`
6. Do not start Phase 1b — wait for operator assignment.

---

## Previous Phase

### Phase 0 — Infra Skeleton — COMPLETE (2026-03-20)
Built by: Infrastructure Agent

**Delivered:**
- `infra/docker/Dockerfile.{backend,worker,frontend}`
- `infra/nginx/nginx.conf` (with SSE buffering disabled per LEARNINGS.md)
- `backend/main.py` — FastAPI app with `/health`, all routers registered
- `backend/requirements.txt`, `backend/alembic.ini`, `backend/celery_app.py`
- `backend/core/` — settings, logging, postgres async engine, qdrant client
- `backend/core/models/` — User, JobPosting, Skill, JobPostingSkill, SurveySession, SurveyMessage, SurveyExtraction
- `backend/api/routers/` — skills, survey, auth, admin (skeleton)
- `backend/agents/` — harvester, synthesizer, taxonomist, interviewer (stubs)
- `backend/agents/taxonomist/taxonomy.yaml` — canonical taxonomy definition
- `data/migrations/env.py` + `script.py.mako` — Alembic async config
- `frontend/` — Next.js 14 skeleton with placeholder pages
- `.env` — all API keys and DB credentials configured
- `docker-compose.yml` — updated with `./data:/data` volume mounts and `POSTGRES_PASSWORD` from env
