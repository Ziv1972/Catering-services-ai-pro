"""
Main FastAPI application
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from backend.config import get_settings
from backend.database import engine, Base, AsyncSessionLocal
from backend.models import User, Site
from backend.models.supplier import Supplier
from backend.models.supplier_budget import SupplierBudget
from backend.models.complaint import FineRule
from backend.models.product import Product
from backend.models.price_list import PriceList, PriceListItem
from backend.models.menu_compliance import ComplianceRule
from backend.api.auth import get_password_hash
from backend.api import auth, meetings, chat, dashboard, complaints
from backend.api import menu_compliance, proformas, historical, anomalies, webhooks, suppliers
from backend.api import supplier_budgets, projects, maintenance, todos, price_lists, fine_rules

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    # Run column migrations for existing tables (create_all doesn't ALTER tables)
    async with AsyncSessionLocal() as session:
        from backend.database import is_sqlite
        migrations = [
            ("supplier_budgets", "shift", "VARCHAR DEFAULT 'all'"),
            ("complaints", "fine_rule_id", "INTEGER"),
            ("complaints", "fine_amount", "FLOAT DEFAULT 0"),
        ]
        for table, column, col_type in migrations:
            try:
                await session.execute(text(f"SELECT {column} FROM {table} LIMIT 1"))
            except Exception:
                await session.rollback()
                try:
                    await session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                    await session.commit()
                    logger.info(f"Added column {table}.{column}")
                except Exception as e:
                    await session.rollback()
                    logger.warning(f"Could not add column {table}.{column}: {e}")

    # Seed default user and sites
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "ziv@hp.com"))
        existing_user = result.scalar_one_or_none()
        if not existing_user:
            session.add(User(
                email="ziv@hp.com",
                full_name="Ziv Reshef",
                hashed_password=get_password_hash("admin123"),
                is_admin=True,
            ))
            logger.info("Created default admin user")
        else:
            existing_user.hashed_password = get_password_hash("admin123")
            logger.info("Reset admin user password")

        result = await session.execute(select(Site))
        if not result.scalars().first():
            session.add(Site(id=1, name="Nes Ziona", code="NZ", monthly_budget=120000))
            session.add(Site(id=2, name="Kiryat Gat", code="KG", monthly_budget=120000))
            logger.info("Created default sites")

        await session.commit()

    # Recalculate proforma totals from line items (fixes migrated data)
    async with AsyncSessionLocal() as session:
        # First check how many need recalculation
        check = await session.execute(text(
            "SELECT COUNT(*) FROM proformas WHERE total_amount = 0 OR total_amount IS NULL"
        ))
        zero_count = check.scalar() or 0
        logger.info(f"Proformas with zero/null totals: {zero_count}")

        if zero_count > 0:
            # Check if line items have data
            items_check = await session.execute(text(
                "SELECT COUNT(*), COALESCE(SUM(total_price), 0) FROM proforma_items"
            ))
            items_row = items_check.fetchone()
            logger.info(f"Proforma items: count={items_row[0]}, sum={items_row[1]}")

            result = await session.execute(text("""
                UPDATE proformas SET total_amount = (
                    SELECT COALESCE(SUM(total_price), 0)
                    FROM proforma_items
                    WHERE proforma_items.proforma_id = proformas.id
                )
                WHERE total_amount = 0 OR total_amount IS NULL
            """))
            await session.commit()
            logger.info(f"Recalculated {zero_count} proforma totals from line items")
        else:
            # Log current totals for verification
            totals_check = await session.execute(text(
                "SELECT COUNT(*), SUM(total_amount) FROM proformas"
            ))
            totals_row = totals_check.fetchone()
            logger.info(f"All proforma totals OK: count={totals_row[0]}, sum={totals_row[1]}")

    # Seed FoodHouse supplier and budgets if missing
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Supplier).where(Supplier.name == "FoodHouse")
        )
        foodhouse = result.scalar_one_or_none()
        if not foodhouse:
            foodhouse = Supplier(
                name="FoodHouse",
                contact_name="FoodHouse Contact",
                is_active=True,
                notes="Main catering supplier",
            )
            session.add(foodhouse)
            await session.flush()
            logger.info(f"Created FoodHouse supplier (id={foodhouse.id})")

        # Create budgets for 2025 and 2026 if missing
        # NZ: ~127K/mo, KG: ~59K/mo (based on existing contract values)
        budget_configs = [
            (1, 127000),  # Nes Ziona
            (2, 59000),   # Kiryat Gat
        ]
        for yr in [2025, 2026]:
            for site_id, monthly in budget_configs:
                existing = await session.execute(
                    select(SupplierBudget).where(
                        SupplierBudget.supplier_id == foodhouse.id,
                        SupplierBudget.site_id == site_id,
                        SupplierBudget.year == yr,
                    )
                )
                if not existing.scalar_one_or_none():
                    session.add(SupplierBudget(
                        supplier_id=foodhouse.id,
                        site_id=site_id,
                        year=yr,
                        yearly_amount=monthly * 12,
                        jan=monthly, feb=monthly, mar=monthly,
                        apr=monthly, may=monthly, jun=monthly,
                        jul=monthly, aug=monthly, sep=monthly,
                        oct=monthly, nov=monthly, dec=monthly,
                        is_active=True,
                    ))
        await session.commit()
        logger.info("FoodHouse supplier and budgets seeded")

    # Seed default fine rules if none exist
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(FineRule))
        if not existing.scalars().first():
            default_fines = [
                FineRule(name="Foreign object in food", category="food_quality", amount=500, description="Physical contamination found in served food"),
                FineRule(name="Spoiled / expired ingredients", category="food_quality", amount=400, description="Use of expired or spoiled ingredients"),
                FineRule(name="Incorrect temperature (hot)", category="temperature", amount=300, description="Hot food served below required temperature"),
                FineRule(name="Incorrect temperature (cold)", category="temperature", amount=300, description="Cold food served above required temperature"),
                FineRule(name="Late delivery / service", category="service", amount=200, description="Catering delivered after agreed time"),
                FineRule(name="Rude / unprofessional staff", category="service", amount=250, description="Staff behavior complaint"),
                FineRule(name="Insufficient variety", category="variety", amount=150, description="Menu variety below contracted minimum"),
                FineRule(name="Missing dietary option", category="dietary", amount=350, description="Required dietary option (vegan, kosher, etc.) not available"),
                FineRule(name="Kitchen / area uncleanliness", category="cleanliness", amount=400, description="Hygiene standard violation in kitchen or dining area"),
                FineRule(name="Equipment malfunction not reported", category="equipment", amount=200, description="Failed to report or fix broken equipment"),
                FineRule(name="Pest sighting", category="cleanliness", amount=500, description="Pest found in kitchen or dining area"),
                FineRule(name="Menu not as contracted", category="food_quality", amount=300, description="Served menu deviates from contracted menu plan"),
            ]
            for f in default_fines:
                f.is_active = True
                session.add(f)
            await session.commit()
            logger.info("Seeded default fine rules")

    # Seed product catalog and price lists if none exist
    async with AsyncSessionLocal() as session:
        existing_products = await session.execute(select(Product))
        if not existing_products.scalars().first():
            product_data = [
                # Proteins
                ("Chicken Breast", "חזה עוף", "protein", "kg"),
                ("Chicken Thigh", "ירך עוף", "protein", "kg"),
                ("Ground Beef", "בשר טחון", "protein", "kg"),
                ("Beef Steak", "סטייק בקר", "protein", "kg"),
                ("Salmon Fillet", "פילה סלמון", "protein", "kg"),
                ("Tilapia Fillet", "פילה טילאפיה", "protein", "kg"),
                ("Eggs", "ביצים", "protein", "unit"),
                ("Tofu", "טופו", "protein", "kg"),
                # Dairy
                ("White Cheese 5%", "גבינה לבנה 5%", "dairy", "kg"),
                ("Yellow Cheese", "גבינה צהובה", "dairy", "kg"),
                ("Cream Cheese", "גבינת שמנת", "dairy", "kg"),
                ("Milk 3%", "חלב 3%", "dairy", "L"),
                ("Butter", "חמאה", "dairy", "kg"),
                ("Yogurt", "יוגורט", "dairy", "unit"),
                # Vegetables
                ("Tomatoes", "עגבניות", "vegetable", "kg"),
                ("Cucumbers", "מלפפונים", "vegetable", "kg"),
                ("Lettuce", "חסה", "vegetable", "unit"),
                ("Onions", "בצל", "vegetable", "kg"),
                ("Potatoes", "תפוחי אדמה", "vegetable", "kg"),
                ("Carrots", "גזר", "vegetable", "kg"),
                ("Bell Peppers", "פלפל", "vegetable", "kg"),
                ("Zucchini", "קישוא", "vegetable", "kg"),
                # Fruits
                ("Apples", "תפוחים", "fruit", "kg"),
                ("Bananas", "בננות", "fruit", "kg"),
                ("Oranges", "תפוזים", "fruit", "kg"),
                ("Watermelon", "אבטיח", "fruit", "kg"),
                # Grains & Staples
                ("Rice", "אורז", "grain", "kg"),
                ("Pasta", "פסטה", "grain", "kg"),
                ("Bread Loaf", "לחם", "grain", "unit"),
                ("Pita Bread", "פיתה", "grain", "unit"),
                ("Flour", "קמח", "grain", "kg"),
                ("Couscous", "קוסקוס", "grain", "kg"),
                # Oils & Condiments
                ("Olive Oil", "שמן זית", "oil", "L"),
                ("Canola Oil", "שמן קנולה", "oil", "L"),
                ("Salt", "מלח", "condiment", "kg"),
                ("Black Pepper", "פלפל שחור", "condiment", "kg"),
                ("Tahini", "טחינה", "condiment", "kg"),
                ("Hummus", "חומוס", "condiment", "kg"),
                # Beverages
                ("Water Bottles (0.5L)", "בקבוקי מים", "beverage", "unit"),
                ("Orange Juice (1L)", "מיץ תפוזים", "beverage", "L"),
                ("Coffee Beans", "פולי קפה", "beverage", "kg"),
                ("Tea Bags (box)", "שקיקי תה", "beverage", "unit"),
            ]
            products = []
            for name, heb, cat, unit in product_data:
                p = Product(name=name, hebrew_name=heb, category=cat, unit=unit, is_active=True)
                session.add(p)
                products.append(p)
            await session.flush()
            logger.info(f"Seeded {len(products)} products")

            # Create price list for FoodHouse
            foodhouse_result = await session.execute(
                select(Supplier).where(Supplier.name == "FoodHouse")
            )
            foodhouse = foodhouse_result.scalar_one_or_none()
            if foodhouse:
                from datetime import date as dt_date
                price_list = PriceList(
                    supplier_id=foodhouse.id,
                    effective_date=dt_date(2025, 1, 1),
                    notes="FoodHouse 2025 price list",
                )
                session.add(price_list)
                await session.flush()

                # Realistic Israeli catering prices per unit
                price_map = {
                    "Chicken Breast": 32, "Chicken Thigh": 24, "Ground Beef": 45,
                    "Beef Steak": 95, "Salmon Fillet": 75, "Tilapia Fillet": 45,
                    "Eggs": 1.2, "Tofu": 28,
                    "White Cheese 5%": 22, "Yellow Cheese": 38, "Cream Cheese": 30,
                    "Milk 3%": 6.5, "Butter": 42, "Yogurt": 4,
                    "Tomatoes": 8, "Cucumbers": 6, "Lettuce": 5,
                    "Onions": 5, "Potatoes": 4.5, "Carrots": 5,
                    "Bell Peppers": 12, "Zucchini": 7,
                    "Apples": 9, "Bananas": 7, "Oranges": 6, "Watermelon": 4,
                    "Rice": 8, "Pasta": 7, "Bread Loaf": 12, "Pita Bread": 2,
                    "Flour": 4, "Couscous": 10,
                    "Olive Oil": 32, "Canola Oil": 12, "Salt": 3,
                    "Black Pepper": 80, "Tahini": 22, "Hummus": 18,
                    "Water Bottles (0.5L)": 2, "Orange Juice (1L)": 9,
                    "Coffee Beans": 65, "Tea Bags (box)": 15,
                }
                for p in products:
                    price = price_map.get(p.name, 10)
                    session.add(PriceListItem(
                        price_list_id=price_list.id,
                        product_id=p.id,
                        price=price,
                        unit=p.unit,
                    ))
                logger.info(f"Seeded FoodHouse price list with {len(products)} items")

            await session.commit()
            logger.info("Product catalog and price lists seeded")

    # Seed default menu compliance rules if none exist
    async with AsyncSessionLocal() as session:
        existing_rules = await session.execute(select(ComplianceRule))
        if not existing_rules.scalars().first():
            default_compliance_rules = [
                # Daily mandatory categories (priority 1 = critical)
                ComplianceRule(
                    name="Daily main course required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include a main course (עיקרית)",
                    parameters={"required_category": "עיקרית"},
                    priority=1,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Daily salad bar required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include salads (סלטים)",
                    parameters={"required_category": "סלטים"},
                    priority=1,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Daily soup required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include soup (מרק)",
                    parameters={"required_category": "מרק"},
                    priority=2,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Daily side dishes required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include side dishes (תוספות)",
                    parameters={"required_category": "תוספות"},
                    priority=1,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Daily bread required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include bread (לחם)",
                    parameters={"required_category": "לחם"},
                    priority=2,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Daily drinks required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include beverages (שתיה)",
                    parameters={"required_category": "שתיה"},
                    priority=2,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Daily dessert required",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Every day must include dessert (קינוח)",
                    parameters={"required_category": "קינוח"},
                    priority=2,
                    is_active=True,
                ),
                # Dietary variety rules
                ComplianceRule(
                    name="Fish served at least once per week",
                    rule_type="frequency",
                    category="Menu Variety",
                    description="Fish must appear at least once per week",
                    parameters={"item": "דג", "min_per_week": 1},
                    priority=2,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Vegetarian option available",
                    rule_type="mandatory",
                    category="Dietary",
                    description="Vegetarian option must be available in the menu",
                    parameters={"required_item": "צמחוני"},
                    priority=1,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Chicken not more than 3 times per week",
                    rule_type="frequency",
                    category="Menu Variety",
                    description="Chicken should not be served more than 3 times per week",
                    parameters={"item": "עוף", "max_per_week": 3},
                    priority=2,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Schnitzel not more than 2 times per week",
                    rule_type="frequency",
                    category="Menu Variety",
                    description="Schnitzel should not be served more than 2 times per week",
                    parameters={"item": "שניצל", "max_per_week": 2},
                    priority=2,
                    is_active=True,
                ),
                ComplianceRule(
                    name="Fresh fruit available daily",
                    rule_type="mandatory",
                    category="Daily Requirements",
                    description="Fresh fruit must be available (פירות)",
                    parameters={"required_category": "פירות"},
                    priority=2,
                    is_active=True,
                ),
            ]
            for rule in default_compliance_rules:
                session.add(rule)
            await session.commit()
            logger.info(f"Seeded {len(default_compliance_rules)} default compliance rules")

    yield

    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001", "https://frontend-production-c346.up.railway.app"],
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(meetings.router, prefix="/api/meetings", tags=["Meetings"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(complaints.router, prefix="/api/complaints", tags=["Complaints"])
app.include_router(menu_compliance.router, prefix="/api/menu-compliance", tags=["Menu Compliance"])
app.include_router(proformas.router, prefix="/api/proformas", tags=["Proformas"])
app.include_router(historical.router, prefix="/api/historical", tags=["Historical"])
app.include_router(anomalies.router, prefix="/api/anomalies", tags=["Anomalies"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(suppliers.router, prefix="/api/suppliers", tags=["Suppliers"])
app.include_router(supplier_budgets.router, prefix="/api/supplier-budgets", tags=["Supplier Budgets"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(maintenance.router, prefix="/api/maintenance", tags=["Maintenance"])
app.include_router(todos.router, prefix="/api/todos", tags=["Todos"])
app.include_router(price_lists.router, prefix="/api/price-lists", tags=["Price Lists"])
app.include_router(fine_rules.router, prefix="/api/fine-rules", tags=["Fine Rules"])


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
