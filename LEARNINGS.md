# Agent Learnings Log (LEARNINGS.md)

> **Instructions for all agents**: This file is a living record of failed attempts, unexpected API behaviors, scraping bottlenecks, UI bugs, and hard-won implementation discoveries. Before starting any task, **search this file for relevant prior entries**. After completing any task (especially one that required debugging or iteration), **add an entry** using the format below.
>
> Do not delete entries. If an issue has been resolved, mark it `[RESOLVED]` and document the fix. This document is the institutional memory of the codebase.

---

## Entry Format

```
### [AGENT/HUMAN] [DATE] — [Short Title]

**Area**: frontend | backend | scraping | llm | database | infra | testing
**Status**: OPEN | RESOLVED | WORKAROUND
**Severity**: BLOCKER | HIGH | MEDIUM | LOW

**What I tried**:
[Describe the approach taken]

**What happened**:
[Describe the failure mode, error message, or unexpected behavior]

**Root Cause** (if known):
[Explain why it happened]

**Resolution / Workaround**:
[Describe the fix, or why a full fix isn't possible]

**Future Risk**:
[Note if this is likely to recur or if there's a fragile dependency]
```

---

## Log Entries

*(No entries yet. This file is initialized at project start. The first agent to encounter a failure mode should add the first entry below this line.)*

---

## Known Fragile Areas (Pre-populated by Architect)

These are anticipated failure modes based on the architecture design. They are not yet confirmed failures — they are risk flags for agents to be aware of.

---

### [ARCHITECT] [Project Start] — Scraper Rate Limiting Risk

**Area**: scraping  
**Status**: OPEN  
**Severity**: HIGH  

**What I tried**: N/A (pre-emptive warning)

**What happened**: N/A

**Root Cause**: Greenhouse, Lever, and LinkedIn career pages implement bot detection at varying sophistication levels. Greenhouse and Lever are generally scraper-friendly for public job data, but LinkedIn actively blocks automated access without a proxy rotation strategy.

**Resolution / Workaround**:
1. LinkedIn should be treated as a Phase 2 source. Do not attempt LinkedIn scraping without a rotating residential proxy service configured in `SCRAPER_PROXY_URL`.
2. For Greenhouse/Lever, implement exponential backoff on 429 responses with a minimum 5-second base delay.
3. Honor `Crawl-delay` directives in `robots.txt`.
4. Set a realistic `User-Agent` header mimicking a browser.
5. Stagger requests across target companies with a randomized 2–8 second delay between each company's page fetch.

**Future Risk**: Even with proxies, LinkedIn may block at the account or IP level. If LinkedIn scraping is required at scale, evaluate the LinkedIn Job Search API (paid) as an alternative.

---

### [ARCHITECT] [Project Start] — LLM Extraction JSON Consistency Risk

**Area**: llm  
**Status**: OPEN  
**Severity**: HIGH  

**What I tried**: N/A (pre-emptive warning)

**What happened**: N/A

**Root Cause**: LLM skill extraction prompts targeting structured JSON output can produce malformed JSON, extra prose before/after the JSON block, or nested structures that deviate from the expected schema. This is a known failure mode for all current LLMs, including Claude, especially for long job posting inputs.

**Resolution / Workaround**:
1. Always use `response_format: json` or explicit JSON mode instructions in the prompt.
2. Wrap LLM output parsing in a try/except block. On JSON parse failure, log the raw output and skip the posting (mark as `extraction_failed` rather than crashing the pipeline).
3. Use a Pydantic model to validate the parsed JSON against the expected schema. Pydantic will catch structural deviations.
4. For very long job postings (> 4000 tokens), chunk the input and merge results. Do not pass full raw HTML — strip to plain text first.
5. Consider using Claude's `tool_use` feature as an alternative to raw JSON prompting — tool use enforces schema compliance at the API level.

**Future Risk**: Model updates can change extraction behavior. Pin the model version in `settings.py` (`SYNTHESIZER_MODEL = "claude-haiku-4-5-20251001"`) and test extraction quality after any model update.

