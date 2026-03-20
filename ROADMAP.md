# Product Roadmap

**Status Legend**: 🔲 Planned | 🔄 In Progress | ✅ Complete | ⏸ Deferred

---

## Phase 0 — Foundation (Infrastructure Sprint)
*Target: Complete before any feature work begins*

### Goals
Get the full local development environment running end-to-end with all services communicating. No features yet — just a working skeleton.

### Deliverables

**Infrastructure**
- 🔲 `docker-compose.yml` with: PostgreSQL, Qdrant, Redis, FastAPI, Celery worker, Nginx, Next.js
- 🔲 Nginx routing: `/api/*` → FastAPI, `/*` → Next.js
- 🔲 `Makefile` with all convenience commands (`up`, `down`, `migrate`, `seed`, `test`, `logs`)
- 🔲 `.env.example` with all required environment variables documented

**Backend Skeleton**
- 🔲 FastAPI app entrypoint (`main.py`) with health check endpoint (`GET /health`)
- 🔲 Pydantic settings via `core/config/settings.py` (env-driven, validates on startup)
- 🔲 SQLAlchemy async engine + session factory (`core/database/postgres.py`)
- 🔲 Qdrant client initialization (`core/database/qdrant.py`)
- 🔲 Alembic configured and initial migration created (`data/migrations/`)
- 🔲 Celery app entrypoint (`celery_app.py`) with a test task

**Frontend Skeleton**
- 🔲 Next.js 14 project initialized with App Router, TypeScript, Tailwind CSS
- 🔲 shadcn/ui initialized with base components
- 🔲 Root layout with Navbar and Footer placeholders
- 🔲 Route structure created (marketing, dashboard, survey)
- 🔲 Typed API client (`lib/api.ts`) pointing to FastAPI base URL

**Database**
- 🔲 All SQLAlchemy ORM models defined: `User`, `JobPosting`, `Skill`, `JobPostingSkill`, `SurveySession`, `SurveyMessage`, `SurveyExtraction`, `Subscriber`
- 🔲 Initial Alembic migration applied successfully
- 🔲 Seed script for skill taxonomy (`scripts/seed_taxonomy.py`)

**Testing**
- 🔲 `pytest` configured for backend with one passing smoke test
- 🔲 `vitest` configured for frontend with one passing smoke test
- 🔲 `make test` runs both suites cleanly

**Acceptance Criteria**: `make up && make migrate && make seed` results in all containers healthy, `GET /health` returns 200, and the Next.js homepage loads at `localhost:3000`.

---

## Phase 1 — MVP: Signal & Presence
*Target: First externally sharable version*

### Goals
Launch a credible public presence with three working surfaces: consulting pages, a basic (read-only) skills dashboard, and a functional conversational survey agent. The backend pipeline must be harvesting and processing real job data.

### Epic 1.1 — Marketing & Consulting Pages

- 🔲 **Homepage**: Hero section, problem statement, services preview, skill dashboard teaser, email lead capture (DB write only)
- 🔲 **Services Page**: Three-tier service cards (1:1, Team, Enterprise) with CTAs
- 🔲 **About Page**: Founder narrative, enterprise AI credentials, platform thesis
- 🔲 **Contact / Book Page**: Calendly embed (or placeholder booking form writing to DB)
- 🔲 **SEO Foundation**: `generateMetadata` on all pages, `robots.txt`, `sitemap.xml` via `next-sitemap`, OG image template
- 🔲 **Blog Shell**: MDX pipeline configured, one seed article published

### Epic 1.2 — Harvester Agent (MVP) ✅ COMPLETE (2026-03-20)

- ✅ Target company list defined in `agents/harvester/sources.py`: 24 companies across Greenhouse (14), Lever (7), and HTML (3)
- ✅ `scraper.py`: Async scraping with `httpx` + `BeautifulSoup`, respects `robots.txt`, exponential backoff on 429/503
- ✅ Deduplication: URL-level dedup before inserting to `job_postings`
- ✅ `scheduler.py`: APScheduler cron job dispatching Celery tasks (harvest 2 AM, synthesize 4 AM, classify 6 AM UTC)
- ✅ Admin endpoint (`POST /api/v1/admin/harvest/trigger`) for manual triggering (API-key protected)
- ✅ Harvester logs run summary to structured log (postings found, new, skipped, errors)

