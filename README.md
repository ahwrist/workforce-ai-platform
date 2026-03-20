# WorkforceAI Platform

> *Translating enterprise-grade AI adoption strategy into individual and team workforce modernization.*

---

## Vision

The AI era is not a disruption that happens to workers — it is a transition that can be navigated with the right intelligence and guidance. WorkforceAI is a full-stack consulting and upskilling platform that bridges the gap between frontier AI capability and real workforce readiness.

The platform is built on a core thesis: **the future of knowledge work runs on agent orchestration.** Not just using AI tools, but designing, deploying, and directing systems of AI agents to amplify human judgment. Workers who understand this paradigm will lead. Those who don't will be displaced by those who do.

WorkforceAI serves professionals and teams navigating career transitions, domain-specific upskilling, and strategic AI adoption — backed by the same systems-level rigor used to modernize large, change-resistant organizations.

---

## The Core Problem

Three forces are colliding simultaneously:

1. **Skill signal decay**: Job requirements are evolving faster than any individual's ability to track them. Traditional job boards and LinkedIn skills are lagging indicators. Workers and teams are making career investments based on stale data.
2. **Upskilling noise**: The market is flooded with courses, certifications, and bootcamps that optimize for enrollment, not outcomes. There is no trusted, data-driven signal for what skills actually matter at frontier companies right now.
3. **Transition paralysis**: Most career coaching addresses soft skills and resume polish. It does not address the strategic question: *how do I architect my role for the AI era?* Especially for workers in non-technical domains who feel left behind by the discourse.

---

## What WorkforceAI Does

| Pillar | Description |
|---|---|
| **Consulting & Coaching** | B2B and 1:1 services for enterprise AI adoption strategy, team upskilling programs, and individual career transition coaching |
| **Frontier Skills Engine** | A live, automated data pipeline that scrapes frontier tech company job postings, extracts emerging skill signals, and surfaces them as interactive, domain-filterable Skill Profiles |
| **Survey Research Agent** | A conversational AI interviewer that replaces static forms — capturing rich qualitative data on career anxieties, current tool usage, and upskilling goals from users |

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js)                  │
│  Marketing Pages │ Skill Dashboard │ Survey Chat UI     │
└────────────────────────┬────────────────────────────────┘
                         │ REST / WebSocket
┌────────────────────────▼────────────────────────────────┐
│                  BACKEND API (FastAPI)                   │
│   /skills   │   /survey   │   /auth   │   /admin        │
└──────┬───────────────────┬────────────────────┬─────────┘
       │                   │                    │
┌──────▼──────┐   ┌────────▼────────┐   ┌──────▼──────┐
│  PostgreSQL │   │   Qdrant        │   │   Redis     │
│  (Primary)  │   │  (Vector DB)    │   │  (Cache /   │
│  Users,     │   │  Skill embeds,  │   │   Sessions) │
│  Survey,    │   │  JD chunks,     │   │             │
│  Jobs cache │   │  Chat history   │   │             │
└─────────────┘   └─────────────────┘   └─────────────┘
       ▲
┌──────┴──────────────────────────────────────────────────┐
│              AGENT PIPELINE (Python / APScheduler)      │
│  Harvester → Synthesizer → Taxonomist → Interviewer     │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend Framework | Next.js 14 (App Router) | SSR/SSG for SEO on marketing pages, RSC for dashboard perf |
| Styling | Tailwind CSS + shadcn/ui | Rapid composition, accessible primitives |
| Backend API | FastAPI (Python 3.11+) | Async-native, Pydantic validation, OpenAPI auto-docs |
| Task Queue | Celery + Redis | Distributed agent pipeline execution |
| Primary DB | PostgreSQL 16 | Relational integrity for users, jobs, survey responses |
| Vector DB | Qdrant | Dense vector similarity search for skill matching |
| LLM Orchestration | LangChain / Anthropic SDK | Skill extraction, taxonomy mapping, conversational agent |
| Auth | NextAuth.js + JWT | Session management, future OAuth integration |
| Containerization | Docker + Docker Compose | Local dev parity, deployment portability |
| Reverse Proxy | Nginx | SSL termination, routing frontend/backend |

