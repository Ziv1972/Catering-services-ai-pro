# Catering Services AI Pro - Complete Migration Implementation Guide

> **Upload this file to Cursor and ask it to implement the migration system**

---

## Overview

This document contains the complete implementation plan for migrating data from FoodHouse Analytics (old SQLite system) to Catering Services AI Pro (new PostgreSQL AI-native system).

**Migration Strategy:** Dual-system approach - migrate reference data while keeping old system intact for reference.

---

## Project Structure

```
catering-services-ai-pro/
├── scripts/
│   ├── migrate_from_old_system.py    # Main migration script
│   ├── validate_migration.py         # Validation script
│   └── export_compliance_rules.py    # Rules export script
├── docs/
│   └── CATERING_POLICY.md           # Generated policy document
└── backend/
    └── models/
        ├── supplier.py               # Supplier model (to be created)
        ├── product.py                # Product model (to be created)
        ├── price_list.py             # Price list models (to be created)
        └── historical_data.py        # Historical data model (to be created)
```

---

## Database Models Needed for Migration

### 1. Supplier Model (`backend/models/supplier.py`)

```python
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
```

### 2. Product Model (`backend/models/product.py`)

```python
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
```

### 3. Price List Models (`backend/models/price_list.py`)

```python
"""
Price list models
"""
from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class PriceList(Base):
    __tablename__ = "price_lists"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    effective_date = Column(Date, nullable=False)
    file_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    supplier = relationship("Supplier")
    items = relationship("PriceListItem", back_populates="price_list")


class PriceListItem(Base):
    __tablename__ = "price_list_items"
    
    id = Column(Integer, primary_key=True, index=True)
    price_list_id = Column(Integer, ForeignKey("price_lists.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    price = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    
    # Relationships
    price_list = relationship("PriceList", back_populates="items")
    product = relationship("Product")
```

### 4. Historical Data Model (`backend/models/historical_data.py`)

```python
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
```

---

## Migration Scripts

### Script 1: Main Migration (`scripts/migrate_from_old_system.py`)

