"""
Meeting model
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class MeetingType(str, enum.Enum):
    SITE_MANAGER = "site_manager"
    TECHNICAL = "technical"
    HP_MANAGEMENT = "hp_management"
    VENDOR = "vendor"
    OTHER = "other"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    meeting_type = Column(Enum(MeetingType, native_enum=False), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=60)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)

    # AI-generated content
    ai_brief = Column(Text, nullable=True)  # Pre-meeting brief
    ai_agenda = Column(Text, nullable=True)  # Suggested agenda
    ai_summary = Column(Text, nullable=True)  # Post-meeting summary

    # Relationships
    site = relationship("Site")
    notes = relationship("MeetingNote", back_populates="meeting")
