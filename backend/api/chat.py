"""
Chat interface API - Natural language interaction with the AI system
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import date, datetime, timedelta

from backend.database import get_db
from backend.models.user import User
from backend.models.proforma import Proforma
from backend.models.supplier_budget import SupplierBudget
from backend.models.supplier import Supplier
from backend.models.site import Site
from backend.models.violation import Violation
from backend.models.meeting import Meeting
from backend.models.todo import TodoItem
from backend.models.daily_meal_count import DailyMealCount
from backend.models.operations import Anomaly
from backend.api.auth import get_current_user
from backend.services.claude_service import claude_service
from backend.utils.db_compat import extract_month

router = APIRouter()

CHAT_SYSTEM_PROMPT = """You are an AI assistant for Catering Services at HP Israel.
You help Ziv manage catering operations across Nes Ziona (NZ) and Kiryat Gat (KG) sites.

You have access to live data context injected below your user's message. Use it to give
specific, data-driven answers. When the user asks about spending, budgets, meals, violations,
or operations — reference the exact numbers from the context.

You can help with:
- Budget analysis: spending vs budget per supplier, per site, per month
- Meal tracking: daily meal counts by type and site
- Violation management: open violations, severity, patterns, fines
- Meeting preparation and upcoming schedule
- Anomaly detection and operational alerts
- Forecasting and trend analysis based on historical data