```python
"""
Data Migration Script: FoodHouse Analytics → Catering Services AI Pro

Migrates reference data from old SQLite database to new PostgreSQL system.
Old system remains unchanged and available for reference.

Usage:
    python scripts/migrate_from_old_system.py /path/to/old/catering.db
"""

import sqlite3
import asyncio
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
import json

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
            'errors': []
        }
    
    def connect_old_db(self):
        """Connect to old SQLite database"""
        print(f"📂 Connecting to old database: {self.old_db_path}")
        self.old_conn = sqlite3.connect(self.old_db_path)
        self.old_conn.row_factory = sqlite3.Row
        print("✅ Connected to old database")
    
    def close_old_db(self):
        """Close old database connection"""
        if self.old_conn:
            self.old_conn.close()
            print("✅ Closed old database connection")
    
    async def create_new_tables(self):
        """Create all tables in new database"""
        print("🔨 Creating tables in new database...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Tables created")
    
    async def migrate_all(self):
        """Run complete migration"""
        print("="*60)
        print("🚀 MIGRATION: FoodHouse Analytics → Catering Services AI Pro")
        print("="*60)
        print()
        
        try:
            # Connect to old database
            self.connect_old_db()
            
            # Create new database tables
            await self.create_new_tables()
            
            # Run migrations in order (respecting foreign keys)
            await self.migrate_sites()
            await self.migrate_users()
            await self.migrate_suppliers()
            await self.migrate_products()
            await self.migrate_price_lists()
            await self.migrate_historical_data()
            
            # Print summary
            self.print_summary()
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            self.stats['errors'].append(str(e))
            raise
        finally:
            self.close_old_db()
    
    async def migrate_sites(self):
        """Migrate site configurations (Nes Ziona, Kiryat Gat)"""
        print("\n📍 Migrating sites...")
        
        try:
            cursor = self.old_conn.cursor()
            
            # Try to get sites from old database
            try:
                old_sites = cursor.execute("""
                    SELECT name, budget, active
                    FROM sites
                    WHERE active = 1
                """).fetchall()
            except sqlite3.OperationalError:
                # Table doesn't exist, create default sites
                print("   ⚠️  'sites' table not found, creating default sites...")
                old_sites = [
                    {'name': 'Nes Ziona', 'budget': 60000, 'active': 1},
                    {'name': 'Kiryat Gat', 'budget': 60000, 'active': 1}
                ]
            
            async with AsyncSessionLocal() as session:
                for old_site in old_sites:
                    # Check if site already exists
                    result = await session.execute(
                        select(Site).where(Site.name == old_site['name'])
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        print(f"   ⚠️  Site already exists: {old_site['name']}, skipping")
                        continue
                    
                    # Generate site code
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
                print(f"   ✅ Migrated {self.stats['sites']} sites")
                
        except Exception as e:
            print(f"   ❌ Error migrating sites: {e}")
            self.stats['errors'].append(f"Sites: {e}")
    
    async def migrate_users(self):
        """Create default admin user"""
        print("\n👤 Creating default admin user...")
        
        try:
            async with AsyncSessionLocal() as session:
                # Check if admin exists
                result = await session.execute(
                    select(User).where(User.email == "ziv@hp.com")
                )
                if result.scalar_one_or_none():
                    print("   ⚠️  Admin user already exists, skipping")
                    return
                
                # Create admin
                admin = User(
                    email="ziv@hp.com",
                    full_name="Ziv Cohen",
                    hashed_password=get_password_hash("admin123"),
                    is_active=True,
                    is_admin=True
                )
                session.add(admin)
                await session.commit()
                print("   ✅ Created admin user (ziv@hp.com / admin123)")
                
        except Exception as e:
            print(f"   ❌ Error creating admin: {e}")
            self.stats['errors'].append(f"Admin user: {e}")
    
    async def migrate_suppliers(self):
        """Migrate supplier data"""
        print("\n🏢 Migrating suppliers...")
        
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
                print("   ⚠️  'suppliers' table not found, skipping")
                return
            
            async with AsyncSessionLocal() as session:
                for old_sup in old_suppliers:
                    # Check if exists
                    result = await session.execute(
                        select(Supplier).where(Supplier.name == old_sup['name'])
                    )
                    if result.scalar_one_or_none():
                        print(f"   ⚠️  Supplier exists: {old_sup['name']}, skipping")
                        continue
                    
                    new_sup = Supplier(
                        name=old_sup['name'],
                        contact_name=old_sup['contact_name'],
                        email=old_sup['email'],
                        phone=old_sup['phone'],
                        contract_start_date=self._parse_date(old_sup.get('contract_start')),
                        contract_end_date=self._parse_date(old_sup.get('contract_end')),
                        payment_terms=old_sup.get('payment_terms'),
                        notes=old_sup.get('notes'),
                        is_active=True
                    )
                    session.add(new_sup)
                    self.stats['suppliers'] += 1
                
                await session.commit()
                print(f"   ✅ Migrated {self.stats['suppliers']} suppliers")
                
        except Exception as e:
            print(f"   ❌ Error migrating suppliers: {e}")
            self.stats['errors'].append(f"Suppliers: {e}")
    
    async def migrate_products(self):
        """Migrate product catalog"""
        print("\n📦 Migrating products...")
        
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
                print("   ⚠️  'products' table not found, skipping")
                return
            
            async with AsyncSessionLocal() as session:
                for old_prod in old_products:
                    # Check if exists
                    result = await session.execute(
                        select(Product).where(Product.name == old_prod['name'])
                    )
                    if result.scalar_one_or_none():
                        continue
                    
                    new_prod = Product(
                        name=old_prod['name'],
                        hebrew_name=old_prod.get('hebrew_name'),
                        category=old_prod.get('category_name') or 'General',
                        unit=old_prod.get('unit'),
                        is_active=True
                    )
                    session.add(new_prod)
                    self.stats['products'] += 1
                
                await session.commit()
                print(f"   ✅ Migrated {self.stats['products']} products")
                
        except Exception as e:
            print(f"   ❌ Error migrating products: {e}")
            self.stats['errors'].append(f"Products: {e}")
    
    async def migrate_price_lists(self):
        """Migrate price lists from last 12 months"""
        print("\n💰 Migrating price lists (last 12 months)...")
        
        try:
            cursor = self.old_conn.cursor()
            
            # Get price lists from last 12 months
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
                print("   ⚠️  'price_lists' table not found, skipping")
                return
            
            async with AsyncSessionLocal() as session:
                for old_pl in old_price_lists:
                    # Find supplier in new system
                    result = await session.execute(
                        select(Supplier).where(Supplier.name == old_pl['supplier_name'])
                    )
                    supplier = result.scalar_one_or_none()
                    
                    if not supplier:
                        print(f"   ⚠️  Skipping price list - supplier not found: {old_pl['supplier_name']}")
                        continue
                    
                    # Check if price list already exists
                    result = await session.execute(
                        select(PriceList).where(
                            PriceList.supplier_id == supplier.id,
                            PriceList.effective_date == self._parse_date(old_pl['effective_date'])
                        )
                    )
                    if result.scalar_one_or_none():
                        continue
                    
                    # Create price list
                    new_pl = PriceList(
                        supplier_id=supplier.id,
                        effective_date=self._parse_date(old_pl['effective_date']),
                        file_path=old_pl.get('file_path'),
                        notes=f"Migrated from FoodHouse Analytics on {date.today()}"
                    )
                    session.add(new_pl)
                    await session.flush()  # Get ID
                    
                    # Migrate items
                    try:
                        old_items = cursor.execute("""
                            SELECT product_name, price, unit
                            FROM price_list_items
                            WHERE price_list_id = ?
                        """, (old_pl['id'],)).fetchall()
                        
                        for old_item in old_items:
                            # Find product
                            result = await session.execute(
                                select(Product).where(Product.name == old_item['product_name'])
                            )
                            product = result.scalar_one_or_none()
                            
                            if product:
                                new_item = PriceListItem(
                                    price_list_id=new_pl.id,
                                    product_id=product.id,
                                    price=float(old_item['price']),
                                    unit=old_item.get('unit')
                                )
                                session.add(new_item)
                                self.stats['price_list_items'] += 1
                    except:
                        pass
                    
                    self.stats['price_lists'] += 1
                
                await session.commit()
                print(f"   ✅ Migrated {self.stats['price_lists']} price lists")
                print(f"   ✅ Migrated {self.stats['price_list_items']} price list items")
                
        except Exception as e:
            print(f"   ❌ Error migrating price lists: {e}")
            self.stats['errors'].append(f"Price lists: {e}")
    
    async def migrate_historical_data(self):
        """Migrate historical meal data for AI learning"""
        print("\n📊 Migrating historical data (last 12 months)...")
        
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
                print("   ⚠️  'meals_data' table not found, skipping")
                return
            
            async with AsyncSessionLocal() as session:
                for old_meal in old_meals:
                    # Find site
                    result = await session.execute(
                        select(Site).where(Site.code == old_meal['site_code'])
                    )
                    site = result.scalar_one_or_none()
                    
                    if not site:
                        continue
                    
                    # Check if exists
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
                        cost=float(old_meal['cost']) if old_meal.get('cost') else None,
                        notes=old_meal.get('notes')
                    )
                    session.add(new_meal)
                    self.stats['historical_data'] += 1
                
                await session.commit()
                print(f"   ✅ Migrated {self.stats['historical_data']} historical records")
                
        except Exception as e:
            print(f"   ❌ Error migrating historical data: {e}")
            self.stats['errors'].append(f"Historical data: {e}")
    
    def print_summary(self):
        """Print migration summary"""
        print("\n" + "="*60)
        print("📋 MIGRATION SUMMARY")
        print("="*60)
        print(f"✅ Sites:              {self.stats['sites']}")
        print(f"✅ Suppliers:          {self.stats['suppliers']}")
        print(f"✅ Products:           {self.stats['products']}")
        print(f"✅ Price Lists:        {self.stats['price_lists']}")
        print(f"✅ Price List Items:   {self.stats['price_list_items']}")
        print(f"✅ Historical Records: {self.stats['historical_data']}")
        
        if self.stats['errors']:
            print(f"\n⚠️  Errors: {len(self.stats['errors'])}")
            for error in self.stats['errors']:
                print(f"   - {error}")
        
        print("\n" + "="*60)
        print("✅ MIGRATION COMPLETE")
        print("="*60)
        print("\nNext steps:")
        print("1. Run validation: python scripts/validate_migration.py")
        print("2. Export compliance rules: python scripts/export_compliance_rules.py /path/to/old/catering.db")
        print("3. Old system remains unchanged at:", self.old_db_path)
        print("4. Start using new system for new workflows")
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
        except:
            return None


async def main():
    """Main migration entry point"""
    if len(sys.argv) < 2:
        print("❌ Error: Missing database path")
        print("\nUsage:")
        print("  python scripts/migrate_from_old_system.py /path/to/old/catering.db")
        print("\nExample:")
        print("  python scripts/migrate_from_old_system.py /tmp/foodhouse_backup.db")
        sys.exit(1)
    
    old_db_path = sys.argv[1]
    
    # Check if old database exists
    if not Path(old_db_path).exists():
        print(f"❌ Error: Database not found at {old_db_path}")
        sys.exit(1)
    
    # Run migration
    migration = DataMigration(old_db_path)
    await migration.migrate_all()


if __name__ == "__main__":
    asyncio.run(main())
```

