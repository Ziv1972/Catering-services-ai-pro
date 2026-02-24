"""
Anomalies API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
from datetime import date

from backend.database import get_db
from backend.models.user import User
from backend.models.operations import Anomaly
from backend.api.auth import get_current_user

router = APIRouter()


class AnomalyResponse(BaseModel):
    id: int
    anomaly_type: str
    entity_type: str
    entity_id: int
    detected_at: date
    description: str
    severity: str
    expected_value: Optional[float]
    actual_value: Optional[float]
    variance_percent: Optional[float]
    acknowledged: bool
    resolved: bool
    resolution_notes: Optional[str]

    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    resolution_notes: str


@router.get("/", response_model=List[AnomalyResponse])
async def list_anomalies(
    resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List anomalies with filters"""
    query = select(Anomaly).order_by(Anomaly.detected_at.desc())

    if resolved is not None:
        query = query.where(Anomaly.resolved == resolved)
    if severity:
        query = query.where(Anomaly.severity == severity)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(
    anomaly_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an anomaly"""
    result = await db.execute(
        select(Anomaly).where(Anomaly.id == anomaly_id)
    )
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.acknowledged = True
    await db.commit()

    return {"message": "Anomaly acknowledged", "id": anomaly_id}


@router.post("/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: int,
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resolve an anomaly"""
    result = await db.execute(
        select(Anomaly).where(Anomaly.id == anomaly_id)
    )
    anomaly = result.scalar_one_or_none()

    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.resolved = True
    anomaly.resolution_notes = body.resolution_notes
    await db.commit()

    return {"message": "Anomaly resolved", "id": anomaly_id}
