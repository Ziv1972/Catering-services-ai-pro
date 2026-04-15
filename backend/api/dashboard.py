"""
Dashboard API - aggregated data for all dashboard sections
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime, date
from typing import Optional

from backend.database import get_db
from backend.models.meeting import Meeting
from backend.models.user import User
from backend.models.supplier_budget import SupplierBudget
from backend.models.proforma import Proforma, ProformaItem
from backend.models.project import Project, ProjectTask
from backend.models.maintenance import MaintenanceBudget, MaintenanceExpense
from backend.models.todo import TodoItem
from backend.api.auth import get_current_user
from backend.utils.db_compat import year_equals, month_equals, extract_month

router = APIRouter()

MONTH_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]


async def _resolve_budget_year(
    db: AsyncSession,
    preferred_year: int,
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
) -> int:
    """Find the best year with budget data, optionally for a specific supplier/site."""
    query = (
        select(func.count(SupplierBudget.id))
        .where(SupplierBudget.year == preferred_year, SupplierBudget.is_active == True)
    )
    if supplier_id:
        query = query.where(SupplierBudget.supplier_id == supplier_id)
    if site_id:
        query = query.where(SupplierBudget.site_id == site_id)

    result = await db.execute(query)
    if (result.scalar() or 0) > 0:
        return preferred_year

    # Fallback: most recent year with budget data for this supplier/site
    fallback_query = (
        select(SupplierBudget.year)
        .where(SupplierBudget.is_active == True)
    )
    if supplier_id:
        fallback_query = fallback_query.where(SupplierBudget.supplier_id == supplier_id)
    if site_id:
        fallback_query = fallback_query.where(SupplierBudget.site_id == site_id)
    fallback_query = fallback_query.order_by(SupplierBudget.year.desc()).limit(1)

    result = await db.execute(fallback_query)
    row = result.scalar_one_or_none()
    return row if row else preferred_year


async def _resolve_proforma_year(
    db: AsyncSession,
    preferred_year: int,
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
) -> int:
    """Find the best year with proforma data, optionally for a specific supplier/site."""
    query = (
        select(func.count(Proforma.id))
        .where(year_equals(Proforma.invoice_date, preferred_year))
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    result = await db.execute(query)
    if (result.scalar() or 0) > 0:
        return preferred_year

    # Fallback: most recent year with proforma data for this supplier/site
    from backend.database import is_sqlite
    if is_sqlite:
        fallback_query = select(func.strftime("%Y", func.max(Proforma.invoice_date)))
    else:
        from sqlalchemy import extract, cast, String
        fallback_query = select(cast(extract("year", func.max(Proforma.invoice_date)), String))

    if supplier_id:
        fallback_query = fallback_query.where(Proforma.supplier_id == supplier_id)
    if site_id:
        fallback_query = fallback_query.where(Proforma.site_id == site_id)

    result = await db.execute(fallback_query)
    row = result.scalar_one_or_none()
    return int(row) if row else preferred_year


@router.get("/")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive dashboard data for all sections"""
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    current_quarter = (current_month - 1) // 3 + 1

    # Resolve best year for budget and proforma data
    budget_year = await _resolve_budget_year(db, current_year)
    proforma_year = await _resolve_proforma_year(db, current_year)

    # Show last month's actual data (current month is still in progress)
    if proforma_year == current_year:
        display_month = current_month - 1 if current_month > 1 else 1
    else:
        # Proforma data is from a previous year — show most recent month
        display_month = 12

    # --- 1. Budget vs Actual (per supplier) ---
    budget_result = await db.execute(
        select(SupplierBudget)
        .options(selectinload(SupplierBudget.supplier), selectinload(SupplierBudget.site))
        .where(SupplierBudget.year == budget_year, SupplierBudget.is_active == True)
    )
    budgets = budget_result.scalars().all()

    # Get actual spending for display month from proforma_year
    actual_result = await db.execute(
        select(
            Proforma.supplier_id,
            Proforma.site_id,
            func.sum(Proforma.total_amount).label("total"),
        )
        .where(
            year_equals(Proforma.invoice_date, proforma_year),
            month_equals(Proforma.invoice_date, display_month),
        )
        .group_by(Proforma.supplier_id, Proforma.site_id)
    )
    actuals = {
        (row.supplier_id, row.site_id): row.total or 0
        for row in actual_result
    }

    # Also get last 3 months average as fallback for "typical" monthly spend
    recent_avg_result = await db.execute(
        select(
            Proforma.supplier_id,
            Proforma.site_id,
            func.sum(Proforma.total_amount).label("total"),
            func.count(func.distinct(extract_month(Proforma.invoice_date))).label("months"),
        )
        .where(year_equals(Proforma.invoice_date, proforma_year))
        .group_by(Proforma.supplier_id, Proforma.site_id)
    )
    avg_actuals = {}
    for row in recent_avg_result:
        months_count = row.months or 1
        avg_actuals[(row.supplier_id, row.site_id)] = {
            "ytd_total": row.total or 0,
            "monthly_avg": round((row.total or 0) / months_count),
            "months_with_data": months_count,
        }

    month_col = MONTH_COLS[display_month - 1]
    budget_summary = []
    for b in budgets:
        monthly_budget = getattr(b, month_col) or 0
        monthly_actual = actuals.get((b.supplier_id, b.site_id), 0)
        avg_data = avg_actuals.get((b.supplier_id, b.site_id), {})
        ytd_actual = avg_data.get("ytd_total", 0)
        monthly_avg = avg_data.get("monthly_avg", 0)

        # Use monthly actual if available, otherwise show monthly average
        shown_actual = monthly_actual if monthly_actual > 0 else monthly_avg

        budget_summary.append({
            "supplier_id": b.supplier_id,
            "supplier_name": b.supplier.name if b.supplier else "Unknown",
            "site_id": b.site_id,
            "site_name": b.site.name if b.site else "Unknown",
            "shift": getattr(b, "shift", "all") or "all",
            "monthly_budget": monthly_budget,
            "monthly_actual": shown_actual,
            "monthly_percent": round(shown_actual / monthly_budget * 100, 1) if monthly_budget > 0 else 0,
            "yearly_budget": b.yearly_amount,
            "ytd_actual": ytd_actual,
            "yearly_percent": round(ytd_actual / b.yearly_amount * 100, 1) if b.yearly_amount > 0 else 0,
            "actual_source_year": proforma_year,
            "is_average": monthly_actual == 0 and monthly_avg > 0,
        })

    # --- 2. Active Projects ---
    projects_result = await db.execute(
        select(Project)
        .options(selectinload(Project.tasks), selectinload(Project.site))
        .where(Project.status.in_(["planning", "active", "on_hold"]))
        .order_by(Project.updated_at.desc())
        .limit(5)
    )
    projects = projects_result.scalars().all()

    project_summary = []
    today = date.today()
    for p in projects:
        tasks = list(p.tasks) if p.tasks else []
        done = sum(1 for t in tasks if t.status == "done")
        overdue = sum(
            1 for t in tasks
            if t.due_date and t.due_date < today and t.status != "done"
        )
        project_summary.append({
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "priority": p.priority,
            "site_name": p.site.name if p.site else None,
            "task_count": len(tasks),
            "done_count": done,
            "overdue_count": overdue,
            "progress": round(done / len(tasks) * 100) if tasks else 0,
            "target_end_date": p.target_end_date.isoformat() if p.target_end_date else None,
        })

    # --- 3. Maintenance Budget (current quarter) ---
    maint_result = await db.execute(
        select(MaintenanceBudget)
        .options(selectinload(MaintenanceBudget.site), selectinload(MaintenanceBudget.expenses))
        .where(
            MaintenanceBudget.year == current_year,
            MaintenanceBudget.quarter == current_quarter,
        )
    )
    maint_budgets = maint_result.scalars().all()

    maintenance_summary = []
    for mb in maint_budgets:
        actual = sum(e.amount for e in mb.expenses) if mb.expenses else 0
        maintenance_summary.append({
            "id": mb.id,
            "site_name": mb.site.name if mb.site else None,
            "quarter": mb.quarter,
            "budget": mb.budget_amount,
            "actual": actual,
            "remaining": mb.budget_amount - actual,
            "percent_used": round(actual / mb.budget_amount * 100, 1) if mb.budget_amount > 0 else 0,
        })

    # --- 4. Upcoming Meetings ---
    meetings_result = await db.execute(
        select(Meeting)
        .where(Meeting.scheduled_at >= now)
        .order_by(Meeting.scheduled_at.asc())
        .limit(10)
    )
    meetings = meetings_result.scalars().all()

    meetings_summary = [
        {
            "id": m.id,
            "title": m.title,
            "meeting_type": m.meeting_type,
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
            "has_brief": m.ai_brief is not None,
        }
        for m in meetings
    ]

    # --- 5. Todos ---
    todos_result = await db.execute(
        select(TodoItem)
        .where(
            TodoItem.user_id == current_user.id,
            TodoItem.status != "done",
        )
        .order_by(TodoItem.due_date.asc().nullslast())
        .limit(10)
    )
    todos = todos_result.scalars().all()

    today = date.today()
    my_todos = []
    delegated_todos = []
    overdue_count = 0

    for t in todos:
        is_overdue = t.due_date is not None and t.due_date < today
        if is_overdue:
            overdue_count += 1
        item = {
            "id": t.id,
            "title": t.title,
            "assigned_to": t.assigned_to,
            "priority": t.priority,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "is_overdue": is_overdue,
        }
        if t.assigned_to:
            delegated_todos.append(item)
        else:
            my_todos.append(item)

    # --- 6. Proforma cost summary (FoodHouse actuals) ---
    proforma_summary_result = await db.execute(
        select(
            Proforma.site_id,
            func.count(Proforma.id).label("count"),
            func.sum(Proforma.total_amount).label("total"),
        )
        .where(year_equals(Proforma.invoice_date, proforma_year))
        .group_by(Proforma.site_id)
    )
    proforma_costs = [
        {"site_id": row.site_id, "count": row.count, "total": row.total or 0}
        for row in proforma_summary_result
    ]

    return {
        "budget_summary": budget_summary,
        "projects": project_summary,
        "maintenance": maintenance_summary,
        "meetings": meetings_summary,
        "todos": {
            "mine": my_todos,
            "delegated": delegated_todos,
            "overdue_count": overdue_count,
        },
        "proforma_costs": proforma_costs,
        "current_quarter": current_quarter,
        "current_year": current_year,
        "budget_year": budget_year,
        "proforma_year": proforma_year,
        "display_month": display_month,
    }