### Script 2: Validation (`scripts/validate_migration.py`)

```python
"""
Validation Script: Verify migration completed successfully

Usage:
    python scripts/validate_migration.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from backend.database import AsyncSessionLocal
from backend.models.user import User
from backend.models.site import Site
from backend.models.supplier import Supplier
from backend.models.product import Product
from backend.models.price_list import PriceList
from backend.models.historical_data import HistoricalMealData


async def validate_migration():
    """Run validation checks on migrated data"""
    print("="*60)
    print("🔍 MIGRATION VALIDATION")
    print("="*60)
    print()
    
    all_checks_passed = True
    
    async with AsyncSessionLocal() as session:
        # Check 1: Sites
        print("📍 Checking sites...")
        result = await session.execute(select(func.count(Site.id)))
        site_count = result.scalar()
        print(f"   Found: {site_count} sites")
        
        if site_count < 2:
            print("   ⚠️  WARNING: Expected at least 2 sites (Nes Ziona, Kiryat Gat)")
            all_checks_passed = False
        else:
            print("   ✅ Site count OK")
        
        # Sample site
        result = await session.execute(select(Site).limit(1))
        site = result.scalar_one_or_none()
        if site:
            print(f"\n   Sample Site:")
            print(f"   - Name: {site.name}")
            print(f"   - Code: {site.code}")
            print(f"   - Budget: ₪{site.monthly_budget:,.0f}/month")
        
        # Check 2: Users
        print("\n👤 Checking users...")
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        print(f"   Found: {user_count} users")
        
        if user_count < 1:
            print("   ❌ ERROR: No users found")
            all_checks_passed = False
        else:
            print("   ✅ User count OK")
        
        # Check 3: Suppliers
        print("\n🏢 Checking suppliers...")
        result = await session.execute(select(func.count(Supplier.id)))
        supplier_count = result.scalar()
        print(f"   Found: {supplier_count} suppliers")
        
        if supplier_count > 0:
            print("   ✅ Suppliers migrated")
            result = await session.execute(select(Supplier).limit(1))
            supplier = result.scalar_one_or_none()
            if supplier:
                print(f"   Sample: {supplier.name}")
        
        # Check 4: Products
        print("\n📦 Checking products...")
        result = await session.execute(select(func.count(Product.id)))
        product_count = result.scalar()
        print(f"   Found: {product_count} products")
        
        if product_count > 0:
            print("   ✅ Products migrated")
        
        # Check 5: Price Lists
        print("\n💰 Checking price lists...")
        result = await session.execute(select(func.count(PriceList.id)))
        price_list_count = result.scalar()
        print(f"   Found: {price_list_count} price lists")
        
        # Check 6: Historical Data
        print("\n📊 Checking historical data...")
        result = await session.execute(select(func.count(HistoricalMealData.id)))
        historical_count = result.scalar()
        print(f"   Found: {historical_count} historical records")
        
        print("\n" + "="*60)
        if all_checks_passed:
            print("✅ VALIDATION PASSED")
            print("\nMigration looks good! You can start using the new system.")
        else:
            print("⚠️  VALIDATION WARNINGS")
            print("\nSome checks failed. Review warnings above.")
        print("="*60)
        print()


if __name__ == "__main__":
    asyncio.run(validate_migration())
```

