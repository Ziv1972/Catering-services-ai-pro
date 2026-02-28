# Catering Services AI Pro

AI-native catering management system for HP Israel. Agent-driven operations management across two sites.

## Architecture Overview

```mermaid
graph TB
    subgraph Frontend["Frontend · Next.js 14"]
        UI[App Router Pages]
        API_CLIENT[Axios API Client]
        NAV[NavHeader Navigation]
        UI --> API_CLIENT
    end

    subgraph Backend["Backend · FastAPI"]
        AUTH[JWT Auth]
        ROUTES[API Routes]
        ORCH[Agent Orchestrator]
        DB_LAYER[Async SQLAlchemy]
        CLAUDE[Claude Service]

        ROUTES --> AUTH
        ROUTES --> DB_LAYER
        ROUTES --> ORCH
        ORCH --> CLAUDE
    end

    subgraph Agents["AI Agents"]
        MP[Meeting Prep Agent]
        CI[Complaint Intelligence]
        BI[Budget Intelligence]
        DC[Dietary Compliance]
        EC[Event Coordination]
        CH[Communication Hub]
    end

    subgraph External["External Services"]
        ANTHROPIC[Anthropic Claude API]
        GMAIL[Gmail API]
        SLACK[Slack SDK]
        GCAL[Google Calendar]
        PA[Power Automate]
    end

    subgraph Storage["Data Layer"]
        SQLITE[(SQLite / PostgreSQL)]
        REDIS[(Redis Cache)]
    end

    API_CLIENT -->|HTTPS| ROUTES
    ORCH --> MP
    ORCH --> CI
    ORCH --> BI
    ORCH --> DC
    ORCH --> EC
    ORCH --> CH
    CLAUDE --> ANTHROPIC
    DB_LAYER --> SQLITE
    ROUTES --> GMAIL
    ROUTES --> SLACK
    ROUTES --> GCAL
    PA -->|Webhooks| ROUTES
```

## Agent Flow

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant O as Orchestrator
    participant A as AI Agent
    participant C as Claude API
    participant DB as Database

    U->>FE: Action (e.g. Prepare Meeting Brief)
    FE->>API: POST /api/meetings/{id}/prepare
    API->>O: route_request("meeting_prep", context)
    O->>A: MeetingPrepAgent.process()
    A->>DB: Gather context (complaints, notes, budget)
    DB-->>A: Historical data
    A->>C: Generate brief with context
    C-->>A: Structured JSON response
    A-->>API: Meeting brief + agenda
    API->>DB: Save ai_brief, ai_agenda
    API-->>FE: Updated meeting data
    FE-->>U: Display AI-generated brief
