"""
Violation tracking model — Exceptions & Violations (חריגות והפרות)
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from enum import Enum


class ViolationSource(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SLACK = "slack"
    MANUAL = "manual"
    FORM = "form"


class ViolationSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationStatus(str, Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ViolationCategory(str, Enum):
    KITCHEN_CLEANLINESS = "kitchen_cleanliness"
    DINING_CLEANLINESS = "dining_cleanliness"
    STAFF_ATTIRE = "staff_attire"
    MISSING_DINING_EQUIPMENT = "missing_dining_equipment"
    PORTION_WEIGHT = "portion_weight"
    MENU_VARIETY = "menu_variety"
    MAIN_COURSE_DEPLETED = "main_course_depleted"
    STAFF_SHORTAGE = "staff_shortage"
    SERVICE = "service"
    POSITIVE_NOTES = "positive_notes"


class RestaurantType(str, Enum):
    MEAT = "meat"
    DAIRY = "dairy"


# Hebrew labels for categories (used by forms and UI)
CATEGORY_LABELS_HE = {
    ViolationCategory.KITCHEN_CLEANLINESS: "ניקיון מטבח וציוד",
    ViolationCategory.DINING_CLEANLINESS: "ניקיון חדר אוכל",
    ViolationCategory.STAFF_ATTIRE: "לבוש עובדים",
    ViolationCategory.MISSING_DINING_EQUIPMENT: "חוסר בציוד סועד (סכו\"ם, מגשים וכו')",
    ViolationCategory.PORTION_WEIGHT: "משקל מנה לא תואם מפרט",
    ViolationCategory.MENU_VARIETY: "מגוון המנות לא תואם תפריט",
    ViolationCategory.MAIN_COURSE_DEPLETED: "מנה עיקרית נגמרה בזמן הארוחה",
    ViolationCategory.STAFF_SHORTAGE: "חוסר עובדים",
    ViolationCategory.SERVICE: "שירות",
    ViolationCategory.POSITIVE_NOTES: "נקודות חיוביות",
}

# Reverse lookup: Hebrew label → enum value
CATEGORY_FROM_HE = {v: k for k, v in CATEGORY_LABELS_HE.items()}

SEVERITY_LABELS_HE = {
    ViolationSeverity.LOW: "נמוך",
    ViolationSeverity.MEDIUM: "בינוני",
    ViolationSeverity.HIGH: "גבוה",
    ViolationSeverity.CRITICAL: "קריטי",
}

SEVERITY_FROM_HE = {v: k for k, v in SEVERITY_LABELS_HE.items()}

# Restaurant field parsing: "קרית גת - מסעדת בשר" → (site_name, restaurant_type)
RESTAURANT_MAP = {
    "קרית גת - מסעדת בשר": ("Kiryat Gat", RestaurantType.MEAT),
    "קרית גת - מסעדת חלב": ("Kiryat Gat", RestaurantType.DAIRY),
    "נס ציונה - מסעדת בשר": ("Nes Ziona", RestaurantType.MEAT),
    "נס ציונה - מסעדת חלב": ("Nes Ziona", RestaurantType.DAIRY),
}


class Violation(Base):
    """Inspection finding — exception or violation"""
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)

    # Source information
    source = Column(SQLEnum(ViolationSource, native_enum=False), nullable=False)
    source_id = Column(String, nullable=True)

    # Violation content
    violation_text = Column(Text, nullable=False)

    # AI-generated classifications
    category = Column(SQLEnum(ViolationCategory, native_enum=False), nullable=True)
    severity = Column(SQLEnum(ViolationSeverity, native_enum=False), nullable=True)
    sentiment_score = Column(Float, nullable=True)

    # AI analysis
    ai_summary = Column(Text, nullable=True)
    ai_root_cause = Column(Text, nullable=True)
    ai_suggested_action = Column(Text, nullable=True)
    pattern_group_id = Column(String, nullable=True)

    # Fine linkage
    fine_rule_id = Column(Integer, ForeignKey("fine_rules.id"), nullable=True)
    fine_amount = Column(Float, nullable=True)

    # Inspector / complainant info
    employee_name = Column(String, nullable=True)
    employee_email = Column(String, nullable=True)
    employee_phone = Column(String, nullable=True)
    is_anonymous = Column(Boolean, default=False)

    # Restaurant type (meat/dairy)
    restaurant_type = Column(SQLEnum(RestaurantType, native_enum=False), nullable=True)

    # Status tracking
    status = Column(SQLEnum(ViolationStatus, native_enum=False), default=ViolationStatus.NEW)

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
    site = relationship("Site", backref="violations")
    fine_rule = relationship("FineRule")


class FineRule(Base):
    """Predefined fine catalog — maps violation types to fine amounts"""
    __tablename__ = "fine_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(SQLEnum(ViolationCategory, native_enum=False), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ViolationPattern(Base):
    """Detected patterns across multiple violations"""
    __tablename__ = "violation_patterns"

    id = Column(Integer, primary_key=True, index=True)
    pattern_id = Column(String, unique=True, nullable=False, index=True)

    # Pattern details
    pattern_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)

    # Affected violations
    violation_count = Column(Integer, default=0)
    first_occurrence = Column(DateTime(timezone=True), nullable=False)
    last_occurrence = Column(DateTime(timezone=True), nullable=False)

    # AI recommendation
    recommendation = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
