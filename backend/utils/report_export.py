"""
Excel export for the Report Generator.

Builds a single .xlsx with two sheets:
  1. "Report"  — the aggregated rows, RTL-aware, header styled, totals footer
  2. "Filters" — the report config + filters (audit trail)
"""
from __future__ import annotations

import io
from datetime import date

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from backend.schemas.report import ReportConfig, ReportResponse


HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
TOTAL_FONT = Font(bold=True)
TOTAL_FILL = PatternFill(start_color="EEF2FF", end_color="EEF2FF", fill_type="solid")
THIN = Side(border_style="thin", color="D1D5DB")
BORDER = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)


# Pretty labels for metric / column keys (English-friendly defaults)
COLUMN_LABELS = {
    "qty": "Quantity",
    "total": "Total",
    "unit_price": "Unit Price",
    "budget": "Budget",
    "actual": "Actual",
    "variance": "Variance",
    "supplier": "Supplier",
    "site": "Site",
    "category": "Category",
    "product": "Product",
    "month": "Month",
    "shift": "Shift",
    "meal_type": "Meal Type",
    "family": "Family",
    "severity": "Severity",
}


def _label(key: str) -> str:
    return COLUMN_LABELS.get(key, key.replace("_", " ").title())


def build_xlsx(report: ReportResponse, config: ReportConfig, title: str) -> bytes:
    """Render a ReportResponse as .xlsx bytes."""
    wb = openpyxl.Workbook()

    # ── Sheet 1: Report data ─────────────────────────────────────────
    ws = wb.active
    ws.title = "Report"
    # Hebrew text in many sources — RTL view by default
    ws.sheet_view.rightToLeft = True

    # Title row (merged)
    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=14)
    if report.columns:
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(report.columns))

    # Header row
    header_row = 3
    for ci, col in enumerate(report.columns, 1):
        cell = ws.cell(row=header_row, column=ci, value=_label(col))
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = BORDER

    # Data rows
    for ri, row in enumerate(report.rows, start=header_row + 1):
        for ci, col in enumerate(report.columns, 1):
            value = row.get(col, "")
            cell = ws.cell(row=ri, column=ci, value=value)
            cell.border = BORDER
            if isinstance(value, (int, float)):
                cell.number_format = "#,##0.##"
                cell.alignment = Alignment(horizontal="right")

    # Totals footer
    total_row = header_row + 1 + len(report.rows)
    if report.totals and report.columns:
        # Find first metric column to position the "Total" label
        # The metric columns are everything not in group_by
        group_by_set = set(config.group_by)
        first_metric_idx = next(
            (i + 1 for i, c in enumerate(report.columns) if c not in group_by_set),
            len(report.columns) + 1,
        )
        label_cell = ws.cell(row=total_row, column=max(1, first_metric_idx - 1), value="Total")
        label_cell.font = TOTAL_FONT
        label_cell.fill = TOTAL_FILL
        for ci, col in enumerate(report.columns, 1):
            if col in report.totals:
                cell = ws.cell(row=total_row, column=ci, value=report.totals[col])
                cell.font = TOTAL_FONT
                cell.fill = TOTAL_FILL
                cell.number_format = "#,##0.##"
                cell.alignment = Alignment(horizontal="right")
                cell.border = BORDER

    # Auto-size columns
    for ci in range(1, len(report.columns) + 1):
        col_letter = get_column_letter(ci)
        max_len = max(
            (len(str(ws.cell(row=r, column=ci).value or "")) for r in range(1, total_row + 1)),
            default=10,
        )
        ws.column_dimensions[col_letter].width = min(max_len + 4, 36)

    # Freeze header
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    # ── Sheet 2: Filters / config audit ──────────────────────────────
    ws2 = wb.create_sheet("Filters")
    ws2.sheet_view.rightToLeft = True
    ws2.cell(row=1, column=1, value="Report Configuration").font = Font(bold=True, size=12)

    f = config.filters
    info_pairs = [
        ("Generated", date.today().isoformat()),
        ("Data Source", config.data_source),
        ("Year", f.year if f.year else "All"),
        ("From Month", f.from_month),
        ("To Month", f.to_month),
        ("Site ID", f.site_id if f.site_id else "All"),
        ("Supplier ID", f.supplier_id if f.supplier_id else "All"),
        ("Shift", f.shift or "—"),
        ("Category", f.category or "—"),
        ("Product Search", f.product_name_like or "—"),
        ("Group By", ", ".join(config.group_by) or "—"),
        ("Metrics", ", ".join(f"{m.name}({m.agg})" for m in config.metrics) or "default"),
        ("Chart Type", config.chart_type),
        ("Row Count", report.row_count),
    ]
    for ri, (k, v) in enumerate(info_pairs, start=3):
        ws2.cell(row=ri, column=1, value=k).font = Font(bold=True)
        ws2.cell(row=ri, column=2, value=str(v))
    ws2.column_dimensions["A"].width = 22
    ws2.column_dimensions["B"].width = 40

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()
