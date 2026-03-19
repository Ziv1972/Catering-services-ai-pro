"""
Proformas (invoices) API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, timedelta
from pydantic import BaseModel
import csv
import io
import logging

from backend.database import get_db
from backend.models.user import User
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.models.price_list import PriceList, PriceListItem
from backend.models.product import Product
from backend.api.auth import get_current_user

logger = logging.getLogger(__name__)

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
        .options(selectinload(Proforma.supplier), selectinload(Proforma.items))
        .where(Proforma.invoice_date >= cutoff)
    )

    if supplier_id:
        query = query.where(Proforma.supplier_id == supplier_id)
    if site_id:
        query = query.where(Proforma.site_id == site_id)

    query = query.order_by(Proforma.invoice_date.desc())

    result = await db.execute(query)
    proformas = result.scalars().all()

    response = []
    for p in proformas:
        flagged_count = sum(1 for item in (p.items or []) if item.flagged)
        item_count = len(p.items or [])
        resp = {
            "id": p.id,
            "supplier_id": p.supplier_id,
            "supplier_name": p.supplier.name if p.supplier else None,
            "site_id": p.site_id,
            "proforma_number": p.proforma_number,
            "invoice_date": p.invoice_date.isoformat(),
            "delivery_date": p.delivery_date.isoformat() if p.delivery_date else None,
            "total_amount": p.total_amount,
            "currency": p.currency,
            "status": p.status,
            "notes": p.notes,
            "item_count": item_count,
            "flagged_count": flagged_count,
        }
        response.append(resp)

    return response


# ── File Upload (XLSX + CSV) ──────────────────────────────────────────


def _parse_proforma_csv(raw: bytes) -> list[dict]:
    """Parse CSV bytes into row dicts. Tries multiple encodings."""
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1255", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise ValueError("Cannot decode file — try UTF-8 or cp1255 encoding")

    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for row in reader:
        cleaned = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        rows.append(cleaned)
    return rows


def _parse_proforma_xlsx(raw: bytes) -> list[dict]:
    """Parse XLSX bytes into row dicts using openpyxl."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("Excel file has no active sheet")

    rows_iter = ws.iter_rows(values_only=True)

    # First row = headers
    header_row = next(rows_iter, None)
    if header_row is None:
        raise ValueError("Excel file is empty")

    headers = [str(h).strip().lower() if h is not None else f"col_{i}" for i, h in enumerate(header_row)]

    rows: list[dict] = []
    for row in rows_iter:
        # Skip completely empty rows
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        cleaned = {}
        for i, cell in enumerate(row):
            if i < len(headers):
                cleaned[headers[i]] = str(cell).strip() if cell is not None else ""
        rows.append(cleaned)

    wb.close()
    return rows


def _detect_proforma_columns(headers: list[str]) -> tuple[str | None, str | None, str | None, str | None]:
    """Auto-detect product_name, quantity, unit, unit_price columns from headers."""
    name_col = None
    qty_col = None
    unit_col = None
    price_col = None

    name_keywords = ["product", "item", "name", "description", "מוצר", "שם", "פריט", "תיאור"]
    qty_keywords = ["quantity", "qty", "amount", "count", "כמות"]
    unit_keywords = ["unit", "uom", "measure", "יחידה", "יח"]
    price_keywords = ["price", "cost", "rate", "מחיר", "עלות", "תעריף", "סכום"]

    for h in headers:
        hl = h.lower().strip()
        if not name_col and any(k in hl for k in name_keywords):
            name_col = h
        elif not qty_col and any(k in hl for k in qty_keywords):
            qty_col = h
        elif not price_col and any(k in hl for k in price_keywords):
            price_col = h
        elif not unit_col and any(k in hl for k in unit_keywords):
            unit_col = h

    return name_col, qty_col, unit_col, price_col


