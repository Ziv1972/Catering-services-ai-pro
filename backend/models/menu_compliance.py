"""
Menu compliance checking models
Migrated from old FoodHouse Analytics 56-rule system
"""
from sqlalchemy import Column, Integer, String, Text, Date, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from backend.database import Base


class ComplianceRule(Base):
    """Compliance rule definition"""
    __tablename__ = "compliance_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    rule_type = Column(String, nullable=False)  # mandatory, frequency
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)  # Dietary, Menu Variety, Daily Requirements
    parameters = Column(JSON, nullable=True)  # {"frequency": "daily", "max_per_week": 2}
    priority = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)


class MenuCheck(Base):
    """Monthly menu compliance check"""
    __tablename__ = "menu_checks"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)

    # Menu file
    file_path = Column(String, nullable=True)
    month = Column(String, nullable=False)  # "2025-02"
    year = Column(Integer, nullable=False)

    # Check status
    total_findings = Column(Integer, default=0)
    critical_findings = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    passed_rules = Column(Integer, default=0)

    # Summary comparison (dishes above/under/even vs standard)
    dishes_above = Column(Integer, default=0)
    dishes_under = Column(Integer, default=0)
    dishes_even = Column(Integer, default=0)

    # Timestamps
    checked_at = Column(Date, nullable=False)

    # Relationships
    site = relationship("Site")
    days = relationship("MenuDay", back_populates="menu_check")
    results = relationship("CheckResult", back_populates="menu_check")


class MenuDay(Base):
    """Individual day in a menu"""
    __tablename__ = "menu_days"

    id = Column(Integer, primary_key=True, index=True)
    menu_check_id = Column(Integer, ForeignKey("menu_checks.id"), nullable=False)

    # Day details
    date = Column(Date, nullable=False)
    day_of_week = Column(String, nullable=False)  # Sunday, Monday, etc.
    week_number = Column(Integer, nullable=False)  # 1-4

    # Day type
    is_holiday = Column(Boolean, default=False)
    is_theme_day = Column(Boolean, default=False)
    day_type_override = Column(String, nullable=True)  # "Purim", "Passover", etc.

    # Menu content (stored as JSON for flexibility)
    menu_items = Column(JSON, nullable=True)  # {category: [items]}

    # Relationships
    menu_check = relationship("MenuCheck", back_populates="days")


class CheckResult(Base):
    """Result of running a compliance rule"""
    __tablename__ = "check_results"

    id = Column(Integer, primary_key=True, index=True)
    menu_check_id = Column(Integer, ForeignKey("menu_checks.id"), nullable=False)

    # Rule identification
    rule_name = Column(String, nullable=False)
    rule_category = Column(String, nullable=True)

    # Result
    passed = Column(Boolean, nullable=False)
    severity = Column(String, nullable=False)  # critical, warning, info

    # Details
    finding_text = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)  # Supporting data

    # Review status
    reviewed = Column(Boolean, default=False)
    review_status = Column(String, nullable=True)  # approved, parser_error, supplier_note
    review_notes = Column(Text, nullable=True)

    # Relationships
    menu_check = relationship("MenuCheck", back_populates="results")
