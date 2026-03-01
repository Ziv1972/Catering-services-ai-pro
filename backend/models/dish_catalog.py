"""
Dish catalog — maps menu dish names to categories and compliance rules.
Users assign categories and rule links so the compliance engine
can match dishes accurately instead of guessing from Hebrew keywords.
"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from backend.database import Base


# Valid dish categories (used for frontend dropdown)
DISH_CATEGORIES = [
    "soup",
    "protein_beef",
    "protein_chicken",
    "schnitzel",
    "chicken_breast",
    "fish",
    "vegan",
    "carbs",
    "legumes",
    "salads",
    "desserts",
    "side_dish",
    "other",
]

# Hebrew labels for display
DISH_CATEGORY_LABELS = {
    "soup": "Soup / מרק",
    "protein_beef": "Protein - Beef / בקר",
    "protein_chicken": "Protein - Chicken / עוף",
    "schnitzel": "Schnitzel / שניצל",
    "chicken_breast": "Chicken Breast / חזה עוף",
    "fish": "Fish / דג",
    "vegan": "Vegan / טבעוני",
    "carbs": "Carbs / פחמימות",
    "legumes": "Legumes / קטניות",
    "salads": "Salads / סלטים",
    "desserts": "Desserts / קינוחים",
    "side_dish": "Side Dish / תוספות",
    "other": "Other / אחר",
}


class DishCatalog(Base):
    """Maps a dish name to a category and optional compliance rule."""
    __tablename__ = "dish_catalog"

    id = Column(Integer, primary_key=True, index=True)
    dish_name = Column(String, nullable=False, unique=True, index=True)
    category = Column(String, nullable=True)  # one of DISH_CATEGORIES
    compliance_rule_id = Column(
        Integer, ForeignKey("compliance_rules.id"), nullable=True
    )
    approved = Column(Boolean, default=False, nullable=False)
    source_check_id = Column(Integer, nullable=True)  # which check extracted this dish
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    compliance_rule = relationship("ComplianceRule", lazy="noload")
