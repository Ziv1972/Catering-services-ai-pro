"""
Supplier budget models - yearly budgets per supplier per site with monthly breakdown
"""
from sqlalchemy import Column, Integer, Float, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base


class SupplierBudget(Base):
    __tablename__ = "supplier_budgets"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    year = Column(Integer, nullable=False)
    yearly_amount = Column(Float, nullable=False, default=0)

    # Monthly budget breakdown
    jan = Column(Float, default=0)
    feb = Column(Float, default=0)
    mar = Column(Float, default=0)
    apr = Column(Float, default=0)
    may = Column(Float, default=0)
    jun = Column(Float, default=0)
    jul = Column(Float, default=0)
    aug = Column(Float, default=0)
    sep = Column(Float, default=0)
    oct = Column(Float, default=0)
    nov = Column(Float, default=0)
    dec = Column(Float, default=0)

    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    supplier = relationship("Supplier")
    site = relationship("Site")
    product_budgets = relationship("SupplierProductBudget", back_populates="supplier_budget")


class SupplierProductBudget(Base):
    __tablename__ = "supplier_product_budgets"

    id = Column(Integer, primary_key=True, index=True)
    supplier_budget_id = Column(Integer, ForeignKey("supplier_budgets.id"), nullable=False)
    product_category = Column(String, nullable=False)
    monthly_quantity_limit = Column(Float, nullable=False)
    unit = Column(String, nullable=False, default="kg")
    monthly_amount_limit = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    supplier_budget = relationship("SupplierBudget", back_populates="product_budgets")