---

### [ARCHITECT] [Project Start] — Qdrant Embedding Upsert Idempotency

**Area**: database  
**Status**: OPEN  
**Severity**: MEDIUM  

**What I tried**: N/A (pre-emptive warning)

**What happened**: N/A

**Root Cause**: If the Synthesizer is re-run on already-processed postings (e.g., after a pipeline crash recovery), it may attempt to upsert embeddings for skills that already exist in Qdrant. Qdrant's `upsert` operation will overwrite the existing vector by `id`, which is the desired behavior — but only if the `id` used is deterministic.

**Resolution / Workaround**:
1. Use the `skill.id` (UUID from PostgreSQL) as the Qdrant point ID. Since UUIDs are stable and unique per canonical skill, re-upserts are safe.
2. Do NOT generate a new UUID at upsert time — always derive the Qdrant point ID from `skill.id`.
3. Verify this pattern in `agents/synthesizer/embedder.py` before running in production.

**Future Risk**: If skill canonical names are changed and IDs are re-generated, old Qdrant points will become orphaned (they will persist with no PostgreSQL record pointing to them). Implement a periodic Qdrant cleanup job that removes points whose IDs do not exist in the `skills` table.

---

### [ARCHITECT] [Project Start] — SSE Streaming Compatibility

**Area**: frontend | backend  
**Status**: OPEN  
**Severity**: MEDIUM  

**What I tried**: N/A (pre-emptive warning)

**What happened**: N/A

**Root Cause**: The Next.js API route proxy layer (`app/api/proxy/[...path]/route.ts`) may buffer the FastAPI SSE stream before forwarding it to the browser, breaking the streaming experience. This is a known issue with Next.js 14's App Router route handlers and `fetch`-based proxying.

**Resolution / Workaround**:
1. Option A (Preferred for MVP): Point the frontend's survey chat directly at the FastAPI origin (`http://localhost:8000`) for the `/survey/message` endpoint, bypassing the Next.js proxy layer entirely. Use CORS headers on the FastAPI side.
2. Option B: Use Next.js `ReadableStream` in the route handler to properly pipe the SSE stream without buffering. This requires careful implementation — see Next.js streaming docs.
3. Do NOT use the standard Next.js `fetch` with `await response.json()` in a proxy route for SSE — this will buffer the entire stream.

**Future Risk**: Nginx in production must also be configured with `proxy_buffering off` and `X-Accel-Buffering: no` for SSE routes. Add this to `infra/nginx/nginx.conf` before production deployment.

---

### [ARCHITECT] [Project Start] — Taxonomy Drift Over Time

**Area**: llm | database  
**Status**: OPEN  
**Severity**: MEDIUM  

**What I tried**: N/A (pre-emptive warning)

**What happened**: N/A

**Root Cause**: As new skills emerge, the Taxonomist's classification may produce inconsistent domain assignments if the `taxonomy.yaml` is not periodically reviewed and updated. Additionally, the fuzzy deduplication logic (collapsing variants to canonical names) may fail for genuinely new skills that have no close anchor in the existing taxonomy.

**Resolution / Workaround**:
1. Add a `low_confidence` boolean flag to `skills` table. When the Taxonomist's classification confidence (extracted from the LLM response) is below a threshold (< 0.75), set `low_confidence = TRUE`.
2. Build an admin endpoint (`GET /api/v1/admin/skills/low-confidence`) to surface these for human review.
3. Schedule a quarterly taxonomy review as a product process, not just a technical one. The taxonomy is a product artifact.

**Future Risk**: If unchecked, taxonomy drift will cause the dashboard domain filters to become unreliable. Domain filter integrity is a core product promise — this must be monitored.

---

## Templates

### Quick Copy: New Entry

```
### [AGENT_NAME] [YYYY-MM-DD] — [Short Title]

**Area**: 
**Status**: OPEN
**Severity**: 

**What I tried**:


**What happened**:


**Root Cause**:


**Resolution / Workaround**:


**Future Risk**:

```
