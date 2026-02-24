"""
Suppliers API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import date
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.supplier import Supplier
from backend.api.auth import get_current_user

router = APIRouter()


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    contract_start_date: Optional[date]
    contract_end_date: Optional[date]
    payment_terms: Optional[str]
    notes: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class SupplierCreate(BaseModel):
    name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    contract_start_date: Optional[date] = None
    contract_end_date: Optional[date] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=List[SupplierResponse])
async def list_suppliers(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all suppliers"""
    query = select(Supplier).order_by(Supplier.name)
    if active_only:
        query = query.where(Supplier.is_active == True)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single supplier"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("/", response_model=SupplierResponse)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new supplier"""
    supplier = Supplier(**data.model_dump(exclude_none=True), is_active=True)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    data: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a supplier"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(supplier, key, value)

    await db.commit()
    await db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deactivate a supplier (soft delete)"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    supplier.is_active = False
    await db.commit()
    return {"message": "Supplier deactivated"}
