"""
Todo/followup API endpoints - personal tasks and delegated task tracking
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.todo import TodoItem
from backend.api.auth import get_current_user

router = APIRouter()


# --- Pydantic Schemas ---

class TodoResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    assigned_to: Optional[str]
    priority: str
    status: str
    due_date: Optional[date]
    completed_at: Optional[datetime]
    linked_entity_type: Optional[str]
    linked_entity_id: Optional[int]
    linked_entity_label: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    is_overdue: bool = False

    class Config:
        from_attributes = True


class TodoCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[date] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None
    linked_entity_label: Optional[str] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None
    linked_entity_label: Optional[str] = None


# --- Helper ---

def _build_todo_response(t: TodoItem) -> TodoResponse:
    is_overdue = (
        t.due_date is not None
        and t.status != "done"
        and t.due_date < date.today()
    )
    return TodoResponse(
        id=t.id,
        user_id=t.user_id,
        title=t.title,
        description=t.description,
        assigned_to=t.assigned_to,
        priority=t.priority,
        status=t.status,
        due_date=t.due_date,
        completed_at=t.completed_at,
        linked_entity_type=t.linked_entity_type,
        linked_entity_id=t.linked_entity_id,
        linked_entity_label=t.linked_entity_label,
        created_at=t.created_at,
        updated_at=t.updated_at,
        is_overdue=is_overdue,
    )


# --- Endpoints ---

@router.get("/", response_model=List[TodoResponse])
async def list_todos(
    filter: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List todos. filter: 'mine' | 'delegated' | 'all' (default)"""
    query = (
        select(TodoItem)
        .where(TodoItem.user_id == current_user.id)
        .order_by(TodoItem.status, TodoItem.due_date.asc().nullslast())
    )

    if filter == "mine":
        query = query.where(TodoItem.assigned_to.is_(None))
    elif filter == "delegated":
        query = query.where(TodoItem.assigned_to.isnot(None))

    if status:
        query = query.where(TodoItem.status == status)
    if priority:
        query = query.where(TodoItem.priority == priority)

    result = await db.execute(query)
    todos = result.scalars().all()
    return [_build_todo_response(t) for t in todos]


@router.post("/", response_model=TodoResponse)
async def create_todo(
    data: TodoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new todo"""
    todo = TodoItem(
        user_id=current_user.id,
        **data.model_dump(exclude_none=True),
        status="pending",
    )
    db.add(todo)
    await db.commit()
    await db.refresh(todo)
    return _build_todo_response(todo)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: int,
    data: TodoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a todo"""
    result = await db.execute(
        select(TodoItem).where(
            TodoItem.id == todo_id,
            TodoItem.user_id == current_user.id
        )
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    updates = data.model_dump(exclude_none=True)

    # Auto-set completed_at when marking done
    if updates.get("status") == "done" and todo.status != "done":
        updates["completed_at"] = datetime.utcnow()
    elif updates.get("status") and updates["status"] != "done":
        updates["completed_at"] = None

    for key, value in updates.items():
        setattr(todo, key, value)

    todo.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(todo)
    return _build_todo_response(todo)


@router.put("/{todo_id}/complete", response_model=TodoResponse)
async def complete_todo(
    todo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a todo as done"""
    result = await db.execute(
        select(TodoItem).where(
            TodoItem.id == todo_id,
            TodoItem.user_id == current_user.id
        )
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    todo.status = "done"
    todo.completed_at = datetime.utcnow()
    todo.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(todo)
    return _build_todo_response(todo)


@router.delete("/{todo_id}")
async def delete_todo(
    todo_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a todo"""
    result = await db.execute(
        select(TodoItem).where(
            TodoItem.id == todo_id,
            TodoItem.user_id == current_user.id
        )
    )
    todo = result.scalar_one_or_none()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    await db.delete(todo)
    await db.commit()
    return {"message": "Todo deleted"}
