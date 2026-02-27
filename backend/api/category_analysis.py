"""
Product category analysis API with 4-level drill-down.
Level 1: Total cost/qty over months
Level 2: Cost/qty by site for a month
Level 3: Cost/qty by product category for a site+month
Level 4: Individual products within a category
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.user import User
from backend.models.proforma import Proforma, ProformaItem
from backend.models.product_category import (
    ProductCategoryGroup,
    ProductCategoryMapping,
    WorkingDaysEntry,
)
from backend.api.auth import get_current_user
from backend.utils.db_compat import year_equals, month_equals, extract_month

router = APIRouter()

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


async def _load_category_mappings(db: AsyncSession) -> list[tuple[str, str, str, str]]:
    """Load all category mappings ordered by group sort_order.
    Returns list of (pattern, group_name, display_he, display_en).
    """
    result = await db.execute(
        select(
            ProductCategoryMapping.product_name_pattern,
            ProductCategoryGroup.name,
            ProductCategoryGroup.display_name_he,
            ProductCategoryGroup.display_name_en,
            ProductCategoryGroup.sort_order,
        )
        .join(ProductCategoryGroup)
        .where(ProductCategoryGroup.is_active == True)
        .order_by(ProductCategoryGroup.sort_order, ProductCategoryMapping.id)
    )
    return [(row[0], row[1], row[2], row[3]) for row in result]


def _match_product_to_category(
    product_name: str,
    mappings: list[tuple[str, str, str, str]],
) -> tuple[str, str, str]:
    """Match a product name against LIKE patterns. Returns (group_name, he, en)."""
    name_lower = product_name.lower()
    for pattern, group_name, display_he, display_en in mappings:
        # Convert SQL LIKE pattern to regex
        regex = pattern.replace("%", ".*").lower()
        if re.search(regex, name_lower):
            return (group_name, display_he, display_en)
    return ("uncategorized", "לא מסווג", "Uncategorized")


async def _get_proforma_items_grouped(
    db: AsyncSession,
    year: int,
    month: Optional[int] = None,
    site_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
) -> list:
    """Fetch proforma items grouped by product_name with totals."""
    query = (
        select(
            ProformaItem.product_name,
            func.sum(ProformaItem.total_price).label("total_cost"),
            func.sum(ProformaItem.quantity).label("total_qty"),
            func.count(ProformaItem.id).label("item_count"),
            func.avg(ProformaItem.unit_price).label("avg_price"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(year_equals(Proforma.invoice_date, year))
    )
    if month:
        query = query.where(month_equals(Proforma.invoice_date, month))
    if site_id:
        query = query.where(Proforma.site_id == site_id)
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    query = query.group_by(ProformaItem.product_name)
    result = await db.execute(query)
    return list(result)


# ─── Groups Endpoint ───

@router.get("/groups")
async def get_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all product category groups."""
    result = await db.execute(
        select(ProductCategoryGroup)
        .options(selectinload(ProductCategoryGroup.mappings))
        .order_by(ProductCategoryGroup.sort_order)
    )
    groups = result.scalars().all()
    return {
        "groups": [
            {
                "id": g.id,
                "name": g.name,
                "display_name_he": g.display_name_he,
                "display_name_en": g.display_name_en,
                "sort_order": g.sort_order,
                "is_active": g.is_active,
                "mapping_count": len(g.mappings),
            }
            for g in groups
        ]
    }


# ─── Cost Drill-Down ───

