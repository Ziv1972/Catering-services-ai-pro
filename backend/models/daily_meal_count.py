"""
Daily meal count model - stores daily meal quantities from email/CSV reports
"""
from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


class DailyMealCount(Base):
    """Daily meal counts per meal type and site, imported from FoodHouse reports"""
    __tablename__ = "daily_meal_counts"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    meal_type = Column(String, nullable=False)       # e.g. "בשרי", "חלבי", "עיקרית בלבד"
    meal_type_en = Column(String, nullable=True)      # e.g. "Meat", "Dairy", "Main Only"
    restaurant_name = Column(String, nullable=True)   # raw name from CSV
    quantity = Column(Float, nullable=False, default=0)
    source = Column(String, nullable=True)            # "email", "csv_upload", "manual"
    notes = Column(Text, nullable=True)

    # Relationships
    site = relationship("Site")

    __table_args__ = (
        UniqueConstraint('date', 'site_id', 'meal_type', name='uq_daily_meal_date_site_type'),
    )
