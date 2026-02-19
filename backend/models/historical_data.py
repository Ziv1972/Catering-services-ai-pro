"""
Historical meal data model
"""
from sqlalchemy import Column, Integer, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class HistoricalMealData(Base):
    __tablename__ = "historical_meal_data"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    meal_count = Column(Integer, nullable=False)
    cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    site = relationship("Site")
