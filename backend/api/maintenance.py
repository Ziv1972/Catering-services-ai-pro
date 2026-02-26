"""
Maintenance budget API endpoints - quarterly budget tracking and expense management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.maintenance import MaintenanceBudget, MaintenanceExpense
from backend.api.auth import get_current_user
from backend.utils.db_compat import year_equals, month_between

router = APIRouter()


# --- Pydantic Schemas ---

class MaintenanceBudgetResponse(BaseModel):
    id: int
    site_id: int
    site_name: Optional[str] = None
    year: int
    quarter: int
    budget_amount: float
    actual_amount: float = 0
    notes: Optional[str]

    class Config:
        from_attributes = True


class MaintenanceBudgetCreate(BaseModel):
    site_id: int
    year: int
    quarter: int
    budget_amount: float
    notes: Optional[str] = None


class MaintenanceBudgetUpdate(BaseModel):
    budget_amount: Optional[float] = None
    notes: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: int
    site_id: int
    site_name: Optional[str] = None
    maintenance_budget_id: Optional[int]
    date: date
    description: str
    amount: float
    category: str
    vendor: Optional[str]
    receipt_reference: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    site_id: int
    maintenance_budget_id: Optional[int] = None
    date: date
    description: str
    amount: float
    category: str = "general"
    vendor: Optional[str] = None
    receipt_reference: Optional[str] = None
    notes: Optional[str] = None


class ExpenseUpdate(BaseModel):
    date: Optional[date] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    receipt_reference: Optional[str] = None
    notes: Optional[str] = None


# --- Budget Endpoints ---

@router.get("/budgets", response_model=List[MaintenanceBudgetResponse])
async def list_budgets(
    site_id: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List maintenance budgets with actual spending"""
    query = (
        select(MaintenanceBudget)
        .options(selectinload(MaintenanceBudget.site), selectinload(MaintenanceBudget.expenses))
        .order_by(MaintenanceBudget.year.desc(), MaintenanceBudget.quarter)
    )
    if site_id:
        query = query.where(MaintenanceBudget.site_id == site_id)
    if year:
        query = query.where(MaintenanceBudget.year == year)

    result = await db.execute(query)
    budgets = result.scalars().all()

    return [
        MaintenanceBudgetResponse(
            id=b.id,
            site_id=b.site_id,
            site_name=b.site.name if b.site else None,
            year=b.year,
            quarter=b.quarter,
            budget_amount=b.budget_amount,
            actual_amount=sum(e.amount for e in b.expenses) if b.expenses else 0,
            notes=b.notes,
        )
        for b in budgets
    ]


