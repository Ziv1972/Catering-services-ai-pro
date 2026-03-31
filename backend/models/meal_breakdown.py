"""
Meal breakdown model - stores detailed meal counts + costs from FoodHouse proforma ריכוז הכנסות sheet.
Extracted at proforma upload time for dashboard Budget vs Actual and meal analytics.
"""
from sqlalchemy import Column, Integer, Float, ForeignKey, Date, String, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


class MealBreakdown(Base):
    """Detailed meal breakdown extracted from FoodHouse proforma ריכוז הכנסות sheet."""
    __tablename__ = "meal_breakdowns"

    id = Column(Integer, primary_key=True, index=True)
    proforma_id = Column(Integer, ForeignKey("proformas.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    invoice_month = Column(Date, nullable=False, index=True)  # first day of month

    # Meal counts from ריכוז הכנסות rows 5-15 (column D = כמות)
    hp_meat = Column(Float, default=0)           # Row 5: ארוחת צהריים בשרית HP INDIGO
    scitex_meat = Column(Float, default=0)       # Row 6: ארוחת צהריים בשרית סאייטקס
    evening_hp = Column(Float, default=0)        # Row 7: ארוחת ערב HP
    evening_contractors = Column(Float, default=0)  # Row 8: ארוחת ערב קבלנים
    hp_dairy = Column(Float, default=0)          # Row 9: ארוחת צהריים חלבית HP INDIGO
    scitex_dairy = Column(Float, default=0)      # Row 10: ארוחת צהריים חלבית סאייטקס
    supplement = Column(Float, default=0)        # Row 11: תוספת מנה עיקרית
    contractors_meat = Column(Float, default=0)  # Row 14: ארוחת צהריים בשרית קבלנים
    contractors_dairy = Column(Float, default=0) # Row 15: ארוחת צהריים חלבית קבלנים
    working_days = Column(Integer, default=0)    # ימי עבודה

    # Per-unit prices from ריכוז הכנסות (column C = מחיר)
    hp_meat_price = Column(Float, default=0)
    scitex_meat_price = Column(Float, default=0)
    evening_hp_price = Column(Float, default=0)
    evening_contractors_price = Column(Float, default=0)
    hp_dairy_price = Column(Float, default=0)
    scitex_dairy_price = Column(Float, default=0)
    supplement_price = Column(Float, default=0)
    contractors_meat_price = Column(Float, default=0)
    contractors_dairy_price = Column(Float, default=0)

    # Total cost from ריכוז הכנסות (sum of column E = סה"כ)
    total_cost = Column(Float, default=0)

    # Relationships
    proforma = relationship("Proforma")
    site = relationship("Site")

    __table_args__ = (
        UniqueConstraint('proforma_id', name='uq_meal_breakdown_proforma'),
    )
