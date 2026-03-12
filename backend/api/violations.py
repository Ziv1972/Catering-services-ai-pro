"""
Violations API endpoints — Exceptions & Violations (חריגות והפרות)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta, date
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.violation import (
    Violation, ViolationPattern, FineRule, ViolationSource,
    ViolationSeverity, ViolationStatus, ViolationCategory
)
from backend.api.auth import get_current_user
from backend.agents.violation_intelligence.agent import ViolationIntelligenceAgent

router = APIRouter()


class ViolationCreate(BaseModel):
    violation_text: str
    site_id: Optional[int] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    is_anonymous: bool = False
    source: ViolationSource = ViolationSource.MANUAL
    category: Optional[ViolationCategory] = None
    severity: Optional[ViolationSeverity] = None
    fine_rule_id: Optional[int] = None
    fine_amount: Optional[float] = None
    restaurant_type: Optional[str] = None


class ViolationResponse(BaseModel):
    id: int
    violation_text: str
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
    restaurant_type: Optional[str] = None
    # AI fine-match fields
    fine_match_confidence: Optional[float] = None
    fine_match_reasoning: Optional[str] = None

    class Config:
        from_attributes = True


class PatternResponse(BaseModel):
    id: int
    pattern_id: str
    pattern_type: str
    description: str
    severity: str
    violation_count: int
    recommendation: Optional[str]
    is_active: bool
    first_occurrence: datetime
    last_occurrence: datetime

    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    resolution_notes: str


def _violation_to_response(
    violation: Violation,
    analysis: Optional[dict] = None,
    fine_rule_name: Optional[str] = None,
) -> ViolationResponse:
    """Convert a Violation ORM object + optional analysis dict to a response."""
    return ViolationResponse(
        id=violation.id,
        violation_text=violation.violation_text,
        site_id=violation.site_id,
        source=violation.source.value if violation.source else "manual",
        category=violation.category.value if violation.category else None,
        severity=violation.severity.value if violation.severity else None,
        sentiment_score=violation.sentiment_score,
        ai_summary=violation.ai_summary,
        ai_root_cause=violation.ai_root_cause,
        ai_suggested_action=violation.ai_suggested_action,
        status=violation.status.value if violation.status else "open",
        received_at=violation.received_at,
        acknowledged_at=violation.acknowledged_at,
        resolved_at=violation.resolved_at,
        pattern_group_id=violation.pattern_group_id,
        employee_name=violation.employee_name,
        is_anonymous=violation.is_anonymous,
        requires_vendor_action=violation.requires_vendor_action,
        fine_rule_id=violation.fine_rule_id,
        fine_amount=violation.fine_amount,
        fine_rule_name=fine_rule_name,
        restaurant_type=violation.restaurant_type.value if violation.restaurant_type else None,
        fine_match_confidence=analysis.get("fine_match_confidence") if analysis else None,
        fine_match_reasoning=analysis.get("fine_match_reasoning") if analysis else None,
    )


@router.post("/", response_model=ViolationResponse)
async def create_violation(
    violation_data: ViolationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new violation and analyze with AI"""

    data = violation_data.model_dump()

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

    violation = Violation(**data, received_at=datetime.utcnow())

    db.add(violation)
    await db.flush()

    analysis = None
    try:
        agent = ViolationIntelligenceAgent()
        analysis = await agent.analyze_violation(db, violation)

        # Auto-link fine rule if AI found a strong match and user didn't manually set one
        suggested_id = analysis.get("suggested_fine_rule_id") if analysis else None
        confidence = analysis.get("fine_match_confidence", 0.0) if analysis else 0.0

        if suggested_id and confidence >= 0.7 and not violation.fine_rule_id:
            rule_result = await db.execute(
                select(FineRule).where(
                    FineRule.id == suggested_id,
                    FineRule.is_active == True,
                )
            )
            matched_rule = rule_result.scalar_one_or_none()
            if matched_rule:
                violation.fine_rule_id = matched_rule.id
                violation.fine_amount = matched_rule.amount
    except Exception:
        pass

    await db.commit()
    await db.refresh(violation)

    # Eager-load fine_rule for the response
    fine_rule_name = None
    if violation.fine_rule_id:
        rule_res = await db.execute(
            select(FineRule).where(FineRule.id == violation.fine_rule_id)
        )
        matched = rule_res.scalar_one_or_none()
        if matched:
            fine_rule_name = matched.name

    response = _violation_to_response(violation, analysis, fine_rule_name)
    return response


