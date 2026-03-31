# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-native catering management system for HP Israel. Agent-driven operations across two sites (Nes Ziona, Kiryat Gat). Built around specialist AI agents that use Claude API for intelligence — not a traditional CRUD app.

## Version & Deploy Policy

**Current Production Version: V02** (commit `67682e3`, 2026-03-31)

### CRITICAL: Deploy only with user approval
- **NEVER push to main or deploy without explicit user approval**
- Production is live and used daily — deploy carefully
- Always ask before pushing: "Changes are ready. Approve push to main + deploy?"
- After deploy, verify production health and increment version (V01 → V02, etc.)

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

Two-layer architecture: **individual agents** for focused tasks + **Agent Crew** for multi-agent orchestration.

#### Individual Agents
`backend/agents/orchestrator.py` routes requests to specialist agents extending `BaseAgent`.

| Agent | Status | Directory |
|-------|--------|-----------|
| Meeting Prep | Implemented | `backend/agents/meeting_prep/` |
| Complaint Intelligence | Implemented | `backend/agents/complaint_intelligence/` |
| Budget Intelligence | Implemented | `backend/agents/budget_intelligence/` |
| Dietary Compliance | Implemented | `backend/agents/dietary_compliance/` |
| Event Coordination | Implemented | `backend/agents/event_coordination/` |
| Communication Hub | Implemented | `backend/agents/communication_hub/` |

#### Agent Crew System (`backend/agents/crew/`)
Multi-agent orchestration with intent analysis, parallel execution, and result synthesis.

| Component | File | Purpose |
|-----------|------|---------|
| Models | `crew/models.py` | AgentRole, AgentTask, AgentMessage, CrewMetrics dataclasses |
| Roles | `crew/roles.py` | 10 role definitions (1 manager + 9 specialists) |
| Registry | `crew/registry.py` | Lazy agent initialization, maps roles to BaseAgent instances |
| Manager | `crew/manager.py` | Intent analysis → delegation → parallel execution → synthesis |
| Session | `crew/session.py` | Blackboard pattern for inter-agent data sharing |
| API | `api/agent_crew.py` | REST endpoints: crew info, chat, direct agent run, roles |
| Frontend | `frontend/src/app/agent-crew/page.tsx` | Crew dashboard, chat interface, agent cards |

**Crew Agents** (10 roles):
| Role ID | Title | Agent Instance |
|---------|-------|---------------|
| operations_manager | Chief Operations Coordinator | Manager (orchestrator) |
| data_analyst | Senior Catering Data Analyst | BudgetIntelligenceAgent |
| menu_compliance | Dietary Compliance & Kashrut | DietaryComplianceAgent |
| invoice_analyst | Senior Procurement Analyst | BudgetIntelligenceAgent |
| budget_intelligence | Chief Budget Officer | BudgetIntelligenceAgent |
| complaint_intelligence | Complaint Resolution Specialist | ComplaintIntelligenceAgent |
| daily_ops_monitor | Real-Time Operations Monitor | BudgetIntelligenceAgent |
| supplier_manager | Vendor Relationship Manager | BudgetIntelligenceAgent |
| event_coordinator | Event Catering Coordinator | EventCoordinationAgent |
| communication_hub | Communications & Reporting | CommunicationHubAgent |

### Frontend (Next.js 14 App Router + TypeScript)

21 pages, Tailwind CSS + Radix UI + Lucide icons + Recharts:

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
| Agent Crew | `/agent-crew` | Multi-agent dashboard, crew chat, agent cards with metrics |

### Services

| Service | File | Purpose |
|---------|------|---------|
| Claude API | `backend/services/claude_service.py` | Async Anthropic API wrapper (generate_response, generate_vision_response, generate_with_tools, generate_structured_response) |
| IMAP Email Poller | `backend/services/meal_email_poller.py` | Background Gmail IMAP poller for FoodHouse daily meal reports |
| Menu Analysis | `backend/services/menu_analysis_service.py` | Compliance check engine |

### Data Layer