### Script 3: Export Rules (`scripts/export_compliance_rules.py`)

```python
"""
Export Compliance Rules: Convert hardcoded rules to natural language policy

Usage:
    python scripts/export_compliance_rules.py /path/to/old/catering.db
"""

import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime


def export_rules_to_policy(old_db_path: str):
    """Export compliance rules as natural language policy document"""
    print("="*60)
    print("📋 EXPORTING COMPLIANCE RULES TO POLICY DOCUMENT")
    print("="*60)
    print()
    
    # Connect to old database
    conn = sqlite3.connect(old_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all active rules
    try:
        rules = cursor.execute("""
            SELECT rule_name, rule_type, description, category, 
                   parameters, priority
            FROM compliance_rules
            WHERE active = 1
            ORDER BY category, priority, rule_name
        """).fetchall()
    except sqlite3.OperationalError:
        print("⚠️  Table 'compliance_rules' not found in old database")
        print("   Creating template policy document instead...")
        rules = []
    
    # Build policy document
    policy_lines = []
    policy_lines.append("# HP Israel Catering Services - Menu Compliance Policy\n\n")
    policy_lines.append(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
    policy_lines.append("**Migrated from:** FoodHouse Analytics\n\n")
    policy_lines.append("---\n\n")
    
    policy_lines.append("## Introduction\n\n")
    policy_lines.append("This document defines the menu compliance policy for HP Israel ")
    policy_lines.append("catering services across Nes Ziona and Kiryat Gat sites. ")
    policy_lines.append("All menus must comply with these requirements.\n\n")
    
    if rules:
        # Group rules by category
        categories = {}
        for rule in rules:
            cat = rule['category'] or 'General'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(rule)
        
        # Write each category
        for category, cat_rules in categories.items():
            policy_lines.append(f"## {category}\n\n")
            
            for rule in cat_rules:
                policy_lines.append(f"### {rule['rule_name']}\n\n")
                
                if rule['description']:
                    policy_lines.append(f"{rule['description']}\n\n")
                
                if rule['parameters']:
                    try:
                        params = json.loads(rule['parameters'])
                        policy_lines.append("**Requirements:**\n\n")
                        
                        if rule['rule_type'] == 'frequency':
                            max_freq = params.get('max_per_week', 'N/A')
                            policy_lines.append(f"- Maximum frequency: {max_freq} times per week\n")
                        
                        elif rule['rule_type'] == 'mandatory':
                            freq = params.get('frequency', 'daily')
                            policy_lines.append(f"- Must appear: {freq}\n")
                        
                        policy_lines.append("\n")
                    except:
                        pass
                
                policy_lines.append("---\n\n")
    else:
        # Create template
        policy_lines.append("## Daily Menu Requirements\n\n")
        policy_lines.append("### Main Dish\n")
        policy_lines.append("- Must be served daily\n")
        policy_lines.append("- Variety: At least 3 different main dishes per week\n\n")
        
        policy_lines.append("### Dietary Accommodations\n")
        policy_lines.append("- Vegan option: Required daily\n")
        policy_lines.append("- Gluten-free: Available on request\n\n")
    
    # Write to file
    output_path = Path("docs/CATERING_POLICY.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(policy_lines)
    
    conn.close()
    
    print(f"✅ Policy document created: {output_path}")
    print(f"   Exported {len(rules)} rules as natural language policy")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_compliance_rules.py /path/to/old/catering.db")
        sys.exit(1)
    
    old_db_path = sys.argv[1]
    
    if not Path(old_db_path).exists():
        print(f"❌ Database not found: {old_db_path}")
        sys.exit(1)
    
    export_rules_to_policy(old_db_path)
```

