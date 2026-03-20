# Product Requirements Document (PRD)

**Product**: WorkforceAI Platform  
**Version**: 1.0 (MVP → V3)  
**Status**: Active Development  
**Last Updated**: See git log  

---

## 1. Product Overview

WorkforceAI is a multi-surface platform combining a consulting service storefront, a live skill intelligence dashboard, and a conversational research agent. Its primary users are:

- **Individual Professionals** transitioning careers or upskilling for the AI era
- **Team Leads & Managers** seeking AI adoption strategy for their departments
- **Enterprise HR / L&D Leaders** seeking workforce modernization programs
- **Students** entering the job market who need a signal on what skills actually matter

The platform's differentiated value proposition rests on three compounding loops:

```
Skill Intelligence (Frontier Skills Engine)
         ↓ attracts users
Consulting Services (conversion)
         ↓ generates revenue + insights
Survey Research Agent (captures qualitative intent data)
         ↓ improves skill intelligence + generates research assets
```

---

## 2. Core Features

---

### Feature 1: Marketing & Consulting Service Pages

**Purpose**: Convert visitors into consulting clients or email subscribers.

**Priority**: P0 — Required for MVP

#### 2.1.1 Pages Required

| Page | Path | Description |
|---|---|---|
| Homepage | `/` | Hero, value prop, CTA to skill dashboard or survey |
| Services | `/services` | Breakdown of consulting offerings (1:1, team, enterprise) |
| About | `/about` | Founder credibility, enterprise AI background, thesis |
| Contact / Book | `/contact` | Calendly embed or booking form |
| Blog / Insights | `/blog` | Long-form thought leadership (SEO surface) |

#### 2.1.2 Homepage Requirements

- **Hero Section**: Clear statement of the core thesis ("The future of work runs on agent orchestration"). Primary CTA button → Skill Dashboard. Secondary CTA → Survey Agent.
- **Problem Statement Section**: Three-column layout surfacing the three core problems (skill signal decay, upskilling noise, transition paralysis).
- **Social Proof / Credibility Bar**: Enterprise client logos or named credentials (Lockheed Martin AI Center, etc.) — must be configurable via CMS or a simple JSON config file.
- **Services Preview**: Card-based summary of the three service tiers with pricing anchors (or "contact for pricing").
- **Skill Dashboard Teaser**: Animated or live preview of the Frontier Skills Engine showing trending skills — pulls from the live API.
- **Lead Capture**: Email capture form that writes to the `subscribers` table in PostgreSQL and triggers a welcome sequence (Phase 1: just DB write; Phase 2: email via Resend/Postmark).

#### 2.1.3 Services Page Requirements

Three tiers must be clearly differentiated:

| Tier | Target | Description |
|---|---|---|
| **1:1 Coaching** | Individual professionals | Career transition coaching, AI upskilling roadmap, 60-min sessions |
| **Team Upskilling** | Managers / team leads (5–50 people) | Custom workshop design, agent orchestration training, tooling audit |
| **Enterprise Advisory** | HR/L&D, C-suite | AI adoption strategy, measurement frameworks, change management |

Each tier card must include: target audience, key deliverables, format (async/sync), pricing anchor or "Schedule a call" CTA.

#### 2.1.4 SEO Requirements

- All marketing pages must use Next.js metadata API (`generateMetadata`) for dynamic OG tags.
- Pages must render with SSG (Static Site Generation) at build time.
- Blog posts must use MDX with front matter for SEO metadata.
- Sitemap must be auto-generated via `next-sitemap`.
- Core Web Vitals targets: LCP < 2.5s, CLS < 0.1, INP < 200ms.

---

### Feature 2: Frontier Skills Engine — Skill Profiles Dashboard

**Purpose**: Serve as the primary data-driven lead magnet. Surface live, filterable skill intelligence derived from actual frontier company job postings.

**Priority**: P0 (basic version for MVP), P1 (personalization for V2)

#### 2.2.1 Data Model

**Job Postings** (harvested raw):
```
job_postings(
  id UUID PRIMARY KEY,
  company VARCHAR,
  title VARCHAR,
  url TEXT UNIQUE,
  raw_html TEXT,
  raw_text TEXT,
  posted_date DATE,
  harvested_at TIMESTAMP,
  processed BOOLEAN DEFAULT FALSE,
  source VARCHAR  -- e.g., 'greenhouse', 'lever', 'linkedin'
)
```

