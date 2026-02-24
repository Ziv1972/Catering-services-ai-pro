"""
Historical data & analytics API endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import date, timedelta

from backend.database import get_db
from backend.models.user import User
from backend.models.historical_data import HistoricalMealData
from backend.models.site import Site
from backend.models.menu_compliance import MenuCheck
from backend.models.proforma import Proforma
from backend.models.complaint import Complaint, ComplaintCategory
from backend.models.operations import Anomaly
from backend.api.auth import get_current_user

router = APIRouter()


@router.get("/meals")
async def get_meal_data(
    site_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get historical meal data"""
    query = (
        select(HistoricalMealData)
        .options(selectinload(HistoricalMealData.site))
        .order_by(HistoricalMealData.date.asc())
    )

    if site_id:
        query = query.where(HistoricalMealData.site_id == site_id)
    if start_date:
        query = query.where(HistoricalMealData.date >= start_date)
    if end_date:
        query = query.where(HistoricalMealData.date <= end_date)

    result = await db.execute(query)
    meals = result.scalars().all()

    return [
        {
            "id": m.id,
            "site_id": m.site_id,
            "site_name": m.site.name if m.site else None,
            "date": m.date.isoformat(),
            "meal_count": m.meal_count,
            "cost": m.cost,
            "notes": m.notes,
        }
        for m in meals
    ]


@router.get("/analytics")
async def get_analytics(
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive analytics from real DB data"""

    # 1. Meal trends by month per site
    meal_query = (
        select(HistoricalMealData)
        .options(selectinload(HistoricalMealData.site))
        .order_by(HistoricalMealData.date.asc())
    )
    if site_id:
        meal_query = meal_query.where(HistoricalMealData.site_id == site_id)

    result = await db.execute(meal_query)
    meals = result.scalars().all()

    # Group meals by month and site
    meal_by_month: dict = {}
    for m in meals:
        month_key = m.date.strftime("%b %Y")
        site_name = m.site.name if m.site else "Unknown"
        if month_key not in meal_by_month:
            meal_by_month[month_key] = {}
        meal_by_month[month_key][site_name] = (
            meal_by_month[month_key].get(site_name, 0) + m.meal_count
        )

    meal_trends = []
    for month, sites in meal_by_month.items():
        entry: dict = {"month": month}
        for site_name, count in sites.items():
            safe_key = site_name.lower().replace(" ", "_")
            entry[safe_key] = count
        meal_trends.append(entry)

    # 2. Cost trends by month
    cost_by_month: dict = {}
    meal_count_by_month: dict = {}
    for m in meals:
        month_key = m.date.strftime("%b %Y")
        if m.cost:
            cost_by_month[month_key] = cost_by_month.get(month_key, 0) + m.cost
            meal_count_by_month[month_key] = (
                meal_count_by_month.get(month_key, 0) + m.meal_count
            )

    cost_trends = []
    for month in cost_by_month:
        total_cost = cost_by_month[month]
        total_meals = meal_count_by_month.get(month, 1)
        cost_trends.append({
            "month": month,
            "avg_cost": round(total_cost / total_meals, 1) if total_meals else 0,
            "total_cost": round(total_cost, 0),
        })

    # 3. Complaint categories from DB
    complaint_result = await db.execute(
        select(Complaint.category, func.count(Complaint.id))
        .where(Complaint.category.isnot(None))
        .group_by(Complaint.category)
    )
    complaint_categories = [
        {"name": row[0].replace("_", " ").title(), "value": row[1]}
        for row in complaint_result.all()
    ]

    # 4. Menu findings by month from DB
    checks_result = await db.execute(
        select(MenuCheck).order_by(MenuCheck.checked_at.asc())
    )
    checks = checks_result.scalars().all()

    menu_by_month: dict = {}
    for c in checks:
        month_key = c.month if c.month else c.checked_at.strftime("%b")
        if month_key not in menu_by_month:
            menu_by_month[month_key] = {"critical": 0, "warnings": 0, "passed": 0}
        menu_by_month[month_key]["critical"] += c.critical_findings or 0
        menu_by_month[month_key]["warnings"] += c.warnings or 0
        menu_by_month[month_key]["passed"] += c.passed_rules or 0

    menu_findings = [
        {"month": month, **data}
        for month, data in menu_by_month.items()
    ]

    # 5. Vendor spending from proformas
    proforma_result = await db.execute(
        select(Proforma)
        .options(selectinload(Proforma.supplier))
        .order_by(Proforma.invoice_date.asc())
    )
    proformas = proforma_result.scalars().all()

    vendor_spending: dict = {}
    vendor_monthly: dict = {}
    for p in proformas:
        name = p.supplier.name if p.supplier else "Unknown"
        vendor_spending[name] = vendor_spending.get(name, 0) + p.total_amount

        month_key = p.invoice_date.strftime("%b %Y")
        if month_key not in vendor_monthly:
            vendor_monthly[month_key] = {}
        vendor_monthly[month_key][name] = (
            vendor_monthly[month_key].get(name, 0) + p.total_amount
        )

    vendor_totals = [
        {"name": name, "value": round(total, 0)}
        for name, total in sorted(vendor_spending.items(), key=lambda x: x[1], reverse=True)
    ]

    # Monthly vendor series with moving average
    sorted_vendor_months = sorted(vendor_monthly.keys())
    vendor_series = []
    running_totals: list[float] = []
    for month in sorted_vendor_months:
        month_total = sum(vendor_monthly[month].values())
        running_totals.append(month_total)
        window = running_totals[-3:] if len(running_totals) >= 3 else running_totals
        ma = sum(window) / len(window)

        entry: dict = {"month": month, "total": round(month_total, 0), "ma_3m": round(ma, 0)}
        for name, amount in vendor_monthly[month].items():
            safe_key = name.lower().replace(" ", "_").replace(".", "")
            entry[safe_key] = round(amount, 0)
        vendor_series.append(entry)

    # 6. Record counts
    counts = {}
    for model, label in [
        (HistoricalMealData, "meals"),
        (MenuCheck, "menu_checks"),
        (Proforma, "proformas"),
        (Anomaly, "anomalies"),
        (Complaint, "complaints"),
    ]:
        count_result = await db.execute(select(func.count(model.id)))
        counts[label] = count_result.scalar() or 0

    check_results_count = await db.execute(
        select(func.count()).select_from(
            select(func.count()).correlate(None).select_from(MenuCheck).subquery()
        )
    )

    return {
        "mealTrends": meal_trends,
        "costTrends": cost_trends,
        "complaintCategories": complaint_categories,
        "menuFindings": menu_findings,
        "vendorTotals": vendor_totals,
        "vendorSeries": vendor_series,
        "counts": counts,
    }
