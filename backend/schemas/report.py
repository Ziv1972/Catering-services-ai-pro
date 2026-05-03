"""
Pydantic schemas for the Report Generator.

A report is described by a single ReportConfig:
  - data_source: which table family to query
  - filters:     year, month range, site, supplier, ...
  - group_by:    one or more dimension names (supplier, category, product, month, site, ...)
  - metrics:     one or more (column, aggregation) pairs
  - chart_type:  preview chart shape

The same config drives both JSON preview (POST /run) and Excel export (POST /export).
"""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# Enumerated values for client + server validation
DATA_SOURCES = (
    "proforma_items",
    "vending",
    "meals",
    "kitchenette",
    "violations",
    "budgets",
)

GROUP_BY_KEYS = (
    "supplier",
    "site",
    "category",
    "product",
    "month",
    "shift",
    "meal_type",
    "family",
    "severity",
)

METRIC_NAMES = (
    "qty",          # quantity / count
    "total",        # total cost / fine amount
    "unit_price",
    "budget",
    "actual",
    "variance",
)

AGG_FUNCS = ("sum", "avg", "min", "max", "count")

CHART_TYPES = ("bar", "line", "pie", "stacked_bar")


class Metric(BaseModel):
    name: str = Field(..., description="One of METRIC_NAMES")
    agg: str = Field("sum", description="One of AGG_FUNCS")


class ReportFilters(BaseModel):
    year: Optional[int] = None
    from_month: int = 1
    to_month: int = 12
    site_id: Optional[int] = None
    supplier_id: Optional[int] = None
    shift: Optional[str] = None  # 'all' | 'day' | 'evening'
    category: Optional[str] = None
    product_name_like: Optional[str] = None


class ReportConfig(BaseModel):
    data_source: str
    filters: ReportFilters = Field(default_factory=ReportFilters)
    group_by: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    chart_type: str = "bar"
    title: Optional[str] = None
    limit: Optional[int] = 500  # cap rows returned for preview/export


class ChartSeries(BaseModel):
    name: str
    data: list[float]


class ChartPayload(BaseModel):
    type: str
    labels: list[str]
    series: list[ChartSeries]


class ReportResponse(BaseModel):
    columns: list[str]            # display column names in order
    rows: list[dict[str, Any]]    # one dict per row, keys match columns
    totals: dict[str, float]      # metric name -> grand total
    chart: ChartPayload
    row_count: int


# ── Saved reports ─────────────────────────────────────────────────────

class SavedReportIn(BaseModel):
    name: str
    description: Optional[str] = None
    config: ReportConfig


class SavedReportOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    data_source: str
    config: ReportConfig
    created_at: str
    updated_at: Optional[str]


# ── Source metadata returned by GET /sources ──────────────────────────

class SourceMetadata(BaseModel):
    key: str
    label: str
    label_he: str
    group_by_options: list[dict[str, str]]   # [{key, label}]
    metric_options: list[dict[str, str]]     # [{name, label, default_agg}]
    default_chart: str