@router.get("/", response_model=List[ViolationResponse])
async def list_violations(
    days: int = Query(7, ge=1, le=90),
    severity: Optional[ViolationSeverity] = None,
    status: Optional[ViolationStatus] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List violations with filters"""

    cutoff = datetime.utcnow() - timedelta(days=days)

    query = (
        select(Violation)
        .options(selectinload(Violation.fine_rule))
        .where(Violation.received_at >= cutoff)
    )

    if severity:
        query = query.where(Violation.severity == severity)
    if status:
        query = query.where(Violation.status == status)
    if site_id:
        query = query.where(Violation.site_id == site_id)

    query = query.order_by(Violation.received_at.desc())

    result = await db.execute(query)
    violations = result.scalars().all()

    return [
        {
            **ViolationResponse.model_validate(v).model_dump(),
            "fine_rule_name": v.fine_rule.name if v.fine_rule else None,
        }
        for v in violations
    ]


@router.get("/patterns/active", response_model=List[PatternResponse])
async def get_active_patterns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get active violation patterns"""

    result = await db.execute(
        select(ViolationPattern)
        .where(ViolationPattern.is_active == True)
        .order_by(ViolationPattern.last_occurrence.desc())
    )
    patterns = result.scalars().all()

    return patterns


@router.get("/summary/weekly")
async def get_weekly_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get weekly violation summary"""

    agent = ViolationIntelligenceAgent()
    summary = await agent.generate_weekly_summary(db)

    return summary


@router.post("/detect-patterns")
async def detect_patterns(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger pattern detection"""

    agent = ViolationIntelligenceAgent()
    patterns = await agent.detect_patterns(db, lookback_days=days)

    return {
        "patterns_found": len(patterns),
        "patterns": patterns
    }


@router.get("/analytics")
async def get_violation_analytics(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    site_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Violation and fine analytics with aggregated metrics for dashboards."""
    today = date.today()
    end_dt = date.fromisoformat(to_date) if to_date else today
    start_dt = date.fromisoformat(from_date) if from_date else end_dt.replace(day=1) - timedelta(days=89)

    query = (
        select(Violation)
        .options(selectinload(Violation.fine_rule), selectinload(Violation.site))
        .where(Violation.received_at >= datetime.combine(start_dt, datetime.min.time()))
        .where(Violation.received_at <= datetime.combine(end_dt, datetime.max.time()))
    )
    if site_id:
        query = query.where(Violation.site_id == site_id)

    result = await db.execute(query.order_by(Violation.received_at.desc()))
    violations = result.scalars().all()

    total_violations = len(violations)
    fined = [v for v in violations if v.fine_amount and v.fine_amount > 0]
    total_fines = len(fined)
    total_fine_amount = sum(v.fine_amount for v in fined)

    resolved = [v for v in violations if v.resolved_at and v.received_at]
    avg_resolution_hours = 0.0
    if resolved:
        avg_resolution_hours = sum(
            (v.resolved_at - v.received_at).total_seconds() / 3600 for v in resolved
        ) / len(resolved)

    by_site: dict = {}
    for v in violations:
        site_key = v.site_id or 0
        site_name = v.site.name if v.site else "Unknown"
        if site_key not in by_site:
            by_site[site_key] = {
                "site_id": site_key, "site_name": site_name,
                "violations": 0, "fines": 0, "fine_amount": 0.0,
            }
        by_site[site_key]["violations"] += 1
        if v.fine_amount and v.fine_amount > 0:
            by_site[site_key]["fines"] += 1
            by_site[site_key]["fine_amount"] += v.fine_amount

    by_category: dict = {}
    for v in violations:
        cat = v.category.value if v.category else "uncategorized"
        if cat not in by_category:
            by_category[cat] = {"category": cat, "count": 0, "fines": 0, "fine_amount": 0.0}
        by_category[cat]["count"] += 1
        if v.fine_amount and v.fine_amount > 0:
            by_category[cat]["fines"] += 1
            by_category[cat]["fine_amount"] += v.fine_amount

    by_severity: dict = {}
    for v in violations:
        sev = v.severity.value if v.severity else "unclassified"
        if sev not in by_severity:
            by_severity[sev] = {"severity": sev, "count": 0, "fines": 0, "fine_amount": 0.0}
        by_severity[sev]["count"] += 1
        if v.fine_amount and v.fine_amount > 0:
            by_severity[sev]["fines"] += 1
            by_severity[sev]["fine_amount"] += v.fine_amount

    by_month: dict = {}
    for v in violations:
        month_key = v.received_at.strftime("%Y-%m")
        if month_key not in by_month:
            by_month[month_key] = {"month": month_key, "violations": 0, "fines": 0, "fine_amount": 0.0}
        by_month[month_key]["violations"] += 1
        if v.fine_amount and v.fine_amount > 0:
            by_month[month_key]["fines"] += 1
            by_month[month_key]["fine_amount"] += v.fine_amount

    top_rules: dict = {}
    for v in violations:
        if v.fine_rule_id and v.fine_rule:
            rule_name = v.fine_rule.name
            if rule_name not in top_rules:
                top_rules[rule_name] = {"rule_name": rule_name, "times_applied": 0, "total_amount": 0.0}
            top_rules[rule_name]["times_applied"] += 1
            top_rules[rule_name]["total_amount"] += v.fine_amount or 0

    violations_list = [
        {
            "id": v.id,
            "date": v.received_at.isoformat(),
            "category": v.category.value if v.category else None,
            "severity": v.severity.value if v.severity else None,
            "fine_rule_name": v.fine_rule.name if v.fine_rule else None,
            "fine_amount": v.fine_amount or 0,
            "status": v.status.value if v.status else "new",
            "site_name": v.site.name if v.site else "Unknown",
            "source": v.source.value if v.source else "manual",
            "restaurant_type": v.restaurant_type.value if v.restaurant_type else None,
            "summary": v.ai_summary or v.violation_text[:100],
        }
        for v in violations
    ]

    return {
        "period": {"from": start_dt.isoformat(), "to": end_dt.isoformat()},
        "summary": {
            "total_violations": total_violations,
            "total_fines": total_fines,
            "total_fine_amount": round(total_fine_amount, 2),
            "avg_resolution_time_hours": round(avg_resolution_hours, 1),
        },
        "by_site": list(by_site.values()),
        "by_category": sorted(by_category.values(), key=lambda x: x["count"], reverse=True),
        "by_severity": list(by_severity.values()),
        "by_month": sorted(by_month.values(), key=lambda x: x["month"]),
        "top_fine_rules": sorted(top_rules.values(), key=lambda x: x["total_amount"], reverse=True),
        "violations_list": violations_list,
    }


@router.post("/analytics/report")
async def generate_analytics_report(
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    site_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate HTML report from violation analytics data."""
    from backend.services.report_service import generate_violation_report_html

    analytics = await get_violation_analytics(from_date, to_date, site_id, db, current_user)
    html = generate_violation_report_html(analytics)

    period = analytics["period"]
    subject = f"Violations & Fine Report: {period['from']} to {period['to']}"

    return {"html": html, "subject": subject, "analytics": analytics}


@router.get("/{violation_id}", response_model=ViolationResponse)
async def get_violation(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single violation"""

    result = await db.execute(
        select(Violation)
        .options(selectinload(Violation.fine_rule))
        .where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()

    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    resp = ViolationResponse.model_validate(violation).model_dump()
    resp["fine_rule_name"] = violation.fine_rule.name if violation.fine_rule else None
    return resp


@router.post("/{violation_id}/acknowledge")
async def acknowledge_violation(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark violation as acknowledged"""

    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()

    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    violation.status = ViolationStatus.ACKNOWLEDGED
    violation.acknowledged_at = datetime.utcnow()

    await db.commit()

    return {"message": "Violation acknowledged", "id": violation_id}


@router.post("/{violation_id}/draft-response")
async def draft_response(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate AI draft response"""

    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()

    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    agent = ViolationIntelligenceAgent()
    draft = await agent.draft_acknowledgment(db, violation)

    return {"draft": draft, "violation_id": violation_id}


@router.post("/{violation_id}/resolve")
async def resolve_violation(
    violation_id: int,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark violation as resolved"""

    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()

    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    violation.status = ViolationStatus.RESOLVED
    violation.resolved_at = datetime.utcnow()
    violation.resolution_notes = body.resolution_notes

    await db.commit()

    return {"message": "Violation resolved", "id": violation_id}
