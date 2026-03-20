# Agent Roles & Responsibilities (AGENT_ROLES.md)

> This document defines the modular roles for all automated agents — both backend pipeline agents and any autonomous coding agents executing tasks on this codebase. Each role has a defined scope, owns specific files and data, and has explicit interface contracts with the other agents it depends on or is depended on by.
>
> **Coding agents** should identify which role best maps to their assigned task and operate within the boundaries defined here. Cross-role changes must be flagged in a PR description or LEARNINGS.md entry.

---

## Agent Role Overview

```
                         ┌─────────────────────────────────┐
                         │         SCHEDULER               │
                         │  (APScheduler — triggers all    │
                         │   pipeline agents on schedule)  │
                         └──────────────┬──────────────────┘
                                        │
            ┌───────────────────────────▼──────────────────────────┐
            │                  INTELLIGENCE PIPELINE               │
            │                                                       │
            ▼                        ▼                        ▼    │
    ┌───────────────┐    ┌───────────────────┐    ┌────────────────┐│
    │  THE HARVESTER│───▶│  THE SYNTHESIZER  │───▶│ THE TAXONOMIST ││
    │  (scraping)   │    │  (LLM extraction) │    │ (classification││
    └───────────────┘    └───────────────────┘    └────────────────┘│
            │                        │                        │    │
            ▼                        ▼                        ▼    │
       job_postings              skills +              skills.domain│
       (raw)                     job_posting_skills    subdomain    │
                                 Qdrant embeddings                  │
            └───────────────────────────────────────────────────────┘
                                        │
                                        │ (separate pipeline, user-triggered)
                                        ▼
                         ┌─────────────────────────────────┐
                         │       THE INTERVIEWER           │
                         │  (conversational survey agent)  │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
                              survey_sessions
                              survey_messages
                              survey_extractions (via Taxonomist assist)
                              Qdrant: survey_sessions collection
```

---

## Role 1: The Harvester

**Identity**: `backend/agents/harvester/`  
**Type**: Autonomous pipeline agent  
**Trigger**: APScheduler cron (every 24h) OR `POST /api/v1/admin/harvest/trigger`  

### Mission
Scout the web for new job postings from frontier technology companies. Collect raw posting data and deposit it into the staging area (`job_postings` table) for downstream processing. The Harvester does not interpret — it only collects.

### Owns

| File | Responsibility |
|---|---|
| `agents/harvester/scraper.py` | Core async scraping logic for all source types |
| `agents/harvester/sources.py` | Configured list of target companies, their career page URLs, and parsing strategy (Greenhouse API vs. raw HTML) |
| `agents/harvester/scheduler.py` | APScheduler job definition and configuration |

### Reads
- `core/config/settings.py` — Scraper configuration (timeout, delay, proxy URL)
- `core/database/postgres.py` — DB session factory

### Writes
- `job_postings` table: inserts new rows with `processed = FALSE`

### Does NOT
- Interpret or extract skills from postings
- Touch the `skills` table
- Call any LLM API

### Interface Contract (Output)
For each discovered job posting, the Harvester writes:

```python
JobPosting(
    id=uuid4(),
    company="Anthropic",
    title="Research Engineer, Alignment",
    url="https://boards.greenhouse.io/anthropic/jobs/123456",
    raw_html="<div>...</div>",
    raw_text="We are looking for...",  # cleaned with BeautifulSoup
    posted_date=date(2025, 1, 15),
    harvested_at=datetime.utcnow(),
    processed=False,
    source="greenhouse"
)
```

### Operational Rules
1. **Deduplication**: Before inserting, check `SELECT 1 FROM job_postings WHERE url = $url`. Skip if exists.
2. **Rate limiting**: Minimum 2-second delay between requests to the same domain. Configurable via `SCRAPER_DELAY_SECONDS` env var.
3. **Error isolation**: A failure on one company's page must not stop the harvest for other companies. Wrap each company's scrape in a try/except and log failures.
4. **robots.txt**: Fetch and parse `robots.txt` for each domain. Skip any path that is disallowed for all user agents.
5. **Run logging**: At completion, log: `{companies_attempted, companies_succeeded, postings_found, postings_new, postings_skipped, errors}`.

### Target Source List (Initial)
Defined in `sources.py`. Initial targets include companies with structured career page APIs (Greenhouse, Lever) for reliability:

- **Greenhouse API** (JSON): Anthropic, OpenAI, Cohere, Mistral, Scale AI, Hugging Face, Weights & Biases, Runway, Stability AI, Midjourney, Perplexity, Character.AI
- **Lever API** (JSON): Notion, Linear, Figma, Vercel, Replit, Cursor
- **Raw HTML** (BeautifulSoup): Google DeepMind, Meta AI, Microsoft Research

