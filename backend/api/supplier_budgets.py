"""
Supplier budget API endpoints - budget vs actual tracking per supplier per site
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

from backend.database import get_db
from backend.models.user import User
from backend.models.supplier import Supplier
from backend.models.site import Site
from backend.models.proforma import Proforma
from backend.models.supplier_budget import SupplierBudget, SupplierProductBudget
from backend.api.auth import get_current_user
from backend.utils.db_compat import year_equals, extract_month

router = APIRouter()

MONTH_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]


# --- Pydantic Schemas ---

class ProductBudgetResponse(BaseModel):
    id: int
    product_category: str
    monthly_quantity_limit: float
    unit: str
    monthly_amount_limit: Optional[float]
    notes: Optional[str]

    class Config:
        from_attributes = True


class SupplierBudgetResponse(BaseModel):
    id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    site_id: int
    site_name: Optional[str] = None
    year: int
    yearly_amount: float
    shift: str = "all"
    jan: float
    feb: float
    mar: float
    apr: float
    may: float
    jun: float
    jul: float
    aug: float
    sep: float
    oct: float
    nov: float
    dec: float
    notes: Optional[str]
    is_active: bool
    product_budgets: List[ProductBudgetResponse] = []

    class Config:
        from_attributes = True


class SupplierBudgetCreate(BaseModel):
    supplier_id: int
    site_id: int
    year: int
    yearly_amount: float
    shift: str = "all"
    jan: float = 0
    feb: float = 0
    mar: float = 0
    apr: float = 0
    may: float = 0
    jun: float = 0
    jul: float = 0
    aug: float = 0
    sep: float = 0
    oct: float = 0
    nov: float = 0
    dec: float = 0
    notes: Optional[str] = None


class SupplierBudgetUpdate(BaseModel):
    yearly_amount: Optional[float] = None
    jan: Optional[float] = None
    feb: Optional[float] = None
    mar: Optional[float] = None
    apr: Optional[float] = None
    may: Optional[float] = None
    jun: Optional[float] = None
    jul: Optional[float] = None
    aug: Optional[float] = None
    sep: Optional[float] = None
    oct: Optional[float] = None
    nov: Optional[float] = None
    dec: Optional[float] = None
    notes: Optional[str] = None


class ProductBudgetCreate(BaseModel):
    product_category: str
    monthly_quantity_limit: float
    unit: str = "kg"
    monthly_amount_limit: Optional[float] = None
    notes: Optional[str] = None


class BudgetVsActualItem(BaseModel):
    supplier_id: int
    supplier_name: str
    site_id: int
    site_name: str
    month: int
    month_name: str
    budget: float
    actual: float
    variance: float
    percent_used: float


class BudgetVsActualResponse(BaseModel):
    year: int
    items: List[BudgetVsActualItem]
    totals: dict


# --- Endpoints ---

@router.get("/", response_model=List[SupplierBudgetResponse])
async def list_budgets(
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
    year: Optional[int] = None,
    shift: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List supplier budgets with optional filters"""
    query = (
        select(SupplierBudget)
        .options(
            selectinload(SupplierBudget.supplier),
            selectinload(SupplierBudget.site),
            selectinload(SupplierBudget.product_budgets),
        )
        .where(SupplierBudget.is_active == True)
    )

    if supplier_id:
        query = query.where(SupplierBudget.supplier_id == supplier_id)
    if site_id:
        query = query.where(SupplierBudget.site_id == site_id)
    if year:
        query = query.where(SupplierBudget.year == year)
    if shift:
        query = query.where(SupplierBudget.shift == shift)

    result = await db.execute(query)
    budgets = result.scalars().all()

    return [
        SupplierBudgetResponse(
            id=b.id,
            supplier_id=b.supplier_id,
            supplier_name=b.supplier.name if b.supplier else None,
            site_id=b.site_id,
            site_name=b.site.name if b.site else None,
            year=b.year,
            yearly_amount=b.yearly_amount,
            shift=b.shift or "all",
            jan=b.jan or 0, feb=b.feb or 0, mar=b.mar or 0,
            apr=b.apr or 0, may=b.may or 0, jun=b.jun or 0,
            jul=b.jul or 0, aug=b.aug or 0, sep=b.sep or 0,
            oct=b.oct or 0, nov=b.nov or 0, dec=b.dec or 0,
            notes=b.notes,
            is_active=b.is_active,
            product_budgets=[
                ProductBudgetResponse.model_validate(pb)
                for pb in b.product_budgets
            ],
        )
        for b in budgets
    ]


