"""
Price list models
"""
from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class PriceList(Base):
    __tablename__ = "price_lists"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    effective_date = Column(Date, nullable=False)
    file_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    supplier = relationship("Supplier")
    items = relationship("PriceListItem", back_populates="price_list")


class PriceListItem(Base):
    __tablename__ = "price_list_items"

    id = Column(Integer, primary_key=True, index=True)
    price_list_id = Column(Integer, ForeignKey("price_lists.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    unit = Column(String, nullable=True)

    # Relationships
    price_list = relationship("PriceList", back_populates="items")
    product = relationship("Product")