**Skills** (extracted by Synthesizer):
```
skills(
  id UUID PRIMARY KEY,
  canonical_name VARCHAR UNIQUE,
  aliases TEXT[],
  domain VARCHAR,           -- e.g., 'data_engineering', 'product', 'design'
  subdomain VARCHAR,
  skill_type VARCHAR,       -- 'technical', 'tool', 'methodology', 'soft'
  embedding VECTOR(1536),   -- stored in Qdrant, id mirrored here
  first_seen DATE,
  last_seen DATE
)

job_posting_skills(
  job_posting_id UUID REFERENCES job_postings(id),
  skill_id UUID REFERENCES skills(id),
  frequency INT DEFAULT 1,
  extracted_at TIMESTAMP
)
```

#### 2.2.2 Dashboard — MVP Requirements (V1)

- **Domain Filter**: Dropdown or tab bar allowing users to filter skill profiles by domain. Initial domains: `Software Engineering`, `Data & AI`, `Product Management`, `Design`, `Operations`, `Marketing`, `Finance`.
- **Trending Skills Table**: For the selected domain, display top N skills ranked by frequency of appearance in job postings over a configurable time window (default: last 30 days).
  - Columns: Skill Name | Domain | Type | # Postings | Trend (↑↓) | First Seen
  - Sortable columns.
  - Searchable via client-side filter.
- **Skill Detail Panel**: Clicking a skill opens a slide-over or modal with:
  - Skill description (generated by Synthesizer, cached)
  - Example job titles that require this skill
  - Example companies hiring for this skill
  - Related skills (sourced via vector similarity from Qdrant)
  - "Add to My Profile" button (V2 feature, placeholder in V1)
- **Data Freshness Indicator**: Display "Last updated: X hours ago" prominently. Users must trust the data is live.
- **Source Transparency**: A collapsible section showing which companies and boards are being monitored.

#### 2.2.3 Dashboard — V2 Requirements (Personalization)

- **User Accounts**: Email/password + OAuth (Google). Session management via NextAuth.js.
- **My Skill Profile**: Authenticated users can:
  - Select their current domain and target domain
  - Mark skills as "I have this" or "I want this"
  - See a gap analysis: skills required in their target domain that they've flagged as missing
- **Custom Alerts**: Users subscribe to a domain or skill and receive email alerts when a new significant skill emerges (threshold: appears in 10+ new postings within 7 days).
- **Personalized Roadmap Seed**: The gap analysis feeds into a structured upskilling roadmap (V3 feature; V2 surfaces raw gap data only).

#### 2.2.4 Frontend Component Breakdown

| Component | Location | Description |
|---|---|---|
| `SkillDashboard` | `app/dashboard/page.tsx` | Page shell, domain filter state |
| `DomainFilterBar` | `components/charts/DomainFilterBar.tsx` | Tab/dropdown domain selector |
| `SkillsTable` | `components/charts/SkillsTable.tsx` | Sortable, filterable data table |
| `SkillDetailPanel` | `components/charts/SkillDetailPanel.tsx` | Slide-over with skill details |
| `TrendSparkline` | `components/charts/TrendSparkline.tsx` | Mini time-series chart per skill |
| `RelatedSkillsBadges` | `components/charts/RelatedSkillsBadges.tsx` | Vector-similar skill chips |

#### 2.2.5 API Endpoints (Skills)

```
GET  /api/v1/skills                          → paginated skill list (filterable by domain, type, date range)
GET  /api/v1/skills/{skill_id}               → skill detail + related skills
GET  /api/v1/skills/trending?domain=X&days=30 → top trending skills for a domain
GET  /api/v1/domains                          → list of available domains with posting counts
GET  /api/v1/skills/search?q={query}          → semantic search via Qdrant
```

---

### Feature 3: Conversational Survey Research Agent

**Purpose**: Replace static lead-capture forms with a dynamic conversational AI that gathers rich qualitative data on user career anxieties, current tool usage, and upskilling goals. Serves dual purpose: lead generation AND ongoing workforce research dataset.

**Priority**: P0 (basic capture for MVP), P1 (full research-grade for V2)

#### 2.3.1 The Interviewer Agent — Behavior Specification

The Interviewer is a LangChain-powered conversational agent backed by Claude (Anthropic). It does NOT behave like a customer service chatbot. It behaves like a skilled qualitative researcher conducting a structured-but-flexible interview.

**Core behaviors**:
- Opens with a warm, direct framing of the conversation's purpose: gathering data to improve the platform and understand workforce trends. Transparency is required — users must know their responses are being used for research.
- Follows a **guided but adaptive interview protocol**. There is a canonical set of research questions (see below), but the agent may probe, rephrase, or reorder them based on the user's previous responses.
- Never asks more than one question per message.
- Acknowledges and reflects the user's prior answer briefly before moving to the next question (active listening behavior).
- After 8–12 exchanges, gracefully closes the interview and offers a CTA: view the Skill Dashboard relevant to their domain, or book a consulting call.
- Must handle: off-topic responses (gently redirect), distressed responses (acknowledge, offer resources, redirect), very short responses (probe for depth).