@router.post("/", response_model=SupplierBudgetResponse)
async def create_budget(
    data: SupplierBudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new supplier budget"""
    budget = SupplierBudget(**data.model_dump(), is_active=True)
    db.add(budget)
    await db.commit()
    await db.refresh(budget)

    # Reload with relationships
    result = await db.execute(
        select(SupplierBudget)
        .options(selectinload(SupplierBudget.supplier), selectinload(SupplierBudget.site))
        .where(SupplierBudget.id == budget.id)
    )
    budget = result.scalar_one()

    return SupplierBudgetResponse(
        id=budget.id,
        supplier_id=budget.supplier_id,
        supplier_name=budget.supplier.name if budget.supplier else None,
        site_id=budget.site_id,
        site_name=budget.site.name if budget.site else None,
        year=budget.year,
        yearly_amount=budget.yearly_amount,
        shift=budget.shift or "all",
        jan=budget.jan or 0, feb=budget.feb or 0, mar=budget.mar or 0,
        apr=budget.apr or 0, may=budget.may or 0, jun=budget.jun or 0,
        jul=budget.jul or 0, aug=budget.aug or 0, sep=budget.sep or 0,
        oct=budget.oct or 0, nov=budget.nov or 0, dec=budget.dec or 0,
        notes=budget.notes,
        is_active=budget.is_active,
        product_budgets=[],
    )


@router.put("/{budget_id}", response_model=SupplierBudgetResponse)
async def update_budget(
    budget_id: int,
    data: SupplierBudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a supplier budget"""
    result = await db.execute(
        select(SupplierBudget)
        .options(selectinload(SupplierBudget.supplier), selectinload(SupplierBudget.site))
        .where(SupplierBudget.id == budget_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(budget, key, value)

    await db.commit()
    await db.refresh(budget)

    return SupplierBudgetResponse(
        id=budget.id,
        supplier_id=budget.supplier_id,
        supplier_name=budget.supplier.name if budget.supplier else None,
        site_id=budget.site_id,
        site_name=budget.site.name if budget.site else None,
        year=budget.year,
        yearly_amount=budget.yearly_amount,
        shift=budget.shift or "all",
        jan=budget.jan or 0, feb=budget.feb or 0, mar=budget.mar or 0,
        apr=budget.apr or 0, may=budget.may or 0, jun=budget.jun or 0,
        jul=budget.jul or 0, aug=budget.aug or 0, sep=budget.sep or 0,
        oct=budget.oct or 0, nov=budget.nov or 0, dec=budget.dec or 0,
        notes=budget.notes,
        is_active=budget.is_active,
        product_budgets=[],
    )


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate a supplier budget"""
    result = await db.execute(
        select(SupplierBudget).where(SupplierBudget.id == budget_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    budget.is_active = False
    await db.commit()
    return {"message": "Budget deactivated"}


@router.get("/vs-actual")
async def budget_vs_actual(
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get budget vs actual spending per supplier/site/month"""
    target_year = year or date.today().year

    # Get all budgets for the year
    budget_query = (
        select(SupplierBudget)
        .options(selectinload(SupplierBudget.supplier), selectinload(SupplierBudget.site))
        .where(SupplierBudget.year == target_year, SupplierBudget.is_active == True)
    )
    if site_id:
        budget_query = budget_query.where(SupplierBudget.site_id == site_id)

    budget_result = await db.execute(budget_query)
    budgets = budget_result.scalars().all()

    # Get actual spending from proformas grouped by supplier, site, month
    month_expr = extract_month(Proforma.invoice_date)
    actual_query = (
        select(
            Proforma.supplier_id,
            Proforma.site_id,
            month_expr.label("month"),
            func.sum(Proforma.total_amount).label("total"),
        )
        .where(year_equals(Proforma.invoice_date, target_year))
        .group_by(Proforma.supplier_id, Proforma.site_id, month_expr)
    )
    if site_id:
        actual_query = actual_query.where(Proforma.site_id == site_id)

    actual_result = await db.execute(actual_query)
    actuals = {}
    for row in actual_result:
        key = (row.supplier_id, row.site_id, int(row.month))
        actuals[key] = row.total or 0

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    items = []
    total_budget = 0
    total_actual = 0

    for b in budgets:
        for m_idx, month_col in enumerate(MONTH_COLS):
            month_num = m_idx + 1
            budget_val = getattr(b, month_col) or 0
            actual_val = actuals.get((b.supplier_id, b.site_id, month_num), 0)
            variance = budget_val - actual_val
            percent = (actual_val / budget_val * 100) if budget_val > 0 else 0

            total_budget += budget_val
            total_actual += actual_val

            items.append({
                "supplier_id": b.supplier_id,
                "supplier_name": b.supplier.name if b.supplier else "Unknown",
                "site_id": b.site_id,
                "site_name": b.site.name if b.site else "Unknown",
                "month": month_num,
                "month_name": month_names[m_idx],
                "budget": budget_val,
                "actual": actual_val,
                "variance": variance,
                "percent_used": round(percent, 1),
            })

    return {
        "year": target_year,
        "items": items,
        "totals": {
            "budget": total_budget,
            "actual": total_actual,
            "variance": total_budget - total_actual,
            "percent_used": round(total_actual / total_budget * 100, 1) if total_budget > 0 else 0,
        },
    }


@router.post("/{budget_id}/product-limits", response_model=ProductBudgetResponse)
async def add_product_limit(
    budget_id: int,
    data: ProductBudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a product-level budget limit"""
    result = await db.execute(
        select(SupplierBudget).where(SupplierBudget.id == budget_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Budget not found")

    product_budget = SupplierProductBudget(
        supplier_budget_id=budget_id,
        **data.model_dump()
    )
    db.add(product_budget)
    await db.commit()
    await db.refresh(product_budget)
    return product_budget