- **Dev**: SQLite (`catering_ai.db` at project root)
- **Prod**: PostgreSQL 15 (via `DATABASE_URL`)
- Auto-converts URLs to async driver (`sqlite+aiosqlite`, `postgresql+asyncpg`)
- Production data: 11,497 proforma items, 68 Hebrew compliance rules, 89 products

### Key Models (21+)

Core: `User`, `Site`, `Supplier`, `Product`, `Proforma`, `ProformaItem`
Budget: `SupplierBudget`, `SupplierProductBudget`, `MaintenanceBudget`, `MaintenanceExpense`
Compliance: `ComplianceRule`, `MenuCheck`, `CheckResult`, `FineRule`
Operations: `Meeting`, `MeetingNote`, `Complaint`, `ComplaintPattern`, `Anomaly`
Tasks: `Project`, `ProjectTask`, `ProjectDocument`, `TaskStatusHistory`, `TodoItem`
Analytics: `ProductCategoryGroup`, `ProductCategoryMapping`, `WorkingDaysEntry`
Kitchenette: `KitchenetteItem`
Daily Ops: `DailyMealCount`, `HistoricalMealData`, `Attachment`

## Daily Meals Automation Pipeline

Hands-free email → database pipeline for FoodHouse daily meal counts:

1. **IMAP Poller** (`backend/services/meal_email_poller.py`) — Daily at 5:00 AM Israel time + once on startup. Connects to `ziv@foodbiz.co.il` via Gmail IMAP, searches for unread emails with subject `HP_FC_REPORT`, parses `.xlsx` attachment (columns: `restaurant id`, `name`, `count deals`), upserts into `daily_meal_counts`
2. **Webhook** (`POST /api/webhooks/daily-meals`) — Alternative: Power Automate sends JSON/CSV
3. **CSV Upload** (`POST /api/webhooks/daily-meals/upload`) — Manual upload from UI (Hebrew cp1255 encoding)
4. **Manual Trigger** (`POST /api/webhooks/daily-meals/poll-now`) — Force immediate IMAP check
5. **Dashboard** — Grouped bar chart (NZ + KG side-by-side), stacked by meal type. Per-site sidebar: meals vs 6-month avg, cost (meals × unit_price from latest proforma) vs budget

Meal type parsing: `בשרי`→Meat, `חלבי`→Dairy, `עיקרית בלבד`→Main Only
Site parsing: `נס ציונה`→NZ, `קרית גת`→KG
Cost per meal: Meat/Dairy ≈₪39.57, Main Only ≈₪8.87 (from latest FoodHouse proforma)

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

## What's Been Built (57 commits)

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
- IMAP email poller: `ziv@foodbiz.co.il` → Gmail IMAP → parses HP_FC_REPORT.xlsx → upserts meals
- Daily scheduler: runs once at 5:00 AM Israel time + once on startup
- Dashboard: grouped bar chart (NZ + KG side-by-side), stacked by meal type (Meat/Dairy/Main Only)
- Per-site sidebar: meals vs 6-month avg + cost (meals × unit_price from proformas) vs budget
- Manual trigger endpoint for testing

### Phase 5: UI/UX Overhaul + Price Lists
- Dashboard redesign: modern KPI cards, semantic color tokens (CSS custom properties), animated transitions, responsive grid
- Price list management overhaul: CSV upload with multi-encoding support (utf-8, cp1255, latin-1) and auto column detection (EN/HE headers)
- Inline price/unit editing with hover-to-reveal actions, add product with catalog auto-creation, duplicate detection
- Backend endpoints: PUT/DELETE items, POST add-product, POST upload CSV
- Branding: "Catering AI Pro" header, "HP Israel - Ziv Reshef Simchoni" subtitle + footer
- Menu compliance rules: search box + category filter pills with counts

### Phase 6: Agent Crew + Fine Rule Intelligence
- **Agent Crew system**: 10-agent orchestration (1 manager + 9 specialists) with intent analysis, parallel execution, result synthesis
- **All 6 AI agents implemented**: Budget Intelligence, Dietary Compliance, Event Coordination, Communication Hub (no longer stubs)
- **Agent Crew frontend page**: `/agent-crew` with crew dashboard, chat interface, agent cards, interaction map
- **Fine rule import from PDF**: Upload contract PDF → AI extracts rules in Hebrew → preview modal with per-rule toggle → replace seeded rules
- **Auto-match complaints to fines**: AI suggests matching fine rule with confidence score when complaint is created, auto-links at ≥70% confidence
- **Deploy fix**: Committed 8 missing agent crew files that caused Railway healthcheck failures
- **File existence check**: Detects ephemeral filesystem file loss after Railway redeployment

