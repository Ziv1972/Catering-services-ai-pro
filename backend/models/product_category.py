"""
Product category grouping for proforma analysis.
Maps proforma line item product names to analysis categories via LIKE patterns.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


class ProductCategoryGroup(Base):
    """One of the 9 product analysis categories."""
    __tablename__ = "product_category_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)          # e.g. "total_meals"
    display_name_he = Column(String, nullable=False)             # e.g. "ארוחות"
    display_name_en = Column(String, nullable=False)             # e.g. "Total Meals"
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)

    mappings = relationship("ProductCategoryMapping", back_populates="group")


class ProductCategoryMapping(Base):
    """Maps a product name pattern (SQL LIKE) to a category group."""
    __tablename__ = "product_category_mappings"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("product_category_groups.id"), nullable=False)
    product_name_pattern = Column(String, nullable=False)        # SQL LIKE pattern e.g. "%ארוחת צהריים%"
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)  # NULL = all suppliers
    notes = Column(String, nullable=True)

    group = relationship("ProductCategoryGroup", back_populates="mappings")
    supplier = relationship("Supplier")


class WorkingDaysEntry(Base):
    """Manual input of working days per site per month."""
    __tablename__ = "working_days_entries"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    working_days = Column(Integer, nullable=False)
    notes = Column(String, nullable=True)

    site = relationship("Site")

    __table_args__ = (
        UniqueConstraint("site_id", "year", "month", name="uq_working_days_site_year_month"),
    )
