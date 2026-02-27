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
    for p in projects:
        tasks = list(p.tasks) if p.tasks else []
        done = sum(1 for t in tasks if t.status == "done")
        project_summary.append({
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "priority": p.priority,
            "site_name": p.site.name if p.site else None,
            "task_count": len(tasks),
            "done_count": done,
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
        month_cat_query = (
            select(
                extract_month(Proforma.invoice_date).label("month"),
                ProformaItem.product_name,
                func.sum(ProformaItem.total_price).label("cost"),
            )
            .join(Proforma, ProformaItem.proforma_id == Proforma.id)
            .where(year_equals(Proforma.invoice_date, proforma_year))
            .group_by(extract_month(Proforma.invoice_date), ProformaItem.product_name)
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

    query = (
        select(
            extract_month(Proforma.invoice_date).label("month"),
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
        .group_by(extract_month(Proforma.invoice_date))
        .order_by(extract_month(Proforma.invoice_date))
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