### Phase 6b: AI Menu Compliance Overhaul (2026-03-25)
- **AI-powered compliance check**: Replaced broken rule-based matching with Claude AI as default. Falls back to rules if API unavailable
- **Intelligent Hebrew matching**: 30+ dish synonym examples in prompt (בריסקט=חזה בקר, שווארמה דג≠אמנון, etc.)
- **Dynamic frequency calculation**: Uses actual working days per month, not hardcoded ×4 weeks
- **Anomaly detection**: Flags vague dish names, consecutive-day repeats, same-day duplicates, >1 ground meat/day
- **Version-numbered Excel export**: `KG menu check - April 2026 version 1.xlsx` with "חוסרים" sheet matching manual check format
- **Frontend AI evidence**: Shows matched items, frequency text, notes from Claude; hides old "Searched keyword" UI for AI results
- **Max tokens fix**: Increased from 4096 to 16384 for AI compliance check (was silently truncating)

### Phase 6c: PDF Proforma Upload Fix (2026-03-26)
- **PDF Hebrew RTL fix**: pdfplumber extracts reversed Hebrew text in RTL PDFs — parser now detects and reverses it
- **Header validation**: After table extraction, validates headers against known keywords (מוצר, כמות, מחיר, product, quantity, price)
- **AI fallback**: If pdfplumber headers are unrecognizable even after reversal, skips to Claude AI text extraction
- **Three-strategy pipeline**: 1) pdfplumber table + fix reversed Hebrew → 2) AI structured extraction from raw text → 3) error with guidance

### Phase 6e: Excel Compliance Export Overhaul (2026-03-30)
- **9-column format**: חוסרים sheet matches manual check format exactly — A=קבוצה, B=סוג, C=תדירות, D=תקן, E=בפועל, F=חוסר, G=פריטים שנמצאו בתפריט, H=הערות, I=הערות נוספות
- **Weekly menu sheet reconstruction**: When original uploaded file is gone (Railway ephemeral FS), rebuilds שבוע 1/2/3... sheets from MenuDay DB records. Row 1 = date headers, Col A = categories, cells = menu items per day
- **AI check: direct generate_response**: Switched from generate_structured_response (which appended conflicting schema) to generate_response with robust JSON array extraction by bracket-matching — immune to Claude preamble text
- **Column G keyword matching**: When Claude omits matched_items, export reconstructs from MenuDay data using Hebrew-aware keyword matching:
  - **Hebrew final-letter normalization**: ף→פ, ם→מ, ן→נ, ך→כ, ץ→צ (fixes "חריף" not matching "חריפות")
  - **ו-conjunction stripping**: "וירוקים"→"ירוקים", "ותפוח"→"תפוח"
  - **Generic catering word exclusion**: סלט, מנת, מנה, פילה, ביתי, מקומי, ברוטב, טרי — not used as keywords
  - **AND matching for 2+ keywords**: "קציצות פרגית" only matches items containing BOTH words — no cross-contamination between different פרגית dishes
  - **Fallback to longest keyword**: When AND finds nothing (spelling variant in menu), tries each keyword alone from longest to shortest
- **AI check current date**: System prompt now injects today's date so AI doesn't return wrong year
- **Upload flow fix**: Panel stays open during AI check, navigates to check detail after completion
- **Commit series**: 5595c16 → b5aeba1 → e47173b → f677fef → cd12128 → a35b3fb → f4949b5 → 00557be → c31fb27

