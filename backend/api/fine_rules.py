"""
Fine rules API endpoints — predefined fine catalog for complaints
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.complaint import FineRule, ComplaintCategory
from backend.api.auth import get_current_user

router = APIRouter()


class FineRuleResponse(BaseModel):
    id: int
    name: str
    category: str
    amount: float
    description: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class FineRuleCreate(BaseModel):
    name: str
    category: str
    amount: float
    description: Optional[str] = None


class FineRuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/", response_model=List[FineRuleResponse])
async def list_fine_rules(
    category: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(FineRule)
    if active_only:
        query = query.where(FineRule.is_active == True)
    if category:
        query = query.where(FineRule.category == category)
    query = query.order_by(FineRule.category, FineRule.amount.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=FineRuleResponse)
async def create_fine_rule(
    data: FineRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rule = FineRule(**data.model_dump(), is_active=True)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=FineRuleResponse)
async def update_fine_rule(
    rule_id: int,
    data: FineRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(FineRule).where(FineRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Fine rule not found")

    for key, value in data.model_dump(exclude_none=True).items():
        setattr(rule, key, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
async def delete_fine_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(FineRule).where(FineRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Fine rule not found")

    rule.is_active = False
    await db.commit()
    return {"message": "Fine rule deactivated"}
