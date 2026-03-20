# CURRENT_TASK.md

## Phase: Phase 1c — Synthesizer Agent
## Epic: Synthesizer & Embedder (Epic 1.3)
## Status: COMPLETE
## Assigned To: Pipeline Agent
## Started: 2026-03-20
## Completed: 2026-03-20

---

## Objective
Implement the Synthesizer agent so it processes all `job_postings WHERE processed = FALSE`,
extracts structured skill entities via Claude (LangChain), generates embeddings via OpenAI
`text-embedding-3-small`, and stores results in `skills`, `job_posting_skills`, and Qdrant.

## Acceptance Criteria
- [x] `run_extraction()` in `agents/synthesizer/extractor.py` — processes all unprocessed postings
- [x] LangChain extraction chain returns `{"skills": [{"name", "type", "context_snippet"}]}`
- [x] Extracted skills upserted to `skills` table (surface-level dedup: normalize case/punctuation)
- [x] `job_posting_skills` junction rows created for each extracted skill
- [x] `JobPosting.processed` set to `TRUE` on success, `extraction_failed = TRUE` on error
- [x] `embed_and_store()` in `agents/synthesizer/embedder.py` — batch embeds skill names via OpenAI
- [x] Embeddings upserted to Qdrant `skills` collection (collection created by lifespan hook)
- [x] Celery task `extract_skills_from_postings` in `pipelines/skill_pipeline.py` wires to `run_extraction()`
- [x] Admin endpoint `POST /api/v1/admin/synthesize/trigger` works end-to-end (already wired, verify)
- [x] Tests added to `backend/tests/test_synthesizer.py` — 14 tests (8 minimum satisfied)
- [x] All 50 tests pass (36 pre-existing + 14 new)

## Context Files to Read First
- `AGENT_ROLES.md` — Role 2: The Synthesizer (interface contract + LLM prompt contract)
- `backend/core/models/skill.py` — Skill ORM model (upsert target)
- `backend/core/models/job_posting.py` — JobPosting model (read + mark processed)
- `backend/core/database/qdrant.py` — Qdrant client + collection setup
- `backend/agents/synthesizer/extractor.py` — current stub
- `backend/agents/synthesizer/embedder.py` — current stub

## Scope — Files You May Modify
- `backend/agents/synthesizer/extractor.py` — full implementation
- `backend/agents/synthesizer/embedder.py` — full implementation
- `backend/tests/test_synthesizer.py` — new file

## Do NOT Touch
- `backend/core/models/` — models are complete; do not alter without flagging
- `backend/api/` — admin router already wired
- `backend/agents/harvester/` — complete
- `data/migrations/` — no new migrations needed

---

## Previous Phase: Phase 1b — Skills API (Epic 1.5) — COMPLETE (2026-03-20)

**Assigned To**: API Agent

**Delivered:**
- `backend/api/schemas/skills.py` — added PaginatedSkills, TrendingSkillItem, DomainResponse
- `backend/api/routers/skills.py` — implemented all 3 skills endpoints
- `backend/api/routers/domains.py` — new file, GET /api/v1/domains/ with taxonomy.yaml labels
- `backend/main.py` — registered domains router
- `backend/tests/test_skills_api.py` — new file, 10 API-level tests
- `backend/tests/conftest.py` — session-scoped event loop fixture
- `backend/pyproject.toml` — added asyncio_default_fixture_loop_scope = "session"

**Verified:** 21 tests passed.

---

## Previous Phase: Phase 1b — Harvester Agent (Epic 1.2) — COMPLETE (2026-03-20)

**Assigned To**: Pipeline Agent

**Delivered:**
- `backend/agents/harvester/sources.py` — expanded to 24 companies (14 Greenhouse, 7 Lever, 3 HTML)
- `backend/agents/harvester/scraper.py` — full async implementation: Greenhouse API, Lever API,
  BeautifulSoup HTML, robots.txt compliance, exponential backoff on 429/503, per-company
  error isolation, URL-level dedup, structured run summary logging
- `backend/agents/harvester/scheduler.py` — APScheduler dispatches Celery tasks (not inline runs)
- `backend/api/routers/admin.py` — API key validation + Celery task dispatch for all three
  pipeline trigger endpoints
- `backend/tests/test_harvester.py` — 15 new tests

**Verified:** 36 tests passed (21 pre-existing + 15 new).

---

## Previous Phase: Phase 1a Infra Blockers — COMPLETE (2026-03-20)

**Assigned To**: Infrastructure Agent

**Fixes delivered:**
- `frontend/package-lock.json` — generated via `npm install`; required for `npm ci` in `Dockerfile.frontend`
- `frontend/next.config.ts` → `frontend/next.config.mjs` — Next.js 14 does not support `.ts` config; renamed and converted to valid ESM
- `docker-compose.override.yml` — corrected from `!reset` (clears list) to `!override` (replaces list) for postgres/redis port remapping; added nginx port remap (`8080:80`) to resolve host port 80 conflict; added `frontend.build.target: dev` to use the dev stage instead of failing production builder
- `Makefile` `test-backend` — fixed path `backend/tests/` → `tests/` (container working directory is `/app` = `./backend`)

**Verified:**
- `docker compose ps` — all 7 services running (postgres healthy, redis, qdrant, api, worker, frontend, nginx)
- `docker compose exec api pytest tests/ -v --tb=short` — 21 passed
- `make health` — API, Qdrant, Redis all respond; no ❌ lines

---

## Previous Phase: Phase 1a — Foundation — COMPLETE (2026-03-20)

**Objective**: Verify all SQLAlchemy ORM models are complete and correct, run Alembic migrations,
and seed the canonical skill taxonomy.

**Verified:**
- `make migrate` — 7 tables created: `users`, `job_postings`, `skills`, `job_posting_skills`,
  `survey_sessions`, `survey_messages`, `survey_extractions`
- `make seed` — 32 anchor skills seeded across 6 domains
- `pytest tests/ -v` — 11 tests passed

---

## Previous Phase: Phase 0 — Infra Skeleton — COMPLETE (2026-03-20)

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