### Phase 6d: Project Improvements + AI Assistant Tool-Use (2026-03-26b)
- **Overdue task highlight**: Tasks with past due dates + not done get light red background (`bg-red-50`), red due date text + ⚠ icon
- **Task status change history**: `TaskStatusHistory` model logs every status change with from_status, to_status, changed_at, changed_by. Shown in expanded task view
- **Gantt chart view**: List/Gantt toggle on project detail page. Custom component with horizontal task bars, month headers, today marker (red line), status-colored bars, legend
- **AI Assistant tool-use**: Complete rewrite of `backend/api/chat.py` using Claude tool-use with 8 data query tools:
  - `query_spending`: Product-level proforma items by supplier/site/month with optional product search
  - `query_budgets`: Budget allocations with monthly breakdown
  - `query_meals`: Daily meal counts by type and site
  - `query_violations`: Violations with severity, fines, patterns
  - `query_meetings`: Upcoming/past meetings
  - `query_price_lists`: Price comparison across suppliers
  - `query_projects`: Projects with tasks and deadlines
  - `query_summary`: High-level operational dashboard
- **Tool-use loop**: Claude chains up to 5 tool calls per question for comprehensive answers
- **Chart rendering**: `ChatMessageRenderer` component parses ````chart` JSON blocks into inline Recharts bar/line/pie charts
- **Table rendering**: Markdown tables in AI responses rendered as styled HTML tables
- **Excel export**: `POST /api/chat/export` generates downloadable .xlsx files (spending items, budgets, meals)
- **`generate_with_tools()`**: New method on `ClaudeService` for tool-use API calls

### Phase 7a: Meal Data Source Fix + Kitchenette + Dashboard Redesign (2026-03-31)
- **MealBreakdown costs**: Added 9 price columns + total_cost. Extraction reads col C (prices) + col E (totals) from ריכוז הכנסות
- **`meals-monthly` rewrite**: Queries MealBreakdown instead of ProformaItem. Returns quantity + supplement + cost per month/site
- **`meals-detail` rewrite**: 9 Hebrew meal type labels pivoted from MealBreakdown fields (was ProformaItem product names)
- **`meals-budget` endpoint (NEW)**: YTD budget vs actual per site from SupplierBudget + MealBreakdown.total_cost
- **KitchenetteItem model (NEW)**: Stores BTB products from ריכוז מטבחונים tab. 7 families auto-classified by Hebrew keywords
- **`kitchenette-monthly` endpoint (NEW)**: Quantities + spending per family per month per site
- **Kitchenette parser**: `_extract_kitchenette_data()` reads ריכוז מטבחונים tab during proforma upload
- **Dashboard redesign (Budget vs Actual section only)**:
  - Top level: 3 gradient KPI cards (Total Meals, Supplement, Total Cost) + grouped bar chart (NZ indigo, KG cyan)
  - Budget Progress: compact progress bars (supplier name, actual/budget, %, colored bar)
  - 3 drill-down tabs: Meal Categories (stacked bars), Budget vs Actual (side-by-side per site), Kitchenette (stacked area + family cards)
  - Year + site filter connected to all panels
- **10 auto-migration entries** in main.py for new MealBreakdown columns
- **Commit**: `67682e3`

## Session Summary Rules

**CRITICAL**: When asked to summarize a session, ALWAYS:
1. Read `README.md` roadmap section to compare against the original plan
2. Show what was in the original roadmap vs what's been built vs what's remaining
3. Update CLAUDE.md and README.md with any new features built
4. Never lose track of the original 6-phase agent roadmap from README.md

## Original Roadmap (from README.md — never lose this)

- [x] Phase 1: Meeting Prep Agent
- [x] Phase 2: Complaint Intelligence Agent
- [x] Frontend: All 9 → 21 pages with CRUD
- [x] Real data migration from FoodHouse Analytics
- [x] **Phase 3: Budget Intelligence Agent** (forecasting, alerts, trends) ✅
- [x] **Phase 4: Event Coordination Agent** (event planning support) ✅
- [x] **Phase 5: Dietary Compliance Agent** (automated menu rule checking) ✅
- [x] **Phase 6: Communication Hub Agent** (Slack/email routing) ✅

**All 6 original agent phases are now complete.**

## What's Next

### Phase 6: Agent Crew + Fine Rule Intelligence (Complete)
- [x] **Agent Crew system** — 10-agent orchestration with CrewManager, intent analysis, parallel execution
- [x] **All 6 AI agents implemented** — Budget, Dietary, Event, Communication (no longer stubs)
- [x] **Agent Crew frontend** — `/agent-crew` page with dashboard, chat, agent cards, interaction map
- [x] **Fine rule import from PDF** — AI extracts rules in Hebrew, preview modal with per-rule toggle
- [x] **Auto-match complaints to fines** — AI suggests matching fine rule with confidence score
- [x] **AI-powered menu compliance** — Replaced broken rule-based check with Claude AI matching
- [x] **Anomaly detection** — Vague names, consecutive days, duplicates, ground meat limit
- [x] **Version-numbered Excel export** — `KG menu check - April 2026 version 1.xlsx`
- [ ] First real fine import test (re-upload PDF after deploy, verify Hebrew extraction)
- [x] First real FoodHouse email test — IMAP poller configured and live (session 2026-03-25b)
- [x] **PDF proforma upload RTL fix** — Hebrew reversal detection + AI fallback (session 2026-03-26)

### Phase 7a: Meal Data Source + Kitchenette + Dashboard (Complete — 2026-03-31)
- [x] **Fix meal data source** — Dashboard reads from MealBreakdown (not ProformaItem). 9 Hebrew meal types
- [x] **MealBreakdown costs** — Price columns + total_cost extracted from ריכוז הכנסות
- [x] **Kitchenette/BTB tracking** — KitchenetteItem model, 7 families, auto-classified, ריכוז מטבחונים parser
- [x] **Dashboard redesign** — KPI cards, gradient bars, budget progress bars, 3 drill-down tabs
- [x] **meals-budget endpoint** — YTD budget vs actual per site
- [x] **kitchenette-monthly endpoint** — Qty + spending per family per month
- [x] **Per-site filtering** — Year + site dropdown on all panels
- [ ] Cost per employee normalization (working_days × diners) — still TODO

### Phase 7b: Agent Intelligence Deepening
- [ ] **Agent Crew PM per project** — Appoint most capable agent as PM for each project (track progress, suggest takeovers, alert problems, meeting summaries with relevant professionals)
- [ ] Dedicated agent implementations (data_analyst, supplier_manager, daily_ops_monitor currently share BudgetIntelligenceAgent)
- [ ] Sequential task dependencies in crew (currently all parallel)
- [ ] Persistent crew sessions (currently in-memory)
- [ ] Monthly fine report — collect fines by date/amount, prepare supplier fine summary table
- [ ] Agent health monitoring & auto-recovery
- [ ] Custom workflows (pre-defined multi-agent sequences)
- [ ] Webhook event triggers (complaint → pattern detection → vendor email pipeline)

### Phase 8: Platform Maturity
- [ ] Notification system (email/Slack alerts for anomalies, complaints, budget overruns)
- [ ] Role-based access control (admin vs viewer vs site manager)
- [ ] Export reports (PDF/Excel)
- [ ] Mobile PWA optimization
- [ ] Audit log for all changes
- [ ] Multi-language UI support (English/Hebrew toggle)
- [ ] Historical trend predictions using AI
- [ ] Cloud file storage (S3/GCS) to survive Railway redeployments

## FoodHouse Proforma Structure

The FoodHouse XLSX proforma is the core data source for meals, costs, and kitchenette tracking. One file per site per month.

### Proforma Tabs

| Tab | Content | Dashboard Use |
|-----|---------|---------------|
| **חשבוניות** | 14 invoices with line items, prices, totals | Price reference only — NOT source for quantities |
| **ריכוז ארוחות** | Daily meal counts + monthly totals + working days | **PRIMARY source** for meal quantities, costs, working days |
| **ריכוז הכנסות** | Financial summary from all invoices | Summary only, not a data source |
| **ריכוז מטבחונים** | Daily BTB product consumption | **Source** for kitchenette cost tracking |

### Meal Data (from ריכוז ארוחות)

**Dashboard top level** shows two numbers:
- **Total meals** (e.g., 17,022) — all meals excluding תוספת מנה עיקרית
- **Supplement** (e.g., 969) — תוספת מנה עיקרית shown separately
- Total Cibus = 17,991 (meals + supplement, excludes coffee cart)

**תוספת מנה עיקרית**: Meat dining room only — employees swipe Cibus card again for a second protein portion. All employees eligible (HP + contractors). Price ₪8.87 vs ₪39.57 for a regular meal.

**Drill-down** by meal type:

| Meal Type | Who Pays |
|-----------|----------|
| ארוחת צהריים בשרית (HP INDIGO) | HP |
| ארוחת צהריים בשרית (HP סאייטקס) | Scitex |
| ארוחות ערב (HP) | HP |
| ארוחות ערב (קבלנים) | HP |
| ארוחת צהריים חלבית (HP INDIGO) | HP |
| ארוחת צהריים חלבית (HP סאייטקס) | Scitex |
| תוספת מנה עיקרית (HP+קבלנים) | HP |
| ארוחות צהריים בשרית (קבלנים) | Each contractor |
| ארוחות צהריים חלבית (קבלנים) | Each contractor |

**Excluded from dashboard**: עגלת קפה (future), ארוחות כלבי נחיה, נתניה (invoice 13)

**Costs**: Sum סה"כ ₪ from ריכוז ארוחות, excluding coffee cart rows.

**Working days (ימי עבודה)**: Found in ריכוז ארוחות — search dynamically for label.

### Kitchenette / BTB Tracking (from ריכוז מטבחונים)

**BTB** = HP pays product cost + 5.5% catering company commission.

**Dashboard**: Trend graph per site, normalized by:
- Variable 1: Working days (from ריכוז ארוחות)
- Variable 2: Number of diners (from ריכוז ארוחות)

**Drill-down by 7 product families** (manually classified):

| Family | Hebrew | Examples | Invoice |
|--------|--------|----------|---------|
| Coffee & Tea | קפה ותה | Instant coffee, tea bags, sugar, mint, lemon | 4 |
| Coffee & Machine Rental | קפה ושכירות מכונות | Café Kedem, black coffee 1kg, Eversys rental | 4 |
| Dairy Products | מוצרי חלב | Milk, Yoplait, desserts, cream, Danone | 4 |
| Dry Goods | יבשים | Granola, waffles, cookies, honey, silan | 4 |
| Fruits | פירות | Fruits, premium fruits, vegetables | 5 |
| Accompaniments | נילווים | Apples/carrots/beets for juice machine, concentrate | 2 |
| Miscellaneous | שונות | Cups, water, soda, sandwiches, toothpicks | 4 |

### Per-Site Requirement

**CRITICAL**: All data must support 3 views:
1. **NZ only** (Nes Ziona, site_id=1)
2. **KG only** (Kiryat Gat, site_id=2)
3. **Combined** (both sites)

### Dashboard Cost Display

The dashboard must show **both** views:
1. **Total cost (סה"כ עלות)** — absolute cost of meals/category/product
2. **Cost per employee (עלות לעובד)** — normalized cost

Both are needed for review and approval. Total cost is the primary view; per-employee is supplementary.

### Current Code vs Required

| Aspect | Current | Required |
|--------|---------|----------|
| Meal quantities | From חשבוניות (proforma_items) | **ריכוז ארוחות** tab |
| Meal costs | From חשבוניות | **ריכוז ארוחות** סה"כ ₪ (excl. coffee cart) |
| Kitchenette tracking | Not implemented | **Trend + drill-down by 7 families** |
| Working days | ריכוז הכנסות (partial) | **ריכוז ארוחות** |
| BTB classification | Not implemented | **7 manual families** |
| Normalization | Not implemented | **working_days × diners** |
| Per-site filtering | Partial | **NZ / KG / Combined** |
| Cost display | Total cost only | **Total cost + cost per employee** |

### Proforma Files

Location: `C:\Users\ReZi146\OneDrive - HP Inc\Documents\פרפורמות\`
- `NZ 2025/` — 12 files (Jan-Dec), `NZ 2026/` — 2 files (Jan-Feb)
- `KG 2025/` — 12 files (Jan-Dec), `KG 2026/` — 2 files (Jan-Feb)
- `א.א.ע/` — 4 PDF files (מ.א אוטומטים, not FoodHouse)
