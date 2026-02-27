"""
Price list API endpoints - supplier price management
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date
from pydantic import BaseModel
import os
import re

from backend.database import get_db
from backend.models.user import User
from backend.models.price_list import PriceList, PriceListItem
from backend.models.product import Product
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.api.auth import get_current_user

router = APIRouter()


class PriceListItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    price: float
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class PriceListResponse(BaseModel):
    id: int
    supplier_id: int
    supplier_name: Optional[str] = None
    effective_date: date
    file_path: Optional[str] = None
    notes: Optional[str] = None
    item_count: int = 0
    items: List[PriceListItemResponse] = []

    class Config:
        from_attributes = True


class PriceListCreate(BaseModel):
    supplier_id: int
    effective_date: date
    notes: Optional[str] = None


class PriceListItemCreate(BaseModel):
    product_id: int
    price: float
    unit: Optional[str] = None


class PriceListItemBulkCreate(BaseModel):
    items: List[PriceListItemCreate]


@router.get("/", response_model=List[PriceListResponse])
async def list_price_lists(
    supplier_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all price lists, optionally filtered by supplier."""
    query = (
        select(PriceList)
        .options(selectinload(PriceList.supplier), selectinload(PriceList.items))
        .order_by(PriceList.effective_date.desc())
    )
    if supplier_id:
        query = query.where(PriceList.supplier_id == supplier_id)

    result = await db.execute(query)
    price_lists = result.scalars().all()

    return [
        PriceListResponse(
            id=pl.id,
            supplier_id=pl.supplier_id,
            supplier_name=pl.supplier.name if pl.supplier else None,
            effective_date=pl.effective_date,
            file_path=pl.file_path,
            notes=pl.notes,
            item_count=len(pl.items) if pl.items else 0,
            items=[],
        )
        for pl in price_lists
    ]


@router.post("/generate-from-proformas")
async def generate_price_list_from_proformas(
    supplier_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Auto-generate a price list from proforma/invoice data.
    Extracts the latest unit price for each product from proforma items.
    """
    # Verify supplier exists
    supp_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = supp_result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Get all proforma items for this supplier, ordered by invoice date desc
    # so we can pick the latest price for each product
    items_q = (
        select(
            ProformaItem.product_name,
            ProformaItem.unit_price,
            ProformaItem.unit,
            ProformaItem.product_id,
            Proforma.invoice_date,
        )
        .join(Proforma, ProformaItem.proforma_id == Proforma.id)
        .where(Proforma.supplier_id == supplier_id)
        .order_by(Proforma.invoice_date.desc())
    )
    result = await db.execute(items_q)
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No proforma data found for this supplier"
        )

    # Build latest price per product (first occurrence = most recent)
    def normalize(name: str) -> str:
        return re.sub(r'\s+', ' ', name.strip().lower())

    seen: dict[str, dict] = {}
    for row in rows:
        key = normalize(row.product_name)
        if key not in seen:
            seen[key] = {
                "product_name": row.product_name,
                "unit_price": row.unit_price,
                "unit": row.unit,
                "product_id": row.product_id,
                "invoice_date": row.invoice_date,
            }

    # Match product names to catalog products
    catalog_result = await db.execute(select(Product).where(Product.is_active == True))
    catalog = catalog_result.scalars().all()
    catalog_map: dict[str, Product] = {}
    for p in catalog:
        catalog_map[normalize(p.name)] = p
        if p.hebrew_name:
            catalog_map[normalize(p.hebrew_name)] = p

    # Determine effective date: latest proforma invoice date
    latest_date = max(info["invoice_date"] for info in seen.values())

    # Create the price list
    price_list = PriceList(
        supplier_id=supplier_id,
        effective_date=latest_date,
        notes=f"Auto-generated from proforma data ({len(seen)} products)",
    )
    db.add(price_list)
    await db.flush()

    # Create items
    items_created = 0
    unmatched_products: list[str] = []
    for key, info in seen.items():
        # Try to find product in catalog by name match
        product = catalog_map.get(key)
        product_id = info["product_id"] or (product.id if product else None)

        if not product_id:
            # Try to create a new product in the catalog
            new_product = Product(
                name=info["product_name"],
                unit=info["unit"],
                is_active=True,
            )
            db.add(new_product)
            await db.flush()
            product_id = new_product.id
            unmatched_products.append(info["product_name"])

        item = PriceListItem(
            price_list_id=price_list.id,
            product_id=product_id,
            price=info["unit_price"],
            unit=info["unit"],
        )
        db.add(item)
        items_created += 1

    await db.commit()

    return {
        "message": f"Generated price list with {items_created} products for {supplier.name}",
        "price_list_id": price_list.id,
        "supplier_name": supplier.name,
        "effective_date": latest_date.isoformat(),
        "items_count": items_created,
        "new_products_created": unmatched_products,
    }


@router.get("/{price_list_id}")
async def get_price_list(
    price_list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a price list with all items."""
    result = await db.execute(
        select(PriceList)
        .options(
            selectinload(PriceList.supplier),
            selectinload(PriceList.items).selectinload(PriceListItem.product),
        )
        .where(PriceList.id == price_list_id)
    )
    pl = result.scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")

    return {
        "id": pl.id,
        "supplier_id": pl.supplier_id,
        "supplier_name": pl.supplier.name if pl.supplier else None,
        "effective_date": pl.effective_date.isoformat(),
        "file_path": pl.file_path,
        "notes": pl.notes,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product.name if item.product else None,
                "hebrew_name": item.product.hebrew_name if item.product else None,
                "category": item.product.category if item.product else None,
                "price": item.price,
                "unit": item.unit or (item.product.unit if item.product else None),
            }
            for item in (pl.items or [])
        ],
    }