**Canonical Research Questions** (agent may reorder/rephrase):

| # | Topic | Example Question |
|---|---|---|
| 1 | Current Role | "What kind of work do you do, and what industry are you in?" |
| 2 | AI Tool Usage | "Which AI tools have you started using in your work, if any? What's been your experience?" |
| 3 | Biggest Anxiety | "What's your biggest fear or concern about AI's impact on your career over the next 3 years?" |
| 4 | Current Upskilling | "Are you currently doing anything to upskill for AI? What's working, what isn't?" |
| 5 | Skill Gap Awareness | "If you had to name one skill you feel behind on, what would it be?" |
| 6 | Decision Bottleneck | "What's the main thing stopping you from making a move on this — time, money, knowing where to start?" |
| 7 | Ideal Outcome | "What would success look like for you in 2 years if the AI transition went in your favor?" |
| 8 | Platform Feedback | "What would make a platform like this genuinely useful to you, vs. just another thing to ignore?" |

#### 2.3.2 Data Capture Requirements

Every survey session must persist:

```
survey_sessions(
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id) NULLABLE,  -- null for anonymous
  session_token VARCHAR UNIQUE,
  started_at TIMESTAMP,
  completed_at TIMESTAMP NULLABLE,
  completion_status VARCHAR,   -- 'completed', 'abandoned', 'redirected'
  self_reported_domain VARCHAR,
  turn_count INT
)

survey_messages(
  id UUID PRIMARY KEY,
  session_id UUID REFERENCES survey_sessions(id),
  role VARCHAR,   -- 'assistant' or 'user'
  content TEXT,
  timestamp TIMESTAMP,
  turn_number INT
)

survey_extractions(
  id UUID PRIMARY KEY,
  session_id UUID REFERENCES survey_sessions(id),
  extracted_at TIMESTAMP,
  current_role TEXT,
  industry TEXT,
  ai_tools_used TEXT[],
  primary_anxiety TEXT,
  upskilling_activities TEXT,
  self_identified_skill_gap TEXT,
  decision_bottleneck TEXT,
  ideal_outcome TEXT,
  domain_classification VARCHAR,  -- Taxonomist-assigned
  sentiment_score FLOAT,
  raw_llm_extraction JSONB
)
```

Chat history for the active session must also be persisted in Qdrant for semantic retrieval (enables future cross-session research queries).

#### 2.3.3 Frontend Component Breakdown

| Component | Location | Description |
|---|---|---|
| `SurveyPage` | `app/survey/page.tsx` | Page shell, session initialization |
| `ChatWindow` | `components/survey/ChatWindow.tsx` | Scrollable message history |
| `MessageBubble` | `components/survey/MessageBubble.tsx` | Styled user/assistant message |
| `TypingIndicator` | `components/survey/TypingIndicator.tsx` | Animated "thinking" state |
| `InputBar` | `components/survey/InputBar.tsx` | Text input + send button |
| `ClosingCTA` | `components/survey/ClosingCTA.tsx` | Post-interview CTA card |

#### 2.3.4 API Endpoints (Survey)

```
POST /api/v1/survey/session              → create new session, return session_token
POST /api/v1/survey/message              → send user message, receive agent response (streaming)
GET  /api/v1/survey/session/{token}      → retrieve session state and history
POST /api/v1/survey/session/{token}/end  → explicitly close and trigger extraction
```

The `/message` endpoint must support **streaming responses** via Server-Sent Events (SSE) so the assistant response types in progressively rather than arriving all at once.

---

## 3. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Page Load (marketing) | LCP < 2.5s (SSG) |
| Dashboard Initial Load | < 3s (SSR with streaming) |
| Survey Response Latency | First token < 1.5s, streaming thereafter |
| API Uptime | 99.5% (MVP), 99.9% (V2+) |
| Data Freshness | Job postings refreshed every 24 hours minimum |
| Mobile Responsiveness | All surfaces fully responsive (Tailwind responsive modifiers) |
| Accessibility | WCAG 2.1 AA compliance for all public-facing pages |
| Rate Limiting | 100 req/min per IP for public endpoints; 1000/min for authenticated |

---

## 4. Out of Scope (for MVP)

- Payment processing / subscription management (V2)
- Video content delivery
- Real-time collaborative features
- Native mobile apps
- User-generated content / community features
- Integration with external LMS platforms