```

## Database Schema

```mermaid
erDiagram
    USERS ||--o{ MEETINGS : creates
    SITES ||--o{ MEETINGS : hosts
    SITES ||--o{ COMPLAINTS : receives
    SITES ||--o{ PROFORMAS : orders
    SITES ||--o{ MENU_CHECKS : audits
    SITES ||--o{ HISTORICAL_MEAL_DATA : records

    SUPPLIERS ||--o{ PROFORMAS : invoices
    PROFORMAS ||--o{ PROFORMA_ITEMS : contains
    PRODUCTS ||--o{ PROFORMA_ITEMS : references

    MENU_CHECKS ||--o{ MENU_DAYS : includes
    MENU_CHECKS ||--o{ CHECK_RESULTS : generates

    MEETINGS ||--o{ MEETING_NOTES : has

    USERS {
        int id PK
        string email UK
        string full_name
        string hashed_password
        boolean is_active
        boolean is_admin
    }

    SITES {
        int id PK
        string name UK
        string code UK
        float monthly_budget
        boolean is_active
    }

    MEETINGS {
        int id PK
        string title
        string meeting_type
        datetime scheduled_at
        int site_id FK
        json ai_brief
        text ai_agenda
        text ai_summary
    }

    COMPLAINTS {
        int id PK
        int site_id FK
        text complaint_text
        string source
        string category
        string severity
        float sentiment_score
        text ai_summary
        text ai_root_cause
        string status
    }

    SUPPLIERS {
        int id PK
        string name UK
        string contact_name
        string email
        string phone
        date contract_start
        date contract_end
        string payment_terms
        boolean is_active
    }

    PROFORMAS {
        int id PK
        int supplier_id FK
        int site_id FK
        string proforma_number
        date invoice_date
        float total_amount
        string status
    }

    PROFORMA_ITEMS {
        int id PK
        int proforma_id FK
        string product_name
        float quantity
        string unit
        float unit_price
        float total_price
        boolean flagged
    }

    MENU_CHECKS {
        int id PK
        int site_id FK
        string month
        int year
        int total_findings
        int critical_findings
    }

    CHECK_RESULTS {
        int id PK
        int menu_check_id FK
        string rule_name
        string rule_category
        boolean passed
        string severity
        text finding_text
    }

    COMPLIANCE_RULES {
        int id PK
        string name UK
        string rule_type
        string description
        string category
        json parameters
        int priority
        boolean is_active
    }

    ANOMALIES {
        int id PK
        string anomaly_type
        string entity_type
        int entity_id
        string severity
        float expected_value
        float actual_value
        float variance_percent
        boolean resolved
    }
```

## AI Agents

```mermaid
graph TD
    ORCH[Agent Orchestrator]

    subgraph Complete["Implemented"]
        MP["Meeting Prep Agent<br/>Generates briefs, agendas,<br/>action items from context"]
        CI["Complaint Intelligence<br/>Analyzes severity, sentiment,<br/>detects patterns, drafts responses"]
    end

    subgraph Planned["Planned"]
        BI["Budget Intelligence<br/>Variance prediction,<br/>cost optimization"]
        DC["Dietary Compliance<br/>Dietary requirement<br/>tracking"]
        EC["Event Coordination<br/>Event logistics<br/>management"]
        CH["Communication Hub<br/>Multi-channel<br/>notifications"]
    end

    ORCH --> MP
    ORCH --> CI
    ORCH -.-> BI
    ORCH -.-> DC
    ORCH -.-> EC
    ORCH -.-> CH

    style MP fill:#4ade80,stroke:#16a34a,color:#000
    style CI fill:#4ade80,stroke:#16a34a,color:#000
    style BI fill:#fbbf24,stroke:#d97706,color:#000
    style DC fill:#fbbf24,stroke:#d97706,color:#000
    style EC fill:#fbbf24,stroke:#d97706,color:#000
    style CH fill:#fbbf24,stroke:#d97706,color:#000
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Radix UI |
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic |
| AI | Anthropic Claude (Sonnet 4), LangChain |
| Database | SQLite (dev) / PostgreSQL 15 (prod) |
| Cache | Redis 7 |
| Icons | Lucide React |
| Charts | Recharts |
| Auth | JWT (python-jose, passlib) |
| Integrations | Gmail API, Slack SDK, Google Calendar, Power Automate |

## Pages (20)

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Central hub: KPI cards, budget vs actual, supplier spending chart, meals charts, daily meals, AI chat |
| `/login` | Login | JWT authentication |
| `/budget` | Budget | Annual supplier budget planning with monthly breakdown and vs-actual comparison |
| `/projects` | Projects | Project management with tasks and document uploads |
| `/projects/[id]` | Project Detail | Task CRUD, document management, file upload with AI processing |
| `/maintenance` | Maintenance | Quarterly maintenance budgets and expense tracking |
| `/meetings` | Meetings | Upcoming meetings with AI-generated briefs |
| `/meetings/new` | Create Meeting | New meeting form with type/site/duration |
| `/meetings/[id]` | Meeting Detail | AI brief, priority topics, questions, action items |
| `/todos` | Todos | Personal/delegated task management with priority and entity linking |
| `/menu-compliance` | Menu Compliance | Upload menus, run compliance checks, manage 68 Hebrew rules |
| `/menu-compliance/[id]` | Compliance Detail | Check results with findings per rule |
| `/suppliers` | Suppliers | Supplier CRUD with contract tracking |
| `/price-lists` | Price Lists | CSV upload, inline editing, add product, auto-generate from proformas, compare lists |
| `/proformas` | Proformas | Invoice management with vendor spending summary |
| `/proformas/[id]` | Proforma Detail | Line items, price comparison against price lists |
| `/complaints` | Complaints | Complaint management, fine rules, AI analysis, pattern detection |
| `/complaints/[id]` | Complaint Detail | AI draft response, resolution tracking |
| `/analytics` | Analytics | Multi-level drill-down: cost (4 levels), quantity (5 levels) |
| `/anomalies` | Anomalies | Operational anomaly tracking with severity and resolution |

## API Endpoints

```mermaid
graph LR
    subgraph Auth["/api/auth"]
        A1["POST /login"]
        A2["POST /register"]
        A3["GET /me"]
    end

    subgraph Meetings["/api/meetings"]
        M1["GET /"]
        M2["POST /"]
        M3["GET /{id}"]
        M4["POST /{id}/prepare"]
    end

    subgraph Complaints["/api/complaints"]
        C1["GET /"]
        C2["POST /"]
        C3["POST /{id}/acknowledge"]
        C4["POST /{id}/draft-response"]
        C5["POST /{id}/resolve"]
        C6["GET /patterns/active"]
        C7["GET /summary/weekly"]
    end

    subgraph MenuCompliance["/api/menu-compliance"]
        MC1["GET /checks"]
        MC2["GET /checks/{id}"]
        MC3["POST /upload-menu"]
        MC4["GET,POST /rules"]
        MC5["PUT,DELETE /rules/{id}"]
    end

    subgraph Proformas["/api/proformas"]
        P1["GET /"]
        P2["POST /"]
        P3["GET /{id}"]
        P4["GET /vendor-spending/summary"]
    end

    subgraph Suppliers["/api/suppliers"]
        S1["GET /"]
        S2["POST /"]
        S3["PUT /{id}"]
        S4["DELETE /{id}"]
    end

    subgraph Other["Other APIs"]
        O1["GET /api/anomalies"]
        O2["GET /api/historical/meals"]
        O3["GET /api/dashboard"]
        O4["POST /api/webhooks/*"]
    end
```

## Request Flow

```mermaid
flowchart LR
    Browser -->|JWT Token| NextJS
    NextJS -->|Axios + Auth Header| FastAPI
    FastAPI -->|Verify Token| Auth
    Auth -->|Authorized| Router
    Router -->|DB Query| SQLAlchemy
    Router -->|AI Request| Orchestrator
    Orchestrator -->|Structured Prompt| Claude
    Claude -->|JSON Response| Orchestrator
    SQLAlchemy -->|Async| Database[(SQLite)]
    Router -->|JSON| NextJS
    NextJS -->|Render| Browser
```

## Project Structure

```
catering-services-ai-pro/
├── backend/
│   ├── agents/                    # AI agent system
│   │   ├── base_agent.py          # Abstract base agent
│   │   ├── orchestrator.py        # Request routing
│   │   ├── meeting_prep/          # Meeting brief generation
│   │   ├── complaint_intelligence/# Complaint analysis
│   │   ├── budget_intelligence/   # Budget analysis (stub)
│   │   ├── dietary_compliance/    # Dietary rules (stub)
│   │   ├── event_coordination/    # Event mgmt (stub)
│   │   └── communication_hub/     # Notifications (stub)
│   ├── api/                       # FastAPI route handlers
│   │   ├── auth.py                # JWT authentication
│   │   ├── meetings.py            # Meetings CRUD + AI
│   │   ├── complaints.py          # Complaints + patterns
│   │   ├── menu_compliance.py     # Menu checks + rules
│   │   ├── proformas.py           # Invoice management
│   │   ├── suppliers.py           # Supplier CRUD
│   │   ├── anomalies.py           # Anomaly detection
│   │   ├── historical.py          # Historical data
│   │   ├── dashboard.py           # Dashboard metrics
│   │   └── webhooks.py            # Gmail/Slack/Calendar
│   ├── models/                    # SQLAlchemy models (20+ tables)
│   ├── services/                  # Claude API, IMAP poller, menu analysis
│   ├── tests/                     # pytest test suite
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Pydantic settings
│   └── database.py                # Async DB sessions
├── frontend/
│   ├── src/
│   │   ├── app/                   # Next.js App Router pages
│   │   │   ├── page.tsx           # Dashboard
│   │   │   ├── login/             # Authentication
│   │   │   ├── meetings/          # Meeting management
│   │   │   ├── complaints/        # Complaint tracking
│   │   │   ├── menu-compliance/   # Compliance audits
│   │   │   ├── proformas/         # Invoice tracking
│   │   │   ├── suppliers/         # Supplier directory
│   │   │   ├── price-lists/       # Price list management
│   │   │   ├── budget/            # Supplier budgets
│   │   │   ├── projects/          # Project management
│   │   │   ├── maintenance/       # Maintenance budgets
│   │   │   ├── todos/             # Task management
│   │   │   ├── anomalies/         # Anomaly alerts
│   │   │   └── analytics/         # Reports & trends
│   │   ├── components/
│   │   │   ├── layout/            # AppShell, NavHeader
│   │   │   └── ui/                # Reusable components
│   │   └── lib/
│   │       └── api.ts             # Axios API client
│   ├── package.json
│   └── tailwind.config.js
├── scripts/                       # Setup & migration utilities
├── docker-compose.yml             # PostgreSQL + Redis + App
├── requirements.txt               # Python dependencies
└── .env                           # Environment config
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env  # Add your ANTHROPIC_API_KEY
python -m backend.main
```

Backend runs on `http://localhost:8000` — API docs at `/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`

### Docker (Production)

```bash
docker-compose up -d
```

Starts PostgreSQL, Redis, backend, and frontend.

### Running Tests

```bash
pytest
```

## Data

Production data migrated from FoodHouse Analytics:

| Entity | Count |
|--------|-------|
| Suppliers | 2 |
| Proformas | 53 |
| Proforma Items | 11,497 |
| Compliance Rules | 68 (Hebrew) |
| Menu Checks | 2 |
| Check Results | 1,118 |
| Menu Days | 45 |
| Products | 89 |
| Categories | 12 |

## Sites

| Code | Name |
|------|------|
| NZ | Nes Ziona |
| KG | Kiryat Gat |

## Roadmap

### Completed
- [x] Phase 1: Meeting Prep Agent — AI brief generation with historical context
- [x] Phase 2: Complaint Intelligence Agent — analysis, patterns, weekly summaries, draft responses
- [x] Frontend: 9 → **20 pages** with full CRUD
- [x] Real data migration from FoodHouse Analytics (11,497 proforma items)
- [x] Dashboard overhaul: budget cards, supplier spending, meals chart, AI chat widget
- [x] Budget drill-down: 4-stage cascading (supplier → month → site → category → products)
- [x] Product category analysis: 4-level drill-down (9 groups, 50+ mappings)
- [x] Analytics page: cost (4 levels) and quantity (5 levels) drill-down
- [x] Complaints with fines, pattern detection, weekly AI summaries
- [x] File upload for projects/tasks with AI processing (summarize/extract)
- [x] Price list generation from proformas, cross-list comparison
- [x] Supplier spending charts, price comparison for proformas
- [x] Menu compliance: upload, rules management, check results
- [x] Project management with tasks, documents, entity linking
- [x] Todo system with priority, delegation, entity linking
- [x] Maintenance budgets (quarterly) and expense tracking
- [x] Daily meals automation: IMAP email poller, webhooks, CSV upload, dashboard chart
- [x] Working days management per site/month

### Completed — Phase 5: UI/UX Overhaul + Price Lists
- [x] Dashboard redesign with modern KPI cards, semantic color tokens, animated transitions, responsive layout
- [x] Price list management — CSV upload (multi-encoding, auto-column detection), inline editing, add product with catalog auto-creation
- [x] Branding update: "Catering AI Pro" header, "HP Israel - Ziv Reshef Simchoni" subtitle, footer
- [x] Menu compliance rules: search box + category filter pills with counts

### Upcoming — Phase 6: Remaining AI Agents
- [ ] Budget Intelligence Agent (forecasting, alerts, trends)
- [ ] Dietary Compliance Agent (automated menu rule checking)
- [ ] Event Coordination Agent (event planning support)
- [ ] Communication Hub Agent (Slack/email routing)

### Future — Phase 7: Platform Maturity
- [ ] Notification system (email/Slack alerts)
- [ ] Role-based access control
- [ ] Export reports (PDF/Excel)
- [ ] Mobile PWA optimization
- [ ] Audit log, multi-language UI

## License

Private — HP Israel Internal Use
