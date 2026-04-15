"""
Main FastAPI application
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from backend.config import get_settings
from backend.api.auth import get_current_user
from backend.database import engine, Base, AsyncSessionLocal
from backend.models import User, Site
from backend.models.supplier import Supplier
from backend.models.supplier_budget import SupplierBudget
from backend.models.violation import FineRule
from backend.models.product import Product
from backend.models.price_list import PriceList, PriceListItem
from backend.models.menu_compliance import ComplianceRule
from backend.models.product_category import ProductCategoryGroup, ProductCategoryMapping
from backend.models.daily_meal_count import DailyMealCount
from backend.api.auth import get_password_hash
from backend.api import auth, meetings, chat, dashboard, violations
from backend.api import menu_compliance, proformas, historical, anomalies, webhooks, suppliers
from backend.api import supplier_budgets, projects, maintenance, todos, price_lists, fine_rules
from backend.api import category_analysis, attachments, dish_catalog, agent_crew, vending

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log database connection info
    from backend.database import database_url, is_sqlite
    db_type = "SQLite" if is_sqlite else "PostgreSQL"
    db_prefix = database_url[:40] if len(database_url) > 40 else database_url
    logger.warning(f"[DB-DIAG] Connecting to {db_type}: {db_prefix}...")
    if is_sqlite:
        logger.warning("[DB-DIAG] WARNING: Using SQLite — data will NOT persist on Railway!")

    # ── Migration: complaints → violations (rename tables + enum values) ──
    async with engine.begin() as conn:
        if not is_sqlite:
            # PostgreSQL: check if old 'complaints' table exists
            has_old = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'complaints')"
            ))
            if has_old.scalar():
                logger.info("Migrating: renaming complaints → violations")
                # Drop new empty violations table if create_all made it before
                await conn.execute(text(
                    "DROP TABLE IF EXISTS violations CASCADE"
                ))
                # Rename table
                await conn.execute(text(
                    "ALTER TABLE complaints RENAME TO violations"
                ))
                # Rename column
                try:
                    await conn.execute(text(
                        "ALTER TABLE violations RENAME COLUMN complaint_text TO violation_text"
                    ))
                except Exception:
                    pass  # column may already be renamed

            # Check if old complaint_patterns table exists
            has_old_patterns = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'complaint_patterns')"
            ))
            if has_old_patterns.scalar():
                await conn.execute(text(
                    "DROP TABLE IF EXISTS violation_patterns CASCADE"
                ))
                await conn.execute(text(
                    "ALTER TABLE complaint_patterns RENAME TO violation_patterns"
                ))

            # Convert enum columns to VARCHAR to avoid enum type conflicts
            has_violations = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'violations')"
            ))
            if has_violations.scalar():
                # Each column that was a PG enum needs USING col::text
                for col in ['category', 'severity', 'source', 'status']:
                    try:
                        await conn.execute(text(
                            f"ALTER TABLE violations "
                            f"ALTER COLUMN {col} TYPE VARCHAR "
                            f"USING {col}::text"
                        ))
                        logger.info(f"Converted violations.{col} to VARCHAR")
                    except Exception as e:
                        logger.info(f"Column {col} already VARCHAR or missing: {e}")

                # Map old category values → new values
                category_migration = {
                    'food_quality': 'kitchen_cleanliness',
                    'FOOD_QUALITY': 'kitchen_cleanliness',
                    'temperature': 'kitchen_cleanliness',
                    'TEMPERATURE': 'kitchen_cleanliness',
                    'cleanliness': 'kitchen_cleanliness',
                    'CLEANLINESS': 'kitchen_cleanliness',
                    'variety': 'menu_variety',
                    'VARIETY': 'menu_variety',
                    'dietary': 'menu_variety',
                    'DIETARY': 'menu_variety',
                    'equipment': 'missing_dining_equipment',
                    'EQUIPMENT': 'missing_dining_equipment',
                    'SERVICE': 'service',
                    'other': 'service',
                    'OTHER': 'service',
                }
                for old_val, new_val in category_migration.items():
                    await conn.execute(text(
                        f"UPDATE violations SET category = '{new_val}' "
                        f"WHERE category = '{old_val}'"
                    ))

                # Catch-all: map any remaining unknown category values
                valid_categories = (
                    "'kitchen_cleanliness','dining_cleanliness','staff_attire',"
                    "'missing_dining_equipment','portion_weight','menu_variety',"
                    "'main_course_depleted','staff_shortage','service','positive_notes'"
                )
                await conn.execute(text(
                    f"UPDATE violations SET category = 'service' "
                    f"WHERE category NOT IN ({valid_categories})"
                ))
                logger.info("Migrated old category enum values to new values")

                # Catch-all for severity: map unknown values
                valid_severities = "'low','medium','high','critical'"
                await conn.execute(text(
                    f"UPDATE violations SET severity = 'medium' "
                    f"WHERE severity IS NOT NULL "
                    f"AND severity NOT IN ({valid_severities})"
                ))

                # Catch-all for source: map unknown values
                valid_sources = "'email','whatsapp','slack','manual','form'"
                await conn.execute(text(
                    f"UPDATE violations SET source = 'manual' "
                    f"WHERE source NOT IN ({valid_sources})"
                ))

                # Catch-all for status: map unknown values
                valid_statuses = "'new','acknowledged','investigating','resolved','dismissed'"
                await conn.execute(text(
                    f"UPDATE violations SET status = 'new' "
                    f"WHERE status IS NOT NULL "
                    f"AND status NOT IN ({valid_statuses})"
                ))
                logger.info("Applied catch-all migration for all enum columns")

            # Also convert fine_rules.category if it uses a native enum
            has_fine_rules = await conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'fine_rules')"
            ))
            if has_fine_rules.scalar():
                try:
                    await conn.execute(text(
                        "ALTER TABLE fine_rules "
                        "ALTER COLUMN category TYPE VARCHAR "
                        "USING category::text"
                    ))
                    logger.info("Converted fine_rules.category to VARCHAR")
                except Exception as e:
                    logger.info(f"fine_rules.category already VARCHAR: {e}")

                # Map old fine_rules category values too
                for old_val, new_val in category_migration.items():
                    await conn.execute(text(
                        f"UPDATE fine_rules SET category = '{new_val}' "
                        f"WHERE category = '{old_val}'"
                    ))

            # Drop ALL old enum types (complaint* and violation* to start fresh)
            for old_type in ['complaintcategory', 'complaintseverity',
                             'complaintsource', 'complaintstatus',
                             'violationcategory', 'violationseverity',
                             'violationsource', 'violationstatus']:
                try:
                    await conn.execute(text(f"DROP TYPE IF EXISTS {old_type} CASCADE"))
                    logger.info(f"Dropped enum type: {old_type}")
                except Exception:
                    pass
        else:
            # SQLite: simple table rename
            try:
                await conn.execute(text(
                    "ALTER TABLE complaints RENAME TO violations"
                ))
                logger.info("SQLite: renamed complaints → violations")
            except Exception:
                pass  # table may not exist or already renamed

    # Create all tables (creates new tables, ignores existing)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    # Run column migrations for existing tables (create_all doesn't ALTER tables)
    async with AsyncSessionLocal() as session:
        from backend.database import is_sqlite
        migrations = [
            ("supplier_budgets", "shift", "VARCHAR DEFAULT 'all'"),
            ("violations", "fine_rule_id", "INTEGER"),
            ("violations", "fine_amount", "FLOAT DEFAULT 0"),
            ("menu_checks", "dishes_above", "INTEGER DEFAULT 0"),
            ("menu_checks", "dishes_under", "INTEGER DEFAULT 0"),
            ("menu_checks", "dishes_even", "INTEGER DEFAULT 0"),
            ("dish_catalog", "approved", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("dish_catalog", "source_check_id", "INTEGER"),
            ("violations", "employee_phone", "VARCHAR"),
            ("violations", "restaurant_type", "VARCHAR"),
            ("compliance_rules", "site_id", "INTEGER"),
            # MealBreakdown: price + cost columns (Phase 1)
            ("meal_breakdowns", "hp_meat_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "scitex_meat_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "evening_hp_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "evening_contractors_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "hp_dairy_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "scitex_dairy_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "supplement_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "contractors_meat_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "contractors_dairy_price", "FLOAT DEFAULT 0"),
            ("meal_breakdowns", "total_cost", "FLOAT DEFAULT 0"),
            # Proforma: persist raw XLSX bytes so kitchenette/meals can be re-extracted
            ("proformas", "file_blob", "BLOB" if is_sqlite else "BYTEA"),
            # Proforma: shift column for vending day/evening split
            ("proformas", "shift", "VARCHAR NOT NULL DEFAULT 'all'"),
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

    # Drop old unique constraint on compliance_rules.name so per-site duplicates work
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(text(
                "ALTER TABLE compliance_rules DROP CONSTRAINT IF EXISTS compliance_rules_name_key"
            ))
            await session.commit()
        except Exception:
            await session.rollback()

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
            logger.info("Admin user already exists, skipping")

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

    # Seed מ.א אוטומטים (vending machines) supplier + 3 budget rows
    async with AsyncSessionLocal() as session:
        VENDING_NAME = "מ.א אוטומטים"
        result = await session.execute(
            select(Supplier).where(Supplier.name == VENDING_NAME)
        )
        vending = result.scalar_one_or_none()
        if not vending:
            vending = Supplier(
                name=VENDING_NAME,
                contact_name="M.A Vending",
                is_active=True,
                notes="Vending machine supplier (NZ + KG day + KG evening)",
            )
            session.add(vending)
            await session.flush()
            logger.info(f"Created {VENDING_NAME} supplier (id={vending.id})")

        # Only seed the KG Evening row at ₪0 (user edits amount via /budget page).
        # Existing NZ + KG budgets are left alone — user decides if KG should be
        # split (day/evening) or kept aggregated ('all') via the Budget page.
        for yr in [2025, 2026]:
            existing = await session.execute(
                select(SupplierBudget).where(
                    SupplierBudget.supplier_id == vending.id,
                    SupplierBudget.site_id == 2,
                    SupplierBudget.year == yr,
                    SupplierBudget.shift == "evening",
                )
            )
            if not existing.scalar_one_or_none():
                session.add(SupplierBudget(
                    supplier_id=vending.id,
                    site_id=2,
                    year=yr,
                    shift="evening",
                    yearly_amount=0,
                    jan=0, feb=0, mar=0, apr=0, may=0, jun=0,
                    jul=0, aug=0, sep=0, oct=0, nov=0, dec=0,
                    is_active=True,
                ))
        await session.commit()
        logger.info("מ.א אוטומטים supplier + 3 budget rows seeded")

    # Seed default fine rules if none exist
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(FineRule))
        if not existing.scalars().first():
            default_fines = [
                FineRule(name="Foreign object in food", category="kitchen_cleanliness", amount=500, description="Physical contamination found in served food"),
                FineRule(name="Spoiled / expired ingredients", category="kitchen_cleanliness", amount=400, description="Use of expired or spoiled ingredients"),
                FineRule(name="Incorrect temperature (hot)", category="kitchen_cleanliness", amount=300, description="Hot food served below required temperature"),
                FineRule(name="Incorrect temperature (cold)", category="kitchen_cleanliness", amount=300, description="Cold food served above required temperature"),
                FineRule(name="Late delivery / service", category="service", amount=200, description="Catering delivered after agreed time"),
                FineRule(name="Rude / unprofessional staff", category="service", amount=250, description="Staff behavior issue"),
                FineRule(name="Insufficient variety", category="menu_variety", amount=150, description="Menu variety below contracted minimum"),
                FineRule(name="Missing dietary option", category="menu_variety", amount=350, description="Required dietary option (vegan, kosher, etc.) not available"),
                FineRule(name="Kitchen / area uncleanliness", category="kitchen_cleanliness", amount=400, description="Hygiene standard violation in kitchen or dining area"),
                FineRule(name="Equipment malfunction not reported", category="missing_dining_equipment", amount=200, description="Failed to report or fix broken equipment"),
                FineRule(name="Pest sighting", category="kitchen_cleanliness", amount=500, description="Pest found in kitchen or dining area"),
                FineRule(name="Menu not as contracted", category="menu_variety", amount=300, description="Served menu deviates from contracted menu plan"),
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

    # --- Compliance rules: migrate existing rules → KG (site_id=2), seed NZ rules ---
    async with AsyncSessionLocal() as session:
        # Tag all existing null-site rules as KG (they were KG-specific from PDF import)
        kg_tagged = await session.execute(
            select(ComplianceRule).where(ComplianceRule.site_id == 2).limit(1)
        )
        if not kg_tagged.scalar():
            await session.execute(
                text("UPDATE compliance_rules SET site_id = 2 WHERE site_id IS NULL")
            )
            await session.commit()
            logger.info("Tagged existing compliance rules as KG (site_id=2)")

        # Seed NZ-specific rules from the חוסרים תפריט נס ציונה template
        nz_tagged = await session.execute(
            select(ComplianceRule).where(ComplianceRule.site_id == 1).limit(1)
        )
        if not nz_tagged.scalar():
            def _nz(name, category, count, freq_text, item_keyword=None, priority=1, description=None):
                return ComplianceRule(
                    name=name,
                    site_id=1,
                    rule_type="item_frequency_monthly",
                    category=category,
                    description=description or f"{freq_text} — {name}",
                    parameters={
                        "count": count,
                        "frequency_text": freq_text,
                        "item_keyword": item_keyword or name,
                        "expected_count": count,
                    },
                    priority=priority,
                    is_active=True,
                )

            nz_rules = [
                # מיוחדים
                _nz("שוברי שגרה", "מיוחדים", 2, "פעמיים בחודש",
                    description="יום תפריט מיוחד כגון יום עיראקי, יום מרוקאי וכד'"),
                _nz("ימים מיוחדים", "מיוחדים", 1, "פעם בחודש",
                    description="ארוע מיוחד כגון יום העצמאות, פורים, חנוכה"),
                # סלטים
                _nz("סלט פטריות אסייתי", "סלטים", 2, "פעמיים בחודש", "פטריות אסייתי"),
                _nz("סלט טבולה בורגול", "סלטים", 2, "פעמיים בחודש", "טבולה"),
                _nz("סלט אבוקדו", "סלטים", 2, "פעמיים בחודש (נובמבר–מרץ)", "אבוקדו"),
                _nz("סלט ארטישוק", "סלטים", 1, "פעם בחודש", "ארטישוק"),
                _nz("פיצוחים וירוקים", "סלטים", 4, "פעם בשבוע", "פיצוחים"),
                _nz("סלט קינואה", "סלטים", 2, "פעמיים בחודש", "קינואה"),
                _nz("סלט עגבניות איטלקי", "סלטים", 2, "פעמיים בחודש", "עגבניות איטלקי"),
                _nz("סלט עגבניות חריף", "סלטים", 2, "פעמיים בחודש", "עגבניות חריף"),
                _nz("סלט קיסר", "סלטים", 2, "פעמיים בחודש", "קיסר"),
                _nz("סלט ויאטנמי אטריות זכוכית", "סלטים", 4, "פעם בשבוע", "ויאטנמי"),
                _nz("סלט סלק ותפוח עץ", "סלטים", 4, "פעם בשבוע", "סלק"),
                _nz("סלט קינואה עדשים", "סלטים", 4, "פעם בשבוע", "קינואה עדשים"),
                _nz("סלט ווקאמה", "סלטים", 4, "פעם בשבוע", "ווקאמה"),
                # עוף
                _nz("עופות שלמים בגריל מסתובב", "עוף", 12, "3 פעמים בשבוע", "עוף שלם"),
                _nz("טבית עופות צלויים עם אורז ובהרט", "עוף", 2, "פעמיים בחודש", "טבית"),
                _nz("כרע עוף ממולא באורז", "עוף", 2, "פעמיים בחודש", "כרע ממולא"),
                _nz("שניצל בהכנה מקומית 170 גרם", "עוף", 12, "3 פעמים בשבוע", "שניצל"),
                _nz("כבד עוף עם בצל ופטריות על פירה", "עוף", 4, "פעם בשבוע", "כבד עוף"),
                _nz("מסאחן פרגית", "עוף", 4, "פעם בשבוע", "מסאחן",
                    description="נספר גם כמנת פרגית לצורך דרישת פרגית פעמיים בשבוע"),
                _nz("קציצות עוף חמוסטה", "עוף", 4, "פעם בשבוע", "חמוסטה"),
                _nz("חזה עוף בגריל", "עוף", 12, "3 פעמים בשבוע", "חזה עוף"),
                # בקר
                _nz("המבורגר ביתי", "בקר", 4, "פעם בשבוע", "המבורגר"),
                _nz("מאפה בשר וחציל שרוף", "בקר", 4, "פעם בשבוע", "מאפה בשר"),
                _nz("בקלאוות בשר", "בקר", 1, "פעם בחודש", "בקלאווה"),
                _nz("צלי כתף מספר 5-6", "בקר", 2, "פעמיים בחודש", "צלי כתף"),
                _nz("אסאדו צלוי באיטיות", "בקר", 3, "שלוש פעמים בחודש", "אסאדו"),
                _nz("כנאפה אסאדו", "בקר", 1, "פעם בחודש", "כנאפה"),
                _nz("בשר ראש", "בקר", 2, "פעמיים בחודש", "בשר ראש"),
                # מנות גריל
                _nz("שווארמה הודו ירך נקבה", "מנות גריל", 4, "פעם בשבוע", "שווארמה הודו",
                    description="שווארמה פרגית מאושרת כתחליף — יש לציין בהערות"),
                _nz("קציצות פרגית", "מנות גריל", 4, "פעם בשבוע", "קציצות פרגית",
                    description="חובת הגשה פרגית פעמיים בשבוע. מנות מאושרות: קציצות פרגית, מסאחן פרגית, מוקפץ פרגית, שיפודי פרגית, סטייק פרגית. פרגית ממולאת וכרע עוף ממולא — לא נספרים"),
                _nz("סטייק פרגית", "מנות גריל", 4, "פעם בשבוע", "סטייק פרגית",
                    description="נספר יחד עם קציצות פרגית לצורך דרישת פרגית פעמיים בשבוע"),
                _nz("סטייק סינטה", "מנות גריל", 2, "פעמיים בחודש", "סינטה",
                    description="אנטריקוט מאושר כתחליף — יש לציין בהערות"),
                # דגים
                _nz("פילה סלמון נורווגי", "דגים", 4, "פעם בשבוע", "סלמון"),
                _nz("פילה אמנון", "דגים", 4, "פעם בשבוע", "אמנון"),
                _nz("חריימה של נסיכה", "דגים", 2, "פעמיים בחודש", "חריימה"),
                _nz("פילה לברק", "דגים", 2, "פעמיים בחודש", "לברק"),
                _nz("פיש וצ'יפס", "דגים", 1, "פעם בחודש", "פיש"),
                _nz("קציצות דגים ביתיות", "דגים", 2, "פעמיים בחודש", "קציצות דגים"),
                # קינוחים
                _nz("סלט פירות", "קינוחים", 16, "כל יום", "פירות"),
                _nz("עוגה", "קינוחים", 16, "כל יום", "עוגה"),
                _nz("עוגת קארנץ שמרים", "קינוחים", 4, "פעם בשבוע לפחות", "קארנץ"),
                _nz("קינוח כוס קרמבו", "קינוחים", 16, "כל יום", "קרמבו"),
                _nz("קינוח ללא סוכר", "קינוחים", 16, "כל יום", "ללא סוכר"),
            ]
            for rule in nz_rules:
                session.add(rule)
            await session.commit()
            logger.info(f"Seeded {len(nz_rules)} NZ compliance rules (site_id=1)")

        # Migrate NZ rule descriptions — update existing rules with notes from compliance report
        nz_desc_updates = [
            ("שוברי שגרה", "יום תפריט מיוחד כגון יום עיראקי, יום מרוקאי וכד'"),
            ("ימים מיוחדים", "ארוע מיוחד כגון יום העצמאות, פורים, חנוכה"),
            ("מסאחן פרגית", "נספר גם כמנת פרגית לצורך דרישת פרגית פעמיים בשבוע"),
            ("שווארמה הודו ירך נקבה", "שווארמה פרגית מאושרת כתחליף — יש לציין בהערות"),
            ("קציצות פרגית", "חובת הגשה פרגית פעמיים בשבוע. מנות מאושרות: קציצות פרגית, מסאחן פרגית, מוקפץ פרגית, שיפודי פרגית, סטייק פרגית. פרגית ממולאת וכרע עוף ממולא — לא נספרים"),
            ("סטייק פרגית", "נספר יחד עם קציצות פרגית לצורך דרישת פרגית פעמיים בשבוע"),
            ("סטייק סינטה", "אנטריקוט מאושר כתחליף — יש לציין בהערות"),
        ]
        for rule_name, desc in nz_desc_updates:
            await session.execute(
                text("UPDATE compliance_rules SET description = :desc WHERE name = :name AND site_id = 1"),
                {"desc": desc, "name": rule_name},
            )
        await session.commit()
        logger.info("Updated NZ compliance rule descriptions with substitution notes")

    # Seed product category groups and mappings
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(ProductCategoryGroup))
        if not existing.scalars().first():
            groups = [
                ProductCategoryGroup(name="total_meals", display_name_he="ארוחות", display_name_en="Total Meals", sort_order=1),
                ProductCategoryGroup(name="working_days", display_name_he="ימי עבודה", display_name_en="Working Days", sort_order=2),
                ProductCategoryGroup(name="extras_lunch", display_name_he="תוספות לצהריים", display_name_en="Extras for Lunch", sort_order=3),
                ProductCategoryGroup(name="kitchenette_fruit", display_name_he="מטבחון - פירות", display_name_en="Kitchenette - Fruit", sort_order=4),
                ProductCategoryGroup(name="kitchenette_dry", display_name_he="מטבחון - יבשים", display_name_en="Kitchenette - Dry Goods", sort_order=5),
                ProductCategoryGroup(name="kitchenette_dairy", display_name_he="מטבחון - חלבי", display_name_en="Kitchenette - Dairy", sort_order=6),
                ProductCategoryGroup(name="coffee_tea", display_name_he="קפה/תה/לימון", display_name_en="Coffee/Tea/Lemon", sort_order=7),
                ProductCategoryGroup(name="cut_veg", display_name_he="פלטות ירקות", display_name_en="Cut Veg Platters", sort_order=8),
                ProductCategoryGroup(name="coffee_beans", display_name_he="פולי קפה", display_name_en="Coffee Beans", sort_order=9),
            ]
            for g in groups:
                session.add(g)
            await session.flush()

            # Build group lookup by name
            grp = {g.name: g.id for g in groups}

            # Product name patterns → category group
            # From user's Excel: קטגוריות חלוקת פריטים במטבחונים.xlsx
            mappings_data = [
                # Group 1: Total Meals
                (grp["total_meals"], "%ארוחת צהריים%"),
                (grp["total_meals"], "%ארוחת ערב%"),
                (grp["total_meals"], "%ארחת ערב%"),
                (grp["total_meals"], "%ארוחת לילה%"),
                (grp["total_meals"], "%ארוחות לילה%"),
                (grp["total_meals"], "%ארוחות שבת%"),
                (grp["total_meals"], "%ארוזיות שומרים%"),
                (grp["total_meals"], "%ארוחות שומרים%"),
                (grp["total_meals"], "%תוספת למנה עיקרית%"),
                (grp["total_meals"], "%תוספת מנה עיקרית%"),
                (grp["total_meals"], "%כריך%"),
                (grp["total_meals"], "%לחמניה%"),
                (grp["total_meals"], "%השלמת ארוחות%"),
                (grp["total_meals"], "%ארוחות צהריים%"),
                # Group 3: Extras for lunch
                (grp["extras_lunch"], "%תפוחים למכונת מיצים%"),
                (grp["extras_lunch"], "%גזר קלוף למכונת מיצים%"),
                (grp["extras_lunch"], "%סלק קלוף למכונת מיצים%"),
                (grp["extras_lunch"], "%ארטיק%"),
                (grp["extras_lunch"], "%תרכיז%"),
                (grp["extras_lunch"], "%הפרש נוזל למדיח%"),
                (grp["extras_lunch"], "%הפרש ממחיר נוזל%"),
                # Group 4: Kitchenette - Fruit
                (grp["kitchenette_fruit"], "%פירות%"),
                # Group 5: Kitchenette - Dry Goods
                (grp["kitchenette_dry"], "%סוכר%"),
                (grp["kitchenette_dry"], "%עוגיות%"),
                (grp["kitchenette_dry"], "%עוגיו%"),
                (grp["kitchenette_dry"], "%וופלים%"),
                (grp["kitchenette_dry"], "%בייגלה%"),
                (grp["kitchenette_dry"], "%גרנולה%"),
                (grp["kitchenette_dry"], "%דבש%"),
                (grp["kitchenette_dry"], "%סילאן%"),
                (grp["kitchenette_dry"], "%חוויאג%"),
                (grp["kitchenette_dry"], "%ממתיק%"),
                (grp["kitchenette_dry"], "%קסמי שיניים%"),
                (grp["kitchenette_dry"], "%קיסמי שינים%"),
                (grp["kitchenette_dry"], "%מלח לימון%"),
                (grp["kitchenette_dry"], "%נוטלה%"),
                # Group 6: Kitchenette - Dairy
                (grp["kitchenette_dairy"], "%דנונה%"),
                (grp["kitchenette_dairy"], "%יופלה%"),
                (grp["kitchenette_dairy"], "%פרילי%"),
                (grp["kitchenette_dairy"], "%מילקי%"),
                (grp["kitchenette_dairy"], "%מעדן%"),
                (grp["kitchenette_dairy"], "%שמנת%"),
                (grp["kitchenette_dairy"], "%חלב%"),
                (grp["kitchenette_dairy"], "%אשל%"),
                (grp["kitchenette_dairy"], "%גיל,%"),
                (grp["kitchenette_dairy"], "%גיל %"),
                (grp["kitchenette_dairy"], "%שוקו%"),
                (grp["kitchenette_dairy"], "%גבינ%"),
                (grp["kitchenette_dairy"], "%משקה שקדים%"),
                # Group 7: Coffee/Tea/Lemon
                (grp["coffee_tea"], "%קפה שחור%"),
                (grp["coffee_tea"], "%קפה נמס%"),
                (grp["coffee_tea"], "%מגורען%"),
                (grp["coffee_tea"], "%נטול קופאין%"),
                (grp["coffee_tea"], "%שקיקי תה%"),
                (grp["coffee_tea"], "%לימון שטוף%"),
                (grp["coffee_tea"], "%נענע%"),
                # Group 8: Cut Veg platters
                (grp["cut_veg"], "%פלטות%ירקות%"),
                (grp["cut_veg"], "%פלטת%ירקות%"),
                # Group 9: Coffee Beans
                (grp["coffee_beans"], "%קפה קדם%"),
                (grp["coffee_beans"], "%שכירות%Eversys%"),
                (grp["coffee_beans"], "%שכירות חודשית%"),
            ]

            for group_id, pattern in mappings_data:
                session.add(ProductCategoryMapping(
                    group_id=group_id,
                    product_name_pattern=pattern,
                ))

            await session.commit()
            logger.info(f"Seeded {len(groups)} product category groups with {len(mappings_data)} mappings")

    # Start background meal email poller (if IMAP configured)
    from backend.services.meal_email_poller import start_meal_email_scheduler
    meal_poller_task = asyncio.create_task(start_meal_email_scheduler())

    # Initialize Agent Crew (always-on)
    from backend.agents.crew.registry import agent_registry
    from backend.agents.crew.manager import crew_manager
    agent_registry._ensure_initialized()
    crew_info = crew_manager.get_crew_info()
    logger.info(
        f"Agent Crew initialized: {crew_info['crew_name']} — "
        f"{crew_info['total_agents']} agents ({len(agent_registry.get_specialist_ids())} specialists + 1 manager)"
    )

    yield

    meal_poller_task.cancel()
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
app.include_router(violations.router, prefix="/api/violations", tags=["Violations"])
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
app.include_router(category_analysis.router, prefix="/api/category-analysis", tags=["Category Analysis"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["Attachments"])
app.include_router(dish_catalog.router, tags=["Dish Catalog"])
app.include_router(agent_crew.router, tags=["Agent Crew"])
app.include_router(vending.router, tags=["Vending"])


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


@app.get("/db-diagnostic")
async def db_diagnostic(
    current_user: User = Depends(get_current_user),
):
    """Diagnostic endpoint to check database connection status. Admin only."""
    from backend.database import is_sqlite
    from sqlalchemy import text as sa_text

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    info = {
        "database_type": "SQLite" if is_sqlite else "PostgreSQL",
        "is_sqlite": is_sqlite,
    }

    try:
        async with AsyncSessionLocal() as session:
            for table in ["users", "sites", "proformas", "proforma_items", "projects", "meetings", "violations", "supplier_budgets"]:
                try:
                    result = await session.execute(sa_text(f"SELECT COUNT(*) FROM {table}"))
                    info[f"count_{table}"] = result.scalar()
                except Exception:
                    info[f"count_{table}"] = "error"
    except Exception:
        info["connection_error"] = "Database connection failed"

    return info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
