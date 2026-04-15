"""
Vending machines (מ.א אוטומטים) endpoints.

Two input sources per monthly invoice:
- PDF invoice  → creates Proforma + ProformaItems (8 categories @ unit prices)
- Excel detail → creates VendingTransaction rows (per-day / per-product / per-qty)

Dashboard reads totals from Proforma (budget vs actual).
/analytics page reads drill-down detail from VendingTransaction.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.database import get_db
from backend.models.proforma import Proforma, ProformaItem
from backend.models.supplier import Supplier
from backend.models.user import User
from backend.models.vending_transaction import VendingTransaction
from backend.utils.db_compat import year_equals, month_equals

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vending", tags=["vending"])

VENDING_SUPPLIER_NAME = "מ.א אוטומטים"


# ── Helpers ─────────────────────────────────────────────────────────────

def _reverse_hebrew_if_rtl(s: str) -> str:
    """pdfplumber often returns Hebrew reversed — reverse when detected."""
    if not s:
        return s
    # Heuristic: if the first Hebrew char is a final-form letter, text is reversed
    hebrew = [c for c in s if '\u0590' <= c <= '\u05FF']
    if hebrew and hebrew[0] in "ךםןףץ":
        return s[::-1]
    return s


async def _get_vending_supplier(db: AsyncSession) -> Supplier:
    result = await db.execute(select(Supplier).where(Supplier.name == VENDING_SUPPLIER_NAME))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(
            status_code=400,
            detail=f"Supplier '{VENDING_SUPPLIER_NAME}' not found — it should be auto-seeded at startup"
        )
    return supplier


def _parse_invoice_pdf(raw: bytes) -> dict:
    """Parse vending invoice PDF → {invoice_number, invoice_date, total_amount, items: [...]}.

    Returns categories with unit_price + quantity + total.
    """
    import pdfplumber

    result = {
        "invoice_number": None,
        "invoice_date": None,
        "total_amount": 0.0,
        "items": [],  # [{category, quantity, unit_price, total_price}]
    }

    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)

        # Invoice number: IN followed by digits
        m = re.search(r"IN\d{6,}", full_text)
        if m:
            result["invoice_number"] = m.group(0)

        # Invoice date: dd/mm/yy
        for line in full_text.split("\n"):
            if "תינובשח ךיראת" in line or "חשבונית תאריך" in line or "תאריך חשבונית" in line:
                m2 = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", line)
                if m2:
                    dd, mm, yy = m2.groups()
                    year = int(yy) if len(yy) == 4 else 2000 + int(yy)
                    try:
                        result["invoice_date"] = date(year, int(mm), int(dd))
                        break
                    except ValueError:
                        pass
        if not result["invoice_date"]:
            m3 = re.search(r"(\d{2})/(\d{2})/(\d{2})", full_text)
            if m3:
                dd, mm, yy = m3.groups()
                try:
                    result["invoice_date"] = date(2000 + int(yy), int(mm), int(dd))
                except ValueError:
                    pass

        # Extract line items from tables
        total_pre_vat = 0.0
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    if not row or len(row) < 4:
                        continue
                    # Row pattern: [total, unit_price, delivery_balance, quantity, product_desc, barcode, sku, line_no]
                    cells = [str(c or "").strip() for c in row]
                    # Must have numeric total in col 0, unit price in col 1
                    try:
                        total_str = cells[0].replace(",", "")
                        total = float(total_str)
                    except (ValueError, IndexError):
                        continue
                    unit_str_m = re.search(r"([\d,]+\.?\d*)", cells[1] if len(cells) > 1 else "")
                    if not unit_str_m:
                        continue
                    try:
                        unit_price = float(unit_str_m.group(1).replace(",", ""))
                    except ValueError:
                        continue
                    # Quantity is in col 3, stripped of units
                    qty_m = re.search(r"([-\d,]+\.?\d*)", cells[3] if len(cells) > 3 else "")
                    if not qty_m:
                        continue
                    try:
                        quantity = float(qty_m.group(1).replace(",", ""))
                    except ValueError:
                        continue
                    if quantity == 0:
                        continue
                    # Product description (reversed Hebrew)
                    desc_raw = cells[4] if len(cells) > 4 else ""
                    desc = _reverse_hebrew_if_rtl(desc_raw).strip()
                    if not desc:
                        continue
                    # Skip credit/refund rows (negative totals) — keep them for accuracy
                    result["items"].append({
                        "category": desc,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "total_price": total,
                    })
                    total_pre_vat += total

        # Find grand total (look for total incl. VAT)
        m_total = re.search(r"ח\"ש\s+([\d,]+\.?\d*)\s+ריחמ\s+כ\"הס", full_text) or \
                  re.search(r"([\d,]+\.?\d*)\s+ח\"ש\s+םולשתל", full_text) or \
                  re.search(r"([\d,]+\.?\d*)\s+ח\"ש\s+לש\"חנ", full_text)
        if m_total:
            try:
                result["total_amount"] = float(m_total.group(1).replace(",", ""))
            except ValueError:
                result["total_amount"] = total_pre_vat
        else:
            result["total_amount"] = total_pre_vat

    return result


def _parse_consumption_xlsx(raw: bytes) -> list[dict]:
    """Parse DataSheet XLSX → list of transactions.

    Returns [{tx_date, product_name, quantity, machine_id (or None)}].
    Cols A=date, B=product, C=qty. Optional machine_id in future KG files.
    """
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    ws = wb[wb.sheetnames[0]]

    transactions = []
    # Detect optional machine_id column by looking at header row for "מכונה" / "machine"
    machine_col = None
    for c in range(1, ws.max_column + 1):
        v = ws.cell(1, c).value
        if v and isinstance(v, str) and ("מכונה" in v or "machine" in v.lower() or "מס' מכונה" in v):
            machine_col = c
            break

    for r in range(2, ws.max_row + 1):
        d = ws.cell(r, 1).value
        if d is None:
            continue
        if isinstance(d, datetime):
            tx_date = d.date()
        elif isinstance(d, date):
            tx_date = d
        else:
            continue
        product = ws.cell(r, 2).value
        qty = ws.cell(r, 3).value
        if not product or not isinstance(qty, (int, float)):
            continue
        machine = ws.cell(r, machine_col).value if machine_col else None
        transactions.append({
            "tx_date": tx_date,
            "product_name": str(product).strip(),
            "quantity": float(qty),
            "machine_id": str(machine).strip() if machine else None,
        })
    return transactions


def _classify_transaction(product_name: str, pdf_items: list[dict]) -> tuple[Optional[str], Optional[float]]:
    """Match a transaction product name to a PDF invoice category → returns (category, unit_price)."""
    if not pdf_items:
        return (None, None)
    name = product_name or ""
    for it in pdf_items:
        cat = it.get("category") or ""
        # Split category into keywords and check if any keyword is in the transaction
        kws = [w for w in re.split(r"\s+", cat) if len(w) >= 3]
        for kw in kws:
            if kw in name:
                return (cat, float(it.get("unit_price") or 0))
    return (None, None)


# ── Endpoints ───────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_vending(
    site_id: int = Form(...),
    shift: str = Form("all"),  # 'all' | 'day' | 'evening'
    invoice_pdf: UploadFile = File(None),
    consumption_xlsx: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload vending invoice PDF + detailed consumption Excel together.

    - PDF creates/updates a Proforma with the 8 category items (prices)
    - Excel creates VendingTransaction rows (drill-down detail)
    - Transactions are linked to the Proforma and priced via category match
    """
    if not invoice_pdf and not consumption_xlsx:
        raise HTTPException(400, "Provide at least one file (PDF invoice or Excel consumption)")
    if shift not in ("all", "day", "evening"):
        raise HTTPException(400, "shift must be 'all', 'day', or 'evening'")

    supplier = await _get_vending_supplier(db)

    proforma: Optional[Proforma] = None
    pdf_items: list[dict] = []
    invoice_date: Optional[date] = None

    # 1. Parse PDF → Proforma + ProformaItems
    if invoice_pdf and invoice_pdf.filename:
        raw_pdf = await invoice_pdf.read()
        try:
            parsed = _parse_invoice_pdf(raw_pdf)
        except Exception as e:
            logger.exception("Failed to parse vending invoice PDF")
            raise HTTPException(500, f"Failed to parse PDF: {e}")

        invoice_date = parsed.get("invoice_date") or date.today()
        invoice_number = parsed.get("invoice_number")
        pdf_items = parsed.get("items", [])
        total_amount = parsed.get("total_amount", 0.0) or sum(it["total_price"] for it in pdf_items)

        # Find existing proforma by (supplier, site, shift, invoice_date) or invoice_number
        exist_q = select(Proforma).where(
            Proforma.supplier_id == supplier.id,
            Proforma.site_id == site_id,
        )
        if invoice_number:
            exist_q = exist_q.where(Proforma.proforma_number == invoice_number)
        else:
            exist_q = exist_q.where(Proforma.invoice_date == invoice_date)
        existing = (await db.execute(exist_q)).scalar_one_or_none()

        if existing:
            proforma = existing
            proforma.total_amount = total_amount
            proforma.shift = shift
            proforma.invoice_date = invoice_date
            # Wipe old items
            await db.execute(delete(ProformaItem).where(ProformaItem.proforma_id == proforma.id))
        else:
            proforma = Proforma(
                supplier_id=supplier.id,
                site_id=site_id,
                shift=shift,
                invoice_date=invoice_date,
                total_amount=total_amount,
                currency="ILS",
                status="validated",
                proforma_number=invoice_number,
                notes=f"Vending invoice {shift} · uploaded by {current_user.email}",
            )
            db.add(proforma)
            await db.flush()

        for it in pdf_items:
            db.add(ProformaItem(
                proforma_id=proforma.id,
                product_name=it["category"],
                quantity=it["quantity"],
                unit=f"unit @ ₪{it['unit_price']}",
                unit_price=it["unit_price"],
                total_price=it["total_price"],
                flagged=False,
            ))
        await db.commit()
        await db.refresh(proforma)

    # 2. Parse Excel → VendingTransactions
    tx_count = 0
    tx_priced = 0
    if consumption_xlsx and consumption_xlsx.filename:
        raw_xlsx = await consumption_xlsx.read()
        try:
            txs = _parse_consumption_xlsx(raw_xlsx)
        except Exception as e:
            logger.exception("Failed to parse vending Excel")
            raise HTTPException(500, f"Failed to parse Excel: {e}")

        # If we have a proforma from PDF, wipe its old transactions
        if proforma:
            await db.execute(
                delete(VendingTransaction).where(VendingTransaction.proforma_id == proforma.id)
            )
        else:
            # No proforma — delete by site+shift+month as best effort
            if txs:
                months = {(t["tx_date"].year, t["tx_date"].month) for t in txs}
                for y, m in months:
                    await db.execute(
                        delete(VendingTransaction).where(
                            VendingTransaction.site_id == site_id,
                            VendingTransaction.shift == shift,
                            year_equals(VendingTransaction.tx_date, y),
                            month_equals(VendingTransaction.tx_date, m),
                        )
                    )

        for t in txs:
            category, unit_price = _classify_transaction(t["product_name"], pdf_items)
            total_price = (unit_price * t["quantity"]) if unit_price else None
            if unit_price is not None:
                tx_priced += 1
            db.add(VendingTransaction(
                proforma_id=proforma.id if proforma else None,
                site_id=site_id,
                shift=shift,
                tx_date=t["tx_date"],
                product_name=t["product_name"],
                category=category,
                quantity=t["quantity"],
                unit_price=unit_price,
                total_price=total_price,
                machine_id=t.get("machine_id"),
            ))
            tx_count += 1
        await db.commit()

    return {
        "proforma_id": proforma.id if proforma else None,
        "invoice_date": invoice_date.isoformat() if invoice_date else None,
        "site_id": site_id,
        "shift": shift,
        "invoice_items": len(pdf_items),
        "transactions_saved": tx_count,
        "transactions_priced": tx_priced,
        "total_amount": proforma.total_amount if proforma else None,
    }


