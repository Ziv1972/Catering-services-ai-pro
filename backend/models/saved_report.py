"""
Saved report configurations — let users persist a named report config
(data source + filters + group_by + metrics) and re-run it on demand.

A SavedReport can optionally be flagged for automatic monthly email
delivery — see `auto_email_*` columns and `MonthlyReportSent` for the
dedupe log.
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


class SavedReport(Base):
    __tablename__ = "saved_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    data_source = Column(String, nullable=False, index=True)
    config_json = Column(Text, nullable=False)

    # Auto-email scheduling
    # When auto_email_enabled is True and the trigger fires (default:
    # both NZ + KG FoodHouse proformas exist for a month), the agent
    # runs this report and emails the .xlsx to the recipients.
    auto_email_enabled = Column(Boolean, default=False, nullable=False)
    auto_email_recipients = Column(Text, nullable=True)  # comma-separated
    auto_email_trigger = Column(String, default="monthly_after_foodhouse", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class MonthlyReportSent(Base):
    """Dedupe + audit log: which auto-email reports we've already sent for
    which (year, month). Prevents double-sending when more proformas land
    for an already-completed month."""
    __tablename__ = "monthly_report_sent"

    id = Column(Integer, primary_key=True, index=True)
    saved_report_id = Column(Integer, ForeignKey("saved_reports.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    recipient_count = Column(Integer, default=0, nullable=False)
    status = Column(String, default="sent", nullable=False)  # 'sent' | 'failed'
    error = Column(Text, nullable=True)

    saved_report = relationship("SavedReport")

    __table_args__ = (
        UniqueConstraint("saved_report_id", "year", "month", name="uq_monthly_report_sent"),
    )
