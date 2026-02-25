"""
Project models - multi-phase project management with linkable tasks
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    status = Column(String, nullable=False, default="planning")
    priority = Column(String, nullable=False, default="medium")
    start_date = Column(Date, nullable=True)
    target_end_date = Column(Date, nullable=True)
    actual_end_date = Column(Date, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    site = relationship("Site")
    tasks = relationship("ProjectTask", back_populates="project", order_by="ProjectTask.order")
    creator = relationship("User")


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")
    order = Column(Integer, nullable=False, default=0)
    assigned_to = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Entity linking - connect task to menus, contracts, suppliers, etc.
    linked_entity_type = Column(String, nullable=True)
    linked_entity_id = Column(Integer, nullable=True)
    linked_entity_label = Column(String, nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="tasks")
