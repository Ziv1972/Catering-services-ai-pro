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
    dishes_above: int = 0
    dishes_under: int = 0
    dishes_even: int = 0
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
            dishes_above=c.dishes_above or 0,
            dishes_under=c.dishes_under or 0,
            dishes_even=c.dishes_even or 0,
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
        "dishes_above": check.dishes_above or 0,
        "dishes_under": check.dishes_under or 0,
        "dishes_even": check.dishes_even or 0,
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
            func.sum(MenuCheck.dishes_above).label("total_above"),
            func.sum(MenuCheck.dishes_under).label("total_under"),
            func.sum(MenuCheck.dishes_even).label("total_even"),
        )
    )
    row = result.one()

    return {
        "total_checks": row.total_checks or 0,
        "total_critical": row.total_critical or 0,
        "total_warnings": row.total_warnings or 0,
        "total_passed": row.total_passed or 0,
        "total_findings": row.total_findings or 0,
        "total_above": row.total_above or 0,
        "total_under": row.total_under or 0,
        "total_even": row.total_even or 0,
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
    """Upload a menu file and run compliance analysis"""
    import os
    from backend.services.menu_analysis_service import run_compliance_check

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

    # Run compliance analysis
    try:
        analysis = await run_compliance_check(check.id, db)
        return {
            "id": check.id,
            "message": "Menu uploaded and compliance check completed.",
            "file_path": file_path,
            "analysis": analysis,
        }
    except Exception as e:
        return {
            "id": check.id,
            "message": f"Menu uploaded. Compliance check failed: {str(e)}",
            "file_path": file_path,
        }


@router.post("/checks/{check_id}/run")
async def rerun_check(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-run compliance analysis on an existing menu check"""
    from backend.services.menu_analysis_service import run_compliance_check

    result = await db.execute(
        select(MenuCheck).where(MenuCheck.id == check_id)
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Menu check not found")

    # Clear old results (days are handled by run_compliance_check)
    from sqlalchemy import delete
    await db.execute(
        delete(CheckResult).where(CheckResult.menu_check_id == check_id)
    )
    await db.commit()

    analysis = await run_compliance_check(check_id, db)
    return {
        "id": check_id,
        "message": "Compliance check re-run completed.",
        "analysis": analysis,
    }


@router.post("/checks/{check_id}/reupload")
async def reupload_menu_file(
    check_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-upload a menu file for an existing check, then re-parse and re-run."""
    import os
    from sqlalchemy import delete as sql_delete
    from backend.services.menu_analysis_service import run_compliance_check

    result = await db.execute(
        select(MenuCheck).where(MenuCheck.id == check_id)
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Menu check not found")

    # Save new file
    upload_dir = "uploads/menus"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = f"{upload_dir}/{check.site_id}_{check.year}_{check.month}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Update check with new file path
    check.file_path = file_path
    check.checked_at = date.today()

    # Clear old results AND old days (force fresh parse)
    await db.execute(
        sql_delete(CheckResult).where(CheckResult.menu_check_id == check_id)
    )
    await db.execute(
        sql_delete(MenuDay).where(MenuDay.menu_check_id == check_id)
    )
    await db.commit()

    # Run fresh compliance analysis (will parse the new file)
    try:
        analysis = await run_compliance_check(check_id, db)
        return {
            "id": check_id,
            "message": "File re-uploaded and compliance check completed.",
            "file_path": file_path,
            "analysis": analysis,
        }
    except Exception as e:
        return {
            "id": check_id,
            "message": f"File re-uploaded. Compliance check failed: {str(e)}",
            "file_path": file_path,
        }


@router.delete("/checks/{check_id}")
async def delete_check(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a menu compliance check and all its results and days."""
    from sqlalchemy import delete as sql_delete

    result = await db.execute(
        select(MenuCheck).where(MenuCheck.id == check_id)
    )
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="Menu check not found")

    # Delete related data
    await db.execute(
        sql_delete(CheckResult).where(CheckResult.menu_check_id == check_id)
    )
    await db.execute(
        sql_delete(MenuDay).where(MenuDay.menu_check_id == check_id)
    )
    await db.delete(check)
    await db.commit()

    return {"message": "Check deleted successfully"}


@router.get("/checks/{check_id}/menu-items")
async def get_menu_items(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all parsed menu items for a check, grouped by day."""
    result = await db.execute(
        select(MenuDay)
        .where(MenuDay.menu_check_id == check_id)
        .order_by(MenuDay.date)
    )
    days = result.scalars().all()

    if not days:
        raise HTTPException(status_code=404, detail="No parsed menu days found for this check")

    return [
        {
            "id": day.id,
            "date": day.date,
            "day_of_week": day.day_of_week,
            "week_number": day.week_number,
            "items": day.menu_items or {},
        }
        for day in days
    ]


@router.get("/checks/{check_id}/search-items")
async def search_menu_items(
    check_id: int,
    keyword: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Search for a keyword across all parsed menu items.

    Returns ALL potential matches (substring, prefix-stripped, fuzzy) so
    the user can review and approve/reject each match.
    """
    from backend.services.menu_analysis_service import (
        _normalize_hebrew, _strip_hebrew_prefixes
    )

    result = await db.execute(
        select(MenuDay)
        .where(MenuDay.menu_check_id == check_id)
        .order_by(MenuDay.date)
    )
    days = result.scalars().all()

    if not days:
        raise HTTPException(status_code=404, detail="No parsed menu days found")

    keyword_lower = keyword.lower().strip()
    variants = _normalize_hebrew(keyword_lower)

    matches = []
    for day in days:
        items = day.menu_items or {}
        for category, item_list in items.items():
            if not isinstance(item_list, list):
                continue
            for item in item_list:
                item_str = str(item).lower()
                match_type = _classify_match(keyword_lower, variants, item_str)
                if match_type:
                    matches.append({
                        "date": day.date,
                        "day_of_week": day.day_of_week,
                        "category": category,
                        "item": item,
                        "match_type": match_type,
                    })

    # Sort: exact first, then contains, then prefix, then fuzzy
    type_order = {"exact": 0, "contains": 1, "prefix": 2, "fuzzy": 3}
    matches.sort(key=lambda m: (type_order.get(m["match_type"], 9), m["date"]))

    # Get unique items for summary
    unique_items = {}
    for m in matches:
        key = m["item"]
        if key not in unique_items:
            unique_items[key] = {
                "item": m["item"],
                "match_type": m["match_type"],
                "days": [],
            }
        unique_items[key]["days"].append(m["date"])

    return {
        "keyword": keyword,
        "variants_searched": variants,
        "total_matches": len(matches),
        "unique_items": list(unique_items.values()),
        "matches_by_day": matches,
    }


def _classify_match(keyword: str, variants: list[str], item_text: str) -> str | None:
    """Classify how well a keyword matches an item.

    Returns match type or None if no match:
    - "exact": keyword equals item or item word
    - "contains": keyword is a substring of item
    - "prefix": keyword matches after stripping Hebrew prefix letters
    - "fuzzy": keyword is similar (≥60% character overlap)
    """
    from backend.services.menu_analysis_service import _strip_hebrew_prefixes

    # Exact match (whole item or any word)
    words = item_text.split()
    for var in variants:
        if var == item_text:
            return "exact"
        if var in words:
            return "exact"

    # Contains (substring)
    for var in variants:
        if var in item_text:
            return "contains"

    # Prefix-stripped match
    for word in words:
        stems = _strip_hebrew_prefixes(word)
        for stem in stems:
            for var in variants:
                if var == stem:
                    return "prefix"
                if var in stem or stem in var:
                    if len(var) >= 3 and len(stem) >= 3:
                        return "prefix"

    # Fuzzy match — character overlap for Hebrew
    for word in words:
        for var in variants:
            if len(var) >= 3 and len(word) >= 3:
                overlap = len(set(var) & set(word))
                max_len = max(len(set(var)), len(set(word)))
                if max_len > 0 and overlap / max_len >= 0.6:
                    return "fuzzy"

    return None


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
        if key == "parameters" and isinstance(value, dict):
            # Merge new parameters into existing ones (don't replace)
            existing = rule.parameters or {}
            setattr(rule, key, {**existing, **value})
        else:
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
