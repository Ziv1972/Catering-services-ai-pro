"""
Supplier model
"""
from sqlalchemy import Column, Integer, String, Date, Text, Boolean
from backend.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    contact_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    # Contract info
    contract_start_date = Column(Date, nullable=True)
    contract_end_date = Column(Date, nullable=True)
    payment_terms = Column(String, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
