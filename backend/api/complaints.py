"""
Complaints API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.complaint import (
    Complaint, ComplaintPattern, FineRule, ComplaintSource,
    ComplaintSeverity, ComplaintStatus, ComplaintCategory
)
from backend.api.auth import get_current_user
from backend.agents.complaint_intelligence.agent import ComplaintIntelligenceAgent

router = APIRouter()


class ComplaintCreate(BaseModel):
    complaint_text: str
    site_id: Optional[int] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    is_anonymous: bool = False
    source: ComplaintSource = ComplaintSource.MANUAL
    category: Optional[ComplaintCategory] = None
    severity: Optional[ComplaintSeverity] = None
    fine_rule_id: Optional[int] = None
    fine_amount: Optional[float] = None


class ComplaintResponse(BaseModel):
    id: int
    complaint_text: str
    site_id: Optional[int]
    source: str
    category: Optional[str]
    severity: Optional[str]
    sentiment_score: Optional[float]
    ai_summary: Optional[str]
    ai_root_cause: Optional[str]
    ai_suggested_action: Optional[str]
    status: str
    received_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    pattern_group_id: Optional[str]
    employee_name: Optional[str]
    is_anonymous: bool
    requires_vendor_action: bool
    fine_rule_id: Optional[int]
    fine_amount: Optional[float]
    fine_rule_name: Optional[str] = None

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
    first_occurrence: datetime
    last_occurrence: datetime

    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    resolution_notes: str


@router.post("/", response_model=ComplaintResponse)
async def create_complaint(
    complaint_data: ComplaintCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new complaint and analyze with AI"""

    data = complaint_data.model_dump()

    # If fine_rule_id given but no fine_amount, auto-fill from the rule
    if data.get("fine_rule_id") and not data.get("fine_amount"):
        rule_result = await db.execute(
            select(FineRule).where(FineRule.id == data["fine_rule_id"])
        )
        rule = rule_result.scalar_one_or_none()
        if rule:
            data["fine_amount"] = rule.amount
            if not data.get("category"):
                data["category"] = rule.category

    complaint = Complaint(**data, received_at=datetime.utcnow())

    db.add(complaint)
    await db.flush()

    try:
        agent = ComplaintIntelligenceAgent()
        await agent.analyze_complaint(db, complaint)
    except Exception:
        pass

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

    query = (
        select(Complaint)
        .options(selectinload(Complaint.fine_rule))
        .where(Complaint.received_at >= cutoff)
    )

    if severity:
        query = query.where(Complaint.severity == severity)
    if status:
        query = query.where(Complaint.status == status)
    if site_id:
        query = query.where(Complaint.site_id == site_id)

    query = query.order_by(Complaint.received_at.desc())

    result = await db.execute(query)
    complaints = result.scalars().all()

    return [
        {
            **ComplaintResponse.model_validate(c).model_dump(),
            "fine_rule_name": c.fine_rule.name if c.fine_rule else None,
        }
        for c in complaints
    ]


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


@router.get("/summary/weekly")
async def get_weekly_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get weekly complaint summary"""

    agent = ComplaintIntelligenceAgent()
    summary = await agent.generate_weekly_summary(db)

    return summary


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


@router.get("/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint(
    complaint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single complaint"""

    result = await db.execute(
        select(Complaint)
        .options(selectinload(Complaint.fine_rule))
        .where(Complaint.id == complaint_id)
    )
    complaint = result.scalar_one_or_none()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    resp = ComplaintResponse.model_validate(complaint).model_dump()
    resp["fine_rule_name"] = complaint.fine_rule.name if complaint.fine_rule else None
    return resp


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

    return {"message": "Complaint acknowledged", "id": complaint_id}


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

    return {"draft": draft, "complaint_id": complaint_id}


@router.post("/{complaint_id}/resolve")
async def resolve_complaint(
    complaint_id: int,
    body: ResolveRequest,
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
    complaint.resolution_notes = body.resolution_notes

    await db.commit()

    return {"message": "Complaint resolved", "id": complaint_id}
