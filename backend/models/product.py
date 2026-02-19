"""
Product model
"""
from sqlalchemy import Column, Integer, String, Boolean
from backend.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    hebrew_name = Column(String, nullable=True)
    category = Column(String, nullable=True)  # Embedded category
    unit = Column(String, nullable=True)  # kg, L, piece, etc.
    is_active = Column(Boolean, default=True)
