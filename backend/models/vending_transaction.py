"""
Vending machine transaction model — stores row-level data from the detailed
Excel report (מ.א אוטומטים). One row per dispense/transaction.

The matching aggregated invoice totals live in Proforma + ProformaItem
(8 product categories with prices from the PDF invoice).
"""
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


class VendingTransaction(Base):
    """One dispense / transaction row from the vending Excel export."""

    __tablename__ = "vending_transactions"

    id = Column(Integer, primary_key=True, index=True)
    proforma_id = Column(Integer, ForeignKey("proformas.id"), nullable=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False, index=True)
    shift = Column(String, nullable=False, default="all", index=True)  # 'all' | 'day' | 'evening'

    tx_date = Column(Date, nullable=False, index=True)
    product_name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)  # matched category from invoice (e.g. "שמיניה")
    quantity = Column(Float, nullable=False, default=0)
    unit_price = Column(Float, nullable=True)   # back-filled from matching invoice
    total_price = Column(Float, nullable=True)  # quantity * unit_price

    machine_id = Column(String, nullable=True, index=True)  # optional (some KG files include it)

    created_at = Column(DateTime, default=datetime.utcnow)

    proforma = relationship("Proforma")
    site = relationship("Site")
