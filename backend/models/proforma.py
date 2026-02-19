"""
Proforma (invoice) models
"""
from sqlalchemy import Column, Integer, String, Text, Date, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base


class Proforma(Base):
    """Supplier invoice/proforma"""
    __tablename__ = "proformas"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)

    # Proforma details
    proforma_number = Column(String, nullable=True)
    invoice_date = Column(Date, nullable=False)
    delivery_date = Column(Date, nullable=True)

    # Financial
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="ILS")

    # Status
    status = Column(String, nullable=False)  # pending, validated, approved, rejected, paid

    # File
    file_path = Column(String, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Relationships
    supplier = relationship("Supplier")
    site = relationship("Site")
    items = relationship("ProformaItem", back_populates="proforma")


class ProformaItem(Base):
    """Line item in a proforma"""
    __tablename__ = "proforma_items"

    id = Column(Integer, primary_key=True, index=True)
    proforma_id = Column(Integer, ForeignKey("proformas.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    # Item details
    product_name = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    # Validation
    price_variance = Column(Float, nullable=True)  # % difference from expected
    flagged = Column(Boolean, default=False)

    # Relationships
    proforma = relationship("Proforma", back_populates="items")
    product = relationship("Product")
