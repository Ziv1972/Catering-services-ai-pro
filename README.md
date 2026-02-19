# Catering Services AI Pro

An AI-native catering management system for HP Israel, designed to make facility operations managers 10x more effective.

## What Makes This Different

This isn't traditional software with AI features bolted on. This is an AI agent system that happens to have a visual interface. The system:

- **Proactively prepares** meeting briefs with data-driven talking points
- **Automatically detects** patterns in complaints and equipment issues
- **Predicts** budget variances before they become problems
- **Drafts** responses to stakeholder requests
- **Suggests** optimizations based on historical data

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Anthropic API key

### Setup

1. Clone and setup:
```bash
git clone <repo-url>
cd catering-services-ai-pro
git checkout dev
```

2. Backend:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials

# Setup database
python scripts/setup_db.py

# Run
uvicorn backend.main:app --reload
```

3. Frontend:
```bash
cd frontend
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Run
npm run dev
```

4. Access:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Using Docker
```bash
docker-compose up
```

## Phase 1: Meeting Prep Agent (MVP)

Current implementation focuses on automating meeting preparation:

1. **Schedule a meeting** via the UI
2. **Generate AI brief** - Click "Prepare Brief"
3. **System gathers context**:
   - Previous meeting notes
   - Recent complaints
   - Budget status
   - Equipment issues
4. **Claude generates**:
   - Priority topics
   - Questions to ask
   - Suggested action items
   - Formatted agenda

### Time Savings
- Manual prep: ~15 minutes
- With AI: ~30 seconds
- **Savings: 97%**

## Roadmap

- [x] Phase 1: Meeting Prep Agent (Current)
- [ ] Phase 2: Complaint Intelligence Agent
- [ ] Phase 3: Budget Intelligence Agent
- [ ] Phase 4: Event Coordination Agent
- [ ] Phase 5: Dietary Compliance Agent
- [ ] Phase 6: Communication Hub Agent
- [ ] Phase 7: Unified Dashboard

## Project Structure
```
backend/
  agents/          # AI agent system
  api/             # FastAPI endpoints
  services/        # External integrations (Claude, Gmail, etc.)
  models/          # Database models

frontend/
  src/app/         # Next.js pages
  src/components/  # React components
  src/lib/         # Utilities & API client

scripts/           # Setup & deployment
docs/              # Documentation
```

## Development

See `.cursorrules` for detailed development guidelines.

### Running Tests
```bash
cd backend
pytest
```

### Code Quality
```bash
# Python
black backend/
ruff backend/

# TypeScript
cd frontend
npm run lint
```

## License

Private - HP Internal Use Only
