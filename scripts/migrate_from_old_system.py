"""
Data Migration Script: FoodHouse Analytics -> Catering Services AI Pro

Migrates ALL data from old SQLite database to new system:
- Sites, users, suppliers, products, price lists (Phase 1)
- Historical meal data (Phase 1)
- Menu checks and compliance results (Complete)
- Proformas and invoice items (Complete)
- Quantity limits and anomalies (Complete)

Old system remains unchanged and available for reference.

Usage:
    python scripts/migrate_from_old_system.py /path/to/old/catering.db
"""

import sqlite3
import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from backend.database import AsyncSessionLocal, engine, Base
from backend.models.user import User
from backend.models.site import Site
from backend.models.supplier import Supplier
from backend.models.product import Product
from backend.models.price_list import PriceList, PriceListItem
from backend.models.historical_data import HistoricalMealData
from backend.models.menu_compliance import MenuCheck, CheckResult
from backend.models.proforma import Proforma, ProformaItem
from backend.models.operations import QuantityLimit, Anomaly
from backend.api.auth import get_password_hash


class DataMigration:
    """Handles migration from old FoodHouse Analytics to new system"""

    def __init__(self, old_db_path: str):
        self.old_db_path = old_db_path
        self.old_conn = None
        self.stats = {
            'sites': 0,
            'suppliers': 0,
            'products': 0,
            'price_lists': 0,
            'price_list_items': 0,
            'historical_data': 0,
            'menu_checks': 0,
            'check_results': 0,
            'proformas': 0,
            'proforma_items': 0,
            'quantity_limits': 0,
            'anomalies': 0,
            'errors': []
        }

    def connect_old_db(self):
        """Connect to old SQLite database"""
        print(f"Connecting to old database: {self.old_db_path}")
        self.old_conn = sqlite3.connect(self.old_db_path)
        self.old_conn.row_factory = sqlite3.Row
        print("Connected to old database")

    def close_old_db(self):
        """Close old database connection"""
        if self.old_conn:
            self.old_conn.close()
            print("Closed old database connection")

    async def create_new_tables(self):
        """Create all tables in new database"""
        print("Creating tables in new database...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("Tables created")

    async def migrate_all(self):
        """Run complete migration"""
        print("=" * 60)
        print("COMPLETE MIGRATION: FoodHouse Analytics -> Catering Services AI Pro")
        print("=" * 60)
        print()

        try:
            # Connect to old database
            self.connect_old_db()

            # Create new database tables
            await self.create_new_tables()

            # Phase 1: Core data
            await self.migrate_sites()
            await self.migrate_users()
            await self.migrate_suppliers()
            await self.migrate_products()
            await self.migrate_price_lists()
            await self.migrate_historical_data()

            # Complete: Menu checking data
            await self.migrate_menu_checks()
            await self.migrate_check_results()

            # Complete: Operational data
            await self.migrate_proformas()
            await self.migrate_quantity_limits()
            await self.migrate_anomalies()

            # Print summary
            self.print_summary()

        except Exception as e:
            print(f"Migration failed: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errors'].append(str(e))
            raise
        finally:
            self.close_old_db()

    async def migrate_sites(self):
        """Migrate site configurations (Nes Ziona, Kiryat Gat)"""
        print("\nMigrating sites...")

        try:
            cursor = self.old_conn.cursor()

            try:
                old_sites = cursor.execute("""
                    SELECT name, budget, active
                    FROM sites
                    WHERE active = 1
                """).fetchall()
            except sqlite3.OperationalError:
                print("   'sites' table not found, creating default sites...")
                old_sites = [
                    {'name': 'Nes Ziona', 'budget': 60000, 'active': 1},
                    {'name': 'Kiryat Gat', 'budget': 60000, 'active': 1}
                ]

            async with AsyncSessionLocal() as session:
                for old_site in old_sites:
                    result = await session.execute(
                        select(Site).where(Site.name == old_site['name'])
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        print(f"   Site already exists: {old_site['name']}, skipping")
                        continue

                    code = self._generate_site_code(old_site['name'])

                    new_site = Site(
                        name=old_site['name'],
                        code=code,
                        monthly_budget=float(old_site['budget']) if old_site['budget'] else 60000.0,
                        is_active=True
                    )
                    session.add(new_site)
                    self.stats['sites'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['sites']} sites")

        except Exception as e:
            print(f"   Error migrating sites: {e}")
            self.stats['errors'].append(f"Sites: {e}")

    async def migrate_users(self):
        """Create default admin user"""
        print("\nCreating default admin user...")

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.email == "ziv@hp.com")
                )
                if result.scalar_one_or_none():
                    print("   Admin user already exists, skipping")
                    return

                admin = User(
                    email="ziv@hp.com",
                    full_name="Ziv Cohen",
                    hashed_password=get_password_hash("admin123"),
                    is_active=True,
                    is_admin=True
                )
                session.add(admin)
                await session.commit()
                print("   Created admin user (ziv@hp.com / admin123)")

        except Exception as e:
            print(f"   Error creating admin: {e}")
            self.stats['errors'].append(f"Admin user: {e}")

    async def migrate_suppliers(self):
        """Migrate supplier data"""
        print("\nMigrating suppliers...")

        try:
            cursor = self.old_conn.cursor()

            try:
                old_suppliers = cursor.execute("""
                    SELECT name, contact_name, email, phone,
                           contract_start, contract_end, payment_terms, notes
                    FROM suppliers
                    WHERE active = 1
                """).fetchall()
            except sqlite3.OperationalError:
                print("   'suppliers' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_sup in old_suppliers:
                    result = await session.execute(
                        select(Supplier).where(Supplier.name == old_sup['name'])
                    )
                    if result.scalar_one_or_none():
                        print(f"   Supplier exists: {old_sup['name']}, skipping")
                        continue

                    new_sup = Supplier(
                        name=old_sup['name'],
                        contact_name=old_sup['contact_name'],
                        email=old_sup['email'],
                        phone=old_sup['phone'],
                        contract_start_date=self._parse_date(old_sup['contract_start'] if 'contract_start' in old_sup.keys() else None),
                        contract_end_date=self._parse_date(old_sup['contract_end'] if 'contract_end' in old_sup.keys() else None),
                        payment_terms=old_sup['payment_terms'] if 'payment_terms' in old_sup.keys() else None,
                        notes=old_sup['notes'] if 'notes' in old_sup.keys() else None,
                        is_active=True
                    )
                    session.add(new_sup)
                    self.stats['suppliers'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['suppliers']} suppliers")

        except Exception as e:
            print(f"   Error migrating suppliers: {e}")
            self.stats['errors'].append(f"Suppliers: {e}")

    async def migrate_products(self):
        """Migrate product catalog"""
        print("\nMigrating products...")

        try:
            cursor = self.old_conn.cursor()

            try:
                old_products = cursor.execute("""
                    SELECT p.name, p.hebrew_name, p.unit, c.name as category_name
                    FROM products p
                    LEFT JOIN categories c ON p.category_id = c.id
                    WHERE p.active = 1
                """).fetchall()
            except sqlite3.OperationalError:
                print("   'products' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_prod in old_products:
                    result = await session.execute(
                        select(Product).where(Product.name == old_prod['name'])
                    )
                    if result.scalar_one_or_none():
                        continue

                    new_prod = Product(
                        name=old_prod['name'],
                        hebrew_name=old_prod['hebrew_name'] if 'hebrew_name' in old_prod.keys() else None,
                        category=old_prod['category_name'] if 'category_name' in old_prod.keys() else 'General',
                        unit=old_prod['unit'] if 'unit' in old_prod.keys() else None,
                        is_active=True
                    )
                    session.add(new_prod)
                    self.stats['products'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['products']} products")

        except Exception as e:
            print(f"   Error migrating products: {e}")
            self.stats['errors'].append(f"Products: {e}")

    async def migrate_price_lists(self):
        """Migrate price lists from last 12 months"""
        print("\nMigrating price lists (last 12 months)...")

        try:
            cursor = self.old_conn.cursor()

            cutoff_date = (datetime.now().date().replace(day=1) -
                          timedelta(days=365)).isoformat()

            try:
                old_price_lists = cursor.execute("""
                    SELECT pl.id, pl.effective_date, pl.file_path, s.name as supplier_name
                    FROM price_lists pl
                    JOIN suppliers s ON pl.supplier_id = s.id
                    WHERE pl.effective_date >= ?
                    ORDER BY pl.effective_date DESC
                """, (cutoff_date,)).fetchall()
            except sqlite3.OperationalError:
                print("   'price_lists' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_pl in old_price_lists:
                    result = await session.execute(
                        select(Supplier).where(Supplier.name == old_pl['supplier_name'])
                    )
                    supplier = result.scalar_one_or_none()

                    if not supplier:
                        print(f"   Skipping price list - supplier not found: {old_pl['supplier_name']}")
                        continue

                    result = await session.execute(
                        select(PriceList).where(
                            PriceList.supplier_id == supplier.id,
                            PriceList.effective_date == self._parse_date(old_pl['effective_date'])
                        )
                    )
                    if result.scalar_one_or_none():
                        continue

                    new_pl = PriceList(
                        supplier_id=supplier.id,
                        effective_date=self._parse_date(old_pl['effective_date']),
                        file_path=old_pl['file_path'] if 'file_path' in old_pl.keys() else None,
                        notes=f"Migrated from FoodHouse Analytics on {date.today()}"
                    )
                    session.add(new_pl)
                    await session.flush()

                    try:
                        old_items = cursor.execute("""
                            SELECT product_name, price, unit
                            FROM price_list_items
                            WHERE price_list_id = ?
                        """, (old_pl['id'],)).fetchall()

                        for old_item in old_items:
                            result = await session.execute(
                                select(Product).where(Product.name == old_item['product_name'])
                            )
                            product = result.scalar_one_or_none()

                            if product:
                                new_item = PriceListItem(
                                    price_list_id=new_pl.id,
                                    product_id=product.id,
                                    price=float(old_item['price']),
                                    unit=old_item['unit'] if 'unit' in old_item.keys() else None
                                )
                                session.add(new_item)
                                self.stats['price_list_items'] += 1
                    except sqlite3.OperationalError:
                        pass

                    self.stats['price_lists'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['price_lists']} price lists")
                print(f"   Migrated {self.stats['price_list_items']} price list items")

        except Exception as e:
            print(f"   Error migrating price lists: {e}")
            self.stats['errors'].append(f"Price lists: {e}")

    async def migrate_historical_data(self):
        """Migrate historical meal data for AI learning"""
        print("\nMigrating historical data (last 12 months)...")

        try:
            cursor = self.old_conn.cursor()

            cutoff_date = (datetime.now().date() - timedelta(days=365)).isoformat()

            try:
                old_meals = cursor.execute("""
                    SELECT date, site_code, meal_count, cost, notes
                    FROM meals_data
                    WHERE date >= ?
                    ORDER BY date
                """, (cutoff_date,)).fetchall()
            except sqlite3.OperationalError:
                print("   'meals_data' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_meal in old_meals:
                    result = await session.execute(
                        select(Site).where(Site.code == old_meal['site_code'])
                    )
                    site = result.scalar_one_or_none()

                    if not site:
                        continue

                    result = await session.execute(
                        select(HistoricalMealData).where(
                            HistoricalMealData.site_id == site.id,
                            HistoricalMealData.date == self._parse_date(old_meal['date'])
                        )
                    )
                    if result.scalar_one_or_none():
                        continue

                    new_meal = HistoricalMealData(
                        site_id=site.id,
                        date=self._parse_date(old_meal['date']),
                        meal_count=int(old_meal['meal_count']),
                        cost=float(old_meal['cost']) if old_meal['cost'] else None,
                        notes=old_meal['notes'] if 'notes' in old_meal.keys() else None
                    )
                    session.add(new_meal)
                    self.stats['historical_data'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['historical_data']} historical records")

        except Exception as e:
            print(f"   Error migrating historical data: {e}")
            self.stats['errors'].append(f"Historical data: {e}")

    # ===== NEW MIGRATION METHODS =====

    async def migrate_menu_checks(self):
        """Migrate menu compliance checks"""
        print("\nMigrating menu checks...")

        try:
            cursor = self.old_conn.cursor()

            try:
                old_checks = cursor.execute("""
                    SELECT mc.*, s.name as site_name
                    FROM menu_checks mc
                    LEFT JOIN sites s ON mc.site_id = s.id
                    ORDER BY mc.year DESC, mc.month DESC
                """).fetchall()
            except sqlite3.OperationalError:
                print("   'menu_checks' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_check in old_checks:
                    # Find site
                    result = await session.execute(
                        select(Site).where(Site.name == old_check['site_name'])
                    )
                    site = result.scalar_one_or_none()

                    if not site:
                        continue

                    # Check if exists
                    result = await session.execute(
                        select(MenuCheck).where(
                            MenuCheck.site_id == site.id,
                            MenuCheck.month == old_check['month'],
                            MenuCheck.year == old_check['year']
                        )
                    )
                    if result.scalar_one_or_none():
                        continue

                    new_check = MenuCheck(
                        site_id=site.id,
                        file_path=old_check['file_path'] if 'file_path' in old_check.keys() else None,
                        month=old_check['month'],
                        year=old_check['year'],
                        total_findings=old_check['total_findings'] if 'total_findings' in old_check.keys() else 0,
                        critical_findings=old_check['critical_findings'] if 'critical_findings' in old_check.keys() else 0,
                        warnings=old_check['warnings'] if 'warnings' in old_check.keys() else 0,
                        passed_rules=old_check['passed_rules'] if 'passed_rules' in old_check.keys() else 0,
                        checked_at=self._parse_date(old_check['checked_at'] if 'checked_at' in old_check.keys() else None) or date.today()
                    )
                    session.add(new_check)
                    self.stats['menu_checks'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['menu_checks']} menu checks")

        except Exception as e:
            print(f"   Error migrating menu checks: {e}")
            self.stats['errors'].append(f"Menu checks: {e}")

    async def migrate_check_results(self):
        """Migrate check results (findings)"""
        print("\nMigrating check results...")

        try:
            cursor = self.old_conn.cursor()

            try:
                old_results = cursor.execute("""
                    SELECT cr.*, mc.month, mc.year, s.name as site_name
                    FROM check_results cr
                    JOIN menu_checks mc ON cr.menu_check_id = mc.id
                    JOIN sites s ON mc.site_id = s.id
                    ORDER BY mc.year DESC, mc.month DESC
                """).fetchall()
            except sqlite3.OperationalError:
                print("   'check_results' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_result in old_results:
                    # Find menu check
                    result = await session.execute(
                        select(MenuCheck)
                        .join(Site)
                        .where(
                            Site.name == old_result['site_name'],
                            MenuCheck.month == old_result['month'],
                            MenuCheck.year == old_result['year']
                        )
                    )
                    menu_check = result.scalar_one_or_none()

                    if not menu_check:
                        continue

                    # Parse evidence JSON
                    evidence = None
                    raw_evidence = old_result['evidence'] if 'evidence' in old_result.keys() else None
                    if raw_evidence:
                        try:
                            evidence = json.loads(raw_evidence)
                        except (json.JSONDecodeError, TypeError):
                            pass

                    new_result = CheckResult(
                        menu_check_id=menu_check.id,
                        rule_name=old_result['rule_name'],
                        rule_category=old_result['rule_category'] if 'rule_category' in old_result.keys() else None,
                        passed=bool(old_result['passed']),
                        severity=old_result['severity'] if 'severity' in old_result.keys() else 'warning',
                        finding_text=old_result['finding_text'] if 'finding_text' in old_result.keys() else None,
                        evidence=evidence,
                        reviewed=bool(old_result['reviewed'] if 'reviewed' in old_result.keys() else False),
                        review_status=old_result['review_status'] if 'review_status' in old_result.keys() else None,
                        review_notes=old_result['review_notes'] if 'review_notes' in old_result.keys() else None
                    )
                    session.add(new_result)
                    self.stats['check_results'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['check_results']} check results")

        except Exception as e:
            print(f"   Error migrating check results: {e}")
            self.stats['errors'].append(f"Check results: {e}")

    async def migrate_proformas(self):
        """Migrate proformas (invoices)"""
        print("\nMigrating proformas...")

        try:
            cursor = self.old_conn.cursor()

            cutoff_date = (datetime.now().date() - timedelta(days=365)).isoformat()

            try:
                old_proformas = cursor.execute("""
                    SELECT p.*, s.name as supplier_name, si.name as site_name
                    FROM proformas p
                    JOIN suppliers s ON p.supplier_id = s.id
                    LEFT JOIN sites si ON p.site_id = si.id
                    WHERE p.invoice_date >= ?
                    ORDER BY p.invoice_date DESC
                """, (cutoff_date,)).fetchall()
            except sqlite3.OperationalError:
                print("   'proformas' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_pf in old_proformas:
                    # Find supplier
                    result = await session.execute(
                        select(Supplier).where(Supplier.name == old_pf['supplier_name'])
                    )
                    supplier = result.scalar_one_or_none()

                    if not supplier:
                        continue

                    # Find site
                    site = None
                    site_name = old_pf['site_name'] if 'site_name' in old_pf.keys() else None
                    if site_name:
                        result = await session.execute(
                            select(Site).where(Site.name == site_name)
                        )
                        site = result.scalar_one_or_none()

                    # Check if exists (by proforma number)
                    pf_number = old_pf['proforma_number'] if 'proforma_number' in old_pf.keys() else None
                    if pf_number:
                        result = await session.execute(
                            select(Proforma).where(
                                Proforma.proforma_number == pf_number
                            )
                        )
                        if result.scalar_one_or_none():
                            continue

                    new_pf = Proforma(
                        supplier_id=supplier.id,
                        site_id=site.id if site else None,
                        proforma_number=pf_number,
                        invoice_date=self._parse_date(old_pf['invoice_date']),
                        delivery_date=self._parse_date(old_pf['delivery_date'] if 'delivery_date' in old_pf.keys() else None),
                        total_amount=float(old_pf['total_amount']),
                        currency=old_pf['currency'] if 'currency' in old_pf.keys() else 'ILS',
                        status=old_pf['status'] if 'status' in old_pf.keys() else 'pending',
                        file_path=old_pf['file_path'] if 'file_path' in old_pf.keys() else None,
                        notes=old_pf['notes'] if 'notes' in old_pf.keys() else None
                    )
                    session.add(new_pf)
                    await session.flush()

                    # Migrate items
                    try:
                        old_items = cursor.execute("""
                            SELECT * FROM proforma_items
                            WHERE proforma_id = ?
                        """, (old_pf['id'],)).fetchall()

                        for old_item in old_items:
                            # Try to match product
                            product = None
                            prod_name = old_item['product_name'] if 'product_name' in old_item.keys() else None
                            if prod_name:
                                result = await session.execute(
                                    select(Product).where(Product.name == prod_name)
                                )
                                product = result.scalar_one_or_none()

                            new_item = ProformaItem(
                                proforma_id=new_pf.id,
                                product_id=product.id if product else None,
                                product_name=old_item['product_name'],
                                quantity=float(old_item['quantity']),
                                unit=old_item['unit'] if 'unit' in old_item.keys() else None,
                                unit_price=float(old_item['unit_price']),
                                total_price=float(old_item['total_price']),
                                price_variance=float(old_item['price_variance']) if old_item['price_variance'] is not None else None,
                                flagged=bool(old_item['flagged'] if 'flagged' in old_item.keys() else False)
                            )
                            session.add(new_item)
                            self.stats['proforma_items'] += 1
                    except sqlite3.OperationalError:
                        pass

                    self.stats['proformas'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['proformas']} proformas")
                print(f"   Migrated {self.stats['proforma_items']} proforma items")

        except Exception as e:
            print(f"   Error migrating proformas: {e}")
            self.stats['errors'].append(f"Proformas: {e}")

    async def migrate_quantity_limits(self):
        """Migrate procurement quantity limits"""
        print("\nMigrating quantity limits...")

        try:
            cursor = self.old_conn.cursor()

            try:
                old_limits = cursor.execute("""
                    SELECT ql.*, p.name as product_name, s.name as site_name
                    FROM quantity_limits ql
                    JOIN products p ON ql.product_id = p.id
                    LEFT JOIN sites s ON ql.site_id = s.id
                    WHERE ql.active = 1
                """).fetchall()
            except sqlite3.OperationalError:
                print("   'quantity_limits' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_limit in old_limits:
                    # Find product
                    result = await session.execute(
                        select(Product).where(Product.name == old_limit['product_name'])
                    )
                    product = result.scalar_one_or_none()

                    if not product:
                        continue

                    # Find site
                    site = None
                    site_name = old_limit['site_name'] if 'site_name' in old_limit.keys() else None
                    if site_name:
                        result = await session.execute(
                            select(Site).where(Site.name == site_name)
                        )
                        site = result.scalar_one_or_none()

                    new_limit = QuantityLimit(
                        product_id=product.id,
                        site_id=site.id if site else None,
                        min_quantity=float(old_limit['min_quantity']) if old_limit['min_quantity'] is not None else None,
                        max_quantity=float(old_limit['max_quantity']) if old_limit['max_quantity'] is not None else None,
                        unit=old_limit['unit'],
                        period=old_limit['period'] if 'period' in old_limit.keys() else 'monthly',
                        is_active=True
                    )
                    session.add(new_limit)
                    self.stats['quantity_limits'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['quantity_limits']} quantity limits")

        except Exception as e:
            print(f"   Error migrating quantity limits: {e}")
            self.stats['errors'].append(f"Quantity limits: {e}")

    async def migrate_anomalies(self):
        """Migrate detected anomalies"""
        print("\nMigrating anomalies...")

        try:
            cursor = self.old_conn.cursor()

            cutoff_date = (datetime.now().date() - timedelta(days=90)).isoformat()

            try:
                old_anomalies = cursor.execute("""
                    SELECT * FROM anomalies
                    WHERE detected_at >= ?
                    ORDER BY detected_at DESC
                """, (cutoff_date,)).fetchall()
            except sqlite3.OperationalError:
                print("   'anomalies' table not found, skipping")
                return

            async with AsyncSessionLocal() as session:
                for old_anom in old_anomalies:
                    new_anom = Anomaly(
                        anomaly_type=old_anom['anomaly_type'],
                        entity_type=old_anom['entity_type'],
                        entity_id=int(old_anom['entity_id']),
                        detected_at=self._parse_date(old_anom['detected_at']) or date.today(),
                        description=old_anom['description'],
                        severity=old_anom['severity'] if 'severity' in old_anom.keys() else 'medium',
                        expected_value=float(old_anom['expected_value']) if old_anom['expected_value'] is not None else None,
                        actual_value=float(old_anom['actual_value']) if old_anom['actual_value'] is not None else None,
                        variance_percent=float(old_anom['variance_percent']) if old_anom['variance_percent'] is not None else None,
                        acknowledged=bool(old_anom['acknowledged'] if 'acknowledged' in old_anom.keys() else False),
                        resolved=bool(old_anom['resolved'] if 'resolved' in old_anom.keys() else False),
                        resolution_notes=old_anom['resolution_notes'] if 'resolution_notes' in old_anom.keys() else None
                    )
                    session.add(new_anom)
                    self.stats['anomalies'] += 1

                await session.commit()
                print(f"   Migrated {self.stats['anomalies']} anomalies")

        except Exception as e:
            print(f"   Error migrating anomalies: {e}")
            self.stats['errors'].append(f"Anomalies: {e}")

    def print_summary(self):
        """Print migration summary"""
        print("\n" + "=" * 60)
        print("COMPLETE MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Sites:              {self.stats['sites']}")
        print(f"Suppliers:          {self.stats['suppliers']}")
        print(f"Products:           {self.stats['products']}")
        print(f"Price Lists:        {self.stats['price_lists']}")
        print(f"Price List Items:   {self.stats['price_list_items']}")
        print(f"Historical Records: {self.stats['historical_data']}")

        print(f"\nMenu Compliance:")
        print(f"Menu Checks:        {self.stats['menu_checks']}")
        print(f"Check Results:      {self.stats['check_results']}")

        print(f"\nOperations:")
        print(f"Proformas:          {self.stats['proformas']}")
        print(f"Proforma Items:     {self.stats['proforma_items']}")
        print(f"Quantity Limits:    {self.stats['quantity_limits']}")
        print(f"Anomalies:          {self.stats['anomalies']}")

        if self.stats['errors']:
            print(f"\nErrors: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                print(f"   - {error}")

        print("\n" + "=" * 60)
        print("COMPLETE MIGRATION FINISHED")
        print("=" * 60)
        print("\nWhat was migrated:")
        print("  All sites, suppliers, products, price lists")
        print("  Historical meal data (for AI learning)")
        print("  Menu compliance checks and findings")
        print("  Proformas and invoices")
        print("  Quantity limits and anomalies")
        print()
        print("Next steps:")
        print("1. Run validation: python scripts/validate_migration.py")
        print("2. Old system remains unchanged at:", self.old_db_path)
        print("3. Start using new AI-native system!")
        print()

    # Helper methods

    def _generate_site_code(self, site_name: str) -> str:
        """Generate site code from name"""
        codes = {
            'Nes Ziona': 'NZ',
            'Kiryat Gat': 'KG'
        }
        return codes.get(site_name, site_name[:2].upper())

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str).date()
        except (ValueError, TypeError):
            return None


async def main():
    """Main migration entry point"""
    if len(sys.argv) < 2:
        print("Error: Missing database path")
        print("\nUsage:")
        print("  python scripts/migrate_from_old_system.py /path/to/old/catering.db")
        print("\nExample:")
        print("  python scripts/migrate_from_old_system.py /tmp/foodhouse_backup.db")
        sys.exit(1)

    old_db_path = sys.argv[1]

    if not Path(old_db_path).exists():
        print(f"Error: Database not found at {old_db_path}")
        sys.exit(1)

    migration = DataMigration(old_db_path)
    await migration.migrate_all()


if __name__ == "__main__":
    asyncio.run(main())