@router.get("/cost/monthly")
async def cost_monthly(
    year: int = Query(default=2026),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 1: Total cost per month for the year."""
    m_expr = extract_month(Proforma.invoice_date)
    query = (
        select(
            m_expr.label("month_str"),
            func.sum(Proforma.total_amount).label("total_cost"),
            func.count(Proforma.id).label("invoice_count"),
        )
        .where(year_equals(Proforma.invoice_date, year))
        .group_by(m_expr)
        .order_by(m_expr)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    result = await db.execute(query)
    items = []
    for row in result:
        m = int(row.month_str)
        items.append({
            "month": m,
            "month_name": MONTH_NAMES.get(m, str(m)),
            "total_cost": round(row.total_cost or 0, 2),
            "invoice_count": row.invoice_count or 0,
        })

    return {"year": year, "items": items}


@router.get("/cost/by-site")
async def cost_by_site(
    year: int = Query(...),
    month: int = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 2: Cost by site for a specific month."""
    from backend.models.site import Site

    query = (
        select(
            Proforma.site_id,
            Site.name.label("site_name"),
            func.sum(Proforma.total_amount).label("total_cost"),
            func.count(Proforma.id).label("invoice_count"),
        )
        .join(Site, Proforma.site_id == Site.id)
        .where(
            year_equals(Proforma.invoice_date, year),
            month_equals(Proforma.invoice_date, month),
        )
        .group_by(Proforma.site_id, Site.name)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    result = await db.execute(query)
    items = [
        {
            "site_id": row.site_id,
            "site_name": row.site_name,
            "total_cost": round(row.total_cost or 0, 2),
            "invoice_count": row.invoice_count or 0,
        }
        for row in result
    ]

    return {"year": year, "month": month, "month_name": MONTH_NAMES.get(month, ""), "items": items}


@router.get("/cost/by-category")
async def cost_by_category(
    year: int = Query(...),
    month: int = Query(...),
    site_id: int = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 3: Cost by product category for a site+month."""
    mappings = await _load_category_mappings(db)
    items = await _get_proforma_items_grouped(db, year, month, site_id, supplier_id)

    # Group by category
    category_totals: dict[str, dict] = {}
    for row in items:
        group_name, display_he, display_en = _match_product_to_category(row.product_name, mappings)
        if group_name not in category_totals:
            category_totals[group_name] = {
                "category_name": group_name,
                "display_name_he": display_he,
                "display_name_en": display_en,
                "total_cost": 0,
                "total_qty": 0,
                "item_count": 0,
            }
        category_totals[group_name]["total_cost"] += row.total_cost or 0
        category_totals[group_name]["total_qty"] += row.total_qty or 0
        category_totals[group_name]["item_count"] += row.item_count or 0

    # Sort by the group's sort_order
    group_order = {m[1]: i for i, m in enumerate(mappings)}
    group_order["uncategorized"] = 999

    sorted_items = sorted(
        category_totals.values(),
        key=lambda x: group_order.get(x["category_name"], 999),
    )
    for item in sorted_items:
        item["total_cost"] = round(item["total_cost"], 2)
        item["total_qty"] = round(item["total_qty"], 1)

    return {
        "year": year,
        "month": month,
        "site_id": site_id,
        "items": sorted_items,
    }


@router.get("/cost/products")
async def cost_products(
    year: int = Query(...),
    month: Optional[int] = Query(default=None),
    site_id: Optional[int] = Query(default=None),
    category_name: str = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 4: Individual products within a category for a site+month (or full year if month omitted)."""
    mappings = await _load_category_mappings(db)
    items = await _get_proforma_items_grouped(db, year, month, site_id, supplier_id)

    # Filter to products matching the requested category
    products = []
    for row in items:
        group_name, _, _ = _match_product_to_category(row.product_name, mappings)
        if group_name == category_name:
            products.append({
                "product_name": row.product_name,
                "total_cost": round(row.total_cost or 0, 2),
                "total_quantity": round(row.total_qty or 0, 1),
                "avg_unit_price": round(row.avg_price or 0, 2),
                "order_count": row.item_count or 0,
            })

    products.sort(key=lambda x: x["total_cost"], reverse=True)

    return {
        "year": year,
        "month": month,
        "site_id": site_id,
        "category_name": category_name,
        "items": products,
    }


# ─── Quantity Drill-Down (same structure, quantity-focused) ───

@router.get("/quantity/monthly")
async def quantity_monthly(
    year: int = Query(default=2026),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 1: Total quantity per month for the year."""
    m_expr = extract_month(Proforma.invoice_date)
    query = (
        select(
            m_expr.label("month_str"),
            func.sum(ProformaItem.quantity).label("total_qty"),
            func.count(func.distinct(Proforma.id)).label("invoice_count"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(year_equals(Proforma.invoice_date, year))
        .group_by(m_expr)
        .order_by(m_expr)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    result = await db.execute(query)
    items = []
    for row in result:
        m = int(row.month_str)
        items.append({
            "month": m,
            "month_name": MONTH_NAMES.get(m, str(m)),
            "total_quantity": round(row.total_qty or 0, 0),
            "invoice_count": row.invoice_count or 0,
        })

    return {"year": year, "items": items}


@router.get("/quantity/by-site")
async def quantity_by_site(
    year: int = Query(...),
    month: int = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 2: Quantity by site for a specific month."""
    from backend.models.site import Site

    query = (
        select(
            Proforma.site_id,
            Site.name.label("site_name"),
            func.sum(ProformaItem.quantity).label("total_qty"),
            func.count(func.distinct(Proforma.id)).label("invoice_count"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .join(Site, Proforma.site_id == Site.id)
        .where(
            year_equals(Proforma.invoice_date, year),
            month_equals(Proforma.invoice_date, month),
        )
        .group_by(Proforma.site_id, Site.name)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    result = await db.execute(query)
    items = [
        {
            "site_id": row.site_id,
            "site_name": row.site_name,
            "total_quantity": round(row.total_qty or 0, 0),
            "invoice_count": row.invoice_count or 0,
        }
        for row in result
    ]

    return {"year": year, "month": month, "month_name": MONTH_NAMES.get(month, ""), "items": items}


@router.get("/quantity/by-category")
async def quantity_by_category(
    year: int = Query(...),
    month: int = Query(...),
    site_id: int = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 3: Quantity by category for a site+month."""
    mappings = await _load_category_mappings(db)
    items = await _get_proforma_items_grouped(db, year, month, site_id, supplier_id)

    category_totals: dict[str, dict] = {}
    for row in items:
        group_name, display_he, display_en = _match_product_to_category(row.product_name, mappings)
        if group_name not in category_totals:
            category_totals[group_name] = {
                "category_name": group_name,
                "display_name_he": display_he,
                "display_name_en": display_en,
                "total_quantity": 0,
                "total_cost": 0,
                "item_count": 0,
            }
        category_totals[group_name]["total_quantity"] += row.total_qty or 0
        category_totals[group_name]["total_cost"] += row.total_cost or 0
        category_totals[group_name]["item_count"] += row.item_count or 0

    group_order = {m[1]: i for i, m in enumerate(mappings)}
    group_order["uncategorized"] = 999

    sorted_items = sorted(
        category_totals.values(),
        key=lambda x: group_order.get(x["category_name"], 999),
    )
    for item in sorted_items:
        item["total_quantity"] = round(item["total_quantity"], 0)
        item["total_cost"] = round(item["total_cost"], 2)

    return {"year": year, "month": month, "site_id": site_id, "items": sorted_items}


@router.get("/quantity/category-monthly")
async def quantity_category_monthly(
    year: int = Query(...),
    site_id: int = Query(...),
    category_name: str = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly breakdown for a specific category at a site (between Level 3 and Level 4)."""
    mappings = await _load_category_mappings(db)

    m_expr = extract_month(Proforma.invoice_date)
    query = (
        select(
            m_expr.label("month_str"),
            ProformaItem.product_name,
            func.sum(ProformaItem.total_price).label("total_cost"),
            func.sum(ProformaItem.quantity).label("total_qty"),
            func.count(ProformaItem.id).label("item_count"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(
            year_equals(Proforma.invoice_date, year),
            Proforma.site_id == site_id,
        )
        .group_by(m_expr, ProformaItem.product_name)
        .order_by(m_expr)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    result = await db.execute(query)

    # Aggregate by month, filtering to requested category
    monthly: dict[int, dict] = {}
    for row in result:
        group_name, _, _ = _match_product_to_category(row.product_name, mappings)
        if group_name != category_name:
            continue
        m = int(row.month_str)
        if m not in monthly:
            monthly[m] = {
                "month": m,
                "month_name": MONTH_NAMES.get(m, str(m)),
                "total_quantity": 0,
                "total_cost": 0,
                "product_count": 0,
            }
        monthly[m]["total_quantity"] += row.total_qty or 0
        monthly[m]["total_cost"] += row.total_cost or 0
        monthly[m]["product_count"] += 1

    items = sorted(monthly.values(), key=lambda x: x["month"])
    for item in items:
        item["total_quantity"] = round(item["total_quantity"], 0)
        item["total_cost"] = round(item["total_cost"], 2)

    return {
        "year": year,
        "site_id": site_id,
        "category_name": category_name,
        "items": items,
    }


@router.get("/quantity/product-monthly")
async def quantity_product_monthly(
    year: int = Query(...),
    site_id: int = Query(...),
    category_name: str = Query(...),
    product_names: str = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Monthly breakdown for specific products within a category at a site."""
    mappings = await _load_category_mappings(db)
    requested = [p.strip() for p in product_names.split(",") if p.strip()]

    m_expr = extract_month(Proforma.invoice_date)
    query = (
        select(
            m_expr.label("month_str"),
            ProformaItem.product_name,
            func.sum(ProformaItem.total_price).label("total_cost"),
            func.sum(ProformaItem.quantity).label("total_qty"),
            func.avg(ProformaItem.unit_price).label("avg_price"),
            func.count(ProformaItem.id).label("order_count"),
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(
            year_equals(Proforma.invoice_date, year),
            Proforma.site_id == site_id,
        )
        .group_by(m_expr, ProformaItem.product_name)
        .order_by(m_expr)
    )
    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)

    result = await db.execute(query)

    products_data: dict[str, dict[int, dict]] = {}
    for row in result:
        group_name, _, _ = _match_product_to_category(row.product_name, mappings)
        if group_name != category_name:
            continue
        if row.product_name not in requested:
            continue

        m = int(row.month_str)
        if row.product_name not in products_data:
            products_data[row.product_name] = {}

        products_data[row.product_name][m] = {
            "month": m,
            "month_name": MONTH_NAMES.get(m, str(m)),
            "total_cost": round(row.total_cost or 0, 2),
            "total_quantity": round(row.total_qty or 0, 0),
            "avg_price": round(row.avg_price or 0, 2),
            "order_count": row.order_count or 0,
        }

    series = []
    for pname in requested:
        if pname in products_data:
            months_data = sorted(products_data[pname].values(), key=lambda x: x["month"])
            series.append({"product_name": pname, "months": months_data})

    return {
        "year": year,
        "site_id": site_id,
        "category_name": category_name,
        "series": series,
    }


@router.get("/quantity/products")
async def quantity_products(
    year: int = Query(...),
    month: int = Query(...),
    site_id: int = Query(...),
    category_name: str = Query(...),
    supplier_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Level 4: Product quantities within a category for a site+month."""
    mappings = await _load_category_mappings(db)
    items = await _get_proforma_items_grouped(db, year, month, site_id, supplier_id)

    products = []
    for row in items:
        group_name, _, _ = _match_product_to_category(row.product_name, mappings)
        if group_name == category_name:
            products.append({
                "product_name": row.product_name,
                "total_quantity": round(row.total_qty or 0, 1),
                "total_cost": round(row.total_cost or 0, 2),
                "avg_unit_price": round(row.avg_price or 0, 2),
                "order_count": row.item_count or 0,
            })

    products.sort(key=lambda x: x["total_quantity"], reverse=True)

    return {
        "year": year,
        "month": month,
        "site_id": site_id,
        "category_name": category_name,
        "items": products,
    }


# ─── Working Days ───

@router.get("/working-days")
async def get_working_days(
    site_id: Optional[int] = Query(default=None),
    year: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get working days entries."""
    query = select(WorkingDaysEntry).options(selectinload(WorkingDaysEntry.site))
    if site_id:
        query = query.where(WorkingDaysEntry.site_id == site_id)
    if year:
        query = query.where(WorkingDaysEntry.year == year)
    query = query.order_by(WorkingDaysEntry.year, WorkingDaysEntry.month)

    result = await db.execute(query)
    entries = result.scalars().all()
    return {
        "items": [
            {
                "id": e.id,
                "site_id": e.site_id,
                "site_name": e.site.name if e.site else None,
                "year": e.year,
                "month": e.month,
                "working_days": e.working_days,
                "notes": e.notes,
            }
            for e in entries
        ]
    }


@router.post("/working-days")
async def set_working_days(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update working days for a site/year/month."""
    site_id = data["site_id"]
    year = data["year"]
    month = data["month"]
    working_days = data["working_days"]

    result = await db.execute(
        select(WorkingDaysEntry).where(
            WorkingDaysEntry.site_id == site_id,
            WorkingDaysEntry.year == year,
            WorkingDaysEntry.month == month,
        )
    )
    entry = result.scalar_one_or_none()

    if entry:
        entry.working_days = working_days
        entry.notes = data.get("notes")
    else:
        entry = WorkingDaysEntry(
            site_id=site_id,
            year=year,
            month=month,
            working_days=working_days,
            notes=data.get("notes"),
        )
        db.add(entry)

    await db.commit()
    return {"status": "ok", "working_days": working_days}