@router.get("/drill-down/budget")
async def budget_drill_down(
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
    year: Optional[int] = None,
    budget_year: Optional[int] = None,
    proforma_year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down: budget vs actual by month with category breakdown."""
    from fastapi.responses import JSONResponse
    import logging
    logger = logging.getLogger(__name__)

    target_year = year or datetime.now().year

    try:
        # Resolve years globally (not per-supplier to avoid PostgreSQL edge cases)
        if not proforma_year:
            proforma_year = await _resolve_proforma_year(db, target_year)
        if not budget_year:
            budget_year = await _resolve_budget_year(db, target_year)

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        # ── Budget per month from SupplierBudget ──
        budget_query = (
            select(SupplierBudget)
            .where(SupplierBudget.year == budget_year, SupplierBudget.is_active == True)
        )
        if supplier_id:
            budget_query = budget_query.where(SupplierBudget.supplier_id == supplier_id)
        if site_id:
            budget_query = budget_query.where(SupplierBudget.site_id == site_id)

        budget_result = await db.execute(budget_query)
        budgets = budget_result.scalars().all()

        monthly_budgets: dict[int, float] = {}
        for b in budgets:
            for m_idx, col in enumerate(MONTH_COLS):
                val = getattr(b, col) or 0
                monthly_budgets[m_idx + 1] = monthly_budgets.get(m_idx + 1, 0) + val

        # ── Actual per month from Proformas ──
        month_expr = extract_month(Proforma.invoice_date)
        actual_query = (
            select(
                month_expr.label("month"),
                func.sum(Proforma.total_amount).label("total"),
                func.count(Proforma.id).label("count"),
            )
            .where(year_equals(Proforma.invoice_date, proforma_year))
            .group_by(month_expr)
            .order_by(month_expr)
        )
        if supplier_id:
            actual_query = actual_query.where(Proforma.supplier_id == supplier_id)
        if site_id:
            actual_query = actual_query.where(Proforma.site_id == site_id)

        result = await db.execute(actual_query)
        monthly_actuals: dict[int, dict] = {}
        for row in result:
            monthly_actuals[int(row.month)] = {"total": row.total or 0, "count": row.count}

        # ── Build monthly items (all 12 months) ──
        items = []
        for m in range(1, 13):
            actual_data = monthly_actuals.get(m, {"total": 0, "count": 0})
            budget_val = monthly_budgets.get(m, 0)
            actual_val = round(actual_data["total"], 0)
            items.append({
                "month": m,
                "month_name": month_names[m - 1],
                "budget": round(budget_val, 0),
                "actual": actual_val,
                "total": actual_val,
                "invoice_count": actual_data["count"],
            })

        # ── Category breakdown (aggregate for year) ──
        from backend.api.category_analysis import (
            _load_category_mappings, _match_product_to_category, _get_proforma_items_grouped,
        )
        mappings = await _load_category_mappings(db)
        prod_items = await _get_proforma_items_grouped(
            db, proforma_year, site_id=site_id, supplier_id=supplier_id,
        )

        category_totals: dict[str, dict] = {}
        for row in prod_items:
            group_name, display_he, display_en = _match_product_to_category(
                row.product_name, mappings,
            )
            if group_name not in category_totals:
                category_totals[group_name] = {
                    "category_name": group_name,
                    "display_name_he": display_he,
                    "display_name_en": display_en,
                    "total_cost": 0,
                    "total_qty": 0,
                }
            category_totals[group_name]["total_cost"] += row.total_cost or 0
            category_totals[group_name]["total_qty"] += row.total_qty or 0

        categories = sorted(category_totals.values(), key=lambda x: x["total_cost"], reverse=True)
        for cat in categories:
            cat["total_cost"] = round(cat["total_cost"], 0)
            cat["total_qty"] = round(cat["total_qty"], 1)

        # ── Per-month category breakdown ──
        cat_month_expr = extract_month(Proforma.invoice_date)
        month_cat_query = (
            select(
                cat_month_expr.label("month"),
                ProformaItem.product_name,
                func.sum(ProformaItem.total_price).label("cost"),
            )
            .join(Proforma, ProformaItem.proforma_id == Proforma.id)
            .where(year_equals(Proforma.invoice_date, proforma_year))
            .group_by(cat_month_expr, ProformaItem.product_name)
        )
        if supplier_id:
            month_cat_query = month_cat_query.where(Proforma.supplier_id == supplier_id)
        if site_id:
            month_cat_query = month_cat_query.where(Proforma.site_id == site_id)

        month_cat_result = await db.execute(month_cat_query)
        monthly_categories: dict[int, dict[str, float]] = {}
        for row in month_cat_result:
            m = int(row.month)
            if m not in monthly_categories:
                monthly_categories[m] = {}
            gname, _, _ = _match_product_to_category(row.product_name, mappings)
            monthly_categories[m][gname] = monthly_categories[m].get(gname, 0) + (row.cost or 0)

        # Attach category breakdown to each month item
        all_cat_names = sorted({c["category_name"] for c in categories})
        for item in items:
            m_cats = monthly_categories.get(item["month"], {})
            item["categories"] = {cn: round(m_cats.get(cn, 0), 0) for cn in all_cat_names}

        return {
            "year": proforma_year,
            "budget_year": budget_year,
            "items": items,
            "categories": categories,
            "category_names": all_cat_names,
        }
    except Exception as e:
        logger.error(f"Budget drill-down failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={
                "year": target_year,
                "budget_year": target_year,
                "items": [],
                "categories": [],
                "category_names": [],
                "error": str(e),
            },
        )


@router.get("/drill-down/products")
async def product_drill_down(
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down: spending by product category, then by item."""
    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    # Get item-level spending
    query = (
        select(
            ProformaItem.product_name,
            func.sum(ProformaItem.total_price).label("total"),
            func.sum(ProformaItem.quantity).label("qty"),
            func.count(ProformaItem.id).label("count"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(year_equals(Proforma.invoice_date, proforma_year))
        .group_by(ProformaItem.product_name)
        .order_by(func.sum(ProformaItem.total_price).desc())
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)
    if site_id:
        query = query.where(Proforma.site_id == site_id)
    if month:
        query = query.where(month_equals(Proforma.invoice_date, month))

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

    return {"year": proforma_year, "month": month, "items": items}


@router.get("/drill-down/product-history")
async def product_history_drill_down(
    product_name: str,
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down: monthly breakdown for a specific product."""
    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    ph_month_expr = extract_month(Proforma.invoice_date)
    query = (
        select(
            ph_month_expr.label("month"),
            func.sum(ProformaItem.total_price).label("total"),
            func.sum(ProformaItem.quantity).label("qty"),
            func.count(ProformaItem.id).label("count"),
            func.avg(ProformaItem.unit_price).label("avg_price"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(
            year_equals(Proforma.invoice_date, proforma_year),
            ProformaItem.product_name == product_name,
        )
        .group_by(ph_month_expr)
        .order_by(ph_month_expr)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    result = await db.execute(query)
    monthly = [
        {
            "month": int(row.month),
            "month_name": month_names[int(row.month) - 1],
            "quantity": round(row.qty or 0, 1),
            "total": round(row.total or 0, 0),
            "avg_price": round(row.avg_price or 0, 2),
            "orders": row.count or 0,
        }
        for row in result
    ]

    return {"product_name": product_name, "year": proforma_year, "monthly": monthly}


@router.get("/drill-down/project")
async def project_drill_down(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down: project tasks and details"""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.tasks), selectinload(Project.site))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        return {"error": "Project not found"}

    tasks = list(project.tasks) if project.tasks else []
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "priority": project.priority,
        "site_name": project.site.name if project.site else None,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "target_end_date": project.target_end_date.isoformat() if project.target_end_date else None,
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "assigned_to": t.assigned_to,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            }
            for t in sorted(tasks, key=lambda x: x.order if x.order else 0)
        ],
    }


