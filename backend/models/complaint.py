"""
Complaint tracking model
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from enum import Enum


class ComplaintSource(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    MANUAL = "manual"
    FORM = "form"


class ComplaintSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ComplaintStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ComplaintCategory(str, Enum):
    FOOD_QUALITY = "food_quality"
    TEMPERATURE = "temperature"
    SERVICE = "service"
    VARIETY = "variety"
    DIETARY = "dietary"
    CLEANLINESS = "cleanliness"
    EQUIPMENT = "equipment"
    OTHER = "other"


class Complaint(Base):
    """Employee complaint or feedback"""
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)

    # Source information
    source = Column(SQLEnum(ComplaintSource, native_enum=False), nullable=False)
    source_id = Column(String, nullable=True)  # Email message ID, Slack thread ID, etc.

    # Complaint content
    complaint_text = Column(Text, nullable=False)

    # AI-generated classifications
    category = Column(SQLEnum(ComplaintCategory, native_enum=False), nullable=True)
    severity = Column(SQLEnum(ComplaintSeverity, native_enum=False), nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0

    # AI analysis
    ai_summary = Column(Text, nullable=True)
    ai_root_cause = Column(Text, nullable=True)
    ai_suggested_action = Column(Text, nullable=True)
    pattern_group_id = Column(String, nullable=True)  # Links related complaints

    # Fine linkage
    fine_rule_id = Column(Integer, ForeignKey("fine_rules.id"), nullable=True)
    fine_amount = Column(Float, nullable=True)  # Actual fine amount applied (may override rule)

    # Complainant (optional, may be anonymous)
    employee_name = Column(String, nullable=True)
    employee_email = Column(String, nullable=True)
    is_anonymous = Column(Boolean, default=False)

    # Status tracking
    status = Column(SQLEnum(ComplaintStatus, native_enum=False), default=ComplaintStatus.NEW)

    # Timestamps
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Response
    response_text = Column(Text, nullable=True)
    response_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Resolution
    resolution_notes = Column(Text, nullable=True)
    requires_vendor_action = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    site = relationship("Site", backref="complaints")
    fine_rule = relationship("FineRule")


class FineRule(Base):
    """Predefined fine catalog — maps violation types to fine amounts"""
    __tablename__ = "fine_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(SQLEnum(ComplaintCategory, native_enum=False), nullable=False)
    amount = Column(Float, nullable=False)  # Fine amount in NIS
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ComplaintPattern(Base):
    """Detected patterns across multiple complaints"""
    __tablename__ = "complaint_patterns"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(String, unique=True, nullable=False, index=True)

    # Pattern details
    pattern_type = Column(String, nullable=False)  # recurring_issue, time_based, location_based, trend
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)

    # Affected complaints
    complaint_count = Column(Integer, default=0)
    first_occurrence = Column(DateTime(timezone=True), nullable=False)
    last_occurrence = Column(DateTime(timezone=True), nullable=False)

    # AI recommendation
    recommendation = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
