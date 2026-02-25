"""
Dashboard API - aggregated data for all dashboard sections
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime, date

from backend.database import get_db
from backend.models.meeting import Meeting
from backend.models.user import User
from backend.models.supplier_budget import SupplierBudget
from backend.models.proforma import Proforma
from backend.models.project import Project, ProjectTask
from backend.models.maintenance import MaintenanceBudget, MaintenanceExpense
from backend.models.todo import TodoItem
from backend.api.auth import get_current_user

router = APIRouter()

MONTH_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]


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

    # --- 1. Budget vs Actual (current month summary per supplier) ---
    budget_result = await db.execute(
        select(SupplierBudget)
        .options(selectinload(SupplierBudget.supplier), selectinload(SupplierBudget.site))
        .where(SupplierBudget.year == current_year, SupplierBudget.is_active == True)
    )
    budgets = budget_result.scalars().all()

    # Get actual spending for current month
    actual_result = await db.execute(
        select(
            Proforma.supplier_id,
            Proforma.site_id,
            func.sum(Proforma.total_amount).label("total"),
        )
        .where(
            func.strftime("%Y", Proforma.invoice_date) == str(current_year),
            func.strftime("%m", Proforma.invoice_date) == f"{current_month:02d}",
        )
        .group_by(Proforma.supplier_id, Proforma.site_id)
    )
    actuals = {
        (row.supplier_id, row.site_id): row.total or 0
        for row in actual_result
    }

    # Also get YTD actual for yearly comparison
    ytd_result = await db.execute(
        select(
            Proforma.supplier_id,
            Proforma.site_id,
            func.sum(Proforma.total_amount).label("total"),
        )
        .where(func.strftime("%Y", Proforma.invoice_date) == str(current_year))
        .group_by(Proforma.supplier_id, Proforma.site_id)
    )
    ytd_actuals = {
        (row.supplier_id, row.site_id): row.total or 0
        for row in ytd_result
    }

    month_col = MONTH_COLS[current_month - 1]
    budget_summary = []
    for b in budgets:
        monthly_budget = getattr(b, month_col) or 0
        monthly_actual = actuals.get((b.supplier_id, b.site_id), 0)
        ytd_actual = ytd_actuals.get((b.supplier_id, b.site_id), 0)
        budget_summary.append({
            "supplier_id": b.supplier_id,
            "supplier_name": b.supplier.name if b.supplier else "Unknown",
            "site_id": b.site_id,
            "site_name": b.site.name if b.site else "Unknown",
            "monthly_budget": monthly_budget,
            "monthly_actual": monthly_actual,
            "monthly_percent": round(monthly_actual / monthly_budget * 100, 1) if monthly_budget > 0 else 0,
            "yearly_budget": b.yearly_amount,
            "ytd_actual": ytd_actual,
            "yearly_percent": round(ytd_actual / b.yearly_amount * 100, 1) if b.yearly_amount > 0 else 0,
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
        "current_quarter": current_quarter,
        "current_year": current_year,
    }
