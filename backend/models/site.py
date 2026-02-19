"""
Site model (Nes Ziona, Kiryat Gat)
"""
from sqlalchemy import Column, Integer, String, Float, Boolean
from backend.database import Base


class Site(Base):
    __tablename__ = "sites"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # "Nes Ziona", "Kiryat Gat"
    code = Column(String, unique=True, nullable=False)  # "NZ", "KG"
    monthly_budget = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