@router.get("/analytics")
async def vending_analytics(
    year: Optional[int] = None,
    month: Optional[int] = None,
    site_id: Optional[int] = None,
    shift: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top products, monthly trend, per-machine usage for the Analytics tab."""
    target_year = year or datetime.now().year

    q = select(
        VendingTransaction.tx_date,
        VendingTransaction.product_name,
        VendingTransaction.category,
        VendingTransaction.quantity,
        VendingTransaction.total_price,
        VendingTransaction.machine_id,
        VendingTransaction.site_id,
        VendingTransaction.shift,
    ).where(year_equals(VendingTransaction.tx_date, target_year))
    if month:
        q = q.where(month_equals(VendingTransaction.tx_date, month))
    if site_id:
        q = q.where(VendingTransaction.site_id == site_id)
    if shift and shift != "all":
        q = q.where(VendingTransaction.shift == shift)

    rows = list((await db.execute(q)).all())

    # Totals
    total_qty = sum(float(r.quantity or 0) for r in rows)
    total_cost = sum(float(r.total_price or 0) for r in rows if r.total_price is not None)

    # Top products (by qty)
    by_product: dict[str, dict] = {}
    for r in rows:
        p = r.product_name or "?"
        if p not in by_product:
            by_product[p] = {"product_name": p, "category": r.category, "qty": 0.0, "cost": 0.0}
        by_product[p]["qty"] += float(r.quantity or 0)
        by_product[p]["cost"] += float(r.total_price or 0) if r.total_price else 0

    top_products = sorted(by_product.values(), key=lambda x: x["qty"], reverse=True)[:25]

    # Monthly trend
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly: dict[int, dict] = {m: {"month": m, "month_name": month_names[m - 1], "qty": 0, "cost": 0} for m in range(1, 13)}
    for r in rows:
        if not r.tx_date:
            continue
        m = r.tx_date.month
        monthly[m]["qty"] += float(r.quantity or 0)
        monthly[m]["cost"] += float(r.total_price or 0) if r.total_price else 0

    # Per machine (only if machines present)
    by_machine: dict[str, dict] = {}
    for r in rows:
        if not r.machine_id:
            continue
        mid = r.machine_id
        if mid not in by_machine:
            by_machine[mid] = {"machine_id": mid, "qty": 0, "cost": 0}
        by_machine[mid]["qty"] += float(r.quantity or 0)
        by_machine[mid]["cost"] += float(r.total_price or 0) if r.total_price else 0
    top_machines = sorted(by_machine.values(), key=lambda x: x["qty"], reverse=True)

    return {
        "year": target_year,
        "month": month,
        "site_id": site_id,
        "shift": shift,
        "total_qty": round(total_qty),
        "total_cost": round(total_cost, 2),
        "top_products": [
            {"product_name": p["product_name"], "category": p["category"],
             "qty": round(p["qty"]), "cost": round(p["cost"], 2)}
            for p in top_products
        ],
        "monthly": [
            {"month": v["month"], "month_name": v["month_name"],
             "qty": round(v["qty"]), "cost": round(v["cost"], 2)}
            for v in monthly.values()
        ],
        "machines": [
            {"machine_id": m["machine_id"],
             "qty": round(m["qty"]), "cost": round(m["cost"], 2)}
            for m in top_machines
        ],
    }


@router.get("/product-trend")
async def product_trend(
    product_name: str,
    year: Optional[int] = None,
    site_id: Optional[int] = None,
    shift: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daily/monthly trend for one product — used in the Analytics drill-down."""
    target_year = year or datetime.now().year
    q = select(
        VendingTransaction.tx_date,
        VendingTransaction.quantity,
        VendingTransaction.total_price,
    ).where(
        year_equals(VendingTransaction.tx_date, target_year),
        VendingTransaction.product_name == product_name,
    )
    if site_id:
        q = q.where(VendingTransaction.site_id == site_id)
    if shift and shift != "all":
        q = q.where(VendingTransaction.shift == shift)

    rows = list((await db.execute(q)).all())
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly: dict[int, dict] = {m: {"month": m, "month_name": month_names[m - 1], "qty": 0, "cost": 0} for m in range(1, 13)}
    for r in rows:
        if not r.tx_date:
            continue
        m = r.tx_date.month
        monthly[m]["qty"] += float(r.quantity or 0)
        monthly[m]["cost"] += float(r.total_price or 0) if r.total_price else 0

    return {
        "product_name": product_name,
        "year": target_year,
        "monthly": [
            {"month": v["month"], "month_name": v["month_name"],
             "qty": round(v["qty"]), "cost": round(v["cost"], 2)}
            for v in monthly.values()
        ],
    }
