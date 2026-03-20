# Architecture Document

**Version**: 1.0  
**Scope**: Full-stack platform architecture, data flows, and service contracts  

---

## 1. System Overview

WorkforceAI is a two-pipeline system sharing a common data store and API layer:

1. **The Intelligence Pipeline**: Autonomous agent chain that continuously harvests, processes, and structures skill data from the web.
2. **The Conversation Pipeline**: Real-time user-facing conversational agent that captures qualitative career data and converts it to structured research.

These pipelines feed a shared FastAPI backend that serves a Next.js frontend across three primary surfaces: marketing pages, the Skill Dashboard, and the Survey Chat UI.

---

## 2. Service Architecture

### 2.1 Container Map

```
┌────────────────────────────────────────────────────────────────────┐
│                         Docker Network: platform-net               │
│                                                                    │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────────┐   │
│  │   nginx     │    │  frontend    │    │    fastapi-api      │   │
│  │  :80 / :443 │───▶│  next.js     │    │    :8000            │   │
│  │             │    │  :3000       │    │    (uvicorn)        │   │
│  └─────────────┘    └──────────────┘    └──────────┬──────────┘   │
│        │                    │                      │              │
│        │ /api/*             │ SSR requests         │              │
│        └────────────────────┼──────────────────────┘              │
│                             │                      │              │
│  ┌──────────────────────────▼──────────────────────▼──────────┐   │
│  │                    Shared Data Layer                        │   │
│  │                                                             │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │   │
│  │  │  PostgreSQL  │  │   Qdrant     │  │     Redis       │   │   │
│  │  │  :5432       │  │   :6333      │  │     :6379       │   │   │
│  │  │  (primary)   │  │  (vectors)   │  │  (cache/queue)  │   │   │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   Agent Worker Layer                         │  │
│  │                                                             │   │
│  │  ┌───────────────────────────────────────────────────────┐  │   │
│  │  │  celery-worker (pipeline agents: Harvester,           │  │   │
│  │  │                 Synthesizer, Taxonomist)              │  │   │
│  │  └───────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 Port Assignments

| Service | Internal Port | External Port (dev) |
|---|---|---|
| Nginx | 80, 443 | 80, 443 |
| Next.js | 3000 | 3000 |
| FastAPI | 8000 | 8000 |
| PostgreSQL | 5432 | 5432 |
| Qdrant | 6333 (HTTP), 6334 (gRPC) | 6333, 6334 |
| Redis | 6379 | 6379 |
| Qdrant Dashboard | 6333 | 6333/dashboard |

---

## 3. Data Flow 1: The Intelligence Pipeline

This pipeline runs asynchronously on a schedule, completely decoupled from user traffic.

### 3.1 Flow Diagram

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    INTELLIGENCE PIPELINE                         │
  │                                                                  │
  │  APScheduler                                                     │
  │  (every 24h)                                                     │
  │       │                                                          │
  │       ▼                                                          │
  │  ┌────────────┐                                                  │
  │  │  HARVESTER │  sources.py → target company list               │
  │  │            │  httpx async GET → career pages / APIs          │
  │  │            │  BeautifulSoup → extract job posting HTML        │
  │  │            │  Dedup check → skip if URL already in DB         │
  │  └─────┬──────┘                                                  │
  │        │ New raw job postings                                    │
  │        │ INSERT INTO job_postings (processed=FALSE)              │
  │        ▼                                                         │
  │  ┌─────────────┐                                                 │
  │  │ SYNTHESIZER │  SELECT * FROM job_postings WHERE processed=F   │
  │  │             │  Chunk raw text (≤ 2000 tokens per chunk)       │
  │  │             │  LLM extraction chain (Claude claude-haiku-4-5) │
  │  │             │  → JSON: [{name, type, context_snippet}]        │
  │  │             │  Batch embed canonical skill names              │
  │  │             │  → Upsert skills, job_posting_skills            │
  │  │             │  → Store embeddings in Qdrant (collection:      │
  │  │             │     "skills")                                   │
  │  │             │  UPDATE job_postings SET processed=TRUE         │
  │  └─────┬───────┘                                                 │
  │        │ Newly extracted skills (unclassified)                   │
  │        ▼                                                         │
  │  ┌─────────────┐                                                 │
  │  │ TAXONOMIST  │  SELECT skills WHERE domain IS NULL             │
  │  │             │  Load taxonomy.yaml as classification context   │
  │  │             │  LLM classification: skill → domain/subdomain   │
  │  │             │  Fuzzy dedup: collapse aliases → canonical name │
  │  │             │  Qdrant similarity: find near-duplicates        │
  │  │             │  UPDATE skills SET domain=X, subdomain=Y        │
  │  └─────────────┘                                                 │
  │        │                                                         │
  │        ▼                                                         │
  │  PostgreSQL: skills table fully populated and classified         │
  │  Qdrant: all skill embeddings indexed and searchable             │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
              │
              │ FastAPI serves processed data
              ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                    SKILL DASHBOARD (Next.js)                    │
  │                                                                 │
  │  GET /api/v1/skills/trending?domain=X&days=30                   │
  │  → PostgreSQL: aggregate job_posting_skills by skill_id         │
  │  → Return top N skills with frequency, trend direction          │
  │                                                                 │
  │  GET /api/v1/skills/{id}                                        │
  │  → PostgreSQL: skill detail + example companies                 │
  │  → Qdrant: top 5 similar skills by embedding cosine similarity  │
  │  → Merge and return SkillDetailResponse                         │
  │                                                                 │
  │  GET /api/v1/skills/search?q=...                                │
  │  → Embed query string (text-embedding-3-small)                  │
  │  → Qdrant: vector search, top 10 results                        │
  │  → Hydrate with PostgreSQL metadata                             │
  └─────────────────────────────────────────────────────────────────┘
```