### Epic 1.3 — Synthesizer Agent (MVP)

- 🔲 `extractor.py`: LangChain chain that takes raw job posting text and returns structured skill list
- 🔲 Prompt design: Extracts skill name, skill type, and contextual snippet. Returns JSON.
- 🔲 Batch processing: Processes all `job_postings` where `processed = FALSE`
- 🔲 `embedder.py`: Generates embeddings for each canonical skill name using `text-embedding-3-small`, stores in Qdrant
- 🔲 Celery task wrapping the full extraction flow, triggered post-harvest
- 🔲 Admin endpoint (`POST /api/v1/admin/synthesize/trigger`) for manual run

### Epic 1.4 — Taxonomist Agent (MVP)

- 🔲 `taxonomy.yaml`: Define the canonical domain taxonomy (7 initial domains, 3–5 subdomains each, ~50 canonical skill anchors)
- 🔲 `mapper.py`: For each extracted skill, classify into domain + subdomain using LLM classification prompt with taxonomy as context
- 🔲 Deduplication: Fuzzy match + embedding similarity to collapse variant skill names onto canonical entries (e.g., "LangChain", "LangChain framework", "langchain" → `LangChain`)
- 🔲 Celery task wrapping taxonomy mapping, triggered post-synthesis

### Epic 1.5 — Skills Dashboard (Read-Only MVP)

- 🔲 `GET /api/v1/skills` endpoint: paginated, filterable by domain
- 🔲 `GET /api/v1/skills/trending` endpoint: top 25 skills per domain, last 30 days
- 🔲 `GET /api/v1/domains` endpoint: domain list with posting counts
- 🔲 `SkillDashboard` page: domain filter bar, trending skills table
- 🔲 `SkillDetailPanel`: slide-over with skill description, example companies, related skills (Qdrant similarity query)
- 🔲 No authentication required for read access in MVP
- 🔲 Data freshness indicator displayed prominently

### Epic 1.6 — Survey / Interviewer Agent (MVP)

- 🔲 `agent.py`: LangChain conversational agent with Claude backend
- 🔲 `prompts.py`: System prompt encoding the researcher persona + question protocol + behavioral rules
- 🔲 Session management: create session, persist all messages, detect completion
- 🔲 Streaming: `/api/v1/survey/message` returns SSE stream
- 🔲 Chat UI: `ChatWindow`, `MessageBubble`, `TypingIndicator`, `InputBar` components
- 🔲 Closing CTA: Post-interview card with domain-relevant Skill Dashboard link and booking CTA
- 🔲 Anonymous sessions: No authentication required to take the survey

**MVP Launch Acceptance Criteria**:
1. Harvest pipeline runs automatically every 24h and populates `job_postings`
2. Skill extraction and taxonomy mapping runs and populates `skills` table
3. Skills dashboard shows real data, filterable by at least 3 domains
4. Survey agent completes a full 8-turn interview and persists the session
5. All marketing pages load and pass Core Web Vitals audit
6. Email capture form writes to `subscribers` table

---

## Phase 2 — V2: Personalization & Intelligence
*Target: Post-MVP, after validating user demand*

### Goals
Add user accounts, personalized skill profiles, gap analysis, and survey data extraction into a research dataset. Transform the platform from a read-only tool into a personalized career intelligence system.

### Epic 2.1 — Authentication & User Accounts

- 🔲 NextAuth.js with email/password + Google OAuth
- 🔲 JWT-based API authentication
- 🔲 User profile: domain, target domain, role, experience level
- 🔲 Session persistence across devices

### Epic 2.2 — Personalized Skill Profiles

- 🔲 "My Skills" module: mark skills as current or target
- 🔲 Gap Analysis view: skills required in target domain minus skills flagged as current
- 🔲 Skill affinity score: how well current skills map to target domain (vector similarity aggregation)
- 🔲 Saved domain preferences persist across sessions