Be concise, actionable, and data-driven. Respond in the same language as the user's message
(Hebrew or English). Use ₪ for currency amounts."""


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    suggestions: list[str] = []


MONTH_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


async def _build_budget_context(db: AsyncSession, current_year: int, current_month: int, suppliers: dict) -> tuple[str, list]:
    """Build per-supplier budget allocations for the current year."""
    budget_result = await db.execute(
        select(SupplierBudget)
        .where(SupplierBudget.year == current_year, SupplierBudget.is_active == True)
    )
    budgets = budget_result.scalars().all()
    if not budgets:
        return "", []

    lines = [f"Supplier budget allocations ({current_year}):"]
    total_yearly = 0
    total_monthly = 0
    for b in budgets:
        supplier_name = suppliers.get(b.supplier_id, f"Supplier #{b.supplier_id}")
        monthly_val = getattr(b, MONTH_COLS[current_month - 1]) or 0
        yearly_val = b.yearly_amount or 0
        total_yearly += yearly_val
        total_monthly += monthly_val

        # Build monthly breakdown string for this supplier
        monthly_vals = []
        for mi in range(12):
            val = getattr(b, MONTH_COLS[mi]) or 0
            if val > 0:
                monthly_vals.append(f"{MONTH_NAMES[mi][:3]}=₪{val:,.0f}")
        monthly_str = ", ".join(monthly_vals) if monthly_vals else "no monthly data"

        lines.append(
            f"  {supplier_name}: yearly=₪{yearly_val:,.0f}, "
            f"this month ({MONTH_NAMES[current_month-1][:3]})=₪{monthly_val:,.0f} | {monthly_str}"
        )

    lines.insert(1, f"  TOTALS: yearly=₪{total_yearly:,.0f}, this month=₪{total_monthly:,.0f}")
    return "\n".join(lines), budgets


async def _build_spending_context(
    db: AsyncSession, current_year: int, current_month: int,
    suppliers: dict, sites: dict, budgets: list
) -> str:
    """Build per-supplier × per-month × per-site actual spending (last 6 months)."""
    # Determine 6-month window
    months_window = []
    for i in range(6):
        m = current_month - i
        y = current_year
        if m <= 0:
            m += 12
            y -= 1
        months_window.append((y, m))

    start_date = date(months_window[-1][0], months_window[-1][1], 1)

    month_expr = extract_month(Proforma.invoice_date)
    spending_result = await db.execute(
        select(
            Proforma.supplier_id,
            Proforma.site_id,
            month_expr.label("month"),
            func.sum(Proforma.total_amount).label("total"),
            func.count(Proforma.id).label("count"),
        )
        .where(
            Proforma.invoice_date.isnot(None),
            Proforma.invoice_date >= start_date,
        )
        .group_by(Proforma.supplier_id, Proforma.site_id, month_expr)
    )
    rows = spending_result.all()

    if not rows:
        return ""

    # Build lookup: { (supplier_id, site_id, month_int): {total, count} }
    lookup = {}
    for row in rows:
        month_int = int(row.month)
        lookup[(row.supplier_id, row.site_id, month_int)] = {
            "total": float(row.total or 0),
            "count": int(row.count or 0),
        }

    # Build budget lookup for quick access
    budget_map = {}  # { (supplier_id, month_int): budget_amount }
    for b in budgets:
        for mi in range(12):
            val = getattr(b, MONTH_COLS[mi]) or 0
            if val > 0:
                budget_map[(b.supplier_id, mi + 1)] = (
                    budget_map.get((b.supplier_id, mi + 1), 0) + val
                )

    sections = []

    # --- Detailed per-supplier × per-month spending ---
    # Group by supplier
    supplier_data = {}
    for (sid, stid, m), v in lookup.items():
        supplier_data.setdefault(sid, []).append((stid, m, v))

    detail_lines = ["Actual spending detail (supplier × month × site, last 6 months):"]
    for sid in sorted(supplier_data.keys(), key=lambda x: suppliers.get(x, "")):
        supplier_name = suppliers.get(sid, f"Supplier #{sid}")
        entries = supplier_data[sid]

        # Group by month for this supplier
        monthly = {}
        for stid, m, v in entries:
            site_name = sites.get(stid, f"Site #{stid}")
            monthly.setdefault(m, []).append((site_name, v["total"], v["count"]))

        for year, month in months_window:
            if month in monthly:
                site_parts = []
                month_total = 0
                for site_name, total, count in monthly[month]:
                    site_parts.append(f"{site_name}=₪{total:,.0f}({count} inv)")
                    month_total += total

                budget_val = budget_map.get((sid, month), 0)
                variance_str = ""
                if budget_val > 0 and year == current_year:
                    variance = budget_val - month_total
                    pct = (month_total / budget_val) * 100
                    status = "under" if variance >= 0 else "OVER"
                    variance_str = f" | budget=₪{budget_val:,.0f}, {status} by ₪{abs(variance):,.0f} ({pct:.0f}%)"

                detail_lines.append(
                    f"  {supplier_name} | {MONTH_NAMES[month-1][:3]} {year}: "
                    f"₪{month_total:,.0f} [{', '.join(site_parts)}]{variance_str}"
                )

    sections.append("\n".join(detail_lines))

    # --- Monthly totals summary ---
    summary_lines = ["Monthly spending totals (last 6 months):"]
    for year, month in months_window:
        month_total = sum(
            v["total"] for (sid, stid, m), v in lookup.items() if m == month
        )
        if month_total > 0:
            total_budget = sum(
                budget_map.get((b.supplier_id, month), 0)
                for b in budgets
            ) if budgets else 0
            # Deduplicate: budget_map already aggregated, so just sum unique supplier budgets
            total_budget_month = sum(
                v for (sid, mi), v in budget_map.items() if mi == month
            )
            var_str = ""
            if total_budget_month > 0 and year == current_year:
                var = total_budget_month - month_total
                pct = (month_total / total_budget_month) * 100
                var_str = f" | budget=₪{total_budget_month:,.0f}, {'under' if var >= 0 else 'OVER'} ₪{abs(var):,.0f} ({pct:.0f}%)"
            summary_lines.append(f"  {MONTH_NAMES[month-1]} {year}: ₪{month_total:,.0f}{var_str}")

    sections.append("\n".join(summary_lines))

    # --- Site totals ---
    site_totals = {}
    for (sid, stid, m), v in lookup.items():
        site_name = sites.get(stid, f"Site #{stid}")
        site_totals[site_name] = site_totals.get(site_name, 0) + v["total"]

    if site_totals:
        site_lines = ["Spending by site (last 6 months):"]
        for name, total in sorted(site_totals.items(), key=lambda x: x[1], reverse=True):
            site_lines.append(f"  {name}: ₪{total:,.0f}")
        sections.append("\n".join(site_lines))

    return "\n\n".join(sections)


async def _build_meals_context(db: AsyncSession, sites: dict) -> str:
    """Build daily meal count summary for the last 30 days."""
    cutoff = date.today() - timedelta(days=30)
    meal_result = await db.execute(
        select(
            DailyMealCount.site_id,
            DailyMealCount.meal_type_en,
            func.sum(DailyMealCount.quantity).label("total"),
            func.count(DailyMealCount.id).label("days"),
        )
        .where(DailyMealCount.date >= cutoff)
        .group_by(DailyMealCount.site_id, DailyMealCount.meal_type_en)
    )
    rows = meal_result.all()
    if not rows:
        return ""

    lines = ["Daily meal counts (last 30 days):"]
    site_meals = {}
    for row in rows:
        site_name = sites.get(row.site_id, f"Site #{row.site_id}")
        meal_type = row.meal_type_en or "Unknown"
        total = float(row.total or 0)
        days = int(row.days or 0)
        avg = total / days if days > 0 else 0
        site_meals.setdefault(site_name, []).append(
            f"{meal_type}: {total:,.0f} total ({days} days, avg {avg:,.0f}/day)"
        )

    for site_name, meals in site_meals.items():
        lines.append(f"  {site_name}:")
        for m in meals:
            lines.append(f"    {m}")

    return "\n".join(lines)


async def _build_violations_context(db: AsyncSession, sites: dict) -> str:
    """Build violation summary with categories, severities, and recent items."""
    # Summary by status
    status_result = await db.execute(
        select(Violation.status, func.count(Violation.id))
        .group_by(Violation.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}
    if not status_counts:
        return ""

    lines = ["Violations summary:"]
    lines.append(f"  By status: {', '.join(f'{s}={c}' for s, c in status_counts.items())}")

    # Open violations by category and severity
    open_result = await db.execute(
        select(
            Violation.category,
            Violation.severity,
            Violation.site_id,
            func.count(Violation.id).label("cnt"),
            func.sum(Violation.fine_amount).label("fines"),
        )
        .where(Violation.status != "resolved")
        .group_by(Violation.category, Violation.severity, Violation.site_id)
    )
    open_rows = open_result.all()
    if open_rows:
        lines.append("  Open violations breakdown:")
        for row in open_rows:
            site_name = sites.get(row.site_id, "Unknown")
            fine_str = f", fines=₪{float(row.fines):,.0f}" if row.fines else ""
            lines.append(
                f"    {row.category or 'N/A'} | {row.severity or 'N/A'} | "
                f"{site_name}: {row.cnt} violations{fine_str}"
            )

    # Recent 5 violations for detail
    recent_result = await db.execute(
        select(Violation)
        .where(Violation.status != "resolved")
        .order_by(Violation.received_at.desc())
        .limit(5)
    )
    recent = recent_result.scalars().all()
    if recent:
        lines.append("  Recent open violations:")
        for v in recent:
            site_name = sites.get(v.site_id, "Unknown")
            fine_str = f", fine=₪{v.fine_amount:,.0f}" if v.fine_amount else ""
            text_preview = (v.violation_text or "")[:80]
            lines.append(
                f"    [{v.severity or 'N/A'}] {v.category or 'N/A'} @ {site_name} "
                f"({v.status}){fine_str}: {text_preview}"
            )

    return "\n".join(lines)


async def _build_meetings_context(db: AsyncSession, sites: dict) -> str:
    """Build upcoming meetings detail."""
    now = datetime.now()
    meeting_result = await db.execute(
        select(Meeting)
        .where(Meeting.scheduled_at >= now)
        .order_by(Meeting.scheduled_at.asc())
        .limit(5)
    )
    meetings = meeting_result.scalars().all()
    if not meetings:
        return ""

    lines = [f"Upcoming meetings ({len(meetings)}):"]
    for m in meetings:
        site_name = sites.get(m.site_id, "")
        site_str = f" @ {site_name}" if site_name else ""
        lines.append(
            f"  {m.scheduled_at.strftime('%Y-%m-%d %H:%M')} | {m.title or 'Untitled'} "
            f"({m.meeting_type or 'general'}{site_str}, {m.duration_minutes or 60}min)"
        )

    return "\n".join(lines)


async def _build_anomalies_context(db: AsyncSession) -> str:
    """Build active anomaly alerts."""
    anomaly_result = await db.execute(
        select(Anomaly)
        .where(Anomaly.resolved == False)
        .order_by(Anomaly.detected_at.desc())
        .limit(10)
    )
    anomalies = anomaly_result.scalars().all()
    if not anomalies:
        return ""

    lines = [f"Active anomalies ({len(anomalies)}):"]
    for a in anomalies:
        exp = f"expected=₪{a.expected_value:,.0f}" if a.expected_value else ""
        act = f"actual=₪{a.actual_value:,.0f}" if a.actual_value else ""
        var = f"variance={a.variance_percent:.0f}%" if a.variance_percent else ""
        metrics = ", ".join(filter(None, [exp, act, var]))
        metrics_str = f" ({metrics})" if metrics else ""
        lines.append(
            f"  [{a.severity or 'N/A'}] {a.anomaly_type or 'unknown'} — "
            f"{a.description or 'no details'}{metrics_str}"
        )

    return "\n".join(lines)


async def _build_todos_context(db: AsyncSession, user: User, today: date) -> str:
    """Build open tasks summary."""
    todo_result = await db.execute(
        select(func.count(TodoItem.id))
        .where(TodoItem.user_id == user.id, TodoItem.status != "done")
    )
    open_todos = todo_result.scalar() or 0
    if open_todos == 0:
        return ""

    overdue_result = await db.execute(
        select(func.count(TodoItem.id))
        .where(
            TodoItem.user_id == user.id,
            TodoItem.status != "done",
            TodoItem.due_date < today,
        )
    )
    overdue = overdue_result.scalar() or 0
    text = f"Open tasks: {open_todos}"
    if overdue > 0:
        text += f" ({overdue} overdue)"
    return text


async def _build_proformas_context(db: AsyncSession) -> str:
    """Build total proforma stats."""
    result = await db.execute(
        select(func.count(Proforma.id), func.sum(Proforma.total_amount))
    )
    row = result.one()
    if row[0] and row[0] > 0:
        return f"Total proformas in system: {row[0]}, total value: ₪{float(row[1]):,.0f}"
    return ""


async def _build_context(db: AsyncSession, user: User) -> str:
    """Build comprehensive live data context for the AI from the database."""
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    today = date.today()

    context_parts = []

    try:
        # Load reference data
        supplier_result = await db.execute(select(Supplier).where(Supplier.is_active == True))
        suppliers = {s.id: s.name for s in supplier_result.scalars().all()}

        site_result = await db.execute(select(Site).where(Site.is_active == True))
        sites = {s.id: s.name for s in site_result.scalars().all()}

        # Build all context sections
        budget_text, budgets = await _build_budget_context(db, current_year, current_month, suppliers)
        if budget_text:
            context_parts.append(budget_text)

        spending_text = await _build_spending_context(
            db, current_year, current_month, suppliers, sites, budgets
        )
        if spending_text:
            context_parts.append(spending_text)

        meals_text = await _build_meals_context(db, sites)
        if meals_text:
            context_parts.append(meals_text)

        violations_text = await _build_violations_context(db, sites)
        if violations_text:
            context_parts.append(violations_text)

        meetings_text = await _build_meetings_context(db, sites)
        if meetings_text:
            context_parts.append(meetings_text)

        anomalies_text = await _build_anomalies_context(db)
        if anomalies_text:
            context_parts.append(anomalies_text)

        todos_text = await _build_todos_context(db, user, today)
        if todos_text:
            context_parts.append(todos_text)

        proformas_text = await _build_proformas_context(db)
        if proformas_text:
            context_parts.append(proformas_text)

    except Exception:
        pass

    if context_parts:
        return "\n\n--- LIVE DATA CONTEXT ---\n\n" + "\n\n".join(context_parts)
    return ""


@router.post("/", response_model=ChatResponse)
@router.post("", response_model=ChatResponse, include_in_schema=False)
async def chat(
    chat_message: ChatMessage,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message to the AI assistant"""
    if not claude_service.is_available:
        raise HTTPException(
            status_code=503,
            detail="AI service is not configured. Please set the ANTHROPIC_API_KEY environment variable."
        )

    try:
        context = await _build_context(db, current_user)
        prompt = chat_message.message
        if context:
            prompt = f"{chat_message.message}\n{context}"

        response = await claude_service.generate_response(
            prompt=prompt,
            system_prompt=CHAT_SYSTEM_PROMPT,
        )

        suggestions = [
            "Prepare brief for next meeting",
            "Show recent violations",
            "Check budget status",
        ]

        return ChatResponse(response=response, suggestions=suggestions)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="AI service temporarily unavailable. Please try again later.")