@router.post("/budgets", response_model=MaintenanceBudgetResponse)
async def create_budget(
    data: MaintenanceBudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a quarterly maintenance budget"""
    budget = MaintenanceBudget(**data.model_dump())
    db.add(budget)
    await db.commit()
    await db.refresh(budget)

    result = await db.execute(
        select(MaintenanceBudget)
        .options(selectinload(MaintenanceBudget.site))
        .where(MaintenanceBudget.id == budget.id)
    )
    budget = result.scalar_one()

    return MaintenanceBudgetResponse(
        id=budget.id,
        site_id=budget.site_id,
        site_name=budget.site.name if budget.site else None,
        year=budget.year,
        quarter=budget.quarter,
        budget_amount=budget.budget_amount,
        actual_amount=0,
        notes=budget.notes,
    )


@router.put("/budgets/{budget_id}", response_model=MaintenanceBudgetResponse)
async def update_budget(
    budget_id: int,
    data: MaintenanceBudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a maintenance budget"""
    result = await db.execute(
        select(MaintenanceBudget)
        .options(selectinload(MaintenanceBudget.site), selectinload(MaintenanceBudget.expenses))
        .where(MaintenanceBudget.id == budget_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(budget, key, value)

    await db.commit()
    await db.refresh(budget)

    return MaintenanceBudgetResponse(
        id=budget.id,
        site_id=budget.site_id,
        site_name=budget.site.name if budget.site else None,
        year=budget.year,
        quarter=budget.quarter,
        budget_amount=budget.budget_amount,
        actual_amount=sum(e.amount for e in budget.expenses) if budget.expenses else 0,
        notes=budget.notes,
    )


# --- Expense Endpoints ---

@router.get("/expenses", response_model=List[ExpenseResponse])
async def list_expenses(
    site_id: Optional[int] = None,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List maintenance expenses"""
    query = (
        select(MaintenanceExpense)
        .options(selectinload(MaintenanceExpense.site))
        .order_by(MaintenanceExpense.date.desc())
    )
    if site_id:
        query = query.where(MaintenanceExpense.site_id == site_id)
    if year:
        query = query.where(year_equals(MaintenanceExpense.date, year))
    if quarter and year:
        q_start_month = (quarter - 1) * 3 + 1
        q_end_month = quarter * 3
        query = query.where(month_between(MaintenanceExpense.date, q_start_month, q_end_month))
    if category:
        query = query.where(MaintenanceExpense.category == category)

    result = await db.execute(query)
    expenses = result.scalars().all()

    return [
        ExpenseResponse(
            id=e.id,
            site_id=e.site_id,
            site_name=e.site.name if e.site else None,
            maintenance_budget_id=e.maintenance_budget_id,
            date=e.date,
            description=e.description,
            amount=e.amount,
            category=e.category,
            vendor=e.vendor,
            receipt_reference=e.receipt_reference,
            notes=e.notes,
        )
        for e in expenses
    ]


@router.post("/expenses", response_model=ExpenseResponse)
async def create_expense(
    data: ExpenseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a maintenance expense"""
    expense = MaintenanceExpense(**data.model_dump(exclude_none=True))
    db.add(expense)
    await db.commit()
    await db.refresh(expense)

    result = await db.execute(
        select(MaintenanceExpense)
        .options(selectinload(MaintenanceExpense.site))
        .where(MaintenanceExpense.id == expense.id)
    )
    expense = result.scalar_one()

    return ExpenseResponse(
        id=expense.id,
        site_id=expense.site_id,
        site_name=expense.site.name if expense.site else None,
        maintenance_budget_id=expense.maintenance_budget_id,
        date=expense.date,
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        vendor=expense.vendor,
        receipt_reference=expense.receipt_reference,
        notes=expense.notes,
    )


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a maintenance expense"""
    result = await db.execute(
        select(MaintenanceExpense)
        .options(selectinload(MaintenanceExpense.site))
        .where(MaintenanceExpense.id == expense_id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(expense, key, value)

    await db.commit()
    await db.refresh(expense)

    return ExpenseResponse(
        id=expense.id,
        site_id=expense.site_id,
        site_name=expense.site.name if expense.site else None,
        maintenance_budget_id=expense.maintenance_budget_id,
        date=expense.date,
        description=expense.description,
        amount=expense.amount,
        category=expense.category,
        vendor=expense.vendor,
        receipt_reference=expense.receipt_reference,
        notes=expense.notes,
    )


@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a maintenance expense"""
    result = await db.execute(
        select(MaintenanceExpense).where(MaintenanceExpense.id == expense_id)
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    await db.delete(expense)
    await db.commit()
    return {"message": "Expense deleted"}


@router.get("/summary")
async def maintenance_summary(
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get maintenance budget vs actual summary"""
    target_year = year or date.today().year

    result = await db.execute(
        select(MaintenanceBudget)
        .options(selectinload(MaintenanceBudget.site), selectinload(MaintenanceBudget.expenses))
        .where(MaintenanceBudget.year == target_year)
        .order_by(MaintenanceBudget.site_id, MaintenanceBudget.quarter)
    )
    budgets = result.scalars().all()

    summary = []
    for b in budgets:
        actual = sum(e.amount for e in b.expenses) if b.expenses else 0
        summary.append({
            "id": b.id,
            "site_id": b.site_id,
            "site_name": b.site.name if b.site else None,
            "quarter": b.quarter,
            "budget": b.budget_amount,
            "actual": actual,
            "remaining": b.budget_amount - actual,
            "percent_used": round(actual / b.budget_amount * 100, 1) if b.budget_amount > 0 else 0,
        })

    return {"year": target_year, "quarters": summary}
