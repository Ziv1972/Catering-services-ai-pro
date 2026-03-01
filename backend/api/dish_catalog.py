"""
Dish Catalog API — CRUD for dish-to-category-to-rule mappings.
Includes extraction of unique dishes from existing menu checks.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.dish_catalog import DishCatalog, DISH_CATEGORIES, DISH_CATEGORY_LABELS
from backend.models.menu_compliance import MenuDay, ComplianceRule

router = APIRouter(prefix="/api/dish-catalog", tags=["dish-catalog"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DishCatalogResponse(BaseModel):
    id: int
    dish_name: str
    category: Optional[str] = None
    compliance_rule_id: Optional[int] = None
    rule_name: Optional[str] = None

    class Config:
        from_attributes = True


class DishCatalogCreate(BaseModel):
    dish_name: str
    category: Optional[str] = None
    compliance_rule_id: Optional[int] = None


class DishCatalogUpdate(BaseModel):
    category: Optional[str] = None
    compliance_rule_id: Optional[int] = None


class CategoryOption(BaseModel):
    value: str
    label: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[CategoryOption])
async def list_categories(
    current_user: User = Depends(get_current_user),
):
    """Return available dish categories for dropdown."""
    return [
        CategoryOption(value=cat, label=DISH_CATEGORY_LABELS.get(cat, cat))
        for cat in DISH_CATEGORIES
    ]


@router.get("", response_model=list[DishCatalogResponse])
async def list_dishes(
    category: Optional[str] = Query(None),
    unassigned: bool = Query(False),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all dishes in the catalog with optional filters."""
    query = select(DishCatalog).order_by(DishCatalog.dish_name)

    if category:
        query = query.where(DishCatalog.category == category)
    if unassigned:
        query = query.where(
            (DishCatalog.category == None) | (DishCatalog.compliance_rule_id == None)
        )
    if search:
        query = query.where(DishCatalog.dish_name.ilike(f"%{search}%"))

    result = await db.execute(query)
    dishes = result.scalars().all()

    return [
        DishCatalogResponse(
            id=d.id,
            dish_name=d.dish_name,
            category=d.category,
            compliance_rule_id=d.compliance_rule_id,
            rule_name=d.compliance_rule.name if d.compliance_rule else None,
        )
        for d in dishes
    ]


@router.post("", response_model=DishCatalogResponse)
async def create_dish(
    data: DishCatalogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a single dish to the catalog."""
    existing = await db.execute(
        select(DishCatalog).where(DishCatalog.dish_name == data.dish_name.strip())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Dish already exists in catalog")

    dish = DishCatalog(
        dish_name=data.dish_name.strip(),
        category=data.category,
        compliance_rule_id=data.compliance_rule_id,
    )
    db.add(dish)
    await db.commit()
    await db.refresh(dish)

    return DishCatalogResponse(
        id=dish.id,
        dish_name=dish.dish_name,
        category=dish.category,
        compliance_rule_id=dish.compliance_rule_id,
        rule_name=dish.compliance_rule.name if dish.compliance_rule else None,
    )


@router.put("/{dish_id}", response_model=DishCatalogResponse)
async def update_dish(
    dish_id: int,
    data: DishCatalogUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update category and/or rule assignment for a dish."""
    result = await db.execute(select(DishCatalog).where(DishCatalog.id == dish_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(dish, key, value)

    await db.commit()
    await db.refresh(dish)

    return DishCatalogResponse(
        id=dish.id,
        dish_name=dish.dish_name,
        category=dish.category,
        compliance_rule_id=dish.compliance_rule_id,
        rule_name=dish.compliance_rule.name if dish.compliance_rule else None,
    )


@router.delete("/{dish_id}")
async def delete_dish(
    dish_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a dish from the catalog."""
    result = await db.execute(select(DishCatalog).where(DishCatalog.id == dish_id))
    dish = result.scalar_one_or_none()
    if not dish:
        raise HTTPException(status_code=404, detail="Dish not found")

    await db.delete(dish)
    await db.commit()
    return {"message": "Dish deleted"}


@router.post("/extract/{check_id}")
async def extract_dishes_from_check(
    check_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract all unique dish names from a menu check's parsed days
    and add them to the catalog (skipping duplicates)."""
    # Get all menu days for this check
    result = await db.execute(
        select(MenuDay).where(MenuDay.menu_check_id == check_id)
    )
    days = result.scalars().all()

    if not days:
        raise HTTPException(status_code=404, detail="No menu days found for this check")

    # Collect unique dishes
    unique_dishes: set[str] = set()
    for day in days:
        items = day.menu_items or {}
        for category, dish_list in items.items():
            if isinstance(dish_list, list):
                for dish in dish_list:
                    name = str(dish).strip()
                    if name:
                        unique_dishes.add(name)

    # Get existing dish names to skip duplicates
    existing_result = await db.execute(select(DishCatalog.dish_name))
    existing_names = {row[0] for row in existing_result.all()}

    new_count = 0
    for dish_name in sorted(unique_dishes):
        if dish_name not in existing_names:
            db.add(DishCatalog(dish_name=dish_name))
            new_count += 1

    await db.commit()

    return {
        "total_dishes_in_menu": len(unique_dishes),
        "new_dishes_added": new_count,
        "already_existed": len(unique_dishes) - new_count,
    }


@router.get("/stats")
async def catalog_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get catalog statistics."""
    all_result = await db.execute(select(DishCatalog))
    all_dishes = all_result.scalars().all()

    total = len(all_dishes)
    categorized = sum(1 for d in all_dishes if d.category)
    rule_linked = sum(1 for d in all_dishes if d.compliance_rule_id)

    by_category: dict[str, int] = {}
    for d in all_dishes:
        cat = d.category or "unassigned"
        by_category[cat] = by_category.get(cat, 0) + 1

    return {
        "total": total,
        "categorized": categorized,
        "uncategorized": total - categorized,
        "rule_linked": rule_linked,
        "unlinked": total - rule_linked,
        "by_category": by_category,
    }
