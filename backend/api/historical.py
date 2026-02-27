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
from backend.models.proforma import Proforma, ProformaItem
from backend.models.complaint import Complaint, ComplaintCategory
from backend.models.operations import Anomaly
from backend.api.auth import get_current_user
from backend.api.category_analysis import _load_category_mappings, _match_product_to_category
from backend.utils.db_compat import year_equals, month_equals, extract_month, extract_year

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

    # 1. Meal trends by month per site — derived from proforma items
    mappings = await _load_category_mappings(db)

    # Query proforma items with site info
    items_query = (
        select(
            ProformaItem.product_name,
            ProformaItem.quantity,
            ProformaItem.total_price,
            extract_month(Proforma.invoice_date).label("month_num"),
            extract_year(Proforma.invoice_date).label("year_str"),
            Proforma.site_id,
            Site.name.label("site_name"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .join(Site, Proforma.site_id == Site.id)
        .order_by(Proforma.invoice_date.asc())
    )
    if site_id:
        items_query = items_query.where(Proforma.site_id == site_id)

    items_result = await db.execute(items_query)
    all_items = list(items_result)

    MONTH_ABBR = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }

    # Group meal items (total_meals category) by month+site
    meal_by_month: dict = {}
    meal_count_by_month: dict = {}
    actual_cost_by_month: dict = {}

    for item in all_items:
        month_num = int(item.month_num)
        year_str = item.year_str
        month_key = f"{MONTH_ABBR[month_num]} {year_str}"
        site_name = item.site_name or "Unknown"

        # Accumulate total proforma cost by month
        actual_cost_by_month[month_key] = (
            actual_cost_by_month.get(month_key, 0) + (item.total_price or 0)
        )

        # Categorize item
        group_name, _, _ = _match_product_to_category(item.product_name, mappings)
        if group_name == "total_meals":
            qty = item.quantity or 0
            if month_key not in meal_by_month:
                meal_by_month[month_key] = {}
            meal_by_month[month_key][site_name] = (
                meal_by_month[month_key].get(site_name, 0) + qty
            )
            meal_count_by_month[month_key] = (
                meal_count_by_month.get(month_key, 0) + qty
            )

    meal_trends = []
    for month, sites in meal_by_month.items():
        entry: dict = {"month": month}
        for sname, count in sites.items():
            safe_key = sname.lower().replace(" ", "_")
            entry[safe_key] = round(count)
        meal_trends.append(entry)

    # 2. Cost trends by month (from proformas with meal-count denominator)
    cost_trends = []
    for month_key in sorted(actual_cost_by_month.keys()):
        actual_cost = actual_cost_by_month[month_key]
        total_meals = meal_count_by_month.get(month_key, 0)
        cost_trends.append({
            "month": month_key,
            "avg_cost": round(actual_cost / total_meals, 1) if total_meals > 0 else 0,
            "total_cost": round(actual_cost, 0),
            "total_meals": round(total_meals),
            "source": "proforma",
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


@router.get("/drill-down/cost")
async def cost_drill_down(
    month: Optional[int] = None,
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down: cost breakdown by product for a given month"""
    target_year = year or date.today().year

    query = (
        select(
            ProformaItem.product_name,
            func.sum(ProformaItem.total_price).label("total"),
            func.sum(ProformaItem.quantity).label("qty"),
            func.count(ProformaItem.id).label("count"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(year_equals(Proforma.invoice_date, target_year))
        .group_by(ProformaItem.product_name)
        .order_by(func.sum(ProformaItem.total_price).desc())
    )
    if month:
        query = query.where(month_equals(Proforma.invoice_date, month))
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    result = await db.execute(query)
    items = [
        {
            "product_name": row.product_name,
            "total_spent": row.total or 0,
            "total_quantity": row.qty or 0,
            "order_count": row.count,
        }
        for row in result
    ]

    return {"year": target_year, "month": month, "items": items}


@router.get("/drill-down/meals")
async def meals_drill_down(
    month: Optional[int] = None,
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down Level 1: meal counts by site for a given month (from proformas)."""
    target_year = year or date.today().year
    mappings = await _load_category_mappings(db)

    query = (
        select(
            ProformaItem.product_name,
            ProformaItem.quantity,
            ProformaItem.total_price,
            Proforma.site_id,
            Site.name.label("site_name"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .join(Site, Proforma.site_id == Site.id)
        .where(year_equals(Proforma.invoice_date, target_year))
    )
    if month:
        query = query.where(month_equals(Proforma.invoice_date, month))
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    result = await db.execute(query)

    # Group by site, only total_meals category
    by_site: dict = {}
    total_meals = 0
    total_cost = 0.0
    for item in result:
        group_name, display_he, display_en = _match_product_to_category(item.product_name, mappings)
        if group_name == "total_meals":
            qty = item.quantity or 0
            sname = item.site_name or "Unknown"
            if sname not in by_site:
                by_site[sname] = {"site_id": item.site_id, "site_name": sname, "meal_count": 0, "cost": 0}
            by_site[sname]["meal_count"] += qty
            by_site[sname]["cost"] += item.total_price or 0
            total_meals += qty
            total_cost += item.total_price or 0

    return {
        "items": [
            {**v, "meal_count": round(v["meal_count"]), "cost": round(v["cost"])}
            for v in sorted(by_site.values(), key=lambda x: x["meal_count"], reverse=True)
        ],
        "total_meals": round(total_meals),
        "total_cost": round(total_cost),
        "year": target_year,
        "month": month,
    }


@router.get("/drill-down/meals/categories")
async def meals_categories_drill_down(
    month: Optional[int] = None,
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down Level 2: meal counts by category for a given month/site (from proformas)."""
    target_year = year or date.today().year
    mappings = await _load_category_mappings(db)

    query = (
        select(
            ProformaItem.product_name,
            ProformaItem.quantity,
            ProformaItem.total_price,
            Proforma.site_id,
            Site.name.label("site_name"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .join(Site, Proforma.site_id == Site.id)
        .where(year_equals(Proforma.invoice_date, target_year))
    )
    if month:
        query = query.where(month_equals(Proforma.invoice_date, month))
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    result = await db.execute(query)

    # Group ALL items by category
    by_category: dict = {}
    total_qty = 0
    total_cost = 0.0
    for item in result:
        group_name, display_he, display_en = _match_product_to_category(item.product_name, mappings)
        qty = item.quantity or 0
        cost = item.total_price or 0
        if group_name not in by_category:
            by_category[group_name] = {
                "category": group_name,
                "display_he": display_he,
                "display_en": display_en,
                "quantity": 0,
                "cost": 0,
            }
        by_category[group_name]["quantity"] += qty
        by_category[group_name]["cost"] += cost
        total_qty += qty
        total_cost += cost

    return {
        "items": [
            {**v, "quantity": round(v["quantity"]), "cost": round(v["cost"])}
            for v in sorted(by_category.values(), key=lambda x: x["cost"], reverse=True)
        ],
        "total_quantity": round(total_qty),
        "total_cost": round(total_cost),
        "year": target_year,
        "month": month,
        "site_id": site_id,
    }