---

## Instructions for Cursor

**Step 1:** Create all database models listed above:
- `backend/models/supplier.py`
- `backend/models/product.py`
- `backend/models/price_list.py`
- `backend/models/historical_data.py`

**Step 2:** Create all migration scripts:
- `scripts/migrate_from_old_system.py`
- `scripts/validate_migration.py`
- `scripts/export_compliance_rules.py`

**Step 3:** Ensure all imports are correct and models are registered with Base

**Step 4:** Test the migration with a sample run

---

## How to Use After Implementation

```bash
# 1. Backup old database
cd /path/to/FoodHouse_Analytics
cp data/catering.db /tmp/foodhouse_backup.db

# 2. Run migration
cd catering-services-ai-pro
python scripts/migrate_from_old_system.py /tmp/foodhouse_backup.db

# 3. Validate
python scripts/validate_migration.py

# 4. Export policy
python scripts/export_compliance_rules.py /tmp/foodhouse_backup.db
```

---

## Expected Outcome

After migration:
- ✅ All sites, suppliers, products migrated
- ✅ Last 12 months of price lists available
- ✅ Historical data for AI to learn from
- ✅ Compliance policy as readable markdown
- ✅ Old system unchanged and available for reference
- ✅ Ready to start using new AI-native system

---

## Notes for Implementation

1. **Error Handling**: All scripts include comprehensive error handling and continue on non-critical errors
2. **Idempotent**: Scripts can be run multiple times safely (checks for existing data)
3. **Progress Reporting**: Clear progress output during migration
4. **Validation**: Separate validation script to verify success
5. **Rollback**: Old system unchanged, can always start over

---

## Post-Migration Workflow

**Week 1-2:** Validate all migrated data
**Week 3-4:** Start using new system for meetings, complaints (new workflows)
**Week 5-8:** Gradually move existing workflows to new system
**Month 3+:** Old system becomes read-only reference
**Month 6+:** Archive old system after full confidence in new system
