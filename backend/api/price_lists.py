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
import csv
import io
import logging
import os
import re

from backend.database import get_db
from backend.models.user import User
from backend.models.price_list import PriceList, PriceListItem
from backend.models.product import Product
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.api.auth import get_current_user

logger = logging.getLogger(__name__)
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


class PriceListItemUpdate(BaseModel):
    price: Optional[float] = None
    unit: Optional[str] = None


class AddProductToList(BaseModel):
    product_name: str
    price: float
    unit: Optional[str] = None
    hebrew_name: Optional[str] = None
    category: Optional[str] = None


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


# ── Inline item editing ──────────────────────────────────────────────


@router.put("/{price_list_id}/items/{item_id}")
async def update_item(
    price_list_id: int,
    item_id: int,
    data: PriceListItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update price / unit for a single item."""
    result = await db.execute(
        select(PriceListItem).where(
            PriceListItem.id == item_id,
            PriceListItem.price_list_id == price_list_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if data.price is not None:
        item.price = data.price
    if data.unit is not None:
        item.unit = data.unit

    await db.commit()
    await db.refresh(item)
    return {"message": "Item updated", "id": item.id, "price": item.price, "unit": item.unit}


@router.delete("/{price_list_id}/items/{item_id}")
async def delete_item(
    price_list_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a single item from a price list."""
    result = await db.execute(
        select(PriceListItem).where(
            PriceListItem.id == item_id,
            PriceListItem.price_list_id == price_list_id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await db.delete(item)
    await db.commit()
    return {"message": "Item deleted"}


@router.post("/{price_list_id}/add-product")
async def add_product_to_list(
    price_list_id: int,
    data: AddProductToList,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new product (by name) to a price list. Creates the product if it doesn't exist."""
    # Verify price list exists
    pl_result = await db.execute(select(PriceList).where(PriceList.id == price_list_id))
    if not pl_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Price list not found")

    # Try to find an existing product by name
    def normalize(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    catalog_result = await db.execute(select(Product).where(Product.is_active == True))
    catalog = catalog_result.scalars().all()

    product = None
    norm_name = normalize(data.product_name)
    for p in catalog:
        if normalize(p.name) == norm_name or (p.hebrew_name and normalize(p.hebrew_name) == norm_name):
            product = p
            break

    if not product:
        product = Product(
            name=data.product_name,
            hebrew_name=data.hebrew_name,
            category=data.category,
            unit=data.unit,
            is_active=True,
        )
        db.add(product)
        await db.flush()

    # Check for duplicate
    dup_result = await db.execute(
        select(PriceListItem).where(
            PriceListItem.price_list_id == price_list_id,
            PriceListItem.product_id == product.id,
        )
    )
    if dup_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Product already exists in this price list")

    item = PriceListItem(
        price_list_id=price_list_id,
        product_id=product.id,
        price=data.price,
        unit=data.unit or product.unit,
    )
    db.add(item)
    await db.commit()

    return {
        "message": "Product added",
        "item_id": item.id,
        "product_id": product.id,
        "product_name": product.name,
        "price": item.price,
        "unit": item.unit,
    }


# ── CSV / Excel file upload ──────────────────────────────────────────


def _parse_csv_bytes(raw: bytes) -> list[dict]:
    """Parse CSV bytes (UTF-8 or cp1255) into a list of row dicts."""
    for encoding in ("utf-8-sig", "utf-8", "cp1255", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, ValueError):
            continue
    else:
        raise ValueError("Cannot decode file — try UTF-8 or cp1255 encoding")

    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for row in reader:
        # Normalise header keys to lowercase, strip whitespace
        row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        rows.append(row)
    return rows


def _detect_columns(rows: list[dict]) -> tuple[str, str, str | None]:
    """Detect which columns map to product_name, price, and unit."""
    headers = set()
    for r in rows:
        headers.update(r.keys())

    name_candidates = [h for h in headers if any(k in h for k in ("product", "name", "item", "שם", "מוצר", "פריט"))]
    price_candidates = [h for h in headers if any(k in h for k in ("price", "מחיר", "unit_price", "cost", "עלות"))]
    unit_candidates = [h for h in headers if any(k in h for k in ("unit", "יחידה", "uom"))]

    name_col = name_candidates[0] if name_candidates else None
    price_col = price_candidates[0] if price_candidates else None
    unit_col = unit_candidates[0] if unit_candidates else None

    if not name_col or not price_col:
        available = ", ".join(sorted(headers))
        raise ValueError(
            f"Cannot detect product name / price columns. "
            f"Available headers: {available}. "
            f"Expected columns containing: product/name/item and price/cost"
        )

    return name_col, price_col, unit_col


@router.post("/upload")
async def upload_price_list(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    effective_date: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CSV file to create a new price list.
    Expected columns: product name, price, and optionally unit.
    Column detection is automatic (supports English & Hebrew headers).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("csv", "tsv", "txt"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported. Please export your Excel as CSV first.",
        )

    # Verify supplier
    supp_result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = supp_result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    raw = await file.read()
    try:
        rows = _parse_csv_bytes(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or has no data rows")

    try:
        name_col, price_col, unit_col = _detect_columns(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Build product catalog lookup
    catalog_result = await db.execute(select(Product).where(Product.is_active == True))
    catalog = catalog_result.scalars().all()

    def normalize(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    catalog_map: dict[str, Product] = {}
    for p in catalog:
        catalog_map[normalize(p.name)] = p
        if p.hebrew_name:
            catalog_map[normalize(p.hebrew_name)] = p

    # Parse effective date
    eff_date = date.today()
    if effective_date:
        try:
            eff_date = date.fromisoformat(effective_date)
        except ValueError:
            pass

    # Create price list
    price_list = PriceList(
        supplier_id=supplier_id,
        effective_date=eff_date,
        file_path=file.filename,
        notes=f"Uploaded from {file.filename} ({len(rows)} rows)",
    )
    db.add(price_list)
    await db.flush()

    items_created = 0
    products_created = 0
    skipped: list[str] = []

    for row in rows:
        product_name = row.get(name_col, "").strip()
        price_str = row.get(price_col, "").strip()
        unit_val = row.get(unit_col, "").strip() if unit_col else None

        if not product_name or not price_str:
            continue

        # Parse price (handle commas, currency symbols)
        price_str = re.sub(r"[^\d.\-]", "", price_str.replace(",", "."))
        try:
            price_val = float(price_str)
        except ValueError:
            skipped.append(product_name)
            continue

        if price_val <= 0:
            skipped.append(product_name)
            continue

        # Find or create product
        product = catalog_map.get(normalize(product_name))
        if not product:
            product = Product(name=product_name, unit=unit_val, is_active=True)
            db.add(product)
            await db.flush()
            catalog_map[normalize(product_name)] = product
            products_created += 1

        item = PriceListItem(
            price_list_id=price_list.id,
            product_id=product.id,
            price=price_val,
            unit=unit_val or product.unit,
        )
        db.add(item)
        items_created += 1

    await db.commit()

    return {
        "message": f"Price list created with {items_created} products for {supplier.name}",
        "price_list_id": price_list.id,
        "items_count": items_created,
        "new_products_created": products_created,
        "skipped": skipped[:10],
        "file_name": file.filename,
    }