### Epic 2.3 — Skill Alerts

- 🔲 Users subscribe to domains or specific skills
- 🔲 Weekly digest email (via Resend) with new trending skills in subscribed domains
- 🔲 Alert threshold: skill must appear in 10+ new postings within 7 days to trigger

### Epic 2.4 — Survey Extraction Pipeline

- 🔲 `storage.py`: Post-session LLM extraction of structured data from raw conversation transcript
- 🔲 Populate `survey_extractions` table with structured fields (role, industry, tools, anxiety, etc.)
- 🔲 Taxonomist classifies domain from self-reported role
- 🔲 Admin dashboard (internal): view aggregated survey insights by domain, anxiety type, tool adoption

### Epic 2.5 — Semantic Skill Search

- 🔲 `GET /api/v1/skills/search?q=` endpoint using Qdrant vector search
- 🔲 Natural language skill queries: "skills for building AI products" → ranked results
- 🔲 Search bar integrated into Dashboard header

### Epic 2.6 — Expanded Data Sources

- 🔲 LinkedIn Jobs scraping (rate-limited, proxy-rotated)
- 🔲 HackerNews Who's Hiring thread parsing (monthly)
- 🔲 Expand target company list to 100+

---

## Phase 3 — V3: Upskilling Roadmaps & Research Platform
*Target: Revenue-generating, research-publishable*

### Goals
Close the loop from skill intelligence to actionable upskilling roadmaps. Monetize via subscriptions. Publish workforce research assets from aggregated survey data.

### Epic 3.1 — AI-Generated Upskilling Roadmaps

- 🔲 Authenticated users with a saved gap analysis can generate a personalized upskilling roadmap
- 🔲 Roadmap is structured: Phase 1 (0–30 days), Phase 2 (30–90 days), Phase 3 (90–180 days)
- 🔲 Each phase contains: skills to acquire, recommended resource types (not specific paid courses), estimated time investment, milestone markers
- 🔲 Roadmap is saved and can be revised on subsequent sessions
- 🔲 Roadmap generation is a paid feature (subscription gate)

### Epic 3.2 — Subscription & Payments

- 🔲 Stripe integration: monthly subscription for personalized roadmaps + alerts
- 🔲 Free tier: read-only dashboard + one survey session
- 🔲 Pro tier: full personalization, alerts, roadmap generation, research downloads

### Epic 3.3 — Research Report Generation

- 🔲 Aggregated survey data (anonymized) used to generate quarterly Workforce AI Readiness Reports
- 🔲 Reports segmented by domain, industry, experience level
- 🔲 Published as gated content (email capture or Pro subscription)
- 🔲 Agent-assisted: LangChain chain synthesizes report sections from extracted survey data + trending skill data

### Epic 3.4 — Enterprise Features

- 🔲 Team accounts: org-level skill profiles and gap analysis
- 🔲 Custom domain monitoring: enterprise clients configure their own target companies
- 🔲 Dedicated research reports: custom audience-specific workforce readiness analysis
- 🔲 White-glove onboarding for enterprise tier

### Epic 3.5 — Blog & Content Engine

- 🔲 Agent-assisted blog post drafting from skill trend data (The Synthesizer generates weekly "Skill of the Week" post drafts)
- 🔲 Newsletter integration (Resend) with automated weekly digest from new skill data
- 🔲 Content calendar management (internal admin tool)

---

## Technical Debt & Infrastructure Milestones

These run parallel to the feature phases and must not be deferred beyond the indicated phase:

| Item | Required By |
|---|---|
| Backend test coverage > 80% | End of MVP |
| Frontend E2E tests (Playwright) for critical flows | End of V2 |
| Structured logging + alerting (Sentry / Datadog) | End of MVP |
| API rate limiting on all public endpoints | End of MVP |
| Automated scraper health monitoring | End of V2 |
| PostgreSQL read replica for analytics queries | End of V2 |
| CI/CD pipeline (GitHub Actions) | End of V2 |
| Secrets management (Doppler or AWS SSM) | End of V2 |
| Horizontal scaling for Celery workers | End of V3 |