### 3.2 LLM Extraction Prompt Contract

The Synthesizer uses a structured extraction prompt. The output contract is:

```json
{
  "skills": [
    {
      "name": "string — canonical skill name, title case",
      "type": "technical | tool | methodology | soft",
      "context_snippet": "string — verbatim 1-2 sentence excerpt from JD that implies this skill"
    }
  ]
}
```

The prompt instructs the model to extract only explicit or strongly implied skills — not to hallucinate skills based on job title alone. Context snippets are stored for audit and display in the skill detail panel.

### 3.3 Embedding Strategy

- **Model**: `text-embedding-3-small` (OpenAI) — 1536 dimensions, cost-efficient for high-volume skill names
- **Input**: Canonical skill name + optional short description (improves disambiguation)
- **Qdrant Collection**: `skills`
  - Vector size: 1536
  - Distance metric: Cosine
  - Payload fields: `skill_id`, `canonical_name`, `domain`, `skill_type`
- **Upsert**: Keyed on `skill_id` — re-embedding on canonical name change is a defined pipeline step

### 3.4 Celery Task Chain

```python
# pipelines/skill_pipeline.py
chain(
    harvest_new_postings.s(),       # Harvester: writes raw postings to PG
    extract_skills_from_postings.s(), # Synthesizer: LLM extraction + embed
    classify_and_deduplicate.s()    # Taxonomist: domain mapping + dedup
)
```

Each task is idempotent. If the chain fails mid-way, re-running is safe — processed flags and upsert keys prevent duplication.

---

## 4. Data Flow 2: The Conversation Pipeline

This pipeline is synchronous and user-triggered, handling real-time chat interactions.

### 4.1 Flow Diagram

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    CONVERSATION PIPELINE                         │
  │                                                                  │
  │  User lands on /survey                                           │
  │       │                                                          │
  │       ▼                                                          │
  │  POST /api/v1/survey/session                                     │
  │  → Generate session_token (UUID)                                 │
  │  → INSERT INTO survey_sessions                                   │
  │  → Return {session_token, opening_message}                       │
  │       │                                                          │
  │       ▼                                                          │
  │  [User reads opening message, types response]                    │
  │       │                                                          │
  │       ▼                                                          │
  │  POST /api/v1/survey/message                                     │
  │  Body: {session_token, content}                                  │
  │       │                                                          │
  │       ▼                                                          │
  │  ┌────────────────────────────────────────────────────────────┐  │
  │  │                   INTERVIEWER AGENT                        │  │
  │  │                                                            │  │
  │  │  1. Load session history from PostgreSQL (all prior turns) │  │
  │  │  2. Append new user message to history                     │  │
  │  │  3. INSERT new user message to survey_messages             │  │
  │  │  4. Build LangChain messages list                          │  │
  │  │     [SystemMessage(researcher_prompt),                     │  │
  │  │      HumanMessage/AIMessage alternating history,           │  │
  │  │      HumanMessage(new_user_content)]                       │  │
  │  │  5. Stream response from Claude (claude-sonnet-4-6)        │  │
  │  │  6. Yield SSE tokens to frontend as they arrive            │  │
  │  │  7. On stream complete:                                    │  │
  │  │     - INSERT completed assistant message to survey_messages │  │
  │  │     - Increment session.turn_count                         │  │
  │  │     - Check completion condition (turn_count >= 8 OR       │  │
  │  │       agent signals closing intent)                        │  │
  │  │     - If complete: trigger post_session_extraction task    │  │
  │  └────────────────────────────────────────────────────────────┘  │
  │       │                                                          │
  │       │ SSE stream → Client renders tokens progressively         │
  │       ▼                                                          │
  │  [Frontend displays response, user types next message]           │
  │       │                                                          │
  │       │ (loop repeats for each turn)                            │
  │       ▼                                                          │
  │  Session Completion Detected                                     │
  │       │                                                          │
  │       ▼                                                          │
  │  Celery: post_session_extraction.delay(session_id)               │
  │       │                                                          │
  │       ▼                                                          │
  │  ┌────────────────────────────────────────────────────────────┐  │
  │  │              POST-SESSION EXTRACTION (async)               │  │
  │  │                                                            │  │
  │  │  1. Load full conversation transcript                      │  │
  │  │  2. LLM extraction prompt → structured fields              │  │
  │  │  3. INSERT INTO survey_extractions                         │  │
  │  │  4. Taxonomist classifies self_reported_domain             │  │
  │  │  5. Store full conversation as Qdrant document             │  │
  │  │     (enables future semantic research queries)             │  │
  │  └────────────────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────────────────┘
