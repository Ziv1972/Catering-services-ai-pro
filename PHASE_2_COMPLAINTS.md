# Phase 2: Complaint Intelligence Agent - Complete Implementation

> **Upload this file to Cursor to build the Complaint Intelligence system**

---

## Overview

Build an AI-powered complaint monitoring and response system that:
- **Monitors multiple channels** (email, Slack, manual entry)
- **Detects patterns** across complaints using AI
- **Auto-categorizes** by severity and type
- **Drafts responses** automatically
- **Alerts on urgent issues**
- **Tracks resolution** to closure

---

## Architecture

```
Complaint Sources → Monitoring Services → AI Analysis → Dashboard + Alerts
     ↓                      ↓                  ↓              ↓
  Email              Email Monitor      Pattern Detection   Priority View
  Slack              Slack Monitor      Categorization      Auto-Drafts
  Manual Entry       Manual Entry       Root Cause          Trends
                                        Sentiment
```

---

## Database Models

### 1. Complaint Model (`backend/models/complaint.py`)

```python
"""
Complaint tracking model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from enum import Enum


class ComplaintSource(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    MANUAL = "manual"
    FORM = "form"


class ComplaintSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplaintStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ComplaintCategory(str, Enum):
    FOOD_QUALITY = "food_quality"
    TEMPERATURE = "temperature"
    SERVICE = "service"
    VARIETY = "variety"
    DIETARY = "dietary"
    CLEANLINESS = "cleanliness"
    EQUIPMENT = "equipment"
    OTHER = "other"


class Complaint(Base):
    """Employee complaint or feedback"""
    __tablename__ = "complaints"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    
    # Source information
    source = Column(SQLEnum(ComplaintSource), nullable=False)
    source_id = Column(String, nullable=True)  # Email message ID, Slack thread ID, etc.
    
    # Complaint content
    complaint_text = Column(Text, nullable=False)
    
    # AI-generated classifications
    category = Column(SQLEnum(ComplaintCategory), nullable=True)
    severity = Column(SQLEnum(ComplaintSeverity), nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    
    # AI analysis
    ai_summary = Column(Text, nullable=True)
    ai_root_cause = Column(Text, nullable=True)
    ai_suggested_action = Column(Text, nullable=True)
    pattern_group_id = Column(String, nullable=True)  # Links related complaints
    
    # Complainant (optional, may be anonymous)
    employee_name = Column(String, nullable=True)
    employee_email = Column(String, nullable=True)
    is_anonymous = Column(Boolean, default=False)
    
    # Status tracking
    status = Column(SQLEnum(ComplaintStatus), default=ComplaintStatus.NEW)
    
    # Timestamps
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Response
    response_text = Column(Text, nullable=True)
    response_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Resolution
    resolution_notes = Column(Text, nullable=True)
    requires_vendor_action = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    site = relationship("Site", backref="complaints")


class ComplaintPattern(Base):
    """Detected patterns across multiple complaints"""
    __tablename__ = "complaint_patterns"
    
    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(String, unique=True, nullable=False, index=True)
    
    # Pattern details
    pattern_type = Column(String, nullable=False)  # recurring_issue, time_based, location_based, trend
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)
    
    # Affected complaints
    complaint_count = Column(Integer, default=0)
    first_occurrence = Column(DateTime(timezone=True), nullable=False)
    last_occurrence = Column(DateTime(timezone=True), nullable=False)
    
    # AI recommendation
    recommendation = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## AI Agents

### 2. Complaint Intelligence Agent (`backend/agents/complaint_intelligence/agent.py`)

```python
"""
Complaint Intelligence Agent
Analyzes complaints, detects patterns, suggests actions
"""
from backend.agents.base_agent import BaseAgent
from backend.models.complaint import (
    Complaint, ComplaintPattern, ComplaintSeverity, 
    ComplaintCategory, ComplaintStatus
)
from backend.models.site import Site
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import uuid