---

## Role 2: The Synthesizer

**Identity**: `backend/agents/synthesizer/`  
**Type**: Autonomous pipeline agent  
**Trigger**: Celery task, triggered by Harvester completion OR `POST /api/v1/admin/synthesize/trigger`  

### Mission
Transform raw job posting text into structured skill intelligence. Read unprocessed job postings, extract skill entities via LLM, generate vector embeddings for each canonical skill, and deposit structured data into the skills layer.

### Owns

| File | Responsibility |
|---|---|
| `agents/synthesizer/extractor.py` | LangChain extraction chain, prompt templates, JSON parsing, Pydantic validation |
| `agents/synthesizer/embedder.py` | Embedding generation and Qdrant upsert logic |

### Reads
- `job_postings` WHERE `processed = FALSE`
- `skills` table (to check existing canonical names before insertion)
- `core/config/settings.py` — Model config (`SYNTHESIZER_MODEL`, `EMBEDDING_MODEL`)

### Writes
- `skills` table: upserts canonical skill records
- `job_posting_skills` table: creates many-to-many associations
- Qdrant `skills` collection: upserts vector points keyed by `skill.id`
- `job_postings` table: sets `processed = TRUE` on completion

### Does NOT
- Classify skills into domains/subdomains (that is the Taxonomist's job)
- Make decisions about taxonomy or canonical naming beyond basic deduplication

### Interface Contract (Output)

For each processed posting, the Synthesizer produces a list of extracted skill objects:

```python
ExtractedSkill(
    name="LangChain",           # As extracted from the JD
    type="tool",                # technical | tool | methodology | soft
    context_snippet="Experience with LangChain or similar LLM orchestration frameworks required."
)
```

These are then upserted into the `skills` table. The Synthesizer performs only **surface-level deduplication**: normalizing case and stripping punctuation before checking for existing records. Deep semantic deduplication (e.g., collapsing "LangChain framework" and "LangChain") is delegated to the Taxonomist.

### LLM Prompt Contract

System prompt key instructions:
- Extract only explicitly mentioned or strongly implied skills
- Do NOT infer skills from job title alone (e.g., do not add "Python" just because the title says "Data Engineer" unless Python is mentioned in the body)
- Return valid JSON matching the schema: `{"skills": [{"name": str, "type": str, "context_snippet": str}]}`
- Limit to a maximum of 20 skills per posting

### Embedding Strategy
- **Model**: `text-embedding-3-small` (1536 dimensions)
- **Input**: `f"{skill.canonical_name}: {skill.description or ''}"`
- **Batch size**: 100 embeddings per API call
- **On failure**: Log and skip — do not crash the pipeline. Mark skill with `embedding_status = 'failed'` for retry.

---

## Role 3: The Taxonomist

**Identity**: `backend/agents/taxonomist/`  
**Type**: Autonomous pipeline agent  
**Trigger**: Celery task, triggered by Synthesizer completion OR `POST /api/v1/admin/classify/trigger`  

### Mission
Impose order on the extracted skill landscape. Classify every unclassified skill into the canonical domain/subdomain taxonomy, deduplicate near-duplicate skill names, and ensure the skill graph remains coherent and queryable by domain.

### Owns

| File | Responsibility |
|---|---|
| `agents/taxonomist/mapper.py` | LLM-powered domain classification, fuzzy dedup logic, semantic dedup via Qdrant |
| `agents/taxonomist/taxonomy.yaml` | The canonical taxonomy definition — the single source of truth for all domain/subdomain structures |

### Reads
- `skills` WHERE `domain IS NULL` (unclassified skills from Synthesizer)
- `taxonomy.yaml` — loaded as classification context for every LLM call
- Qdrant `skills` collection — for similarity-based near-duplicate detection

### Writes
- `skills` table: sets `domain`, `subdomain`, `skill_type`, `low_confidence` for each skill
- `skills` table: merges near-duplicate records (updates `job_posting_skills` FK references, then deletes duplicate row)

### Does NOT
- Scrape, extract, or embed skills
- Interact with the user-facing API directly

### Taxonomy Schema (`taxonomy.yaml`)

```yaml
domains:
  software_engineering:
    label: "Software Engineering"
    subdomains:
      - backend_development
      - frontend_development
      - devops_platform
      - mobile
      - security
    canonical_anchors:
      - "Python"
      - "TypeScript"
      - "Kubernetes"
      - "CI/CD"
      - "REST APIs"

  data_and_ai:
    label: "Data & AI"
    subdomains:
      - machine_learning
      - data_engineering
      - analytics
      - ai_agents
      - mlops
    canonical_anchors:
      - "PyTorch"
      - "LangChain"
      - "dbt"
      - "Apache Spark"
      - "RAG"

  product_management:
    label: "Product Management"
    subdomains:
      - growth
      - platform
      - enterprise
      - ai_product
    canonical_anchors:
      - "Product Roadmap"
      - "A/B Testing"
      - "PRD"
      - "User Research"

  # ... additional domains
```

### Deduplication Logic

The Taxonomist uses a two-pass dedup strategy:

**Pass 1 — Exact + Fuzzy Text Match**:
- Normalize: lowercase, strip punctuation, trim whitespace
- Compute Levenshtein distance against all existing canonical names in the same domain
- If distance ≤ 2, flag as likely duplicate → LLM arbitration to confirm merge

**Pass 2 — Semantic Similarity**:
- Query Qdrant for the top 3 most similar embeddings to the new skill's embedding
- If cosine similarity > 0.92, flag as likely duplicate → LLM arbitration to confirm merge
- LLM arbitration prompt: "Are '{skill_a}' and '{skill_b}' the same skill or distinct? Answer SAME or DISTINCT with a one-line rationale."

On confirmed merge: update all `job_posting_skills` records to point to the surviving canonical skill, then delete the duplicate skill record and its Qdrant point.

### Confidence Scoring

Every domain classification decision includes a confidence score extracted from the LLM response:

```json
{
  "domain": "data_and_ai",
  "subdomain": "ai_agents",
  "confidence": 0.91,
  "rationale": "LangChain is a framework specifically used for building LLM-powered agents and chains."
}
```

If `confidence < 0.75`, set `skills.low_confidence = TRUE` for human review.

---

## Role 4: The Interviewer

**Identity**: `backend/agents/interviewer/`  
**Type**: Real-time conversational agent  
**Trigger**: User-initiated via `POST /api/v1/survey/message`  

### Mission
Conduct empathetic, research-quality qualitative interviews with platform users. Dynamically guide users through a structured question protocol while adapting to their responses. Capture rich, open-text data that reveals career anxieties, tool adoption patterns, and upskilling needs. Close each interview with a relevant, personalized CTA.

### Owns

| File | Responsibility |
|---|---|
| `agents/interviewer/agent.py` | LangChain ConversationalAgent definition, streaming execution, session state |
| `agents/interviewer/prompts.py` | System prompt, question protocol, behavioral rules, closing CTA logic |
| `agents/interviewer/storage.py` | Session loading, message persistence, completion detection, extraction task trigger |

### Reads
- `survey_sessions` and `survey_messages` tables (to load conversation history)
- `core/config/settings.py` — `INTERVIEWER_MODEL` config

### Writes
- `survey_messages` table: every turn (user + assistant)
- `survey_sessions` table: `turn_count`, `completion_status`, `completed_at`
- Triggers `post_session_extraction` Celery task on completion
- `survey_extractions` table: via post-session extraction (delegated to Celery task)
- Qdrant `survey_sessions` collection: full transcript on completion

### Does NOT
- Provide consulting advice or product recommendations
- Access the skills database or reference skill data during the interview
- Reveal internal question numbering or the existence of a question protocol to the user

### Persona Definition

The Interviewer adopts the following persona, encoded in the system prompt:

> *You are a thoughtful workforce researcher conducting a structured conversation to understand how professionals are navigating the AI transition. You are warm, curious, and direct. You do not give advice or pitch products during the interview — your role is only to listen, understand, and probe for depth. You ask one question at a time. You briefly acknowledge what the person just said before moving to your next question. You are genuinely interested in their experience.*

### Question Protocol

The canonical questions are defined in `prompts.py` as a prioritized list. The Interviewer agent is instructed to:

1. Begin with question 1 (current role/domain) — this is always first, as the answer informs all subsequent questions.
2. Cover questions 2–7 in approximately this order, but may reorder based on conversational flow.
3. Always cover question 8 (platform feedback) near the end.
4. After 8 turns minimum (or 12 maximum), deliver the closing message and CTA.

The Interviewer must NOT:
- Ask two questions in one message
- Ask a question that was clearly already answered in a prior turn
- Break character to explain the interview structure
- Manufacture or assume answers the user did not give

### Behavioral Rules (System Prompt Encoded)

| Scenario | Required Behavior |
|---|---|
| User gives a one-word answer | Probe gently: "Can you tell me more about that?" or "What's behind that for you?" |
| User asks what this data is used for | Respond transparently: explain it's for workforce research and improving the platform. Do not deflect. |
| User expresses distress about job loss or AI anxiety | Acknowledge the concern with empathy. Do not minimize or immediately pivot to the next question. Allow one full turn of acknowledgment before continuing. |
| User goes off-topic | Acknowledge briefly, then redirect: "That's interesting context — I want to make sure I ask you about [topic]. Can we go there?" |
| User asks for advice | "I'm not here to give advice today — I'm just here to understand your experience. But I'd encourage you to check out [platform resource] after we're done." |

### Closing CTA Logic

The closing message is dynamically generated based on the domain self-identified during the interview:

```python
def get_closing_cta(domain: str) -> str:
    domain_dashboard_map = {
        "data_and_ai": "/dashboard/data-and-ai",
        "software_engineering": "/dashboard/software-engineering",
        "product_management": "/dashboard/product-management",
        # ... etc
    }
    dashboard_path = domain_dashboard_map.get(domain, "/dashboard")
    return f"Based on what you've shared, I'd recommend checking out our {domain} Skill Profile — it shows which skills are trending at frontier companies right now. You can also book a call if you'd like to talk through what this means for your specific situation."
```

### Post-Session Extraction (Celery Subtask)

After a session completes, the Interviewer triggers a Celery task (`post_session_extraction`) that:
1. Loads the full conversation transcript
2. Sends to Claude with an extraction prompt targeting all `survey_extractions` fields
3. Inserts the structured extraction record
4. Calls the Taxonomist to classify `self_reported_domain`
5. Embeds and stores the full transcript in Qdrant `survey_sessions` collection

---

## Role 5: The Scheduler

**Identity**: `backend/agents/harvester/scheduler.py`  
**Type**: Orchestration layer  
**Managed by**: APScheduler within the Celery worker container  

### Mission
Ensure the intelligence pipeline runs on a reliable schedule without human intervention. Provide manual trigger endpoints for testing and admin override.

### Schedule

| Job | Cron Expression | Description |
|---|---|---|
| `harvest_job` | `0 2 * * *` (2 AM UTC daily) | Trigger Harvester |
| `synthesize_job` | `0 4 * * *` (4 AM UTC daily) | Trigger Synthesizer (runs after harvest) |
| `classify_job` | `0 6 * * *` (6 AM UTC daily) | Trigger Taxonomist (runs after synthesis) |
| `cleanup_abandoned_sessions` | `0 1 * * *` (1 AM UTC daily) | Mark survey sessions abandoned after 30min inactivity |
| `qdrant_orphan_cleanup` | `0 3 * * 0` (Sunday 3 AM UTC weekly) | Remove Qdrant points with no matching PostgreSQL skill record |

---

## Coding Agent Roles

When autonomous coding agents are assigned tasks on this repository, they should self-identify into one of the following roles and operate within those boundaries:

| Coding Agent Role | Scope | Primary Files |
|---|---|---|
| **Frontend Agent** | Next.js UI components, page layouts, API client, styles | `frontend/` |
| **API Agent** | FastAPI routers, schemas, middleware | `backend/api/` |
| **Pipeline Agent** | Harvester, Synthesizer, Taxonomist logic | `backend/agents/harvester/`, `synthesizer/`, `taxonomist/` |
| **Conversation Agent** | Interviewer agent, prompts, survey storage | `backend/agents/interviewer/` |
| **Database Agent** | ORM models, Alembic migrations, seed scripts | `backend/core/models/`, `data/migrations/` |
| **Infrastructure Agent** | Docker, Nginx, environment config | `infra/`, `docker-compose.yml`, `.env.example` |
| **Documentation Agent** | Markdown docs, LEARNINGS.md entries | `docs/` |

### Coding Agent Operating Rules

1. **Read before writing**: Always read the relevant `AGENT_ROLES.md` section, the files you intend to modify, and any related LEARNINGS.md entries before writing code.
2. **Single responsibility**: Do not cross role boundaries within a single task. If a task requires changes in two different roles (e.g., both a new API route and a new frontend component), complete them sequentially and log each in LEARNINGS.md.
3. **Log failures**: Any task that required more than one attempt, hit an unexpected API behavior, or produced a workaround must be logged in LEARNINGS.md before the task is closed.
4. **Test your own work**: Each role has a corresponding test directory. Do not close a task without at least one passing test covering the new behavior.
5. **Never modify `taxonomy.yaml` without a rationale**: This file is a product artifact. Changes require a brief comment in the PR or LEARNINGS.md explaining the classification rationale.
