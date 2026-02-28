# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-native catering management system for HP Israel. Agent-driven operations across two sites (Nes Ziona, Kiryat Gat). Built around specialist AI agents that use Claude API for intelligence — not a traditional CRUD app.

**Production URLs:**
- Backend: `https://courteous-amazement-production-02e2.up.railway.app`
- Frontend: `https://frontend-production-c346.up.railway.app`

## Commands

### Backend
```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend
```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
npm run build        # production build
npm run lint         # ESLint
```

### Testing
```bash
pytest                                              # all tests
pytest backend/tests/test_api.py                    # single file
pytest backend/tests/test_api.py::test_name -v      # single test
# pytest.ini: asyncio_mode = auto
```

### Docker
```bash
docker-compose up -d    # full stack: PostgreSQL + Redis
```

## Architecture

### Backend (FastAPI + async SQLAlchemy)

- **Entry point**: `backend/main.py` — FastAPI app with lifespan that auto-creates tables, runs migrations, seeds data, and starts background services
- **Config**: `backend/config.py` — Pydantic `Settings` loaded from `.env`
- **Database**: `backend/database.py` — async SQLAlchemy sessions, auto-detects SQLite vs PostgreSQL
- **Models**: `backend/models/` — 20+ SQLAlchemy ORM models (one per file)
- **API routes**: `backend/api/` — 21 FastAPI routers (150+ endpoints), JWT-protected except auth and webhook test
- **Services**: `backend/services/` — Claude API wrapper, IMAP email poller, menu analysis

### AI Agent System

`backend/agents/orchestrator.py` routes requests to specialist agents extending `BaseAgent`.

| Agent | Status | Directory |
|-------|--------|-----------|
| Meeting Prep | Implemented | `backend/agents/meeting_prep/` |
| Complaint Intelligence | Implemented | `backend/agents/complaint_intelligence/` |
| Budget Intelligence | Stub | `backend/agents/budget_intelligence/` |
| Dietary Compliance | Stub | `backend/agents/dietary_compliance/` |
| Event Coordination | Stub | `backend/agents/event_coordination/` |
| Communication Hub | Stub | `backend/agents/communication_hub/` |

### Frontend (Next.js 14 App Router + TypeScript)

20 pages, Tailwind CSS + Radix UI + Lucide icons + Recharts:

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Central hub: quick stats, supplier spending chart, meals charts, budget drill-down, AI chat |
| Login | `/login` | JWT authentication |
| Budget | `/budget` | Annual supplier budget planning with monthly breakdown and vs-actual comparison |
| Projects | `/projects` | Project management with tasks and document uploads |
| Project Detail | `/projects/[id]` | Task CRUD, document management |
| Maintenance | `/maintenance` | Quarterly maintenance budgets and expense tracking |
| Meetings | `/meetings` | Upcoming meetings with AI-generated briefs |
| Create Meeting | `/meetings/new` | New meeting form with type/site/duration |
| Meeting Detail | `/meetings/[id]` | AI brief, priority topics, questions, action items |
| Todos | `/todos` | Personal/delegated task management with priority and entity linking |
| Menu Compliance | `/menu-compliance` | Upload menus, run compliance checks, manage Hebrew rules |
| Compliance Detail | `/menu-compliance/[id]` | Check results with findings per rule |
| Suppliers | `/suppliers` | Supplier CRUD with contract tracking |
| Price Lists | `/price-lists` | CSV upload, inline editing, add product, auto-generate from proformas, compare lists |
| Proformas | `/proformas` | Invoice management with vendor spending summary |
| Proforma Detail | `/proformas/[id]` | Line items, price comparison against price lists |
| Complaints | `/complaints` | Complaint management, fine rules, AI analysis, pattern detection |
| Complaint Detail | `/complaints/[id]` | AI draft response, resolution tracking |
| Analytics | `/analytics` | Multi-level drill-down: cost analysis (4 levels), quantity analysis (5 levels) |
| Anomalies | `/anomalies` | Operational anomaly tracking with severity and resolution |

### Services

| Service | File | Purpose |
|---------|------|---------|
| Claude API | `backend/services/claude_service.py` | Async Anthropic API wrapper |
| IMAP Email Poller | `backend/services/meal_email_poller.py` | Background Gmail IMAP poller for FoodHouse daily meal reports |
| Menu Analysis | `backend/services/menu_analysis_service.py` | Compliance check engine |

### Data Layer

- **Dev**: SQLite (`catering_ai.db` at project root)
- **Prod**: PostgreSQL 15 (via `DATABASE_URL`)
- Auto-converts URLs to async driver (`sqlite+aiosqlite`, `postgresql+asyncpg`)
- Production data: 11,497 proforma items, 68 Hebrew compliance rules, 89 products

### Key Models (20+)

Core: `User`, `Site`, `Supplier`, `Product`, `Proforma`, `ProformaItem`
Budget: `SupplierBudget`, `SupplierProductBudget`, `MaintenanceBudget`, `MaintenanceExpense`
Compliance: `ComplianceRule`, `MenuCheck`, `CheckResult`, `FineRule`
Operations: `Meeting`, `MeetingNote`, `Complaint`, `ComplaintPattern`, `Anomaly`
Tasks: `Project`, `ProjectTask`, `ProjectDocument`, `TodoItem`
Analytics: `ProductCategoryGroup`, `ProductCategoryMapping`, `WorkingDaysEntry`
Daily Ops: `DailyMealCount`, `HistoricalMealData`, `Attachment`

## Daily Meals Automation Pipeline

Hands-free email → database pipeline for FoodHouse daily meal counts:

1. **IMAP Poller** (`backend/services/meal_email_poller.py`) — Background task polls Gmail for FoodHouse emails, extracts CSV, upserts into `daily_meal_counts`
2. **Webhook** (`POST /api/webhooks/daily-meals`) — Alternative: Power Automate sends JSON/CSV
3. **CSV Upload** (`POST /api/webhooks/daily-meals/upload`) — Manual upload from UI (Hebrew cp1255 encoding)
4. **Manual Trigger** (`POST /api/webhooks/daily-meals/poll-now`) — Force immediate IMAP check
5. **Dashboard** — Stacked bar chart by meal type (Meat/Dairy/Main Only) with budget comparison

Meal type parsing: `בשרי`→Meat, `חלבי`→Dairy, `עיקרית בלבד`→Main Only
Site parsing: `נס ציונה`→NZ, `קרית גת`→KG

## Test Infrastructure

Tests use in-memory SQLite via fixtures in `backend/tests/conftest.py`:
- `db_session` — fresh DB per test
- `seed_data` — default user (`test@hp.com` / `testpass123`) + 2 sites
- `client` — authenticated `httpx.AsyncClient` with JWT
- `unauth_client` — unauthenticated client

**Known issue**: `test_dashboard` expects `upcoming_meetings` key but API returns `meetings`

## Environment Variables

Required in `.env`:
- `DATABASE_URL` — SQLite (dev) or PostgreSQL (prod)
- `SECRET_KEY` — JWT signing key
- `ANTHROPIC_API_KEY` — Claude API key
- `CLAUDE_MODEL` — defaults to `claude-sonnet-4-20250514`

IMAP email poller (for daily meal automation):
- `IMAP_HOST` — e.g. `imap.gmail.com`
- `IMAP_EMAIL` — Gmail address
- `IMAP_PASSWORD` — Gmail App Password (16-char)
- `MEAL_EMAIL_SENDER` — sender filter (partial match)
- `MEAL_EMAIL_SUBJECT` — subject filter (partial match)
- `MEAL_POLL_INTERVAL_MIN` — polling interval (default: 60)

Optional: `GMAIL_CREDENTIALS_PATH`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `CALENDAR_CREDENTIALS_PATH`

Frontend: `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`)

## Key Patterns

### Claude API calls
```python
from backend.services.claude_service import claude_service
response = await claude_service.generate_structured_response(
    prompt=prompt, system_prompt=SYSTEM_PROMPT, response_format=EXPECTED_SCHEMA
)
```

### Database queries (async SQLAlchemy 2.0)
```python
result = await db.execute(
    select(Model).where(Model.field == value).order_by(Model.created_at.desc())
)
items = result.scalars().all()
```

### API endpoint structure
```python
@router.post("/{id}/action")
async def action(
    id: int, data: RequestSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
```

## Deployment

- **Railway**: Backend via root `Dockerfile` + `railway.json` (health check at `/health`)
- **Frontend**: Separate Railway deployment from `frontend/`
- Startup auto-seeds: admin user, sites, suppliers, budgets, fine rules, products, compliance rules, category groups
- Background: IMAP email poller starts automatically if configured

## Hebrew Content

Compliance rules, meal types, product names, and some domain data are in Hebrew. The system manages catering for HP Israel — Hebrew text in database seeds and UI is expected.

## What's Been Built (44 commits)

### Phase 1: Foundation
- FastAPI backend with async SQLAlchemy, JWT auth, 2-site support
- Next.js 14 frontend with App Router, Tailwind, Recharts
- AI agents: Meeting Prep + Complaint Intelligence
- Real data migration from FoodHouse Analytics

### Phase 2: Dashboard & Analytics
- Dashboard overhaul: budget cards, project status, maintenance, todos, AI chat widget
- Budget drill-down: 4-stage cascading (supplier → month → site → category → products)
- Product category analysis with 4-level drill-down (9 category groups, 50+ mappings)
- Analytics page: cost (4 levels) and quantity (5 levels) drill-down
- Working days management per site/month

### Phase 3: Operations
- Complaints with fines, pattern detection, weekly AI summaries
- File upload for projects/tasks with AI processing (summarize/extract)
- Price list generation from proformas, cross-list comparison
- Supplier spending charts, price comparison for proformas
- Menu compliance: upload, rules management, check results

### Phase 4: Daily Meal Automation
- DailyMealCount model with upsert logic
- Webhook endpoints for Power Automate + CSV upload
- Dashboard: stacked bar chart by meal type with budget comparison
- IMAP email poller for hands-free Gmail → database pipeline
- Manual trigger endpoint for testing

### Phase 5: UI/UX Overhaul + Price Lists (Latest)
- Dashboard redesign: modern KPI cards, semantic color tokens (CSS custom properties), animated transitions, responsive grid
- Price list management overhaul: CSV upload with multi-encoding support (utf-8, cp1255, latin-1) and auto column detection (EN/HE headers)
- Inline price/unit editing with hover-to-reveal actions, add product with catalog auto-creation, duplicate detection
- Backend endpoints: PUT/DELETE items, POST add-product, POST upload CSV
- Branding: "Catering AI Pro" header, "HP Israel - Ziv Reshef Simchoni" subtitle + footer

## Session Summary Rules

**CRITICAL**: When asked to summarize a session, ALWAYS:
1. Read `README.md` roadmap section to compare against the original plan
2. Show what was in the original roadmap vs what's been built vs what's remaining
3. Update CLAUDE.md and README.md with any new features built
4. Never lose track of the original 6-phase agent roadmap from README.md

## Original Roadmap (from README.md — never lose this)

- [x] Phase 1: Meeting Prep Agent
- [x] Phase 2: Complaint Intelligence Agent
- [x] Frontend: All 9 → 20 pages with CRUD
- [x] Real data migration from FoodHouse Analytics
- [ ] **Phase 3: Budget Intelligence Agent** (forecasting, alerts, trends)
- [ ] **Phase 4: Event Coordination Agent** (event planning support)
- [ ] **Phase 5: Dietary Compliance Agent** (automated menu rule checking)
- [ ] **Phase 6: Communication Hub Agent** (Slack/email routing)

## What's Next

### Phase 5: UI/UX Overhaul + Price Lists (Completed)
- [x] **Dashboard redesign** — modern KPI cards, semantic color tokens, animated transitions, responsive layout
- [x] **Price list management** — CSV upload (multi-encoding, auto-column detection), inline editing, add product with catalog auto-creation
- [x] **Branding** — "Catering AI Pro" header, "HP Israel - Ziv Reshef Simchoni" subtitle + footer
- [ ] Fix `test_dashboard` test (key mismatch: `upcoming_meetings` → `meetings`)
- [ ] First real FoodHouse email test — tune IMAP sender/subject filters

### Phase 6: Remaining AI Agents
- [ ] Implement **Budget Intelligence Agent** (variance prediction, cost optimization, spend alerts)
- [ ] Implement **Dietary Compliance Agent** (automated menu rule checking against 68 Hebrew rules)
- [ ] Implement **Event Coordination Agent** (event logistics management)
- [ ] Implement **Communication Hub Agent** (Slack/email multi-channel notifications)

### Phase 7: Platform Maturity
- [ ] Notification system (email/Slack alerts for anomalies, complaints, budget overruns)
- [ ] Role-based access control (admin vs viewer vs site manager)
- [ ] Export reports (PDF/Excel)
- [ ] Mobile PWA optimization
- [ ] Audit log for all changes
- [ ] Multi-language UI support (English/Hebrew toggle)
- [ ] Historical trend predictions using AI
