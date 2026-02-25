"""
Todo/followup model - personal tasks and delegated task tracking
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from datetime import datetime
from backend.database import Base


class TodoItem(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    assigned_to = Column(String, nullable=True)
    priority = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="pending")
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Entity linking - connect to menus, contracts, suppliers, etc.
    linked_entity_type = Column(String, nullable=True)
    linked_entity_id = Column(Integer, nullable=True)
    linked_entity_label = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
