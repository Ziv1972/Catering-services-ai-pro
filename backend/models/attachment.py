"""
Generic Attachment model - universal file storage for any entity in the app.
Supports AI processing (summarize / extract data).
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.database import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)

    # Polymorphic link to any entity
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)

    # File metadata
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)

    # AI processing results
    ai_summary = Column(Text, nullable=True)
    ai_extracted_data = Column(Text, nullable=True)  # JSON string
    processing_status = Column(String, nullable=True)  # None, "processing", "done", "error"

    # Audit
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    uploader = relationship("User")
