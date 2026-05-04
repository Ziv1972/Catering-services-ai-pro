"""
Report Generator API.

Endpoints:
  GET    /api/reports/sources           — metadata describing each data source's
                                           group-by + metric options (drives the UI)
  POST   /api/reports/run               — run a ReportConfig, return JSON preview
  POST   /api/reports/export            — run a ReportConfig, return .xlsx blob

Saved reports (CRUD):
  GET    /api/reports/saved             — list current user's saved reports
  POST   /api/reports/saved             — create
  GET    /api/reports/saved/{id}        — fetch one (with config)
  PUT    /api/reports/saved/{id}        — update
  DELETE /api/reports/saved/{id}        — delete
  POST   /api/reports/saved/{id}/run    — run a saved config (preview JSON)
  POST   /api/reports/saved/{id}/export — run a saved config (xlsx)
"""
from __future__ import annotations

import io
import json
import logging
import re
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.auth import get_current_user
from backend.database import get_db
from backend.models.user import User
from backend.models.saved_report import SavedReport
from backend.schemas.report import (
    ReportConfig, ReportResponse, SavedReportIn, SavedReportOut,
    DATA_SOURCES,
)
from backend.services.report_engine import ReportEngine, SOURCE_METADATA
from backend.utils.report_export import build_xlsx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _validate_config(config: ReportConfig) -> None:
    if config.data_source not in DATA_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown data_source. Allowed: {', '.join(DATA_SOURCES)}",
        )
    meta = SOURCE_METADATA.get(config.data_source, {})
    valid_groups = {o["key"] for o in meta.get("group_by_options", [])}
    for g in config.group_by:
        if g not in valid_groups:
            raise HTTPException(
                status_code=400,
                detail=f"group_by '{g}' not valid for source {config.data_source}. "
                       f"Allowed: {', '.join(sorted(valid_groups))}",
            )
    valid_metrics = {o["name"] for o in meta.get("metric_options", [])}
    for m in config.metrics:
        if m.name not in valid_metrics:
            raise HTTPException(
                status_code=400,
                detail=f"metric '{m.name}' not valid for source {config.data_source}. "
                       f"Allowed: {', '.join(sorted(valid_metrics))}",
            )


def _default_title(config: ReportConfig) -> str:
    meta = SOURCE_METADATA.get(config.data_source, {})
    base = meta.get("label", config.data_source)
    f = config.filters
    parts = [base]
    if f.year:
        parts.append(str(f.year))
    if f.from_month and f.to_month and (f.from_month != 1 or f.to_month != 12):
        parts.append(f"M{f.from_month:02d}-M{f.to_month:02d}")
    return " — ".join(parts)


# ── Metadata ─────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources(current_user: User = Depends(get_current_user)):
    """Return the list of data sources and their group-by + metric options.
    The frontend uses this to render the dynamic config form."""
    return {
        "sources": [
            {"key": k, **v} for k, v in SOURCE_METADATA.items()
        ]
    }


# ── Run / Export ─────────────────────────────────────────────────────

@router.post("/run", response_model=ReportResponse)
async def run_report(
    config: ReportConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a report and return JSON preview (rows + chart series + totals)."""
    _validate_config(config)
    engine = ReportEngine(db)
    try:
        return await engine.run(config)
    except Exception as e:
        logger.exception("Report run failed")
        raise HTTPException(status_code=500, detail=f"Report run failed: {e}")


@router.post("/export")
async def export_report(
    config: ReportConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run a report and return an .xlsx download."""
    _validate_config(config)
    engine = ReportEngine(db)
    try:
        report = await engine.run(config)
    except Exception as e:
        logger.exception("Report run failed during export")
        raise HTTPException(status_code=500, detail=f"Report run failed: {e}")

    title = config.title or _default_title(config)
    xlsx_bytes = build_xlsx(report, config, title)

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _content_disposition(title)},
    )


def _content_disposition(title: str) -> str:
    """Build a Content-Disposition header that is safe for non-ASCII titles
    (Hebrew, em-dashes, etc). HTTP headers can only carry Latin-1, so we use
    both an ASCII-safe `filename=` and an RFC 5987 `filename*=UTF-8''…` form
    that browsers prefer when present.
    """
    full = f"{title}_{date.today().isoformat()}.xlsx"
    # ASCII-only fallback: drop anything outside printable ASCII, collapse
    # whitespace and slashes, never empty.
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", full).strip("_") or "report.xlsx"
    if not ascii_name.endswith(".xlsx"):
        ascii_name += ".xlsx"
    encoded = quote(full, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


# ── Saved reports CRUD ──────────────────────────────────────────────

def _saved_to_out(s: SavedReport) -> SavedReportOut:
    return SavedReportOut(
        id=s.id,
        name=s.name,
        description=s.description,
        data_source=s.data_source,
        config=ReportConfig(**json.loads(s.config_json)),
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else None,
    )


@router.get("/saved", response_model=list[SavedReportOut])
async def list_saved(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SavedReport)
        .where(SavedReport.user_id == current_user.id)
        .order_by(SavedReport.updated_at.desc().nullslast(), SavedReport.created_at.desc())
    )
    return [_saved_to_out(s) for s in result.scalars().all()]


@router.post("/saved", response_model=SavedReportOut)
async def create_saved(
    payload: SavedReportIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_config(payload.config)
    saved = SavedReport(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        data_source=payload.config.data_source,
        config_json=payload.config.model_dump_json(),
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return _saved_to_out(saved)


async def _load_saved(db: AsyncSession, user_id: int, report_id: int) -> SavedReport:
    res = await db.execute(
        select(SavedReport).where(
            SavedReport.id == report_id,
            SavedReport.user_id == user_id,
        )
    )
    saved = res.scalar_one_or_none()
    if not saved:
        raise HTTPException(status_code=404, detail="Saved report not found")
    return saved


@router.get("/saved/{report_id}", response_model=SavedReportOut)
async def get_saved(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = await _load_saved(db, current_user.id, report_id)
    return _saved_to_out(saved)


@router.put("/saved/{report_id}", response_model=SavedReportOut)
async def update_saved(
    report_id: int,
    payload: SavedReportIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _validate_config(payload.config)
    saved = await _load_saved(db, current_user.id, report_id)
    saved.name = payload.name
    saved.description = payload.description
    saved.data_source = payload.config.data_source
    saved.config_json = payload.config.model_dump_json()
    await db.commit()
    await db.refresh(saved)
    return _saved_to_out(saved)


@router.delete("/saved/{report_id}")
async def delete_saved(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = await _load_saved(db, current_user.id, report_id)
    await db.delete(saved)
    await db.commit()
    return {"deleted": report_id}


@router.post("/saved/{report_id}/run", response_model=ReportResponse)
async def run_saved(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = await _load_saved(db, current_user.id, report_id)
    config = ReportConfig(**json.loads(saved.config_json))
    return await ReportEngine(db).run(config)


@router.post("/saved/{report_id}/export")
async def export_saved(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved = await _load_saved(db, current_user.id, report_id)
    config = ReportConfig(**json.loads(saved.config_json))
    report = await ReportEngine(db).run(config)
    title = saved.name or _default_title(config)
    xlsx_bytes = build_xlsx(report, config, title)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": _content_disposition(title)},
    )