@router.get("/drill-down/maintenance")
async def maintenance_drill_down(
    site_id: Optional[int] = None,
    quarter: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Drill-down: maintenance expenses for a quarter/site"""
    target_year = year or datetime.now().year
    target_quarter = quarter or ((datetime.now().month - 1) // 3 + 1)

    expense_query = (
        select(MaintenanceExpense)
        .options(selectinload(MaintenanceExpense.site))
        .order_by(MaintenanceExpense.date.desc())
    )
    if site_id:
        expense_query = expense_query.where(MaintenanceExpense.site_id == site_id)

    # Filter by quarter date range
    q_start_month = (target_quarter - 1) * 3 + 1
    q_end_month = target_quarter * 3
    from backend.utils.db_compat import month_between
    expense_query = expense_query.where(
        year_equals(MaintenanceExpense.date, target_year),
        month_between(MaintenanceExpense.date, q_start_month, q_end_month),
    )

    result = await db.execute(expense_query)
    expenses = result.scalars().all()

    return {
        "year": target_year,
        "quarter": target_quarter,
        "expenses": [
            {
                "id": e.id,
                "date": e.date.isoformat() if e.date else None,
                "description": e.description,
                "amount": e.amount,
                "category": e.category,
                "vendor": e.vendor,
                "site_name": e.site.name if e.site else None,
            }
            for e in expenses
        ],
        "total": sum(e.amount for e in expenses),
    }


@router.get("/supplier-monthly")
async def supplier_monthly_spending(
    year: Optional[int] = None,
    from_month: int = Query(default=1, ge=1, le=12),
    to_month: int = Query(default=12, ge=1, le=12),
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly actual spending per supplier for a given year and month range."""
    from backend.models.supplier import Supplier
    from backend.models.site import Site

    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    month_expr = extract_month(Proforma.invoice_date)
    query = (
        select(
            month_expr.label("month"),
            Proforma.supplier_id,
            Supplier.name.label("supplier_name"),
            Proforma.site_id,
            Site.name.label("site_name"),
            func.sum(Proforma.total_amount).label("total"),
            func.count(Proforma.id).label("invoice_count"),
        )
        .join(Supplier, Proforma.supplier_id == Supplier.id)
        .join(Site, Proforma.site_id == Site.id)
        .where(year_equals(Proforma.invoice_date, proforma_year))
        .group_by(month_expr, Proforma.supplier_id, Supplier.name, Proforma.site_id, Site.name)
        .order_by(month_expr)
    )
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    result = await db.execute(query)

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Build supplier series keyed by "supplier (site)"
    supplier_series: dict[str, dict] = {}
    for row in result:
        m = int(row.month)
        if m < from_month or m > to_month:
            continue
        key = f"{row.supplier_name} ({row.site_name})"
        if key not in supplier_series:
            supplier_series[key] = {
                "label": key,
                "supplier_id": row.supplier_id,
                "site_id": row.site_id,
                "supplier_name": row.supplier_name,
                "site_name": row.site_name,
                "months": {},
                "total": 0,
            }
        supplier_series[key]["months"][m] = {
            "month": m,
            "month_name": month_names[m - 1],
            "total": round(row.total or 0, 2),
            "invoice_count": row.invoice_count or 0,
        }
        supplier_series[key]["total"] += row.total or 0

    # Build unified chart data: one row per month, columns per supplier
    chart_data = []
    for m in range(from_month, to_month + 1):
        row_data: dict = {"month": m, "month_name": month_names[m - 1]}
        for key, series in supplier_series.items():
            row_data[key] = round(series["months"].get(m, {}).get("total", 0), 2)
        chart_data.append(row_data)

    # Sort series by total descending
    sorted_series = sorted(supplier_series.values(), key=lambda x: x["total"], reverse=True)
    for s in sorted_series:
        s["total"] = round(s["total"], 2)
        s["months"] = sorted(s["months"].values(), key=lambda x: x["month"])

    # Get available sites for filter
    sites_result = await db.execute(select(Site.id, Site.name).order_by(Site.name))
    sites = [{"id": r.id, "name": r.name} for r in sites_result]

    return {
        "year": proforma_year,
        "from_month": from_month,
        "to_month": to_month,
        "chart_data": chart_data,
        "series": sorted_series,
        "series_keys": [s["label"] for s in sorted_series],
        "sites": sites,
    }


@router.get("/meals-monthly")
async def meals_monthly(
    year: Optional[int] = None,
    from_month: int = Query(default=1, ge=1, le=12),
    to_month: int = Query(default=12, ge=1, le=12),
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FoodHouse meals per month from MealBreakdown (ריכוז הכנסות). Returns quantity + spending."""
    from backend.models.site import Site
    from backend.models.meal_breakdown import MealBreakdown

    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    # Meal quantity fields (excluding supplement)
    meal_fields = [
        "hp_meat", "scitex_meat", "evening_hp", "evening_contractors",
        "hp_dairy", "scitex_dairy", "contractors_meat", "contractors_dairy",
    ]

    # Query MealBreakdown grouped by month + site
    month_expr = extract_month(MealBreakdown.invoice_month)
    q = (
        select(MealBreakdown, Site.name.label("site_name"))
        .join(Site, MealBreakdown.site_id == Site.id)
        .where(year_equals(MealBreakdown.invoice_month, proforma_year))
    )
    if site_id:
        q = q.where(MealBreakdown.site_id == site_id)

    result = await db.execute(q)
    rows = list(result)

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Aggregate by month + site
    # { month -> { site_name -> { meals, supplement, cost, working_days } } }
    by_month: dict[int, dict[str, dict]] = {}
    site_set: set[str] = set()

    for mb, site_name in rows:
        m = mb.invoice_month.month
        if m < from_month or m > to_month:
            continue
        site_set.add(site_name)
        if m not in by_month:
            by_month[m] = {}
        total_meals = sum(getattr(mb, f, 0) or 0 for f in meal_fields)
        supplement = mb.supplement or 0
        cost = mb.total_cost or 0
        wd = mb.working_days or 0
        by_month[m][site_name] = {
            "meals": total_meals,
            "supplement": supplement,
            "cost": cost,
            "working_days": wd,
        }

    # Build chart data
    chart_data = []
    site_keys = sorted(site_set)
    for m in range(from_month, to_month + 1):
        row: dict = {"month": m, "month_name": month_names[m - 1]}
        month_data = by_month.get(m, {})
        total_meals = 0
        total_supplement = 0
        total_cost = 0.0
        for sk in site_keys:
            sd = month_data.get(sk, {})
            meals = round(sd.get("meals", 0))
            row[sk] = meals
            row[f"{sk}_supplement"] = round(sd.get("supplement", 0))
            row[f"{sk}_cost"] = round(sd.get("cost", 0), 2)
            total_meals += meals
            total_supplement += round(sd.get("supplement", 0))
            total_cost += sd.get("cost", 0)
        row["total"] = total_meals
        row["total_supplement"] = total_supplement
        row["total_cost"] = round(total_cost, 2)
        chart_data.append(row)

    # Sites for filter
    sites_result = await db.execute(select(Site.id, Site.name).order_by(Site.name))
    sites = [{"id": r.id, "name": r.name} for r in sites_result]

    return {
        "year": proforma_year,
        "from_month": from_month,
        "to_month": to_month,
        "chart_data": chart_data,
        "site_keys": site_keys,
        "sites": sites,
    }


@router.get("/meals-detail")
async def meals_detail(
    year: Optional[int] = None,
    from_month: int = Query(default=1, ge=1, le=12),
    to_month: int = Query(default=12, ge=1, le=12),
    site_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Breakdown of 9 meal types from MealBreakdown (ריכוז הכנסות) over time."""
    from backend.models.meal_breakdown import MealBreakdown

    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    # 9 meal type fields → Hebrew labels
    MEAL_TYPE_LABELS = {
        "hp_meat": "ארוחת צהריים בשרית HP",
        "scitex_meat": "ארוחת צהריים בשרית סאייטקס",
        "evening_hp": "ארוחת ערב HP",
        "evening_contractors": "ארוחת ערב קבלנים",
        "hp_dairy": "ארוחת צהריים חלבית HP",
        "scitex_dairy": "ארוחת צהריים חלבית סאייטקס",
        "supplement": "תוספת מנה עיקרית",
        "contractors_meat": "ארוחת צהריים בשרית קבלנים",
        "contractors_dairy": "ארוחת צהריים חלבית קבלנים",
    }

    q = (
        select(MealBreakdown)
        .where(year_equals(MealBreakdown.invoice_month, proforma_year))
    )
    if site_id:
        q = q.where(MealBreakdown.site_id == site_id)

    result = await db.execute(q)
    breakdowns = list(result.scalars().all())

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Pivot: { hebrew_label -> { month -> { qty, cost } } }
    product_data: dict[str, dict[int, dict]] = {}
    product_totals: dict[str, dict] = {}

    for label in MEAL_TYPE_LABELS.values():
        product_data[label] = {}
        product_totals[label] = {"qty": 0, "cost": 0}

    for mb in breakdowns:
        m = mb.invoice_month.month
        if m < from_month or m > to_month:
            continue
        for field, label in MEAL_TYPE_LABELS.items():
            qty = getattr(mb, field, 0) or 0
            price = getattr(mb, f"{field}_price", 0) or 0
            cost = qty * price
            if m not in product_data[label]:
                product_data[label][m] = {"qty": 0, "cost": 0}
            product_data[label][m]["qty"] += qty
            product_data[label][m]["cost"] += cost
            product_totals[label]["qty"] += qty
            product_totals[label]["cost"] += cost

    # Sort by total qty descending, filter out zero-quantity types
    sorted_products = sorted(
        [k for k in product_totals if product_totals[k]["qty"] > 0],
        key=lambda p: product_totals[p]["qty"],
        reverse=True,
    )

    # Build chart data
    chart_data = []
    for m in range(from_month, to_month + 1):
        row: dict = {"month": m, "month_name": month_names[m - 1]}
        for pname in sorted_products:
            row[pname] = round(product_data[pname].get(m, {}).get("qty", 0))
        chart_data.append(row)

    series = [
        {
            "product_name": pname,
            "total_qty": round(product_totals[pname]["qty"]),
            "total_cost": round(product_totals[pname]["cost"], 2),
        }
        for pname in sorted_products
    ]

    return {
        "year": proforma_year,
        "from_month": from_month,
        "to_month": to_month,
        "chart_data": chart_data,
        "product_keys": sorted_products,
        "series": series,
    }


@router.get("/meals-budget")
async def meals_budget(
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly budget vs actual meal spending per site from MealBreakdown + SupplierBudget."""
    from backend.models.site import Site
    from backend.models.supplier import Supplier
    from backend.models.meal_breakdown import MealBreakdown

    target_year = year or datetime.now().year

    # Get FoodHouse supplier for budget lookup
    fh_result = await db.execute(
        select(Supplier).where(Supplier.name.ilike("%foodhouse%"))
    )
    foodhouse = fh_result.scalar_one_or_none()

    # Get all sites
    sites_result = await db.execute(select(Site).order_by(Site.name))
    all_sites = list(sites_result.scalars().all())

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_cols = ["jan", "feb", "mar", "apr", "may", "jun",
                  "jul", "aug", "sep", "oct", "nov", "dec"]

    # Get budgets per site
    budget_by_site: dict[int, list[float]] = {}
    if foodhouse:
        budget_q = select(SupplierBudget).where(
            SupplierBudget.supplier_id == foodhouse.id,
            SupplierBudget.year == target_year,
        )
        if site_id:
            budget_q = budget_q.where(SupplierBudget.site_id == site_id)
        budgets = await db.execute(budget_q)
        for b in budgets.scalars().all():
            monthly = [getattr(b, mc, 0) or 0 for mc in month_cols]
            budget_by_site[b.site_id] = monthly

    # Get actual spending from MealBreakdown — use same year as budget
    mb_q = (
        select(MealBreakdown)
        .where(year_equals(MealBreakdown.invoice_month, target_year))
    )
    if site_id:
        mb_q = mb_q.where(MealBreakdown.site_id == site_id)

    mb_result = await db.execute(mb_q)
    breakdowns = list(mb_result.scalars().all())

    # Aggregate actual cost by site + month
    # Use total_cost which is the full proforma cost (all meal types)
    # This matches what the budget covers: the total FoodHouse invoice
    actual_by_site_month: dict[int, dict[int, float]] = {}
    for mb in breakdowns:
        m = mb.invoice_month.month
        sid = mb.site_id
        if sid not in actual_by_site_month:
            actual_by_site_month[sid] = {}
        actual_by_site_month[sid][m] = (actual_by_site_month[sid].get(m, 0)
                                         + (mb.total_cost or 0))

    # Build per-site response
    site_data = []
    for s in all_sites:
        if site_id and s.id != site_id:
            continue
        budget_months = budget_by_site.get(s.id, [0] * 12)
        actual_months = actual_by_site_month.get(s.id, {})

        monthly_data = []
        # Track cumulative YTD (year-to-date) up to the latest month with actual data
        latest_month = max(actual_months.keys()) if actual_months else 0
        ytd_budget = 0.0
        ytd_actual = 0.0

        for m in range(1, 13):
            b = budget_months[m - 1]
            a = actual_months.get(m, 0)
            if m <= latest_month:
                ytd_budget += b
                ytd_actual += a
            monthly_data.append({
                "month": m,
                "month_name": month_names[m - 1],
                "budget": round(b, 2),
                "actual": round(a, 2),
                "diff": round(b - a, 2),
                "pct": round((a / b * 100) if b > 0 else 0, 1),
            })

        yearly_budget = sum(budget_months)
        yearly_actual = sum(actual_months.values())

        site_data.append({
            "site_id": s.id,
            "site_name": s.name,
            "yearly_budget": round(yearly_budget, 2),
            "yearly_actual": round(yearly_actual, 2),
            "yearly_pct": round((yearly_actual / yearly_budget * 100) if yearly_budget > 0 else 0, 1),
            # YTD: cumulative budget vs actual up to the latest month with data
            "ytd_budget": round(ytd_budget, 2),
            "ytd_actual": round(ytd_actual, 2),
            "ytd_pct": round((ytd_actual / ytd_budget * 100) if ytd_budget > 0 else 0, 1),
            "latest_month": latest_month,
            "monthly": monthly_data,
        })

    return {
        "year": target_year,
        "sites": site_data,
    }


@router.get("/kitchenette-monthly")
async def kitchenette_monthly(
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kitchenette/BTB spending per family per month per site.

    Sources data from ProformaItem joined with ProductCategoryGroup (same source as
    the Budget vs Actual drill-down). This guarantees the Kitchenette panel and the
    drill-down stay in sync. Includes BTB-related category groups: kitchenette_*,
    coffee_tea, coffee_beans, cut_veg, extras_lunch.
    """
    from backend.models.proforma import Proforma, ProformaItem
    from backend.models.product_category import ProductCategoryGroup, ProductCategoryMapping
    import re

    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    # Load all category mappings (pattern → group)
    mapping_q = (
        select(
            ProductCategoryMapping.product_name_pattern,
            ProductCategoryGroup.name,
            ProductCategoryGroup.display_name_he,
        )
        .join(ProductCategoryGroup)
        .where(ProductCategoryGroup.is_active == True)
        .order_by(ProductCategoryGroup.sort_order, ProductCategoryMapping.id)
    )
    mappings = list((await db.execute(mapping_q)).all())

    # Family keys we treat as "kitchenette" (BTB) — exclude meals-related + uncategorized.
    # Uncategorized products are hidden from this panel (they're surfaced in the main
    # Budget vs Actual drill-down instead).
    EXCLUDED_GROUPS = {"total_meals", "working_days", "uncategorized"}
    family_labels: dict[str, str] = {}
    for _, group_name, display_he in mappings:
        if group_name in EXCLUDED_GROUPS:
            continue
        family_labels.setdefault(group_name, display_he)

    def classify(name: str) -> str | None:
        nl = name.lower()
        for pattern, group_name, _ in mappings:
            if group_name in EXCLUDED_GROUPS:
                continue
            regex = pattern.replace("%", ".*").lower()
            try:
                if re.search(regex, nl):
                    return group_name
            except re.error:
                continue
        return None

    # Pull all proforma line items for the year (+ optional site)
    # Top kitchenette view always combines both sites (HP Indigo top-level overview).
    # Site filtering happens inside the drill-down (kitchenette-drilldown endpoint).
    items_q = (
        select(
            ProformaItem.product_name,
            ProformaItem.quantity,
            ProformaItem.total_price,
            Proforma.invoice_date,
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(year_equals(Proforma.invoice_date, proforma_year))
    )

    rows = list((await db.execute(items_q)).all())

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    family_data: dict[str, dict[int, dict]] = {fk: {} for fk in family_labels}
    family_totals: dict[str, dict] = {fk: {"qty": 0, "cost": 0} for fk in family_labels}

    for product_name, qty, total_price, invoice_date in rows:
        if not invoice_date:
            continue
        fk = classify(product_name or "")
        if fk is None or fk not in family_labels:
            continue  # skip uncategorized — not a kitchenette product
        m = invoice_date.month
        if m not in family_data[fk]:
            family_data[fk][m] = {"qty": 0, "cost": 0}
        family_data[fk][m]["qty"] += float(qty or 0)
        family_data[fk][m]["cost"] += float(total_price or 0)
        family_totals[fk]["qty"] += float(qty or 0)
        family_totals[fk]["cost"] += float(total_price or 0)

    # Only include families that have non-zero cost
    visible = {k: v for k, v in family_labels.items() if family_totals[k]["cost"] > 0}
    sorted_families = sorted(visible.keys(), key=lambda f: family_totals[f]["cost"], reverse=True)

    chart_data = []
    for m in range(1, 13):
        row: dict = {"month": m, "month_name": month_names[m - 1]}
        for fk in sorted_families:
            label = family_labels[fk]
            row[f"{label}_qty"] = round(family_data[fk].get(m, {}).get("qty", 0))
            row[f"{label}_cost"] = round(family_data[fk].get(m, {}).get("cost", 0), 2)
        chart_data.append(row)

    series = [
        {
            "family_key": fk,
            "family_name": family_labels[fk],
            "total_qty": round(family_totals[fk]["qty"]),
            "total_cost": round(family_totals[fk]["cost"], 2),
        }
        for fk in sorted_families
    ]

    return {
        "year": proforma_year,
        "chart_data": chart_data,
        "families": series,
    }


@router.get("/kitchenette-drilldown")
async def kitchenette_drilldown(
    family_key: str,
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    month: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Drill-down for one kitchenette family.

    - Without month: returns monthly time series + per-site split (Level 1)
    - With month: returns product-level breakdown for that family/site/month (Level 2)
    """
    from backend.models.proforma import Proforma, ProformaItem
    from backend.models.product_category import ProductCategoryGroup, ProductCategoryMapping
    from backend.models.site import Site
    import re

    target_year = year or datetime.now().year
    proforma_year = await _resolve_proforma_year(db, target_year)

    # Patterns that classify products into THIS family
    pat_q = (
        select(ProductCategoryMapping.product_name_pattern)
        .join(ProductCategoryGroup)
        .where(ProductCategoryGroup.name == family_key)
        .where(ProductCategoryGroup.is_active == True)
    )
    patterns = [r[0] for r in (await db.execute(pat_q)).all()]

    # Family display name
    name_q = select(ProductCategoryGroup.display_name_he, ProductCategoryGroup.display_name_en).where(
        ProductCategoryGroup.name == family_key
    )
    name_row = (await db.execute(name_q)).first()
    family_he = name_row[0] if name_row else family_key
    family_en = name_row[1] if name_row else family_key

    # Pull all candidate items for the year (filter by site if given)
    items_q = (
        select(
            ProformaItem.product_name,
            ProformaItem.quantity,
            ProformaItem.total_price,
            ProformaItem.unit,
            Proforma.invoice_date,
            Proforma.site_id,
            Site.name.label("site_name"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .join(Site, Proforma.site_id == Site.id, isouter=True)
        .where(year_equals(Proforma.invoice_date, proforma_year))
    )
    if site_id:
        items_q = items_q.where(Proforma.site_id == site_id)

    rows = list((await db.execute(items_q)).all())

    # Filter to ones matching family patterns
    def matches(name: str) -> bool:
        nl = (name or "").lower()
        for p in patterns:
            try:
                if re.search(p.replace("%", ".*").lower(), nl):
                    return True
            except re.error:
                continue
        return False

    matched = [r for r in rows if matches(r[0])]

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Level 2: product breakdown for given month
    if month:
        products: dict[str, dict] = {}
        for product_name, qty, total_price, unit, inv_date, sid, sname in matched:
            if not inv_date or inv_date.month != month:
                continue
            key = product_name
            if key not in products:
                products[key] = {
                    "product_name": product_name,
                    "unit": unit or "unit",
                    "qty": 0.0,
                    "cost": 0.0,
                    "by_site": {},
                }
            products[key]["qty"] += float(qty or 0)
            products[key]["cost"] += float(total_price or 0)
            sk = sname or f"site_{sid}"
            products[key]["by_site"][sk] = products[key]["by_site"].get(sk, 0) + float(total_price or 0)
        product_list = sorted(
            [{"product_name": p["product_name"], "unit": p["unit"],
              "qty": round(p["qty"], 2), "cost": round(p["cost"], 2),
              "by_site": {k: round(v, 2) for k, v in p["by_site"].items()}}
             for p in products.values()],
            key=lambda x: x["cost"], reverse=True,
        )
        return {
            "year": proforma_year,
            "month": month,
            "month_name": month_names[month - 1],
            "family_key": family_key,
            "family_he": family_he,
            "family_en": family_en,
            "level": "products",
            "products": product_list,
            "total_cost": round(sum(p["cost"] for p in product_list), 2),
            "total_qty": round(sum(p["qty"] for p in product_list), 2),
        }

    # Level 1: monthly time series (split per site)
    monthly: dict[int, dict] = {m: {"month": m, "month_name": month_names[m - 1], "total": 0.0} for m in range(1, 13)}
    site_totals: dict[str, float] = {}
    for product_name, qty, total_price, unit, inv_date, sid, sname in matched:
        if not inv_date:
            continue
        m = inv_date.month
        sk = sname or f"site_{sid}"
        monthly[m][sk] = monthly[m].get(sk, 0) + float(total_price or 0)
        monthly[m]["total"] += float(total_price or 0)
        site_totals[sk] = site_totals.get(sk, 0) + float(total_price or 0)

    chart = []
    for m in range(1, 13):
        row = {"month": m, "month_name": month_names[m - 1], "total": round(monthly[m]["total"], 2)}
        for sk in site_totals:
            row[sk] = round(monthly[m].get(sk, 0), 2)
        chart.append(row)

    return {
        "year": proforma_year,
        "family_key": family_key,
        "family_he": family_he,
        "family_en": family_en,
        "level": "monthly",
        "chart_data": chart,
        "sites": [{"name": k, "total": round(v, 2)} for k, v in sorted(site_totals.items(), key=lambda x: -x[1])],
        "total_cost": round(sum(site_totals.values()), 2),
    }


@router.get("/daily-meals")
async def dashboard_daily_meals(
    days: int = Query(default=30, ge=1, le=90),
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Daily meal counts from FoodHouse reports for the last N days.
    Returns bars by date, broken down by meal type + site,
    plus monthly aggregates with budget comparison.
    """
    from backend.models.daily_meal_count import DailyMealCount
    from backend.models.site import Site
    from backend.models.supplier import Supplier
    from datetime import timedelta

    today = date.today()
    start_date = today - timedelta(days=days)

    # ── Fetch daily meal records ──
    query = (
        select(DailyMealCount)
        .where(DailyMealCount.date >= start_date)
        .order_by(DailyMealCount.date.desc())
    )
    if site_id:
        query = query.where(DailyMealCount.site_id == site_id)

    result = await db.execute(query)
    records = result.scalars().all()

    # ── Site lookup ──
    sites_result = await db.execute(select(Site.id, Site.name).order_by(Site.name))
    sites = {r.id: r.name for r in sites_result}
    sites_list = [{"id": sid, "name": sname} for sid, sname in sites.items()]

    # ── Group by date ──
    by_date: dict[str, dict] = {}
    meal_type_set: set[str] = set()

    for r in records:
        d = r.date.isoformat()
        mt_label = r.meal_type_en or r.meal_type or "Unknown"
        site_name = sites.get(r.site_id, "Unknown")
        key = f"{mt_label} ({site_name})" if not site_id else mt_label
        meal_type_set.add(key)

        if d not in by_date:
            by_date[d] = {"date": d, "total": 0}
        by_date[d][key] = by_date[d].get(key, 0) + r.quantity
        by_date[d]["total"] += r.quantity

    # Build chart data sorted by date ascending
    chart_data = sorted(by_date.values(), key=lambda x: x["date"])
    meal_type_keys = sorted(meal_type_set)

    # ── Monthly aggregates for budget comparison (per-site) ──
    from backend.models.proforma import Proforma
    from sqlalchemy import func, extract

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    current_month = today.month

    # Sum daily meals by month AND site
    monthly_meals_by_site: dict[tuple[int, int], float] = {}  # (month, site_id) -> qty
    for r in records:
        key = (r.date.month, r.site_id)
        monthly_meals_by_site[key] = monthly_meals_by_site.get(key, 0) + r.quantity

    # 6-month historical average meals per site per month
    six_months_ago = today.replace(day=1) - timedelta(days=180)
    hist_query = (
        select(
            extract("month", DailyMealCount.date).label("m"),
            DailyMealCount.site_id,
            func.sum(DailyMealCount.quantity).label("total"),
        )
        .where(
            DailyMealCount.date >= six_months_ago,
            DailyMealCount.date < today.replace(day=1),
        )
        .group_by(extract("month", DailyMealCount.date), DailyMealCount.site_id)
    )
    hist_result = await db.execute(hist_query)
    hist_rows = hist_result.all()
    # Average across months per site
    site_month_totals: dict[int, list[float]] = {}  # site_id -> list of monthly totals
    for row in hist_rows:
        sid = row.site_id
        if sid not in site_month_totals:
            site_month_totals[sid] = []
        site_month_totals[sid].append(float(row.total))
    avg_meals_by_site: dict[int, float] = {
        sid: round(sum(totals) / len(totals)) if totals else 0
        for sid, totals in site_month_totals.items()
    }

    # Get FoodHouse supplier
    fh_result = await db.execute(
        select(Supplier).where(Supplier.name.ilike("%foodhouse%"))
    )
    foodhouse = fh_result.scalar_one_or_none()

    # Get FoodHouse budgets per site
    budgets_by_site: dict[int, list] = {}
    if foodhouse:
        budget_query = (
            select(SupplierBudget)
            .where(
                SupplierBudget.supplier_id == foodhouse.id,
                SupplierBudget.year == today.year,
                SupplierBudget.is_active == True,
            )
        )
        if site_id:
            budget_query = budget_query.where(SupplierBudget.site_id == site_id)
        budget_result = await db.execute(budget_query)
        for b in budget_result.scalars().all():
            budgets_by_site.setdefault(b.site_id, []).append(b)

    # Get latest meal unit prices from FoodHouse proformas per site
    # Meal types: Meat/Dairy = "ארוחת צהריים בשרית/חלבית", Main Only = "מנה עיקרית"
    from backend.models.proforma import ProformaItem
    meal_prices_by_site: dict[int, dict[str, float]] = {}  # site_id -> {meal_type: price}
    if foodhouse:
        price_query = (
            select(
                Proforma.site_id,
                ProformaItem.product_name,
                ProformaItem.unit_price,
            )
            .join(ProformaItem, ProformaItem.proforma_id == Proforma.id)
            .where(
                Proforma.supplier_id == foodhouse.id,
                ProformaItem.product_name.op("LIKE")("%ארוח%"),
            )
            .order_by(Proforma.invoice_date.desc())
        )
        price_result = await db.execute(price_query)
        for row in price_result:
            sid = row.site_id
            if sid and sid not in meal_prices_by_site:
                meal_prices_by_site[sid] = {}
            if sid:
                name_lower = row.product_name.lower()
                if "בשרית" in name_lower and "Meat" not in meal_prices_by_site[sid]:
                    meal_prices_by_site[sid]["Meat"] = row.unit_price
                elif "חלבית" in name_lower and "Dairy" not in meal_prices_by_site[sid]:
                    meal_prices_by_site[sid]["Dairy"] = row.unit_price

        # Main Only price (תוספת למנה עיקרית)
        main_query = (
            select(
                Proforma.site_id,
                ProformaItem.unit_price,
            )
            .join(ProformaItem, ProformaItem.proforma_id == Proforma.id)
            .where(
                Proforma.supplier_id == foodhouse.id,
                ProformaItem.product_name.op("LIKE")("%מנה עיקרית%"),
            )
            .order_by(Proforma.invoice_date.desc())
        )
        main_result = await db.execute(main_query)
        for row in main_result:
            sid = row.site_id
            if sid and sid in meal_prices_by_site and "Main Only" not in meal_prices_by_site[sid]:
                meal_prices_by_site[sid]["Main Only"] = row.unit_price

    # Calculate cost per site: sum(meals_by_type × price_per_type)
    # Group daily meals by (month, site_id, meal_type)
    meals_by_type: dict[tuple[int, int, str], float] = {}  # (month, site_id, meal_type) -> qty
    for r in records:
        mt = r.meal_type_en or r.meal_type or "Unknown"
        key = (r.date.month, r.site_id, mt)
        meals_by_type[key] = meals_by_type.get(key, 0) + r.quantity

    cost_by_site: dict[int, float] = {}
    for (m, sid, mt), qty in meals_by_type.items():
        if m == current_month:
            prices = meal_prices_by_site.get(sid, {})
            price = prices.get(mt, prices.get("Meat", 0))  # fallback to Meat price
            cost_by_site[sid] = cost_by_site.get(sid, 0) + qty * price

    # Build per-site budget comparison for current month
    budget_comparison = []
    target_sites = [site_id] if site_id else list(sites.keys())
    for sid in target_sites:
        site_name = sites.get(sid, "Unknown")
        meals = round(monthly_meals_by_site.get((current_month, sid), 0))
        avg_meals = avg_meals_by_site.get(sid, 0)
        site_budgets = budgets_by_site.get(sid, [])
        month_budget = sum(getattr(b, MONTH_COLS[current_month - 1]) or 0 for b in site_budgets)
        cost = round(cost_by_site.get(sid, 0))
        budget_comparison.append({
            "month": current_month,
            "month_name": month_names[current_month - 1],
            "site_id": sid,
            "site_name": site_name,
            "meals": meals,
            "avg_meals_6m": avg_meals,
            "cost": cost,
            "budget": round(month_budget),
        })

    # ── Summary totals ──
    total_meals = sum(r.quantity for r in records)
    days_with_data = len(by_date)
    avg_daily = round(total_meals / days_with_data) if days_with_data > 0 else 0

    return {
        "chart_data": chart_data,
        "meal_type_keys": meal_type_keys,
        "budget_comparison": budget_comparison,
        "sites": sites_list,
        "summary": {
            "total_meals": round(total_meals),
            "days_with_data": days_with_data,
            "avg_daily": avg_daily,
            "date_range": {
                "from": start_date.isoformat(),
                "to": today.isoformat(),
            },
        },
    }


@router.get("/debug-data")
async def debug_data(
    db: AsyncSession = Depends(get_db),
):
    """Temporary debug endpoint to check data state on production."""
    from backend.models.supplier import Supplier

    # Check proformas
    proforma_result = await db.execute(
        select(
            Proforma.id,
            Proforma.invoice_date,
            Proforma.supplier_id,
            Proforma.site_id,
            Proforma.total_amount,
        )
        .order_by(Proforma.invoice_date.desc())
        .limit(10)
    )
    proformas = [
        {
            "id": row.id,
            "date": str(row.invoice_date),
            "supplier_id": row.supplier_id,
            "site_id": row.site_id,
            "total_amount": row.total_amount,
        }
        for row in proforma_result
    ]

    # Check proforma items count and totals
    items_result = await db.execute(
        select(
            ProformaItem.proforma_id,
            func.count(ProformaItem.id).label("count"),
            func.sum(ProformaItem.total_price).label("total"),
        )
        .group_by(ProformaItem.proforma_id)
        .order_by(ProformaItem.proforma_id.desc())
        .limit(10)
    )
    items_summary = [
        {"proforma_id": row.proforma_id, "item_count": row.count, "items_total": row.total}
        for row in items_result
    ]

    # Check suppliers
    suppliers_result = await db.execute(select(Supplier))
    suppliers = [{"id": s.id, "name": s.name} for s in suppliers_result.scalars().all()]

    # Check budgets
    budget_result = await db.execute(
        select(SupplierBudget.id, SupplierBudget.supplier_id, SupplierBudget.site_id,
               SupplierBudget.year, SupplierBudget.jan, SupplierBudget.yearly_amount,
               SupplierBudget.is_active)
        .order_by(SupplierBudget.year.desc())
    )
    budgets = [
        {"id": r.id, "supplier_id": r.supplier_id, "site_id": r.site_id,
         "year": r.year, "jan": r.jan, "yearly": r.yearly_amount, "active": r.is_active}
        for r in budget_result
    ]

    # Resolve years
    now = datetime.now()
    budget_year = await _resolve_budget_year(db, now.year)
    proforma_year = await _resolve_proforma_year(db, now.year)

    return {
        "current_time": now.isoformat(),
        "budget_year": budget_year,
        "proforma_year": proforma_year,
        "display_month": now.month - 1 if now.month > 1 else 1,
        "recent_proformas": proformas,
        "proforma_items_summary": items_summary,
        "suppliers": suppliers,
        "budgets": budgets,
    }