---

## Repository Structure

```
workforce-ai-platform/
├── frontend/                        # Next.js 14 web application
│   ├── app/
│   │   ├── (marketing)/             # Route group: public-facing pages
│   │   │   ├── page.tsx             # Homepage / hero
│   │   │   ├── services/page.tsx    # Consulting services
│   │   │   ├── about/page.tsx
│   │   │   └── layout.tsx
│   │   ├── dashboard/               # Skill Profiles dashboard (auth-gated)
│   │   │   ├── page.tsx
│   │   │   ├── [domain]/page.tsx    # Domain-specific skill profile
│   │   │   └── layout.tsx
│   │   ├── survey/                  # Conversational Survey Agent UI
│   │   │   ├── page.tsx
│   │   │   └── layout.tsx
│   │   ├── api/                     # Next.js API routes (thin proxy/auth layer)
│   │   │   ├── auth/[...nextauth]/route.ts
│   │   │   └── proxy/[...path]/route.ts
│   │   ├── layout.tsx               # Root layout
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                      # shadcn/ui primitives
│   │   ├── charts/                  # Skill trend visualizations (Recharts)
│   │   ├── survey/                  # Chat interface components
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   └── TypingIndicator.tsx
│   │   └── layout/
│   │       ├── Navbar.tsx
│   │       ├── Footer.tsx
│   │       └── Sidebar.tsx
│   ├── lib/
│   │   ├── api.ts                   # Typed fetch wrapper for FastAPI
│   │   ├── auth.ts                  # NextAuth config
│   │   └── utils.ts
│   ├── styles/
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                         # Python FastAPI backend + agent pipeline
│   ├── agents/
│   │   ├── harvester/               # Job posting scraper agent
│   │   │   ├── __init__.py
│   │   │   ├── scraper.py           # Source-specific scraping logic
│   │   │   ├── sources.py           # Configured target companies/boards
│   │   │   └── scheduler.py        # APScheduler job definitions
│   │   ├── synthesizer/             # LLM skill extraction agent
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py         # Prompt chains for skill extraction
│   │   │   └── embedder.py          # Vector embedding generation
│   │   ├── taxonomist/              # Skill mapping + domain classification
│   │   │   ├── __init__.py
│   │   │   ├── mapper.py            # Skill → domain taxonomy mapping
│   │   │   └── taxonomy.yaml        # Canonical skill taxonomy definition
│   │   └── interviewer/             # Conversational survey agent
│   │       ├── __init__.py
│   │       ├── agent.py             # LangChain agent definition
│   │       ├── prompts.py           # System prompts and question flows
│   │       └── storage.py          # Survey response persistence
│   ├── api/
│   │   ├── routers/
│   │   │   ├── skills.py            # GET /skills, /skills/{domain}
│   │   │   ├── survey.py            # POST /survey/message, GET /survey/session
│   │   │   ├── auth.py              # POST /auth/token, /auth/refresh
│   │   │   └── admin.py             # Pipeline trigger endpoints (protected)
│   │   ├── schemas/
│   │   │   ├── skills.py            # Pydantic models for skill responses
│   │   │   ├── survey.py            # Pydantic models for chat messages
│   │   │   └── auth.py
│   │   └── middleware/
│   │       ├── auth.py              # JWT validation middleware
│   │       └── rate_limit.py        # Redis-backed rate limiting
│   ├── core/
│   │   ├── config/
│   │   │   ├── settings.py          # Pydantic BaseSettings (env-driven config)
│   │   │   └── logging.py           # Structured logging setup
│   │   ├── database/
│   │   │   ├── postgres.py          # SQLAlchemy async engine + session factory
│   │   │   └── qdrant.py            # Qdrant client initialization
│   │   ├── models/
│   │   │   ├── job_posting.py       # SQLAlchemy ORM models
│   │   │   ├── skill.py
│   │   │   ├── survey_session.py
│   │   │   └── user.py
│   │   └── utils/
│   │       ├── text.py              # Text cleaning, chunking utilities
│   │       └── retry.py             # Exponential backoff decorators
│   ├── pipelines/
│   │   └── skill_pipeline.py        # Orchestrates Harvester→Synthesizer→Taxonomist
│   ├── scripts/
│   │   ├── seed_taxonomy.py         # Populate initial taxonomy
│   │   └── backfill_embeddings.py   # One-time embedding generation
│   ├── main.py                      # FastAPI app entrypoint
│   ├── celery_app.py                # Celery worker entrypoint
│   ├── requirements.txt
│   └── pyproject.toml
│
├── data/
│   ├── migrations/                  # Alembic migration files
│   │   └── env.py
│   ├── seeds/                       # Initial data seeds
│   └── fixtures/                    # Test fixtures
│
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.frontend
│   │   ├── Dockerfile.backend
│   │   └── Dockerfile.worker
│   ├── nginx/
│   │   └── nginx.conf
│   └── terraform/                   # Future cloud provisioning
│
├── docs/                            # All project documentation
│   ├── README.md                    # This file
│   ├── PRODUCT_REQUIREMENTS.md
│   ├── ARCHITECTURE.md
│   ├── ROADMAP.md
│   ├── DECISIONS.md
│   ├── LEARNINGS.md
│   └── AGENT_ROLES.md
│
├── docker-compose.yml               # Full local dev stack
├── docker-compose.prod.yml          # Production overrides
├── .env.example                     # Environment variable template
├── .gitignore
└── Makefile                         # Developer convenience commands
```

