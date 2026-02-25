"""
Maintenance budget models - quarterly budgets and expense tracking
"""
from sqlalchemy import Column, Integer, Float, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class MaintenanceBudget(Base):
    __tablename__ = "maintenance_budgets"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    budget_amount = Column(Float, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    # Relationships
    site = relationship("Site")
    expenses = relationship("MaintenanceExpense", back_populates="budget")


class MaintenanceExpense(Base):
    __tablename__ = "maintenance_expenses"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    maintenance_budget_id = Column(Integer, ForeignKey("maintenance_budgets.id"), nullable=True)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False, default="general")
    vendor = Column(String, nullable=True)
    receipt_reference = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    site = relationship("Site")
    budget = relationship("MaintenanceBudget", back_populates="expenses")