class ComplaintIntelligenceAgent(BaseAgent):
    """
    Analyzes complaints, detects patterns, and suggests responses
    """
    
    def __init__(self):
        super().__init__(name="ComplaintIntelligenceAgent")
    
    async def analyze_complaint(
        self,
        db: AsyncSession,
        complaint: Complaint
    ) -> Dict[str, Any]:
        """
        Analyze a single complaint using AI
        """
        
        # Get site context if available
        site_name = "Unknown"
        if complaint.site_id:
            result = await db.execute(select(Site).where(Site.id == complaint.site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name
        
        prompt = f"""
        Analyze this employee complaint from HP Israel catering services:
        
        COMPLAINT TEXT:
        {complaint.complaint_text}
        
        CONTEXT:
        - Source: {complaint.source}
        - Site: {site_name}
        - Date: {complaint.received_at.strftime('%Y-%m-%d %H:%M')}
        
        Provide detailed analysis as JSON:
        {{
            "category": "food_quality|temperature|service|variety|dietary|cleanliness|equipment|other",
            "severity": "low|medium|high|critical",
            "sentiment_score": -1.0 to 1.0 (negative to positive),
            "summary": "One clear sentence summarizing the complaint",
            "root_cause": "Likely underlying cause based on the complaint text",
            "suggested_action": "Specific, actionable step Ziv should take",
            "urgency": "immediate|today|this_week|routine",
            "requires_vendor_action": true|false,
            "time_pattern": "Any time-of-day pattern mentioned (e.g., 'lunch rush', '12:45pm', 'morning')"
        }}
        
        Be specific and actionable in suggested_action. Consider:
        - Is this a recurring issue that needs systematic fix?
        - Is this a vendor performance issue?
        - Is this an equipment/facility issue?
        - Is this a one-time incident?
        """
        
        analysis = await self.generate_structured_response(
            prompt=prompt,
            system_prompt=self._get_system_prompt()
        )
        
        # Update complaint with AI analysis
        complaint.category = ComplaintCategory(analysis["category"])
        complaint.severity = ComplaintSeverity(analysis["severity"])
        complaint.sentiment_score = float(analysis["sentiment_score"])
        complaint.ai_summary = analysis["summary"]
        complaint.ai_root_cause = analysis["root_cause"]
        complaint.ai_suggested_action = analysis["suggested_action"]
        complaint.requires_vendor_action = analysis["requires_vendor_action"]
        
        return analysis
    
    async def detect_patterns(
        self,
        db: AsyncSession,
        lookback_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns across recent complaints
        """
        
        # Get recent complaints
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        result = await db.execute(
            select(Complaint)
            .where(Complaint.received_at >= cutoff_date)
            .order_by(Complaint.received_at.desc())
        )
        complaints = result.scalars().all()
        
        if len(complaints) < 2:
            return []
        
        # Prepare complaint data for AI
        complaint_data = []
        for c in complaints:
            complaint_data.append({
                "id": c.id,
                "date": c.received_at.isoformat(),
                "site": c.site.name if c.site else "Unknown",
                "category": c.category.value if c.category else None,
                "severity": c.severity.value if c.severity else None,
                "summary": c.ai_summary or c.complaint_text[:100],
                "root_cause": c.ai_root_cause
            })
        
        prompt = f"""
        Analyze these {len(complaints)} complaints from the last {lookback_days} days for patterns:
        
        COMPLAINTS:
        {json.dumps(complaint_data, indent=2)}
        
        Identify meaningful patterns. Return as JSON array:
        [{{
            "pattern_type": "recurring_issue|time_based|location_based|trend",
            "description": "Clear description of the pattern",
            "complaint_ids": [list of complaint IDs that share this pattern],
            "severity": "low|medium|high|critical",
            "recommendation": "Specific action to address this pattern",
            "evidence": "What makes this a real pattern, not coincidence"
        }}]
        
        Only report patterns where:
        - At least 2-3 complaints share the same specific issue
        - There's a clear time, location, or cause pattern
        - It's actionable (not just "people complain sometimes")
        
        Examples of GOOD patterns:
        - "Cold food at Nes Ziona between 12:45-1:00pm (3 complaints, staffing issue)"
        - "Vegan portions too small (4 complaints, increasing trend)"
        
        Examples of BAD patterns (don't report):
        - "People don't like some foods" (too vague)
        - "2 complaints" (too few, could be random)
        
        Return empty array [] if no meaningful patterns found.
        """
        
        patterns = await self.generate_structured_response(prompt)
        
        # Store detected patterns
        for pattern_data in patterns:
            pattern_id = str(uuid.uuid4())
            
            # Update complaints with pattern ID
            for complaint_id in pattern_data["complaint_ids"]:
                result = await db.execute(
                    select(Complaint).where(Complaint.id == complaint_id)
                )
                complaint = result.scalar_one_or_none()
                if complaint:
                    complaint.pattern_group_id = pattern_id
            
            # Create pattern record
            complaint_ids = pattern_data["complaint_ids"]
            first_complaint = await db.execute(
                select(Complaint)
                .where(Complaint.id.in_(complaint_ids))
                .order_by(Complaint.received_at.asc())
                .limit(1)
            )
            last_complaint = await db.execute(
                select(Complaint)
                .where(Complaint.id.in_(complaint_ids))
                .order_by(Complaint.received_at.desc())
                .limit(1)
            )
            
            first = first_complaint.scalar_one_or_none()
            last = last_complaint.scalar_one_or_none()
            
            if first and last:
                pattern = ComplaintPattern(
                    pattern_id=pattern_id,
                    pattern_type=pattern_data["pattern_type"],
                    description=pattern_data["description"],
                    severity=pattern_data["severity"],
                    complaint_count=len(complaint_ids),
                    first_occurrence=first.received_at,
                    last_occurrence=last.received_at,
                    recommendation=pattern_data["recommendation"]
                )
                db.add(pattern)
        
        await db.commit()
        
        return patterns
    
    async def draft_acknowledgment(
        self,
        db: AsyncSession,
        complaint: Complaint
    ) -> str:
        """
        Draft an acknowledgment response for a complaint
        """
        
        site_name = "Unknown"
        if complaint.site_id:
            result = await db.execute(select(Site).where(Site.id == complaint.site_id))
            site = result.scalar_one_or_none()
            if site:
                site_name = site.name
        
        # Detect language (Hebrew or English)
        has_hebrew = any('\u0590' <= c <= '\u05FF' for c in complaint.complaint_text)
        language = "Hebrew" if has_hebrew else "English"
        
        prompt = f"""
        Draft an acknowledgment email for this complaint:
        
        COMPLAINT: {complaint.complaint_text}
        SITE: {site_name}
        AI ANALYSIS: {complaint.ai_summary}
        SUGGESTED ACTION: {complaint.ai_suggested_action}
        SEVERITY: {complaint.severity.value if complaint.severity else 'unknown'}
        
        TONE: Professional, empathetic, action-oriented
        LENGTH: 2-3 sentences
        LANGUAGE: {language}
        
        Structure:
        1. Thank them for the specific feedback
        2. Brief acknowledgment of the issue
        3. What you're doing about it (be honest, don't over-promise)
        
        Examples:
        
        ENGLISH:
        "Thank you for letting me know about the temperature issue during lunch. 
        I'm aware that food has been served cold during the rush, and I'm working 
        with the catering manager to address staffing during peak times. I'll 
        follow up with you by Friday with an update."
        
        HEBREW:
        "תודה שהודעת לי על בעיית הטמפרטורה בארוחת הצהריים. אני מודע לכך שהאוכל 
        הוגש קר בשעות העומס, ואני עובד עם מנהל הקייטרינג על שיפור התפעול בשעות 
        השיא. אעדכן אותך עד יום שישי."
        
        Return ONLY the email text, no subject line, no preamble.
        """
        
        draft = await self.generate_response(prompt, system_prompt=self._get_system_prompt())
        
        return draft.strip()
    
    async def generate_weekly_summary(
        self,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Generate weekly summary of complaints for dashboard
        """
        
        # Last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get complaints
        result = await db.execute(
            select(Complaint).where(Complaint.received_at >= week_ago)
        )
        complaints = result.scalars().all()
        
        # Get patterns
        patterns_result = await db.execute(
            select(ComplaintPattern)
            .where(
                and_(
                    ComplaintPattern.is_active == True,
                    ComplaintPattern.last_occurrence >= week_ago
                )
            )
        )
        patterns = patterns_result.scalars().all()
        
        # Category breakdown
        category_counts = {}
        for c in complaints:
            if c.category:
                cat = c.category.value
                category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Severity breakdown
        severity_counts = {}
        for c in complaints:
            if c.severity:
                sev = c.severity.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Response rate
        responded = len([c for c in complaints if c.acknowledged_at])
        response_rate = (responded / len(complaints) * 100) if complaints else 0
        
        # Average resolution time
        resolved = [c for c in complaints if c.resolved_at and c.received_at]
        if resolved:
            avg_resolution_hours = sum(
                (c.resolved_at - c.received_at).total_seconds() / 3600 
                for c in resolved
            ) / len(resolved)
        else:
            avg_resolution_hours = 0
        
        summary = {
            "total_complaints": len(complaints),
            "by_category": category_counts,
            "by_severity": severity_counts,
            "active_patterns": len(patterns),
            "response_rate": round(response_rate, 1),
            "avg_resolution_hours": round(avg_resolution_hours, 1),
            "critical_count": severity_counts.get("critical", 0),
            "high_count": severity_counts.get("high", 0)
        }
        
        return summary
    
    def _get_system_prompt(self) -> str:
        """System prompt for complaint analysis"""
        return """You are an AI assistant helping Ziv Reshef-Simchoni, the Food Service Manager at HP Israel.

Your role is to analyze employee complaints about catering services and provide actionable insights.

Context:
- Ziv manages catering across two sites: Nes Ziona and Kiryat Gat
- He works with vendors (Foodhouse, L.Eshel, etc.) who provide meals
- Common issues: food temperature, quality, variety, dietary accommodations
- Ziv values specific, actionable recommendations over vague advice

When analyzing complaints:
- Be specific about root causes
- Suggest concrete actions Ziv can take
- Consider if it's a vendor issue, equipment issue, or process issue
- Note if it's part of a larger pattern
- Be empathetic but professional"""
```

---

## API Endpoints

### 3. Complaints API (`backend/api/complaints.py`)

```python
"""
Complaints API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.complaint import (
    Complaint, ComplaintPattern, ComplaintSource, 
    ComplaintSeverity, ComplaintStatus, ComplaintCategory
)
from backend.api.auth import get_current_user
from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


class ComplaintCreate(BaseModel):
    complaint_text: str
    site_id: Optional[int] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    is_anonymous: bool = False
    source: ComplaintSource = ComplaintSource.MANUAL


class ComplaintResponse(BaseModel):
    id: int
    complaint_text: str
    site_id: Optional[int]
    source: str
    category: Optional[str]
    severity: Optional[str]
    ai_summary: Optional[str]
    ai_suggested_action: Optional[str]
    status: str
    received_at: datetime
    pattern_group_id: Optional[str]
    
    class Config:
        from_attributes = True


class PatternResponse(BaseModel):
    id: int
    pattern_id: str
    pattern_type: str
    description: str
    severity: str
    complaint_count: int
    recommendation: Optional[str]
    is_active: bool
    
    class Config:
        from_attributes = True


@router.post("/", response_model=ComplaintResponse)
async def create_complaint(
    complaint_data: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new complaint"""
    
    complaint = Complaint(
        **complaint_data.model_dump(),
        received_at=datetime.utcnow()
    )
    
    db.add(complaint)
    await db.flush()
    
    # Analyze with AI
    agent = ComplaintIntelligenceAgent()
    await agent.analyze_complaint(db, complaint)
    
    await db.commit()
    await db.refresh(complaint)
    
    return complaint


@router.get("/", response_model=List[ComplaintResponse])
async def list_complaints(
    days: int = Query(7, ge=1, le=90),
    severity: Optional[ComplaintSeverity] = None,
    status: Optional[ComplaintStatus] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List complaints with filters"""
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    query = select(Complaint).where(Complaint.received_at >= cutoff)
    
    if severity:
        query = query.where(Complaint.severity == severity)
    if status:
        query = query.where(Complaint.status == status)
    if site_id:
        query = query.where(Complaint.site_id == site_id)
    
    query = query.order_by(Complaint.received_at.desc())
    
    result = await db.execute(query)
    complaints = result.scalars().all()
    
    return complaints


@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(
    complaint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single complaint"""
    
    result = await db.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    return complaint


@router.post("/{complaint_id}/acknowledge")
async def acknowledge_complaint(
    complaint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark complaint as acknowledged"""
    
    result = await db.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    complaint.status = ComplaintStatus.ACKNOWLEDGED
    complaint.acknowledged_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Complaint acknowledged"}


@router.post("/{complaint_id}/draft-response")
async def draft_response(
    complaint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate AI draft response"""
    
    result = await db.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    agent = ComplaintIntelligenceAgent()
    draft = await agent.draft_acknowledgment(db, complaint)
    
    return {"draft": draft}


@router.post("/{complaint_id}/resolve")
async def resolve_complaint(
    complaint_id: int,
    resolution_notes: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark complaint as resolved"""
    
    result = await db.execute(
        select(Complaint).where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()
    
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    
    complaint.status = ComplaintStatus.RESOLVED
    complaint.resolved_at = datetime.utcnow()
    complaint.resolution_notes = resolution_notes
    
    await db.commit()
    
    return {"message": "Complaint resolved"}


@router.get("/patterns/active", response_model=List[PatternResponse])
async def get_active_patterns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get active complaint patterns"""
    
    result = await db.execute(
        select(ComplaintPattern)
        .where(ComplaintPattern.is_active == True)
        .order_by(ComplaintPattern.last_occurrence.desc())
    )
    patterns = result.scalars().all()
    
    return patterns


@router.post("/detect-patterns")
async def detect_patterns(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger pattern detection"""
    
    agent = ComplaintIntelligenceAgent()
    patterns = await agent.detect_patterns(db, lookback_days=days)
    
    return {
        "patterns_found": len(patterns),
        "patterns": patterns
    }


@router.get("/summary/weekly")
async def get_weekly_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get weekly complaint summary"""
    
    agent = ComplaintIntelligenceAgent()
    summary = await agent.generate_weekly_summary(db)
    
    return summary
```

---

## Background Tasks

### 4. Complaint Tasks (`backend/tasks/complaint_tasks.py`)

```python
"""
Background tasks for complaint monitoring
"""
from celery import shared_task
from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent
from backend.database import AsyncSessionLocal
import asyncio


@shared_task
def detect_complaint_patterns_task():
    """
    Detect patterns across complaints
    Runs daily
    """
    
    async def detect():
        async with AsyncSessionLocal() as db:
            agent = ComplaintIntelligenceAgent()
            patterns = await agent.detect_patterns(db, lookback_days=7)
            return len(patterns)
    
    pattern_count = asyncio.run(detect())
    
    return {
        "patterns_detected": pattern_count,
        "lookback_days": 7
    }
```

---

## Installation & Setup

### 1. Install Dependencies

```bash
cd backend
pip install celery redis

# Add to requirements.txt
celery==5.3.6
redis==5.0.1
```

### 2. Create Migration

```bash
alembic revision -m "add complaint models"
```

Edit migration file:

```python
def upgrade():
    # Create complaints table
    # Create complaint_patterns table
    # (Cursor will generate full migration based on models)
    pass

def downgrade():
    op.drop_table('complaint_patterns')
    op.drop_table('complaints')
```

Run migration:
```bash
alembic upgrade head
```

### 3. Update Main App

```python
# backend/main.py
from backend.api import auth, meetings, complaints  # Add complaints

app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(complaints.router)  # Add this
```

---

## Frontend Components (Coming in separate file)

Phase 2 frontend will include:
- Complaints dashboard
- Pattern detection view
- Complaint detail with AI analysis
- Draft response interface
- Weekly summary widget

---

## Testing

After implementation:

```bash
# Create test complaint
curl -X POST http://localhost:8000/api/complaints \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "complaint_text": "The lunch was cold again today at 12:45pm",
    "site_id": 1,
    "source": "manual"
  }'

# Get weekly summary
curl http://localhost:8000/api/complaints/summary/weekly \
  -H "Authorization: Bearer YOUR_TOKEN"

# Detect patterns
curl -X POST http://localhost:8000/api/complaints/detect-patterns?days=7 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Success Metrics

**Before AI:**
- Response time: 2-3 days
- Missed complaints: ~15-20%
- Pattern detection: Manual, slow
- Time spent: 2-3 hours/week

**After AI:**
- Response time: <24 hours
- Missed complaints: 0%
- Pattern detection: Automatic, AI-powered
- Time spent: 30 minutes/week

**ROI:** Save ~2.5 hours/week = 10 hours/month = 120 hours/year

---

Upload this to Cursor and ask it to implement Phase 2 backend!
