"""
Report Engine — strategy dispatcher for the unified Report Generator.

Each data source has a `_query_*` method that builds rows from the database.
A common post-processing step turns rows into a chart payload.

The engine intentionally avoids any I/O concerns (no FastAPI types, no Excel) —
that lives in the API layer and the export utility.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable
from datetime import date

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.proforma import Proforma, ProformaItem
from backend.models.product import Product
from backend.models.supplier import Supplier
from backend.models.site import Site
from backend.models.vending_transaction import VendingTransaction
from backend.models.meal_breakdown import MealBreakdown
from backend.models.kitchenette_item import KitchenetteItem, KITCHENETTE_FAMILIES
from backend.models.violation import Violation
from backend.models.supplier_budget import SupplierBudget
from backend.schemas.report import (
    ReportConfig, ReportFilters, ReportResponse,
    ChartPayload, ChartSeries, Metric,
)
from backend.utils.db_compat import (
    year_equals, month_equals, month_between, extract_month,
)

logger = logging.getLogger(__name__)


# ── Static metadata: what each data source supports ──────────────────────

SOURCE_METADATA: dict[str, dict[str, Any]] = {
    "proforma_items": {
        "label": "Proforma Items",
        "label_he": "פריטי חשבונית",
        "group_by_options": [
            {"key": "supplier", "label": "Supplier"},
            {"key": "site", "label": "Site"},
            {"key": "category", "label": "Category"},
            {"key": "product", "label": "Product"},
            {"key": "month", "label": "Month"},
        ],
        "metric_options": [
            {"name": "qty", "label": "Quantity", "default_agg": "sum"},
            {"name": "total", "label": "Total Cost", "default_agg": "sum"},
            {"name": "unit_price", "label": "Unit Price", "default_agg": "avg"},
        ],
        "default_chart": "bar",
    },
    "vending": {
        "label": "Vending (מ.א)",
        "label_he": "מכונות אוטומטיות",
        "group_by_options": [
            {"key": "site", "label": "Site"},
            {"key": "shift", "label": "Shift"},
            {"key": "category", "label": "Category"},
            {"key": "product", "label": "Product"},
            {"key": "month", "label": "Month"},
        ],
        "metric_options": [
            {"name": "qty", "label": "Quantity", "default_agg": "sum"},
            {"name": "total", "label": "Total", "default_agg": "sum"},
            {"name": "unit_price", "label": "Unit Price", "default_agg": "avg"},
        ],
        "default_chart": "bar",
    },
    "meals": {
        "label": "Meals (FoodHouse)",
        "label_he": "ארוחות",
        "group_by_options": [
            {"key": "site", "label": "Site"},
            {"key": "meal_type", "label": "Meal Type"},
            {"key": "month", "label": "Month"},
        ],
        "metric_options": [
            {"name": "qty", "label": "Meals", "default_agg": "sum"},
            {"name": "total", "label": "Cost", "default_agg": "sum"},
        ],
        "default_chart": "bar",
    },
    "kitchenette": {
        "label": "Kitchenette (BTB)",
        "label_he": "מטבחונים",
        "group_by_options": [
            {"key": "site", "label": "Site"},
            {"key": "family", "label": "Family"},
            {"key": "product", "label": "Product"},
            {"key": "month", "label": "Month"},
        ],
        "metric_options": [
            {"name": "qty", "label": "Quantity", "default_agg": "sum"},
            {"name": "total", "label": "Total Cost", "default_agg": "sum"},
        ],
        "default_chart": "bar",
    },
    "violations": {
        "label": "Violations",
        "label_he": "חריגות והפרות",
        "group_by_options": [
            {"key": "site", "label": "Site"},
            {"key": "category", "label": "Category"},
            {"key": "severity", "label": "Severity"},
            {"key": "month", "label": "Month"},
        ],
        "metric_options": [
            {"name": "qty", "label": "Count", "default_agg": "count"},
            {"name": "total", "label": "Fine Amount", "default_agg": "sum"},
        ],
        "default_chart": "bar",
    },
    "budgets": {
        "label": "Budget vs Actual",
        "label_he": "תקציב מול ביצוע",
        "group_by_options": [
            {"key": "supplier", "label": "Supplier"},
            {"key": "site", "label": "Site"},
            {"key": "month", "label": "Month"},
        ],
        "metric_options": [
            {"name": "budget", "label": "Budget", "default_agg": "sum"},
            {"name": "actual", "label": "Actual", "default_agg": "sum"},
            {"name": "variance", "label": "Variance", "default_agg": "sum"},
        ],
        "default_chart": "bar",
    },
}


SITE_DISPLAY = {1: "Nes Ziona", 2: "Kiryat Gat"}
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_BUDGET_COLS = ["jan", "feb", "mar", "apr", "may", "jun",
                     "jul", "aug", "sep", "oct", "nov", "dec"]
MEAL_TYPE_FIELDS = [
    ("hp_meat", "HP Meat (Indigo)"),
    ("scitex_meat", "HP Meat (Scitex)"),
    ("evening_hp", "Evening HP"),
    ("evening_contractors", "Evening Contractors"),
    ("hp_dairy", "HP Dairy (Indigo)"),
    ("scitex_dairy", "HP Dairy (Scitex)"),
    ("supplement", "Supplement"),
    ("contractors_meat", "Contractors Meat"),
    ("contractors_dairy", "Contractors Dairy"),
]
MEAL_PRICE_FIELDS = {
    "hp_meat": "hp_meat_price",
    "scitex_meat": "scitex_meat_price",
    "evening_hp": "evening_hp_price",
    "evening_contractors": "evening_contractors_price",
    "hp_dairy": "hp_dairy_price",
    "scitex_dairy": "scitex_dairy_price",
    "supplement": "supplement_price",
    "contractors_meat": "contractors_meat_price",
    "contractors_dairy": "contractors_dairy_price",
}


# ── Engine ─────────────────────────────────────────────────────────────

class ReportEngine:
    """Run a ReportConfig against the database and return a ReportResponse."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._supplier_names: dict[int, str] = {}
        self._site_names: dict[int, str] = {}

    async def _load_lookups(self) -> None:
        if not self._supplier_names:
            res = await self.db.execute(select(Supplier.id, Supplier.name))
            self._supplier_names = {sid: name for sid, name in res.all()}
        if not self._site_names:
            res = await self.db.execute(select(Site.id, Site.name))
            self._site_names = {sid: name for sid, name in res.all()}

    async def run(self, config: ReportConfig) -> ReportResponse:
        await self._load_lookups()
        ds = config.data_source
        if ds == "proforma_items":
            rows = await self._query_proforma_items(config)
        elif ds == "vending":
            rows = await self._query_vending(config)
        elif ds == "meals":
            rows = await self._query_meals(config)
        elif ds == "kitchenette":
            rows = await self._query_kitchenette(config)
        elif ds == "violations":
            rows = await self._query_violations(config)
        elif ds == "budgets":
            rows = await self._query_budgets(config)
        else:
            raise ValueError(f"Unknown data_source: {ds}")
        return self._assemble(config, rows)

    # ─── Aggregation in Python (after rows are loaded) ─────────────────
    # Doing aggregation Python-side keeps the engine simple and lets us
    # support pivot/unpivot (meals, budgets) uniformly. Row counts here
    # are bounded by `limit` and by realistic monthly invoice volume.

    def _aggregate(
        self,
        raw_rows: Iterable[dict[str, Any]],
        group_by: list[str],
        metrics: list[Metric],
    ) -> list[dict[str, Any]]:
        if not group_by:
            # Single grand-total row
            agg: dict[str, list[float]] = {m.name: [] for m in metrics}
            counts: list[int] = []
            n = 0
            for r in raw_rows:
                n += 1
                for m in metrics:
                    val = r.get(m.name)
                    if val is not None:
                        agg[m.name].append(float(val))
            row: dict[str, Any] = {"_label": "All"}
            for m in metrics:
                row[m.name] = self._reduce(agg[m.name], m.agg, count=n)
            return [row]

        buckets: dict[tuple, dict[str, Any]] = {}
        for r in raw_rows:
            key = tuple(r.get(g, "—") for g in group_by)
            if key not in buckets:
                buckets[key] = {g: r.get(g, "—") for g in group_by}
                buckets[key]["__count"] = 0
                for m in metrics:
                    buckets[key][f"__vals_{m.name}"] = []
            buckets[key]["__count"] += 1
            for m in metrics:
                val = r.get(m.name)
                if val is not None:
                    buckets[key][f"__vals_{m.name}"].append(float(val))

        out = []
        for bucket in buckets.values():
            row = {g: bucket[g] for g in group_by}
            cnt = bucket["__count"]
            for m in metrics:
                row[m.name] = self._reduce(bucket[f"__vals_{m.name}"], m.agg, count=cnt)
            out.append(row)
        return out

    @staticmethod
    def _reduce(values: list[float], agg: str, count: int = 0) -> float:
        if agg == "count":
            return float(count)
        if not values:
            return 0.0
        if agg == "sum":
            return round(sum(values), 2)
        if agg == "avg":
            return round(sum(values) / len(values), 2)
        if agg == "min":
            return round(min(values), 2)
        if agg == "max":
            return round(max(values), 2)
        return round(sum(values), 2)

    # ─── Source: Proforma items ───────────────────────────────────────

    async def _query_proforma_items(self, config: ReportConfig) -> list[dict[str, Any]]:
        f = config.filters
        filters = [Proforma.invoice_date.isnot(None)]
        if f.year:
            filters.append(year_equals(Proforma.invoice_date, f.year))
        filters.append(month_between(Proforma.invoice_date, f.from_month, f.to_month))
        if f.site_id:
            filters.append(Proforma.site_id == f.site_id)
        if f.supplier_id:
            filters.append(Proforma.supplier_id == f.supplier_id)

        q = (
            select(
                ProformaItem.product_name,
                ProformaItem.quantity,
                ProformaItem.unit_price,
                ProformaItem.total_price,
                Proforma.invoice_date,
                Proforma.site_id,
                Proforma.supplier_id,
                Product.category,
            )
            .join(Proforma, ProformaItem.proforma_id == Proforma.id)
            .outerjoin(Product, ProformaItem.product_id == Product.id)
            .where(and_(*filters))
        )
        if f.category:
            q = q.where(Product.category == f.category)
        if f.product_name_like:
            q = q.where(ProformaItem.product_name.ilike(f"%{f.product_name_like}%"))

        result = await self.db.execute(q)
        raw = []
        for product_name, qty, unit_price, total, inv_date, site_id, supplier_id, cat in result.all():
            raw.append({
                "product": product_name,
                "qty": float(qty or 0),
                "unit_price": float(unit_price or 0),
                "total": float(total or 0),
                "month": MONTH_NAMES[inv_date.month - 1] if inv_date else "—",
                "site": self._site_names.get(site_id) or "—",
                "supplier": self._supplier_names.get(supplier_id) or "—",
                "category": cat or "—",
            })
        return raw

    # ─── Source: Vending ──────────────────────────────────────────────

    async def _query_vending(self, config: ReportConfig) -> list[dict[str, Any]]:
        f = config.filters
        q = select(VendingTransaction)
        if f.year:
            q = q.where(year_equals(VendingTransaction.tx_date, f.year))
        q = q.where(month_between(VendingTransaction.tx_date, f.from_month, f.to_month))
        if f.site_id:
            q = q.where(VendingTransaction.site_id == f.site_id)
        if f.shift and f.shift != "all":
            q = q.where(VendingTransaction.shift == f.shift)
        if f.category:
            q = q.where(VendingTransaction.category == f.category)
        if f.product_name_like:
            q = q.where(VendingTransaction.product_name.ilike(f"%{f.product_name_like}%"))

        result = await self.db.execute(q)
        rows = []
        for tx in result.scalars().all():
            rows.append({
                "product": tx.product_name,
                "category": tx.category or "—",
                "site": self._site_names.get(tx.site_id) or "—",
                "shift": tx.shift or "all",
                "month": MONTH_NAMES[tx.tx_date.month - 1] if tx.tx_date else "—",
                "qty": float(tx.quantity or 0),
                "unit_price": float(tx.unit_price or 0),
                "total": float(tx.total_price or 0),
            })
        return rows

    # ─── Source: Meals (unpivot 9 meal-type columns) ─────────────────

    async def _query_meals(self, config: ReportConfig) -> list[dict[str, Any]]:
        f = config.filters
        q = select(MealBreakdown)
        if f.year:
            q = q.where(year_equals(MealBreakdown.invoice_month, f.year))
        q = q.where(month_between(MealBreakdown.invoice_month, f.from_month, f.to_month))
        if f.site_id:
            q = q.where(MealBreakdown.site_id == f.site_id)

        result = await self.db.execute(q)
        rows = []
        for mb in result.scalars().all():
            month_label = MONTH_NAMES[mb.invoice_month.month - 1] if mb.invoice_month else "—"
            site_label = self._site_names.get(mb.site_id) or "—"
            for field, label in MEAL_TYPE_FIELDS:
                qty = float(getattr(mb, field, 0) or 0)
                if qty == 0:
                    continue
                price = float(getattr(mb, MEAL_PRICE_FIELDS[field], 0) or 0)
                rows.append({
                    "meal_type": label,
                    "site": site_label,
                    "month": month_label,
                    "qty": qty,
                    "total": round(qty * price, 2),
                })
        return rows

    # ─── Source: Kitchenette ─────────────────────────────────────────

    async def _query_kitchenette(self, config: ReportConfig) -> list[dict[str, Any]]:
        f = config.filters
        q = select(KitchenetteItem)
        if f.year:
            q = q.where(year_equals(KitchenetteItem.invoice_month, f.year))
        q = q.where(month_between(KitchenetteItem.invoice_month, f.from_month, f.to_month))
        if f.site_id:
            q = q.where(KitchenetteItem.site_id == f.site_id)
        if f.product_name_like:
            q = q.where(KitchenetteItem.product_name.ilike(f"%{f.product_name_like}%"))

        result = await self.db.execute(q)
        rows = []
        for ki in result.scalars().all():
            rows.append({
                "product": ki.product_name,
                "family": KITCHENETTE_FAMILIES.get(ki.family, ki.family),
                "site": self._site_names.get(ki.site_id) or "—",
                "month": MONTH_NAMES[ki.invoice_month.month - 1] if ki.invoice_month else "—",
                "qty": float(ki.quantity or 0),
                "total": float(ki.total_cost or 0),
            })
        return rows

    # ─── Source: Violations ──────────────────────────────────────────

    async def _query_violations(self, config: ReportConfig) -> list[dict[str, Any]]:
        f = config.filters
        q = select(Violation)
        if f.year:
            q = q.where(year_equals(Violation.received_at, f.year))
        q = q.where(month_between(Violation.received_at, f.from_month, f.to_month))
        if f.site_id:
            q = q.where(Violation.site_id == f.site_id)
        if f.category:
            q = q.where(Violation.category == f.category)

        result = await self.db.execute(q)
        rows = []
        for v in result.scalars().all():
            rows.append({
                "site": self._site_names.get(v.site_id) or "—",
                "category": v.category or "—",
                "severity": v.severity or "—",
                "month": MONTH_NAMES[v.received_at.month - 1] if v.received_at else "—",
                "qty": 1.0,
                "total": float(v.fine_amount or 0),
            })
        return rows

    # ─── Source: Budgets vs Actual ────────────────────────────────────

    async def _query_budgets(self, config: ReportConfig) -> list[dict[str, Any]]:
        f = config.filters
        if not f.year:
            f = f.copy(update={"year": date.today().year})

        bq = select(SupplierBudget).where(
            SupplierBudget.year == f.year,
            SupplierBudget.is_active == True,  # noqa: E712
        )
        if f.site_id:
            bq = bq.where(SupplierBudget.site_id == f.site_id)
        if f.supplier_id:
            bq = bq.where(SupplierBudget.supplier_id == f.supplier_id)
        budget_rows = (await self.db.execute(bq)).scalars().all()

        # Actuals: sum total_amount from proformas grouped by supplier/site/month
        pq = (
            select(
                Proforma.supplier_id,
                Proforma.site_id,
                extract_month(Proforma.invoice_date).label("m"),
                func.sum(Proforma.total_amount).label("actual"),
            )
            .where(year_equals(Proforma.invoice_date, f.year))
            .group_by(Proforma.supplier_id, Proforma.site_id, extract_month(Proforma.invoice_date))
        )
        actuals: dict[tuple[int, int, int], float] = {}
        for sid, site_id, m_str, total in (await self.db.execute(pq)).all():
            try:
                m = int(m_str)
            except (TypeError, ValueError):
                continue
            actuals[(sid, site_id or 0, m)] = float(total or 0)

        rows = []
        for b in budget_rows:
            for mi, col in enumerate(MONTH_BUDGET_COLS, start=1):
                if mi < f.from_month or mi > f.to_month:
                    continue
                budget_amt = float(getattr(b, col) or 0)
                actual_amt = actuals.get((b.supplier_id, b.site_id or 0, mi), 0.0)
                rows.append({
                    "supplier": self._supplier_names.get(b.supplier_id) or "—",
                    "site": self._site_names.get(b.site_id) or "—",
                    "month": MONTH_NAMES[mi - 1],
                    "budget": budget_amt,
                    "actual": actual_amt,
                    "variance": round(actual_amt - budget_amt, 2),
                })
        return rows

    # ─── Assemble ────────────────────────────────────────────────────

    def _assemble(self, config: ReportConfig, raw_rows: list[dict[str, Any]]) -> ReportResponse:
        # Default metrics if user didn't specify any
        metrics = config.metrics or self._default_metrics(config.data_source)

        agg_rows = self._aggregate(raw_rows, config.group_by, metrics)

        # Stable ordering: alphabetical within first dimension
        if config.group_by:
            try:
                agg_rows.sort(key=lambda r: tuple(str(r.get(g, "")) for g in config.group_by))
            except Exception:
                pass

        # Cap rows for preview
        if config.limit and len(agg_rows) > config.limit:
            agg_rows = agg_rows[: config.limit]

        # Column ordering: group-by columns then metric columns
        columns = list(config.group_by) + [m.name for m in metrics]

        # Totals across all rows (for footer + summary)
        totals: dict[str, float] = {}
        for m in metrics:
            if m.agg == "count":
                totals[m.name] = sum(float(r.get(m.name, 0) or 0) for r in agg_rows)
            else:
                totals[m.name] = round(sum(float(r.get(m.name, 0) or 0) for r in agg_rows), 2)

        chart = self._build_chart(agg_rows, config, metrics)

        return ReportResponse(
            columns=columns,
            rows=agg_rows,
            totals=totals,
            chart=chart,
            row_count=len(agg_rows),
        )

    @staticmethod
    def _default_metrics(data_source: str) -> list[Metric]:
        meta = SOURCE_METADATA.get(data_source, {})
        opts = meta.get("metric_options", [])
        return [Metric(name=o["name"], agg=o["default_agg"]) for o in opts[:1]] or [Metric(name="qty", agg="sum")]

    @staticmethod
    def _build_chart(
        rows: list[dict[str, Any]],
        config: ReportConfig,
        metrics: list[Metric],
    ) -> ChartPayload:
        if not config.group_by or not rows:
            return ChartPayload(type=config.chart_type, labels=[], series=[])

        first_dim = config.group_by[0]
        labels = [str(r.get(first_dim, "—")) for r in rows]

        # If chart_type is pie, only first metric rendered
        active_metrics = metrics[:1] if config.chart_type == "pie" else metrics

        series = [
            ChartSeries(
                name=m.name,
                data=[float(r.get(m.name, 0) or 0) for r in rows],
            )
            for m in active_metrics
        ]
        return ChartPayload(type=config.chart_type, labels=labels, series=series)
