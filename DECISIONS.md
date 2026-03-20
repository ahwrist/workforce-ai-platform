# Architecture Decision Log (DECISIONS.md)

> This document records significant technical decisions made during the design and development of the WorkforceAI platform. Each entry explains **what** was decided, **why**, and what alternatives were considered and rejected. Agents and contributors must consult this document before proposing changes to the stack or architectural patterns.

**Format**: Each decision is numbered sequentially. Do not renumber or delete entries. Superseded decisions are marked `[SUPERSEDED by ADR-XXX]`.

---

## ADR-001: Next.js (App Router) as the Frontend Framework

**Status**: Accepted  
**Date**: Project inception  
**Deciders**: Platform architect  

### Decision
Use Next.js 14 with the App Router as the frontend framework.

### Context
The platform has three distinct surface types with different performance and SEO requirements:
1. **Marketing pages**: Need SSG for maximum SEO performance and fast initial load. Google indexing quality directly impacts consulting lead generation.
2. **Skill Dashboard**: Needs fast data fetching with real-time filtering — React Server Components + Client Components provide a clean model for this.
3. **Survey Chat UI**: Highly interactive, stateful — Client Components required throughout.

### Rationale
- **SSG/SSR/RSC in one framework**: Next.js App Router supports all three rendering strategies within a single codebase. Marketing pages use `generateStaticParams` for SSG; dashboard uses RSC with streaming; survey UI is pure client.
- **SEO via `generateMetadata`**: Dynamic, page-specific OG tags and meta descriptions from a single API without a separate SSR server.
- **React ecosystem**: Largest component ecosystem, best compatibility with UI libraries (shadcn/ui, Recharts, etc.).
- **TypeScript first-class**: Reduces runtime bugs, critical for a data-heavy dashboard.

### Alternatives Considered

| Framework | Why Rejected |
|---|---|
| Remix | Excellent DX but smaller ecosystem; fewer UI component options; less mature RSC story |
| SvelteKit | Strong SSG/SSR, but team familiarity with React is higher; fewer AI/data viz component libraries |
| Astro | Excellent for static marketing sites, but poor fit for the interactive dashboard and real-time survey UI without adding a React island anyway |
| Plain React (Vite) | No SSG, poor SEO story for marketing pages — a hard disqualifier |

---

## ADR-002: FastAPI as the Backend API Framework

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use FastAPI (Python 3.11+) as the backend API framework.

### Context
The backend must: (1) serve a REST API to the Next.js frontend, (2) orchestrate async agent pipelines, and (3) stream LLM responses via SSE.

### Rationale
- **Async native**: FastAPI's `async def` endpoints and `asyncio` integration are essential for non-blocking SSE streaming and concurrent scraping.
- **Pydantic V2**: Schema validation and serialization are already needed for LangChain (which uses Pydantic internally). Using FastAPI means zero friction between API schemas and agent data models.
- **Auto-generated OpenAPI docs**: The `/docs` endpoint serves as a living API contract for frontend developers and agents.
- **Python monolith**: Keeping the API, agents, and pipelines in the same Python process (or Celery workers) avoids cross-language IPC overhead and keeps the codebase unified.

### Alternatives Considered

