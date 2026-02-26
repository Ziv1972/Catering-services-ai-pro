"""
Projects API endpoints - multi-phase project management with linkable tasks
"""
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel

from backend.database import get_db
from backend.models.user import User
from backend.models.project import Project, ProjectTask, ProjectDocument
from backend.api.auth import get_current_user

UPLOAD_DIR = "uploads/projects"

router = APIRouter()


# --- Pydantic Schemas ---

class DocumentResponse(BaseModel):
    id: int
    project_id: int
    task_id: Optional[int]
    filename: str
    original_filename: str
    file_size: Optional[int]
    content_type: Optional[str]
    uploaded_by: Optional[int]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class TaskResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: Optional[str]
    status: str
    order: int
    assigned_to: Optional[str]
    due_date: Optional[date]
    completed_at: Optional[datetime]
    linked_entity_type: Optional[str]
    linked_entity_id: Optional[int]
    linked_entity_label: Optional[str]
    notes: Optional[str]
    created_at: Optional[datetime]
    documents: List[DocumentResponse] = []

    class Config:
        from_attributes = True


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    site_id: Optional[int]
    site_name: Optional[str] = None
    status: str
    priority: str
    start_date: Optional[date]
    target_end_date: Optional[date]
    actual_end_date: Optional[date]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    tasks: List[TaskResponse] = []
    documents: List[DocumentResponse] = []
    task_count: int = 0
    done_count: int = 0

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    site_id: Optional[int] = None
    status: str = "planning"
    priority: str = "medium"
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    site_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[date] = None
    target_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "pending"
    order: int = 0
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None
    linked_entity_label: Optional[str] = None
    notes: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    order: Optional[int] = None
    assigned_to: Optional[str] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[int] = None
    linked_entity_label: Optional[str] = None
    notes: Optional[str] = None


# --- Helper ---

def _build_project_response(p: Project) -> ProjectResponse:
    tasks = list(p.tasks) if p.tasks else []
    done = sum(1 for t in tasks if t.status == "done")
    project_docs = list(p.documents) if p.documents else []
    # Only project-level docs (no task_id)
    project_level_docs = [d for d in project_docs if d.task_id is None]
    return ProjectResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        site_id=p.site_id,
        site_name=p.site.name if p.site else None,
        status=p.status,
        priority=p.priority,
        start_date=p.start_date,
        target_end_date=p.target_end_date,
        actual_end_date=p.actual_end_date,
        created_at=p.created_at,
        updated_at=p.updated_at,
        tasks=[TaskResponse(
            **{k: v for k, v in TaskResponse.model_validate(t).__dict__.items() if k != 'documents'},
            documents=[DocumentResponse.model_validate(d) for d in (t.documents or [])],
        ) for t in tasks],
        documents=[DocumentResponse.model_validate(d) for d in project_level_docs],
        task_count=len(tasks),
        done_count=done,
    )


# --- Project Endpoints ---

@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    status: Optional[str] = None,
    site_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all projects with tasks"""
    query = (
        select(Project)
        .options(selectinload(Project.tasks).selectinload(ProjectTask.documents), selectinload(Project.documents), selectinload(Project.site))
        .order_by(Project.updated_at.desc())
    )
    if status:
        query = query.where(Project.status == status)
    if site_id:
        query = query.where(Project.site_id == site_id)

    result = await db.execute(query)
    projects = result.scalars().all()
    return [_build_project_response(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single project with all tasks"""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.tasks).selectinload(ProjectTask.documents), selectinload(Project.documents), selectinload(Project.site))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _build_project_response(project)


@router.post("/", response_model=ProjectResponse)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new project"""
    project = Project(
        **data.model_dump(exclude_none=True),
        created_by=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    result = await db.execute(
        select(Project)
        .options(selectinload(Project.tasks).selectinload(ProjectTask.documents), selectinload(Project.documents), selectinload(Project.site))
        .where(Project.id == project.id)
    )
    project = result.scalar_one()
    return _build_project_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a project"""
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.tasks).selectinload(ProjectTask.documents), selectinload(Project.documents), selectinload(Project.site))
        .where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    updates = data.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(project, key, value)

    project.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(project)
    return _build_project_response(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a project"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project.status = "cancelled"
    await db.commit()
    return {"message": "Project cancelled"}


# --- Task Endpoints ---

@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def add_task(
    project_id: int,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Add a task to a project"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    task = ProjectTask(project_id=project_id, **data.model_dump(exclude_none=True))
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: int,
    task_id: int,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a project task"""
    result = await db.execute(
        select(ProjectTask).where(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = data.model_dump(exclude_none=True)

    # Auto-set completed_at when status changes to done
    if updates.get("status") == "done" and task.status != "done":
        updates["completed_at"] = datetime.utcnow()

    for key, value in updates.items():
        setattr(task, key, value)

    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{project_id}/tasks/{task_id}")
async def delete_task(
    project_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a task from a project"""
    result = await db.execute(
        select(ProjectTask).where(
            ProjectTask.id == task_id,
            ProjectTask.project_id == project_id
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return {"message": "Task deleted"}


# --- Document Endpoints ---

@router.post("/{project_id}/documents", response_model=DocumentResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    task_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a document to a project or task"""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    if task_id:
        task_result = await db.execute(
            select(ProjectTask).where(
                ProjectTask.id == task_id,
                ProjectTask.project_id == project_id,
            )
        )
        if not task_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Task not found")

    # Create upload directory
    project_dir = f"{UPLOAD_DIR}/{project_id}"
    os.makedirs(project_dir, exist_ok=True)

    # Generate unique filename to avoid collisions
    ext = os.path.splitext(file.filename or "file")[1]
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = f"{project_dir}/{unique_name}"

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = ProjectDocument(
        project_id=project_id,
        task_id=task_id,
        filename=unique_name,
        original_filename=file.filename or "file",
        file_path=file_path,
        file_size=len(content),
        content_type=file.content_type,
        uploaded_by=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/{project_id}/documents", response_model=List[DocumentResponse])
async def list_documents(
    project_id: int,
    task_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents for a project or task"""
    query = select(ProjectDocument).where(ProjectDocument.project_id == project_id)
    if task_id is not None:
        query = query.where(ProjectDocument.task_id == task_id)
    query = query.order_by(ProjectDocument.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{project_id}/documents/{doc_id}/download")
async def download_document(
    project_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a project document"""
    result = await db.execute(
        select(ProjectDocument).where(
            ProjectDocument.id == doc_id,
            ProjectDocument.project_id == project_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=doc.file_path,
        filename=doc.original_filename,
        media_type=doc.content_type or "application/octet-stream",
    )


@router.delete("/{project_id}/documents/{doc_id}")
async def delete_document(
    project_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a project document"""
    result = await db.execute(
        select(ProjectDocument).where(
            ProjectDocument.id == doc_id,
            ProjectDocument.project_id == project_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted"}
