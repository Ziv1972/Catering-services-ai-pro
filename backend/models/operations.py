"""
Operational tracking models
"""
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class QuantityLimit(Base):
    """Procurement quantity limits"""
    __tablename__ = "quantity_limits"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)

    # Limits
    min_quantity = Column(Float, nullable=True)
    max_quantity = Column(Float, nullable=True)
    unit = Column(String, nullable=False)

    # Period
    period = Column(String, nullable=False)  # daily, weekly, monthly

    # Active
    is_active = Column(Boolean, default=True)

    # Relationships
    product = relationship("Product")
    site = relationship("Site")


class Anomaly(Base):
    """Detected anomalies in data"""
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)

    # What
    anomaly_type = Column(String, nullable=False)  # price_spike, usage_spike, etc.
    entity_type = Column(String, nullable=False)  # product, supplier, site
    entity_id = Column(Integer, nullable=False)

    # When
    detected_at = Column(Date, nullable=False)

    # Details
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)  # low, medium, high

    # Value
    expected_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    variance_percent = Column(Float, nullable=True)

    # Resolution
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
