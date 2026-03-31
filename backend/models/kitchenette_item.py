"""
Kitchenette (BTB) item model - stores monthly product consumption from FoodHouse proforma
ריכוז מטבחונים tab. Each row = one product for one site/month.
"""
from sqlalchemy import Column, Integer, Float, ForeignKey, Date, String, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


# 7 BTB product families for drill-down
KITCHENETTE_FAMILIES = {
    "coffee_tea": "קפה ותה",
    "coffee_machines": "קפה ושכירות מכונות",
    "dairy": "מוצרי חלב",
    "dry_goods": "יבשים",
    "fruits": "פירות",
    "accompaniments": "נילווים",
    "misc": "שונות",
}

# Keywords for auto-classifying products into families
FAMILY_KEYWORDS = {
    "coffee_tea": ["קפה נמס", "קפה מגורען", "קפה נטול", "תה", "סוכר", "נענע", "לימון", "ממתיק"],
    "coffee_machines": ["eversys", "אוורסיס", "שכירות", "מכונ", "קפה כד", "קפה שחור 1", "קפה קדם"],
    "dairy": ["חלב", "יופלה", "דנונה", "קוטג", "שמנת", "קצפת", "גבינ", "יוגורט", "קרם"],
    "dry_goods": ["גרנולה", "ופל", "עוגיות", "דבש", "סילן", "ביסקוויט", "קרקר", "חטיף"],
    "fruits": ["פירות", "ירקות", "פרי"],
    "accompaniments": ["תפוחים", "גזר", "סלק", "מיץ", "תרכיז", "מסחטה"],
    "misc": ["כוסות", "מים", "סודה", "כריכ", "קיסמ", "מפית", "סנדוויץ"],
}


def classify_product(product_name: str) -> str:
    """Classify a kitchenette product into one of the 7 BTB families."""
    name_lower = product_name.strip()
    for family_key, keywords in FAMILY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return family_key
    return "misc"


class KitchenetteItem(Base):
    """Monthly kitchenette/BTB product consumption from FoodHouse proforma."""
    __tablename__ = "kitchenette_items"

    id = Column(Integer, primary_key=True, index=True)
    proforma_id = Column(Integer, ForeignKey("proformas.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    invoice_month = Column(Date, nullable=False, index=True)

    product_name = Column(String, nullable=False)
    family = Column(String, nullable=False, default="misc")  # one of KITCHENETTE_FAMILIES keys
    quantity = Column(Float, default=0)
    price = Column(Float, default=0)           # base price (מחיר)
    price_with_commission = Column(Float, default=0)  # כולל עמלה 5.5%
    total_cost = Column(Float, default=0)      # סה"כ ₪

    # Relationships
    proforma = relationship("Proforma")
    site = relationship("Site")