```

### 4.2 Streaming Implementation

The survey message endpoint uses SSE (Server-Sent Events):

```python
# api/routers/survey.py
from fastapi.responses import StreamingResponse

async def stream_agent_response(session_token: str, user_content: str):
    async for chunk in interviewer_agent.astream(user_content, session_token):
        yield f"data: {json.dumps({'token': chunk})}\n\n"
    yield "data: [DONE]\n\n"

@router.post("/survey/message")
async def send_message(body: SurveyMessageRequest):
    return StreamingResponse(
        stream_agent_response(body.session_token, body.content),
        media_type="text/event-stream"
    )
```

Frontend consumes with `EventSource` or a custom `fetchEventSource` wrapper.

### 4.3 Session State Machine

```
CREATED → ACTIVE → COMPLETING → COMPLETED
                              → ABANDONED (no activity for 30min)
```

- `CREATED`: Session record exists, opening message delivered
- `ACTIVE`: User has responded at least once
- `COMPLETING`: Agent has delivered closing message + CTA
- `COMPLETED`: `completed_at` set, extraction queued
- `ABANDONED`: No user activity for 30 minutes (cleanup cron)

### 4.4 Qdrant Storage for Conversations

Each completed session is stored as a Qdrant document for future semantic research queries:

- **Collection**: `survey_sessions`
- **Document**: Full transcript as concatenated text
- **Embedding**: Embedded full transcript (chunked if > 8192 tokens)
- **Payload**: `session_id`, `domain`, `completion_status`, `turn_count`, `completed_at`

This enables future queries like: "Find all sessions where users expressed anxiety about job automation in data roles."

---

## 5. API Contract Reference

### 5.1 Response Envelope

All API responses follow a consistent envelope:

```json
{
  "data": { ... },
  "meta": {
    "timestamp": "ISO 8601",
    "version": "1.0"
  },
  "error": null
}
```

Error responses:

```json
{
  "data": null,
  "meta": { "timestamp": "...", "version": "1.0" },
  "error": {
    "code": "SKILL_NOT_FOUND",
    "message": "Skill with id abc123 does not exist",
    "detail": null
  }
}
```

### 5.2 Pagination

List endpoints use cursor-based pagination:

```json
{
  "data": {
    "items": [...],
    "next_cursor": "eyJpZCI6MTIzfQ==",
    "has_more": true,
    "total": 847
  }
}
```

### 5.3 Authentication

Protected endpoints require a Bearer token in the Authorization header:

```
Authorization: Bearer <jwt_token>
```

JWTs are issued by `POST /api/v1/auth/token` and expire in 7 days (configurable). Refresh tokens are stored in Redis with a 30-day TTL.

---

## 6. Database Schema (Reference)

Full schema is defined in SQLAlchemy ORM models at `backend/core/models/`. Alembic manages migrations. Key relationships:

```
users
  └── survey_sessions (user_id FK, nullable)
        ├── survey_messages (session_id FK)
        └── survey_extractions (session_id FK, 1:1)

job_postings
  └── job_posting_skills (job_posting_id FK)
        └── skills (skill_id FK)

skills
  └── (embedding stored in Qdrant, skill_id mirrored as payload)
```

---

## 7. Security Considerations

| Surface | Control |
|---|---|
| Public API endpoints | IP-based rate limiting (Redis, 100 req/min) |
| Admin endpoints | API key authentication (header: `X-Admin-Key`) |
| User endpoints | JWT Bearer token |
| Database | No direct external exposure; only accessible within Docker network |
| Scraping | Respect `robots.txt`, honor rate limits, use proxy rotation for high-volume sources |
| LLM API keys | Stored in environment variables only, never in code or logs |
| Survey data | PII fields (if any) flagged for GDPR compliance; anonymous sessions by default |