@router.post("/", response_model=PriceListResponse)
async def create_price_list(
    data: PriceListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new price list."""
    pl = PriceList(
        supplier_id=data.supplier_id,
        effective_date=data.effective_date,
        notes=data.notes,
    )
    db.add(pl)
    await db.commit()
    await db.refresh(pl)

    result = await db.execute(
        select(PriceList)
        .options(selectinload(PriceList.supplier))
        .where(PriceList.id == pl.id)
    )
    pl = result.scalar_one()

    return PriceListResponse(
        id=pl.id,
        supplier_id=pl.supplier_id,
        supplier_name=pl.supplier.name if pl.supplier else None,
        effective_date=pl.effective_date,
        notes=pl.notes,
        item_count=0,
        items=[],
    )


@router.post("/{price_list_id}/items")
async def add_items(
    price_list_id: int,
    data: PriceListItemBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add items to a price list."""
    result = await db.execute(
        select(PriceList).where(PriceList.id == price_list_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Price list not found")

    created = []
    for item_data in data.items:
        item = PriceListItem(
            price_list_id=price_list_id,
            product_id=item_data.product_id,
            price=item_data.price,
            unit=item_data.unit,
        )
        db.add(item)
        created.append(item)

    await db.commit()
    return {"message": f"Added {len(created)} items", "count": len(created)}


@router.delete("/{price_list_id}")
async def delete_price_list(
    price_list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a price list and its items."""
    result = await db.execute(
        select(PriceList).where(PriceList.id == price_list_id)
    )
    pl = result.scalar_one_or_none()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")

    await db.delete(pl)
    await db.commit()
    return {"message": "Price list deleted"}


@router.get("/products/catalog")
async def get_product_catalog(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the product catalog for price list item selection."""
    query = select(Product).where(Product.is_active == True).order_by(Product.name)
    if category:
        query = query.where(Product.category == category)

    result = await db.execute(query)
    products = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "hebrew_name": p.hebrew_name,
            "category": p.category,
            "unit": p.unit,
        }
        for p in products
    ]


@router.get("/products/categories")
async def get_product_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get distinct product categories."""
    result = await db.execute(
        select(Product.category)
        .where(Product.is_active == True, Product.category.isnot(None))
        .distinct()
        .order_by(Product.category)
    )
    return [row[0] for row in result]


@router.get("/compare")
async def compare_price_lists(
    price_list_id_1: int,
    price_list_id_2: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare two price lists to show price changes."""
    items_1_result = await db.execute(
        select(PriceListItem)
        .options(selectinload(PriceListItem.product))
        .where(PriceListItem.price_list_id == price_list_id_1)
    )
    items_2_result = await db.execute(
        select(PriceListItem)
        .options(selectinload(PriceListItem.product))
        .where(PriceListItem.price_list_id == price_list_id_2)
    )

    prices_1 = {item.product_id: item for item in items_1_result.scalars().all()}
    prices_2 = {item.product_id: item for item in items_2_result.scalars().all()}

    all_product_ids = set(prices_1.keys()) | set(prices_2.keys())
    comparisons = []

    for pid in all_product_ids:
        item1 = prices_1.get(pid)
        item2 = prices_2.get(pid)
        old_price = item1.price if item1 else None
        new_price = item2.price if item2 else None
        product_name = (item1 or item2).product.name if (item1 or item2).product else f"Product #{pid}"

        change = None
        change_pct = None
        if old_price and new_price:
            change = new_price - old_price
            change_pct = round(change / old_price * 100, 1) if old_price > 0 else 0

        comparisons.append({
            "product_id": pid,
            "product_name": product_name,
            "old_price": old_price,
            "new_price": new_price,
            "change": change,
            "change_percent": change_pct,
            "status": "increased" if change and change > 0 else "decreased" if change and change < 0 else "unchanged" if change == 0 else "new" if not old_price else "removed",
        })

    comparisons.sort(key=lambda x: abs(x.get("change_percent") or 0), reverse=True)

    return {
        "comparisons": comparisons,
        "summary": {
            "total_products": len(comparisons),
            "increased": sum(1 for c in comparisons if c["status"] == "increased"),
            "decreased": sum(1 for c in comparisons if c["status"] == "decreased"),
            "unchanged": sum(1 for c in comparisons if c["status"] == "unchanged"),
            "new": sum(1 for c in comparisons if c["status"] == "new"),
            "removed": sum(1 for c in comparisons if c["status"] == "removed"),
        }
    }