@router.post("/upload")
async def upload_proforma(
    file: UploadFile = File(...),
    supplier_id: int = Form(...),
    site_id: int = Form(None),
    invoice_date: str = Form(None),
    proforma_number: str = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an XLSX or CSV file to create a proforma with line items."""
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("xlsx", "xls", "csv", "tsv", "txt"):
        raise HTTPException(
            status_code=400,
            detail="Supported formats: Excel (.xlsx) or CSV (.csv)",
        )

    # Verify supplier exists
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    raw = await file.read()
    try:
        if ext in ("xlsx", "xls"):
            rows = _parse_proforma_xlsx(raw)
        else:
            rows = _parse_proforma_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=400, detail="File is empty or has no data rows")

    # Detect columns
    headers = list(rows[0].keys())
    name_col, qty_col, unit_col, price_col = _detect_proforma_columns(headers)

    if not name_col:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect product name column. Headers found: {headers}",
        )
    if not price_col and not qty_col:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect quantity or price columns. Headers found: {headers}",
        )

    # Parse invoice date
    inv_date = date.today()
    if invoice_date:
        try:
            inv_date = date.fromisoformat(invoice_date)
        except ValueError:
            pass

    # Create proforma
    proforma = Proforma(
        supplier_id=supplier_id,
        site_id=site_id,
        proforma_number=proforma_number or None,
        invoice_date=inv_date,
        total_amount=0,
        currency="ILS",
        status="pending",
        notes=f"Uploaded from {file.filename}",
    )
    db.add(proforma)
    await db.flush()

    # Parse items
    items_created = 0
    skipped = 0
    total_amount = 0.0

    for row in rows:
        product_name = row.get(name_col, "").strip()
        if not product_name:
            skipped += 1
            continue

        # Parse quantity
        quantity = 1.0
        if qty_col and row.get(qty_col):
            try:
                quantity = float(row[qty_col].replace(",", ""))
            except (ValueError, AttributeError):
                quantity = 1.0

        # Parse unit price
        unit_price = 0.0
        if price_col and row.get(price_col):
            try:
                unit_price = float(row[price_col].replace(",", "").replace("₪", "").strip())
            except (ValueError, AttributeError):
                unit_price = 0.0

        # Parse unit
        unit = "unit"
        if unit_col and row.get(unit_col):
            unit = row[unit_col].strip() or "unit"

        total_price = quantity * unit_price
        total_amount += total_price

        item = ProformaItem(
            proforma_id=proforma.id,
            product_name=product_name,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            total_price=total_price,
            flagged=False,
        )
        db.add(item)
        items_created += 1

    proforma.total_amount = total_amount
    await db.commit()
    await db.refresh(proforma)

    return {
        "id": proforma.id,
        "supplier_id": proforma.supplier_id,
        "supplier_name": supplier.name,
        "invoice_date": proforma.invoice_date.isoformat(),
        "total_amount": round(proforma.total_amount, 2),
        "items_created": items_created,
        "skipped": skipped,
        "status": "pending",
        "message": f"Created proforma with {items_created} items from {file.filename}",
    }


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


def _normalize_product_name(name: str) -> str:
    """Normalize product name for matching (lowercase, stripped)."""
    return name.strip().lower()


@router.post("/{proforma_id}/compare-prices")
async def compare_proforma_prices(
    proforma_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compare proforma items against the supplier's latest price list.
    Updates price_variance and flagged fields on each ProformaItem.
    Returns the comparison results.
    """
    # Load the proforma with items
    result = await db.execute(
        select(Proforma)
        .options(selectinload(Proforma.items), selectinload(Proforma.supplier))
        .where(Proforma.id == proforma_id)
    )
    proforma = result.scalar_one_or_none()
    if not proforma:
        raise HTTPException(status_code=404, detail="Proforma not found")

    # Find the latest price list for this supplier (effective_date <= proforma date)
    pl_result = await db.execute(
        select(PriceList)
        .options(selectinload(PriceList.items).selectinload(PriceListItem.product))
        .where(
            PriceList.supplier_id == proforma.supplier_id,
            PriceList.effective_date <= proforma.invoice_date,
        )
        .order_by(PriceList.effective_date.desc())
        .limit(1)
    )
    price_list = pl_result.scalar_one_or_none()

    # If no price list before invoice date, try the latest one for this supplier
    if not price_list:
        pl_result = await db.execute(
            select(PriceList)
            .options(selectinload(PriceList.items).selectinload(PriceListItem.product))
            .where(PriceList.supplier_id == proforma.supplier_id)
            .order_by(PriceList.effective_date.desc())
            .limit(1)
        )
        price_list = pl_result.scalar_one_or_none()

    if not price_list:
        return {
            "proforma_id": proforma_id,
            "price_list_id": None,
            "price_list_date": None,
            "message": "No price list found for this supplier",
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "expected_price": None,
                    "price_variance": None,
                    "flagged": False,
                    "match_status": "no_price_list",
                }
                for item in proforma.items
            ],
            "summary": {"total_items": len(proforma.items), "matched": 0, "flagged": 0, "unmatched": len(proforma.items)},
        }

    # Build lookup: product name (normalized) → expected price
    price_lookup: dict[str, float] = {}
    for pl_item in price_list.items:
        if pl_item.product:
            price_lookup[_normalize_product_name(pl_item.product.name)] = pl_item.price
            if pl_item.product.hebrew_name:
                price_lookup[_normalize_product_name(pl_item.product.hebrew_name)] = pl_item.price

    # Compare each proforma item
    comparison_items = []
    matched_count = 0
    flagged_count = 0
    variance_threshold = 5.0  # flag if > 5% variance

    for item in proforma.items:
        normalized_name = _normalize_product_name(item.product_name)
        expected_price = price_lookup.get(normalized_name)

        if expected_price is not None:
            matched_count += 1
            variance_pct = round(
                ((item.unit_price - expected_price) / expected_price) * 100, 1
            ) if expected_price > 0 else 0.0

            is_flagged = abs(variance_pct) > variance_threshold

            # Update the item in DB
            item.price_variance = variance_pct
            item.flagged = is_flagged

            if is_flagged:
                flagged_count += 1

            comparison_items.append({
                "id": item.id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": round(item.unit_price, 2),
                "total_price": round(item.total_price, 2),
                "expected_price": round(expected_price, 2),
                "price_variance": variance_pct,
                "flagged": is_flagged,
                "match_status": "matched",
            })
        else:
            # No match found in price list
            item.price_variance = None
            item.flagged = False
            comparison_items.append({
                "id": item.id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": round(item.unit_price, 2),
                "total_price": round(item.total_price, 2),
                "expected_price": None,
                "price_variance": None,
                "flagged": False,
                "match_status": "unmatched",
            })

    await db.commit()

    # Sort: flagged first, then by absolute variance
    comparison_items.sort(
        key=lambda x: (
            0 if x["flagged"] else 1,
            -(abs(x["price_variance"]) if x["price_variance"] is not None else 0),
        )
    )

    return {
        "proforma_id": proforma_id,
        "price_list_id": price_list.id,
        "price_list_date": price_list.effective_date.isoformat(),
        "supplier_name": proforma.supplier.name if proforma.supplier else None,
        "items": comparison_items,
        "summary": {
            "total_items": len(comparison_items),
            "matched": matched_count,
            "flagged": flagged_count,
            "unmatched": len(comparison_items) - matched_count,
        },
    }
