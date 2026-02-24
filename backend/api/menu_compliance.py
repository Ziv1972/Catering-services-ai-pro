"""
Menu Compliance API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.menu_compliance import MenuCheck, MenuDay, CheckResult, ComplianceRule
from backend.api.auth import get_current_user

router = APIRouter()


class ComplianceRuleResponse(BaseModel):
    id: int
    name: str
    rule_type: str
    description: Optional[str]
    category: Optional[str]
    parameters: Optional[dict]
    priority: int
    is_active: bool

    class Config:
        from_attributes = True


class ComplianceRuleCreate(BaseModel):
    name: str
    rule_type: str = "mandatory"
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[dict] = None
    priority: int = 1


class ComplianceRuleUpdate(BaseModel):
    name: Optional[str] = None
    rule_type: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[dict] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class CheckResultResponse(BaseModel):
    id: int
    rule_name: str
    rule_category: Optional[str]
    passed: bool
    severity: str
    finding_text: Optional[str]
    evidence: Optional[dict]
    reviewed: bool
    review_status: Optional[str]
    review_notes: Optional[str]

    class Config:
        from_attributes = True


class MenuCheckResponse(BaseModel):
    id: int
    site_id: int
    month: str
    year: int
    total_findings: int
    critical_findings: int
    warnings: int
    passed_rules: int
    checked_at: date
    file_path: Optional[str]

    class Config:
        from_attributes = True


class MenuCheckDetailResponse(MenuCheckResponse):
    site_name: Optional[str] = None


@router.get("/checks", response_model=List[MenuCheckDetailResponse])
async def list_checks(
    site_id: Optional[int] = None,
    year: Optional[int] = None,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List menu compliance checks"""
    query = select(MenuCheck).options(selectinload(MenuCheck.site))

    if site_id:
        query = query.where(MenuCheck.site_id == site_id)
    if year:
        query = query.where(MenuCheck.year == year)

    query = query.order_by(MenuCheck.checked_at.desc())

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    checks = result.scalars().all()

    return [
        MenuCheckDetailResponse(
            id=c.id,
            site_id=c.site_id,
            month=c.month,
            year=c.year,
            total_findings=c.total_findings,
            critical_findings=c.critical_findings,
            warnings=c.warnings,
            passed_rules=c.passed_rules,
            checked_at=c.checked_at,
            file_path=c.file_path,
            site_name=c.site.name if c.site else None,
        )
        for c in checks
    ]


@router.get("/checks/{check_id}")
async def get_check(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single menu check with site info"""
    result = await db.execute(
        select(MenuCheck)
        .options(selectinload(MenuCheck.site))
        .where(MenuCheck.id == check_id)
    )
    check = result.scalar_one_or_none()

    if not check:
        raise HTTPException(status_code=404, detail="Menu check not found")

    return {
        "id": check.id,
        "site_id": check.site_id,
        "site_name": check.site.name if check.site else None,
        "month": check.month,
        "year": check.year,
        "total_findings": check.total_findings,
        "critical_findings": check.critical_findings,
        "warnings": check.warnings,
        "passed_rules": check.passed_rules,
        "checked_at": check.checked_at.isoformat(),
        "file_path": check.file_path,
    }


@router.get("/checks/{check_id}/results", response_model=List[CheckResultResponse])
async def get_check_results(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get results for a menu check"""
    result = await db.execute(
        select(MenuCheck).where(MenuCheck.id == check_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Menu check not found")

    results = await db.execute(
        select(CheckResult)
        .where(CheckResult.menu_check_id == check_id)
        .order_by(CheckResult.passed.asc(), CheckResult.severity.asc())
    )

    return results.scalars().all()


@router.get("/stats")
async def get_compliance_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall compliance statistics"""
    result = await db.execute(
        select(
            func.count(MenuCheck.id).label("total_checks"),
            func.sum(MenuCheck.critical_findings).label("total_critical"),
            func.sum(MenuCheck.warnings).label("total_warnings"),
            func.sum(MenuCheck.passed_rules).label("total_passed"),
            func.sum(MenuCheck.total_findings).label("total_findings"),
        )
    )
    row = result.one()

    return {
        "total_checks": row.total_checks or 0,
        "total_critical": row.total_critical or 0,
        "total_warnings": row.total_warnings or 0,
        "total_passed": row.total_passed or 0,
        "total_findings": row.total_findings or 0,
    }


@router.post("/upload-menu")
async def upload_menu(
    site_id: int = Form(...),
    month: str = Form(...),
    year: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a menu file for compliance checking"""
    import os

    upload_dir = "uploads/menus"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = f"{upload_dir}/{site_id}_{year}_{month}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    check = MenuCheck(
        site_id=site_id,
        month=month,
        year=year,
        file_path=file_path,
        checked_at=date.today(),
        total_findings=0,
        critical_findings=0,
        warnings=0,
        passed_rules=0,
    )
    db.add(check)
    await db.commit()
    await db.refresh(check)

    return {
        "id": check.id,
        "message": "Menu uploaded successfully. Run compliance check to analyze.",
        "file_path": file_path,
    }


# --- Compliance Rules CRUD ---


@router.get("/rules", response_model=List[ComplianceRuleResponse])
async def list_rules(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all compliance rules"""
    query = select(ComplianceRule).order_by(ComplianceRule.priority, ComplianceRule.name)
    if active_only:
        query = query.where(ComplianceRule.is_active == True)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/rules", response_model=ComplianceRuleResponse)
async def create_rule(
    data: ComplianceRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new compliance rule"""
    rule = ComplianceRule(**data.model_dump(exclude_none=True), is_active=True)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=ComplianceRuleResponse)
async def update_rule(
    rule_id: int,
    data: ComplianceRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a compliance rule"""
    result = await db.execute(
        select(ComplianceRule).where(ComplianceRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate a compliance rule"""
    result = await db.execute(
        select(ComplianceRule).where(ComplianceRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = False
    await db.commit()
    return {"message": "Rule deactivated"}