---

## Prerequisites

- Docker Desktop 4.x+
- Node.js 20+ (for local frontend dev without Docker)
- Python 3.11+ (for local backend dev without Docker)
- `make` (for convenience commands)

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/workforce-ai-platform.git
cd workforce-ai-platform

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys (Anthropic, scraping proxies, etc.)

# 3. Start the full stack
make up

# 4. Run database migrations
make migrate

# 5. Seed the skill taxonomy
make seed

# 6. Open the application
# Frontend: http://localhost:3000
# Backend API docs: http://localhost:8000/docs
# Qdrant dashboard: http://localhost:6333/dashboard
```

---

## Makefile Commands

```bash
make up           # Start all Docker services
make down         # Stop all services
make migrate      # Run Alembic migrations
make seed         # Seed initial taxonomy and fixtures
make harvest      # Trigger the Harvester agent manually
make synthesize   # Run skill extraction on harvested postings
make test         # Run full test suite (backend pytest + frontend vitest)
make logs         # Tail logs for all services
make shell-api    # Open shell in the backend API container
make shell-db     # Open psql in the PostgreSQL container
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for skill extraction + Interviewer agent |
| `DATABASE_URL` | PostgreSQL connection string |
| `QDRANT_URL` | Qdrant host URL |
| `REDIS_URL` | Redis connection string |
| `NEXTAUTH_SECRET` | NextAuth.js secret |
| `SCRAPER_PROXY_URL` | Optional: rotating proxy for scraping |

---

## Contributing & Agent Handoff

This repository is designed for autonomous agent execution. All agents reading this repository should begin with the documentation in `/docs/` in this order:

1. `README.md` ← You are here
2. `ARCHITECTURE.md` — Understand the data flows before touching code
3. `PRODUCT_REQUIREMENTS.md` — Understand what each feature must do
4. `AGENT_ROLES.md` — Understand which agent owns which part of the codebase
5. `DECISIONS.md` — Understand *why* the stack is built this way before proposing changes
6. `LEARNINGS.md` — Check for known failure modes before attempting a task

**All agents must log their work to `LEARNINGS.md` before closing a task.**
