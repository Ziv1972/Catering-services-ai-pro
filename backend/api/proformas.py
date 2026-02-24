"""
Proformas (invoices) API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, timedelta
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.api.auth import get_current_user

router = APIRouter()


class ProformaItemResponse(BaseModel):
    id: int
    product_name: str
    quantity: float
    unit: Optional[str]
    unit_price: float
    total_price: float
    price_variance: Optional[float]
    flagged: bool

    class Config:
        from_attributes = True


class ProformaResponse(BaseModel):
    id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    site_id: Optional[int]
    proforma_number: Optional[str]
    invoice_date: date
    delivery_date: Optional[date]
    total_amount: float
    currency: str
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ProformaResponse])
async def list_proformas(
    months: int = Query(6, ge=1, le=24),
    supplier_id: Optional[int] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List proformas with filters"""
    cutoff = date.today() - timedelta(days=months * 30)

    query = (
        select(Proforma)
        .options(selectinload(Proforma.supplier))
        .where(Proforma.invoice_date >= cutoff)
    )

    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    query = query.order_by(Proforma.invoice_date.desc())

    result = await db.execute(query)
    proformas = result.scalars().all()

    return [
        ProformaResponse(
            id=p.id,
            supplier_id=p.supplier_id,
            supplier_name=p.supplier.name if p.supplier else None,
            site_id=p.site_id,
            proforma_number=p.proforma_number,
            invoice_date=p.invoice_date,
            delivery_date=p.delivery_date,
            total_amount=p.total_amount,
            currency=p.currency,
            status=p.status,
            notes=p.notes,
        )
        for p in proformas
    ]


@router.get("/{proforma_id}")
async def get_proforma(
    proforma_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single proforma with items"""
    result = await db.execute(
        select(Proforma)
        .options(
            selectinload(Proforma.supplier),
            selectinload(Proforma.site),
            selectinload(Proforma.items),
        )
        .where(Proforma.id == proforma_id)
    )
    proforma = result.scalar_one_or_none()

    if not proforma:
        raise HTTPException(status_code=404, detail="Proforma not found")

    return {
        "id": proforma.id,
        "supplier_name": proforma.supplier.name if proforma.supplier else None,
        "site_name": proforma.site.name if proforma.site else None,
        "proforma_number": proforma.proforma_number,
        "invoice_date": proforma.invoice_date.isoformat(),
        "delivery_date": proforma.delivery_date.isoformat() if proforma.delivery_date else None,
        "total_amount": proforma.total_amount,
        "currency": proforma.currency,
        "status": proforma.status,
        "notes": proforma.notes,
        "items": [
            {
                "id": item.id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "price_variance": item.price_variance,
                "flagged": item.flagged,
            }
            for item in proforma.items
        ],
    }


@router.get("/{proforma_id}/items", response_model=List[ProformaItemResponse])
async def get_proforma_items(
    proforma_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get items for a proforma"""
    result = await db.execute(
        select(ProformaItem).where(ProformaItem.proforma_id == proforma_id)
    )
    return result.scalars().all()


class ProformaItemCreate(BaseModel):
    product_name: str
    quantity: float
    unit: Optional[str] = None
    unit_price: float


class ProformaCreate(BaseModel):
    supplier_id: int
    site_id: Optional[int] = None
    proforma_number: Optional[str] = None
    invoice_date: date
    delivery_date: Optional[date] = None
    currency: str = "ILS"
    status: str = "pending"
    notes: Optional[str] = None
    items: List[ProformaItemCreate] = []


@router.post("/", response_model=ProformaResponse)
async def create_proforma(
    data: ProformaCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new proforma with items"""
    result = await db.execute(
        select(Supplier).where(Supplier.id == data.supplier_id)
    )
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    total_amount = sum(item.quantity * item.unit_price for item in data.items)

    proforma = Proforma(
        supplier_id=data.supplier_id,
        site_id=data.site_id,
        proforma_number=data.proforma_number,
        invoice_date=data.invoice_date,
        delivery_date=data.delivery_date,
        total_amount=total_amount,
        currency=data.currency,
        status=data.status,
        notes=data.notes,
    )
    db.add(proforma)
    await db.flush()

    for item_data in data.items:
        item = ProformaItem(
            proforma_id=proforma.id,
            product_name=item_data.product_name,
            quantity=item_data.quantity,
            unit=item_data.unit,
            unit_price=item_data.unit_price,
            total_price=item_data.quantity * item_data.unit_price,
            flagged=False,
        )
        db.add(item)

    await db.commit()
    await db.refresh(proforma)

    return ProformaResponse(
        id=proforma.id,
        supplier_id=proforma.supplier_id,
        supplier_name=supplier.name,
        site_id=proforma.site_id,
        proforma_number=proforma.proforma_number,
        invoice_date=proforma.invoice_date,
        delivery_date=proforma.delivery_date,
        total_amount=proforma.total_amount,
        currency=proforma.currency,
        status=proforma.status,
        notes=proforma.notes,
    )


@router.get("/vendor-spending/summary")
async def get_vendor_spending(
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get vendor spending summary with monthly breakdown"""
    cutoff = date.today() - timedelta(days=months * 30)

    # Get all proformas with supplier info
    result = await db.execute(
        select(Proforma)
        .options(selectinload(Proforma.supplier))
        .where(Proforma.invoice_date >= cutoff)
        .order_by(Proforma.invoice_date.asc())
    )
    proformas = result.scalars().all()

    # Group by supplier, then by month
    vendor_data: dict = {}
    monthly_totals: dict = {}

    for p in proformas:
        supplier_name = p.supplier.name if p.supplier else "Unknown"
        month_key = p.invoice_date.strftime("%Y-%m")

        if supplier_name not in vendor_data:
            vendor_data[supplier_name] = {}
        vendor_data[supplier_name][month_key] = (
            vendor_data[supplier_name].get(month_key, 0) + p.total_amount
        )

        monthly_totals[month_key] = monthly_totals.get(month_key, 0) + p.total_amount

    # Build monthly series with moving average
    sorted_months = sorted(monthly_totals.keys())
    monthly_series = []
    running_values: list[float] = []

    for month in sorted_months:
        total = monthly_totals[month]
        running_values.append(total)

        # 3-month moving average
        window = running_values[-3:] if len(running_values) >= 3 else running_values
        ma = sum(window) / len(window)

        monthly_series.append({
            "month": month,
            "total": round(total, 2),
            "moving_avg": round(ma, 2),
        })

    # Per-vendor totals
    vendor_totals = []
    for name, months_data in vendor_data.items():
        total = sum(months_data.values())
        vendor_totals.append({
            "supplier": name,
            "total": round(total, 2),
            "months": {k: round(v, 2) for k, v in sorted(months_data.items())},
        })

    vendor_totals.sort(key=lambda x: x["total"], reverse=True)

    return {
        "monthly_series": monthly_series,
        "vendor_totals": vendor_totals,
        "grand_total": round(sum(monthly_totals.values()), 2),
    }
