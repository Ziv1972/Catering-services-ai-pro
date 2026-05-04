"""
Daily Operations Monitor — data-quality anomaly detection.

Triggered automatically after every vending and proforma upload to catch the
silent-failure cases we used to miss:
  - Vending Excel uploaded but no PDF invoice for the same site+month
  - Proforma PDF uploaded but no Excel consumption rows exist
  - Vending transactions present but unit_price is NULL (matcher failed)
  - Proforma parsed with 0 line items (PDF/Excel parser regression)
  - Proforma total is 0 or contains only refund rows

Findings are persisted as `Anomaly` records that surface in /anomalies.
The agent is dedupe-aware — re-running it doesn't create duplicate findings.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.base_agent import BaseAgent
from backend.models.operations import Anomaly
from backend.models.proforma import Proforma, ProformaItem
from backend.models.vending_transaction import VendingTransaction
from backend.models.supplier import Supplier
from backend.utils.db_compat import year_equals, month_equals

logger = logging.getLogger(__name__)

VENDING_SUPPLIER_NAME = "מ.א אוטומטים"

# Re-run dedupe window — if the same anomaly was logged within this many days,
# refresh it instead of inserting a new row.
DEDUPE_DAYS = 30


class DailyOpsMonitorAgent(BaseAgent):
    """Real-time data-quality monitor. Creates Anomaly records when uploads
    leave the system in an inconsistent state."""

    def __init__(self):
        super().__init__(name="DailyOpsMonitorAgent")

    # ── BaseAgent contract ────────────────────────────────────────────

    async def process(self, context: dict[str, Any]) -> dict[str, Any]:
        action = context.get("action", "scan_all")
        db: AsyncSession = context["db"]

        if action == "check_vending_upload":
            return await self.check_vending_upload(
                db,
                site_id=context["site_id"],
                year=context["year"],
                month=context["month"],
                shift=context.get("shift", "all"),
            )
        if action == "check_proforma_upload":
            return await self.check_proforma_upload(db, proforma_id=context["proforma_id"])
        if action == "scan_all":
            return await self.scan_all(db)
        return {"error": f"Unknown action: {action}"}

    # ── Public entry points ───────────────────────────────────────────

    async def check_vending_upload(
        self,
        db: AsyncSession,
        site_id: int,
        year: int,
        month: int,
        shift: str = "all",
    ) -> dict[str, Any]:
        """Run all vending checks for a single (site, year, month). Called
        right after a vending upload finishes. Errors are caught and logged
        so the upload itself never fails because of monitoring."""
        findings: list[dict] = []
        try:
            findings += await self._check_vending_period(db, site_id, year, month)
        except Exception as e:
            logger.exception("vending check failed for site=%s %s-%02d", site_id, year, month)
            findings.append({"error": str(e)})
        return {"findings": findings, "site_id": site_id, "year": year, "month": month}

    async def check_proforma_upload(
        self,
        db: AsyncSession,
        proforma_id: int,
    ) -> dict[str, Any]:
        """Run all proforma-level checks for one proforma. Called right after
        a proforma upload finishes."""
        findings: list[dict] = []
        try:
            findings += await self._check_proforma(db, proforma_id)
            # Also re-check the corresponding (site, month) so vending-pair
            # status is updated (e.g., the missing-invoice anomaly should
            # auto-resolve once the matching PDF lands).
            res = await db.execute(select(Proforma).where(Proforma.id == proforma_id))
            p = res.scalar_one_or_none()
            if p and p.invoice_date:
                # Only check vending-pair if this is the vending supplier
                supplier_res = await db.execute(select(Supplier).where(Supplier.id == p.supplier_id))
                supplier = supplier_res.scalar_one_or_none()
                if supplier and supplier.name == VENDING_SUPPLIER_NAME and p.site_id:
                    findings += await self._check_vending_period(
                        db, p.site_id, p.invoice_date.year, p.invoice_date.month
                    )
        except Exception as e:
            logger.exception("proforma check failed for id=%s", proforma_id)
            findings.append({"error": str(e)})
        return {"findings": findings, "proforma_id": proforma_id}

    async def scan_all(self, db: AsyncSession, months_back: int = 24) -> dict[str, Any]:
        """Walk every (site, year, month) that has either a proforma or
        vending transactions in the last N months and run all checks.
        Used by the manual scan endpoint and bootstrap after deploys."""
        cutoff = date.today() - timedelta(days=months_back * 30)

        # Vending periods: distinct (site_id, year, month) from VendingTransaction
        vt_q = select(
            VendingTransaction.site_id,
            func.strftime("%Y", VendingTransaction.tx_date).label("y"),
            func.strftime("%m", VendingTransaction.tx_date).label("m"),
        ).where(VendingTransaction.tx_date >= cutoff).distinct()
        vt_periods = set()
        for sid, y, m in (await db.execute(vt_q)).all():
            try:
                vt_periods.add((int(sid), int(y), int(m)))
            except (TypeError, ValueError):
                continue

        # Vending supplier proforma periods
        sup_res = await db.execute(select(Supplier).where(Supplier.name == VENDING_SUPPLIER_NAME))
        vending_supplier = sup_res.scalar_one_or_none()
        proforma_periods: set[tuple[int, int, int]] = set()
        if vending_supplier:
            pq = select(Proforma).where(
                Proforma.supplier_id == vending_supplier.id,
                Proforma.invoice_date >= cutoff,
            )
            for p in (await db.execute(pq)).scalars().all():
                if p.site_id and p.invoice_date:
                    proforma_periods.add((p.site_id, p.invoice_date.year, p.invoice_date.month))

        all_periods = vt_periods | proforma_periods
        period_findings = []
        for site_id, y, m in sorted(all_periods):
            period_findings += await self._check_vending_period(db, site_id, y, m)

        # Proforma-level checks for ALL recent proformas
        all_proformas = (await db.execute(
            select(Proforma).where(Proforma.invoice_date >= cutoff)
        )).scalars().all()
        proforma_findings = []
        for p in all_proformas:
            proforma_findings += await self._check_proforma(db, p.id)

        return {
            "periods_scanned": len(all_periods),
            "proformas_scanned": len(all_proformas),
            "vending_findings": len(period_findings),
            "proforma_findings": len(proforma_findings),
            "total_findings": len(period_findings) + len(proforma_findings),
        }

    # ── Vending period checks ─────────────────────────────────────────

    async def _check_vending_period(
        self,
        db: AsyncSession,
        site_id: int,
        year: int,
        month: int,
    ) -> list[dict]:
        """Check a single (site, year, month) for vending data integrity.
        entity_id encoding: site_id * 1000000 + year * 100 + month (stable, unique)."""
        entity_id = site_id * 1000000 + year * 100 + month
        period_label = f"site {site_id} {year}-{month:02d}"
        findings: list[dict] = []

        # Count transactions for this period
        tx_count_res = await db.execute(
            select(func.count(VendingTransaction.id)).where(
                VendingTransaction.site_id == site_id,
                year_equals(VendingTransaction.tx_date, year),
                month_equals(VendingTransaction.tx_date, month),
            )
        )
        tx_count = tx_count_res.scalar() or 0

        # Count un-priced transactions
        unpriced_count_res = await db.execute(
            select(func.count(VendingTransaction.id)).where(
                VendingTransaction.site_id == site_id,
                year_equals(VendingTransaction.tx_date, year),
                month_equals(VendingTransaction.tx_date, month),
                VendingTransaction.unit_price.is_(None),
            )
        )
        unpriced_count = unpriced_count_res.scalar() or 0

        # Count vending proformas for this site+month
        sup_res = await db.execute(select(Supplier).where(Supplier.name == VENDING_SUPPLIER_NAME))
        vending_supplier = sup_res.scalar_one_or_none()
        proforma_count = 0
        if vending_supplier:
            pf_count_res = await db.execute(
                select(func.count(Proforma.id)).where(
                    Proforma.supplier_id == vending_supplier.id,
                    Proforma.site_id == site_id,
                    year_equals(Proforma.invoice_date, year),
                    month_equals(Proforma.invoice_date, month),
                )
            )
            proforma_count = pf_count_res.scalar() or 0

        # Anomaly 1: transactions exist but no PDF invoice
        if tx_count > 0 and proforma_count == 0:
            await self._upsert_anomaly(
                db,
                anomaly_type="vending_missing_invoice",
                entity_type="vending_period",
                entity_id=entity_id,
                severity="high",
                description=(
                    f"{tx_count} vending transactions exist for {period_label} "
                    f"but no PDF invoice has been uploaded — totals will read ₪0."
                ),
                actual_value=float(tx_count),
                expected_value=1.0,
            )
            findings.append({"type": "vending_missing_invoice", "tx_count": tx_count})
        else:
            await self._auto_resolve(db, "vending_missing_invoice", "vending_period", entity_id,
                                     resolution_note="PDF invoice now present.")

        # Anomaly 2: proforma exists but no transactions
        if proforma_count > 0 and tx_count == 0:
            await self._upsert_anomaly(
                db,
                anomaly_type="vending_missing_consumption",
                entity_type="vending_period",
                entity_id=entity_id,
                severity="medium",
                description=(
                    f"PDF invoice uploaded for {period_label} but no Excel consumption "
                    f"rows exist — drill-down analytics will be empty."
                ),
                actual_value=0.0,
                expected_value=1.0,
            )
            findings.append({"type": "vending_missing_consumption"})
        else:
            await self._auto_resolve(db, "vending_missing_consumption", "vending_period", entity_id,
                                     resolution_note="Excel consumption now present.")

        # Anomaly 3: pricing failure (>10% of txs unpriced)
        if tx_count > 0 and unpriced_count > 0:
            pct = (unpriced_count / tx_count) * 100
            severity = "high" if pct > 50 else "medium" if pct > 10 else "low"
            await self._upsert_anomaly(
                db,
                anomaly_type="vending_pricing_failure",
                entity_type="vending_period",
                entity_id=entity_id,
                severity=severity,
                description=(
                    f"{unpriced_count}/{tx_count} ({pct:.0f}%) vending transactions for "
                    f"{period_label} have no unit_price — matcher couldn't link them to "
                    f"a PDF invoice category. Try POST /api/vending/reprice."
                ),
                actual_value=float(unpriced_count),
                expected_value=0.0,
                variance_percent=round(pct, 1),
            )
            findings.append({"type": "vending_pricing_failure", "unpriced": unpriced_count, "pct": pct})
        else:
            await self._auto_resolve(db, "vending_pricing_failure", "vending_period", entity_id,
                                     resolution_note="All transactions priced.")

        return findings

    # ── Proforma-level checks ────────────────────────────────────────

    async def _check_proforma(self, db: AsyncSession, proforma_id: int) -> list[dict]:
        """Inspect a single proforma for parser/data quality issues."""
        res = await db.execute(select(Proforma).where(Proforma.id == proforma_id))
        p = res.scalar_one_or_none()
        if not p:
            return []
        items_res = await db.execute(
            select(ProformaItem).where(ProformaItem.proforma_id == proforma_id)
        )
        items = items_res.scalars().all()
        findings: list[dict] = []
        label = f"proforma #{p.id} ({p.proforma_number or 'no#'} {p.invoice_date})"

        # Empty items
        if not items:
            await self._upsert_anomaly(
                db,
                anomaly_type="proforma_empty_items",
                entity_type="proforma",
                entity_id=p.id,
                severity="high",
                description=(
                    f"{label} was uploaded but extracted 0 line items — "
                    f"likely a parser failure for this file format."
                ),
                actual_value=0.0,
                expected_value=1.0,
            )
            findings.append({"type": "proforma_empty_items"})
        else:
            await self._auto_resolve(db, "proforma_empty_items", "proforma", p.id,
                                     resolution_note="Items now present.")

        # Zero or negative total
        if (p.total_amount or 0) <= 0:
            await self._upsert_anomaly(
                db,
                anomaly_type="proforma_zero_total",
                entity_type="proforma",
                entity_id=p.id,
                severity="medium",
                description=f"{label} has total_amount={p.total_amount or 0} — verify the PDF parsed correctly.",
                actual_value=float(p.total_amount or 0),
                expected_value=1.0,
            )
            findings.append({"type": "proforma_zero_total"})
        else:
            await self._auto_resolve(db, "proforma_zero_total", "proforma", p.id,
                                     resolution_note="Total now positive.")

        # Refund-only proforma (every item has qty <= 0)
        if items and all((it.quantity or 0) <= 0 for it in items):
            await self._upsert_anomaly(
                db,
                anomaly_type="proforma_refund_only",
                entity_type="proforma",
                entity_id=p.id,
                severity="low",
                description=(
                    f"{label} contains only refund/credit rows ({len(items)} items, all qty<=0). "
                    f"Verify this is intentional."
                ),
                actual_value=float(len(items)),
            )
            findings.append({"type": "proforma_refund_only"})

        return findings

    # ── Anomaly upsert + auto-resolve helpers ────────────────────────

    async def _upsert_anomaly(
        self,
        db: AsyncSession,
        *,
        anomaly_type: str,
        entity_type: str,
        entity_id: int,
        severity: str,
        description: str,
        actual_value: Optional[float] = None,
        expected_value: Optional[float] = None,
        variance_percent: Optional[float] = None,
    ) -> Anomaly:
        """Create-or-refresh an anomaly. If an unresolved row exists with the
        same (type, entity_type, entity_id), update its description/values
        rather than inserting a duplicate. This lets re-runs after bug fixes
        keep the row count bounded."""
        existing_q = select(Anomaly).where(
            Anomaly.anomaly_type == anomaly_type,
            Anomaly.entity_type == entity_type,
            Anomaly.entity_id == entity_id,
            Anomaly.resolved == False,  # noqa: E712
        ).order_by(Anomaly.detected_at.desc())
        existing = (await db.execute(existing_q)).scalars().first()

        if existing:
            existing.description = description
            existing.severity = severity
            existing.actual_value = actual_value
            existing.expected_value = expected_value
            existing.variance_percent = variance_percent
            existing.detected_at = date.today()
            await db.commit()
            return existing

        anomaly = Anomaly(
            anomaly_type=anomaly_type,
            entity_type=entity_type,
            entity_id=entity_id,
            detected_at=date.today(),
            description=description,
            severity=severity,
            expected_value=expected_value,
            actual_value=actual_value,
            variance_percent=variance_percent,
            acknowledged=False,
            resolved=False,
        )
        db.add(anomaly)
        await db.commit()
        await db.refresh(anomaly)
        return anomaly

    async def _auto_resolve(
        self,
        db: AsyncSession,
        anomaly_type: str,
        entity_type: str,
        entity_id: int,
        resolution_note: str,
    ) -> None:
        """If an unresolved anomaly of this type exists for this entity but
        the condition no longer holds, mark it resolved automatically."""
        q = select(Anomaly).where(
            Anomaly.anomaly_type == anomaly_type,
            Anomaly.entity_type == entity_type,
            Anomaly.entity_id == entity_id,
            Anomaly.resolved == False,  # noqa: E712
        )
        for a in (await db.execute(q)).scalars().all():
            a.resolved = True
            a.resolution_notes = resolution_note + " (auto-resolved by DailyOpsMonitor)"
        await db.commit()