| Framework | Why Rejected |
|---|---|
| Django + DRF | Synchronous by default (Django 4.x has async support but it's bolted on); heavier ORM that conflicts with SQLAlchemy; DRF serializers are redundant given Pydantic |
| Flask | Too minimal for this use case; no native async; manual OpenAPI generation |
| Node.js (Express/Hono) | Splitting the backend into Node.js would mean two runtimes for the Python AI/data work, introducing IPC complexity. Python must be the backend language given the AI pipeline requirements. |

---

## ADR-003: PostgreSQL as the Primary Relational Database

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use PostgreSQL 16 as the primary relational database for all structured data.

### Rationale
- **JSONB support**: `survey_extractions.raw_llm_extraction` and similar fields benefit from queryable JSONB without a separate document store.
- **Array types**: `skills.aliases TEXT[]` is a natural fit for PostgreSQL's native array columns.
- **`pgvector` optionality**: If Qdrant is later replaced or supplemented, PostgreSQL's `pgvector` extension provides a migration path.
- **SQLAlchemy async support**: Full async ORM support via `asyncpg` driver.
- **Alembic migrations**: Industry-standard migration tooling for PostgreSQL.

### Alternatives Considered

| Database | Why Rejected |
|---|---|
| MySQL | Weaker JSONB support; less feature-rich for the data types needed |
| SQLite | Not appropriate for production multi-container deployments |
| MongoDB | Document model is a poor fit for relational skill/job/user data; joins are painful |
| Supabase | Managed PostgreSQL is appealing for V2/V3, but adds vendor dependency at MVP stage |

---

## ADR-004: Qdrant as the Vector Database

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use Qdrant as the dedicated vector database for skill embeddings and conversation semantic search.

### Rationale
- **Self-hosted**: Qdrant runs as a Docker container with no external service dependency, keeping the MVP stack fully local and cost-free at development time.
- **Performance**: Qdrant uses HNSW indexing for efficient approximate nearest-neighbor search, suitable for collections scaling to millions of skill embeddings.
- **Filtering**: Qdrant's payload filtering allows vector search to be scoped (e.g., "find similar skills within the `data_engineering` domain") — critical for the related skills feature.
- **REST + gRPC**: Both interfaces available; REST used for simplicity, gRPC available for high-throughput embedding upserts.
- **Python client**: First-class `qdrant-client` Python library with async support.

### Alternatives Considered

| Vector DB | Why Rejected |
|---|---|
| Pinecone | Managed-only (no self-host); adds external API cost and dependency from day one |
| Weaviate | More complex schema configuration; heavier resource footprint than needed for MVP |
| pgvector | Would work for MVP scale, but lacks the filtering and collection-management features needed for V2/V3 semantic search |
| Chroma | Simple and lightweight, but limited metadata filtering and less production-proven at scale |

---

## ADR-005: Redis for Task Queue and Caching

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use Redis as both the Celery broker/backend and the application cache layer.

### Rationale
- **Unified service**: One Redis instance serves multiple purposes — Celery task queue, rate limiting (via Redis counters), session storage, and response caching — reducing container count.
- **Celery compatibility**: Redis is the most commonly used and best-documented Celery broker.
- **Rate limiting**: Redis `INCR` + `EXPIRE` is the canonical pattern for sliding-window rate limiting without an additional service.

### Alternatives Considered

| Option | Why Rejected |
|---|---|
| RabbitMQ | Superior as a dedicated message broker, but adds a separate service with no benefit at MVP scale |
| SQS | Managed, but adds AWS dependency; overkill for MVP |
| In-memory (no Redis) | Cannot persist task state across container restarts |

---

## ADR-006: LangChain + Anthropic SDK for LLM Orchestration

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use LangChain as the LLM orchestration framework with the Anthropic Claude API as the primary model provider.

### Rationale
- **Claude for Interviewer**: Claude's instruction-following quality and conversational naturalness is superior to GPT-4o for the structured-but-adaptive interview protocol. The researcher persona requires nuanced context-holding.
- **Claude Haiku for Synthesizer**: High-volume skill extraction from job postings must be cost-efficient. Claude Haiku delivers strong JSON extraction at a fraction of the cost of Sonnet.
- **LangChain abstractions**: `ConversationChain` with `ConversationBufferMemory` handles the survey session history management. Changing the underlying model later requires one line change.
- **Streaming**: LangChain's async streaming (`astream`) integrates cleanly with FastAPI's `StreamingResponse`.

### Model Assignment

| Agent | Model | Rationale |
|---|---|---|
| Harvester | N/A (no LLM) | Pure scraping + parsing |
| Synthesizer | `claude-haiku-4-5` | High volume, structured extraction, cost priority |
| Taxonomist | `claude-haiku-4-5` | Classification task, short prompts, cost priority |
| Interviewer | `claude-sonnet-4-6` | Conversational quality, nuance, user-facing |
| Post-session Extractor | `claude-haiku-4-5` | Structured extraction from completed transcript |

### Alternatives Considered

| Option | Why Rejected |
|---|---|
| OpenAI GPT-4o | Higher cost; GPT-4o's structured output is comparable but Claude's conversational quality edges it for the Interviewer persona |
| Direct SDK (no LangChain) | Would require building conversation history management, prompt templating, and streaming wrappers manually |
| LlamaIndex | Better suited for RAG document pipelines; LangChain's agent and chain abstractions are a better fit for the agentic pipeline architecture |

---

## ADR-007: Celery for Asynchronous Pipeline Execution

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use Celery with Redis as broker for all asynchronous agent pipeline tasks.

### Rationale
- **Decoupling**: The intelligence pipeline (Harvester → Synthesizer → Taxonomist) must run independently of the API server and not block user-facing requests.
- **Scheduling**: APScheduler integrated into the Celery worker provides cron-style scheduling for the daily harvest without a separate cron service.
- **Task chaining**: Celery's `chain()` primitive cleanly expresses the sequential pipeline steps with error isolation per step.
- **Retry logic**: Built-in retry with exponential backoff is critical for scraping tasks that hit rate limits.

### Alternatives Considered

| Option | Why Rejected |
|---|---|
| FastAPI background tasks | Appropriate for lightweight fire-and-forget tasks; not designed for long-running, distributed pipeline steps with retry logic |
| Airflow | Significant operational overhead; DAG-based model is overkill for a three-step pipeline at MVP |
| Prefect / Dagster | Both are strong options for V2/V3 when the pipeline complexity grows; over-engineered for MVP |
| APScheduler alone | Can schedule tasks but lacks the distributed worker model and retry infrastructure |

---

## ADR-008: Monorepo Structure

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use a single monorepo containing both the `frontend/` and `backend/` directories, managed with Docker Compose.

### Rationale
- **Solo/small team**: At MVP scale with a small team or autonomous agents, the overhead of managing two separate repositories (separate CI/CD, versioning, dependency management) outweighs the benefits.
- **Shared context**: Documentation, infrastructure definitions (`docker-compose.yml`, `Makefile`), and environment configuration are shared across frontend and backend — a monorepo keeps them co-located.
- **Agent handoff**: Autonomous coding agents working on this repo benefit from having the full context (frontend API client and backend router) in a single working directory.

### Alternatives Considered

| Option | Why Rejected |
|---|---|
| Separate repos (frontend-repo, backend-repo) | Adds cross-repo coordination overhead; worse DX for solo development; agents need context from both |
| Turborepo/Nx monorepo tooling | Adds tooling complexity; appropriate for large multi-package monorepos, not a two-app structure |

---

## ADR-009: shadcn/ui as the Frontend Component System

**Status**: Accepted  
**Date**: Project inception  

### Decision
Use shadcn/ui (built on Radix UI primitives + Tailwind CSS) as the primary UI component library.

### Rationale
- **Ownership model**: shadcn/ui components are copied into the project, not installed as a dependency. This means full control over component code — critical for customizing the design system to match the platform's brand.
- **Accessibility**: Radix UI primitives handle ARIA attributes, keyboard navigation, and focus management correctly out of the box — satisfies WCAG 2.1 AA requirements without custom implementation.
- **Tailwind compatible**: Components use Tailwind utility classes, consistent with the rest of the frontend styling approach.
- **No version lock-in**: Since components are owned code, there is no risk of breaking changes from upstream library updates.

### Alternatives Considered

| Library | Why Rejected |
|---|---|
| Material UI (MUI) | Opinionated visual style that conflicts with bespoke brand design; heavy bundle |
| Chakra UI | Less accessible out of the box; runtime CSS-in-JS performance concerns |
| Ant Design | Enterprise-focused visual language; poor fit for a modern consulting/SaaS brand |
| Headless UI (Tailwind Labs) | Limited component set; would require significant custom implementation |
