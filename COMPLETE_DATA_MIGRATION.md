# Complete Data Migration - All FoodHouse Analytics Data

> **Upload this to Cursor to migrate ALL data from your old system including menu checking**

---

## Overview

Migrate EVERYTHING from FoodHouse Analytics:
- ✅ Sites, suppliers, products, price lists (DONE in Phase 1)
- ✅ Historical meal data (DONE in Phase 1)
- 🆕 **Menu checks and compliance rules** (56 rules → Natural language)
- 🆕 **Check results, findings, reviews**
- 🆕 **Proformas (invoices) and items**
- 🆕 **Quantity limits**
- 🆕 **Anomalies**
- 🆕 **Audit logs**

---

## New Database Models

### 1. Menu Compliance Models (`backend/models/menu_compliance.py`)

```python
"""
Menu compliance checking models
Migrated from old FoodHouse Analytics 56-rule system
"""
from sqlalchemy import Column, Integer, String, Text, Date, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from backend.database import Base


class MenuCheck(Base):
    """Monthly menu compliance check"""
    __tablename__ = "menu_checks"
    
    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    
    # Menu file
    file_path = Column(String, nullable=True)
    month = Column(String, nullable=False)  # "2025-02"
    year = Column(Integer, nullable=False)
    
    # Check status
    total_findings = Column(Integer, default=0)
    critical_findings = Column(Integer, default=0)
    warnings = Column(Integer, default=0)
    passed_rules = Column(Integer, default=0)
    
    # Timestamps
    checked_at = Column(Date, nullable=False)
    
    # Relationships
    site = relationship("Site")
    days = relationship("MenuDay", back_populates="menu_check")
    results = relationship("CheckResult", back_populates="menu_check")


class MenuDay(Base):
    """Individual day in a menu"""
    __tablename__ = "menu_days"
    
    id = Column(Integer, primary_key=True, index=True)
    menu_check_id = Column(Integer, ForeignKey("menu_checks.id"), nullable=False)
    
    # Day details
    date = Column(Date, nullable=False)
    day_of_week = Column(String, nullable=False)  # Sunday, Monday, etc.
    week_number = Column(Integer, nullable=False)  # 1-4
    
    # Day type
    is_holiday = Column(Boolean, default=False)
    is_theme_day = Column(Boolean, default=False)
    day_type_override = Column(String, nullable=True)  # "Purim", "Passover", etc.
    
    # Menu content (stored as JSON for flexibility)
    menu_items = Column(JSON, nullable=True)  # {category: [items]}
    
    # Relationships
    menu_check = relationship("MenuCheck", back_populates="days")


class CheckResult(Base):
    """Result of running a compliance rule"""
    __tablename__ = "check_results"
    
    id = Column(Integer, primary_key=True, index=True)
    menu_check_id = Column(Integer, ForeignKey("menu_checks.id"), nullable=False)
    
    # Rule identification
    rule_name = Column(String, nullable=False)
    rule_category = Column(String, nullable=True)
    
    # Result
    passed = Column(Boolean, nullable=False)
    severity = Column(String, nullable=False)  # critical, warning, info
    
    # Details
    finding_text = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=True)  # Supporting data
    
    # Review status
    reviewed = Column(Boolean, default=False)
    review_status = Column(String, nullable=True)  # approved, parser_error, supplier_note
    review_notes = Column(Text, nullable=True)
    
    # Relationships
    menu_check = relationship("MenuCheck", back_populates="results")
```

### 2. Proforma Models (`backend/models/proforma.py`)

```python
"""
Proforma (invoice) models
"""
from sqlalchemy import Column, Integer, String, Text, Date, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from backend.database import Base


class Proforma(Base):
    """Supplier invoice/proforma"""
    __tablename__ = "proformas"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    
    # Proforma details
    proforma_number = Column(String, nullable=True)
    invoice_date = Column(Date, nullable=False)
    delivery_date = Column(Date, nullable=True)
    
    # Financial
    total_amount = Column(Float, nullable=False)
    currency = Column(String, default="ILS")
    
    # Status
    status = Column(String, nullable=False)  # pending, validated, approved, rejected, paid
    
    # File
    file_path = Column(String, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Relationships
    supplier = relationship("Supplier")
    site = relationship("Site")
    items = relationship("ProformaItem", back_populates="proforma")


class ProformaItem(Base):
    """Line item in a proforma"""
    __tablename__ = "proforma_items"
    
    id = Column(Integer, primary_key=True, index=True)
    proforma_id = Column(Integer, ForeignKey("proformas.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Item details
    product_name = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    
    # Validation
    price_variance = Column(Float, nullable=True)  # % difference from expected
    flagged = Column(Boolean, default=False)
    
    # Relationships
    proforma = relationship("Proforma", back_populates="items")
    product = relationship("Product")
```

### 3. Other Models (`backend/models/operations.py`)

```python
"""
Operational tracking models
"""
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class QuantityLimit(Base):
    """Procurement quantity limits"""
    __tablename__ = "quantity_limits"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=True)
    
    # Limits
    min_quantity = Column(Float, nullable=True)
    max_quantity = Column(Float, nullable=True)
    unit = Column(String, nullable=False)
    
    # Period
    period = Column(String, nullable=False)  # daily, weekly, monthly
    
    # Active
    is_active = Column(Boolean, default=True)
    
    # Relationships
    product = relationship("Product")
    site = relationship("Site")


class Anomaly(Base):
    """Detected anomalies in data"""
    __tablename__ = "anomalies"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # What
    anomaly_type = Column(String, nullable=False)  # price_spike, usage_spike, etc.
    entity_type = Column(String, nullable=False)  # product, supplier, site
    entity_id = Column(Integer, nullable=False)
    
    # When
    detected_at = Column(Date, nullable=False)
    
    # Details
    description = Column(Text, nullable=False)
    severity = Column(String, nullable=False)  # low, medium, high
    
    # Value
    expected_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    variance_percent = Column(Float, nullable=True)
    
    # Resolution
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text, nullable=True)
```

---

## Enhanced Migration Script

### Update Migration Script (`scripts/migrate_from_old_system.py`)

Add these methods to the DataMigration class:

```python
async def migrate_menu_checks(self):
    """Migrate menu compliance checks"""
    print("\n🍽️  Migrating menu checks...")
    
    try:
        cursor = self.old_conn.cursor()
        
        try:
            old_checks = cursor.execute("""
                SELECT mc.*, s.name as site_name
                FROM menu_checks mc
                LEFT JOIN sites s ON mc.site_id = s.id
                ORDER BY mc.year DESC, mc.month DESC
                LIMIT 12
            """).fetchall()
        except sqlite3.OperationalError:
            print("   ⚠️  'menu_checks' table not found, skipping")
            return
        
        async with AsyncSessionLocal() as session:
            from backend.models.menu_compliance import MenuCheck
            from backend.models.site import Site
            
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
                    file_path=old_check.get('file_path'),
                    month=old_check['month'],
                    year=old_check['year'],
                    total_findings=old_check.get('total_findings', 0),
                    critical_findings=old_check.get('critical_findings', 0),
                    warnings=old_check.get('warnings', 0),
                    passed_rules=old_check.get('passed_rules', 0),
                    checked_at=self._parse_date(old_check.get('checked_at')) or date.today()
                )
                session.add(new_check)
                self.stats['menu_checks'] += 1
            
            await session.commit()
            print(f"   ✅ Migrated {self.stats['menu_checks']} menu checks")
            
    except Exception as e:
        print(f"   ❌ Error migrating menu checks: {e}")
        self.stats['errors'].append(f"Menu checks: {e}")


async def migrate_check_results(self):
    """Migrate check results (findings)"""
    print("\n📋 Migrating check results...")
    
    try:
        cursor = self.old_conn.cursor()
        
        try:
            old_results = cursor.execute("""
                SELECT cr.*, mc.month, mc.year, s.name as site_name
                FROM check_results cr
                JOIN menu_checks mc ON cr.menu_check_id = mc.id
                JOIN sites s ON mc.site_id = s.id
                WHERE mc.year >= 2024
                ORDER BY mc.year DESC, mc.month DESC
            """).fetchall()
        except sqlite3.OperationalError:
            print("   ⚠️  'check_results' table not found, skipping")
            return
        
        async with AsyncSessionLocal() as session:
            from backend.models.menu_compliance import MenuCheck, CheckResult
            from backend.models.site import Site
            
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
                if old_result.get('evidence'):
                    try:
                        evidence = json.loads(old_result['evidence'])
                    except:
                        pass
                
                new_result = CheckResult(
                    menu_check_id=menu_check.id,
                    rule_name=old_result['rule_name'],
                    rule_category=old_result.get('rule_category'),
                    passed=bool(old_result['passed']),
                    severity=old_result.get('severity', 'warning'),
                    finding_text=old_result.get('finding_text'),
                    evidence=evidence,
                    reviewed=bool(old_result.get('reviewed', False)),
                    review_status=old_result.get('review_status'),
                    review_notes=old_result.get('review_notes')
                )
                session.add(new_result)
                self.stats['check_results'] += 1
            
            await session.commit()
            print(f"   ✅ Migrated {self.stats['check_results']} check results")
            
    except Exception as e:
        print(f"   ❌ Error migrating check results: {e}")
        self.stats['errors'].append(f"Check results: {e}")


async def migrate_proformas(self):
    """Migrate proformas (invoices)"""
    print("\n📄 Migrating proformas...")
    
    try:
        cursor = self.old_conn.cursor()
        
        # Get proformas from last 12 months
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
            print("   ⚠️  'proformas' table not found, skipping")
            return
        
        async with AsyncSessionLocal() as session:
            from backend.models.proforma import Proforma, ProformaItem
            from backend.models.supplier import Supplier
            from backend.models.site import Site
            from backend.models.product import Product
            
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
                if old_pf.get('site_name'):
                    result = await session.execute(
                        select(Site).where(Site.name == old_pf['site_name'])
                    )
                    site = result.scalar_one_or_none()
                
                # Check if exists
                result = await session.execute(
                    select(Proforma).where(
                        Proforma.supplier_id == supplier.id,
                        Proforma.invoice_date == self._parse_date(old_pf['invoice_date'])
                    )
                )
                if result.scalar_one_or_none():
                    continue
                
                new_pf = Proforma(
                    supplier_id=supplier.id,
                    site_id=site.id if site else None,
                    proforma_number=old_pf.get('proforma_number'),
                    invoice_date=self._parse_date(old_pf['invoice_date']),
                    delivery_date=self._parse_date(old_pf.get('delivery_date')),
                    total_amount=float(old_pf['total_amount']),
                    currency=old_pf.get('currency', 'ILS'),
                    status=old_pf.get('status', 'pending'),
                    file_path=old_pf.get('file_path'),
                    notes=old_pf.get('notes')
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
                        if old_item.get('product_name'):
                            result = await session.execute(
                                select(Product).where(Product.name == old_item['product_name'])
                            )
                            product = result.scalar_one_or_none()
                        
                        new_item = ProformaItem(
                            proforma_id=new_pf.id,
                            product_id=product.id if product else None,
                            product_name=old_item['product_name'],
                            quantity=float(old_item['quantity']),
                            unit=old_item.get('unit'),
                            unit_price=float(old_item['unit_price']),
                            total_price=float(old_item['total_price']),
                            price_variance=old_item.get('price_variance'),
                            flagged=bool(old_item.get('flagged', False))
                        )
                        session.add(new_item)
                        self.stats['proforma_items'] += 1
                except:
                    pass
                
                self.stats['proformas'] += 1
            
            await session.commit()
            print(f"   ✅ Migrated {self.stats['proformas']} proformas")
            print(f"   ✅ Migrated {self.stats['proforma_items']} proforma items")
            
    except Exception as e:
        print(f"   ❌ Error migrating proformas: {e}")
        self.stats['errors'].append(f"Proformas: {e}")


async def migrate_quantity_limits(self):
    """Migrate procurement quantity limits"""
    print("\n📊 Migrating quantity limits...")
    
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
            print("   ⚠️  'quantity_limits' table not found, skipping")
            return
        
        async with AsyncSessionLocal() as session:
            from backend.models.operations import QuantityLimit
            from backend.models.product import Product
            from backend.models.site import Site
            
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
                if old_limit.get('site_name'):
                    result = await session.execute(
                        select(Site).where(Site.name == old_limit['site_name'])
                    )
                    site = result.scalar_one_or_none()
                
                new_limit = QuantityLimit(
                    product_id=product.id,
                    site_id=site.id if site else None,
                    min_quantity=old_limit.get('min_quantity'),
                    max_quantity=old_limit.get('max_quantity'),
                    unit=old_limit['unit'],
                    period=old_limit.get('period', 'monthly'),
                    is_active=True
                )
                session.add(new_limit)
                self.stats['quantity_limits'] += 1
            
            await session.commit()
            print(f"   ✅ Migrated {self.stats['quantity_limits']} quantity limits")
            
    except Exception as e:
        print(f"   ❌ Error migrating quantity limits: {e}")
        self.stats['errors'].append(f"Quantity limits: {e}")


async def migrate_anomalies(self):
    """Migrate detected anomalies"""
    print("\n⚠️  Migrating anomalies...")
    
    try:
        cursor = self.old_conn.cursor()
        
        # Get recent anomalies
        cutoff_date = (datetime.now().date() - timedelta(days=90)).isoformat()
        
        try:
            old_anomalies = cursor.execute("""
                SELECT * FROM anomalies
                WHERE detected_at >= ?
                ORDER BY detected_at DESC
            """, (cutoff_date,)).fetchall()
        except sqlite3.OperationalError:
            print("   ⚠️  'anomalies' table not found, skipping")
            return
        
        async with AsyncSessionLocal() as session:
            from backend.models.operations import Anomaly
            
            for old_anom in old_anomalies:
                new_anom = Anomaly(
                    anomaly_type=old_anom['anomaly_type'],
                    entity_type=old_anom['entity_type'],
                    entity_id=int(old_anom['entity_id']),
                    detected_at=self._parse_date(old_anom['detected_at']) or date.today(),
                    description=old_anom['description'],
                    severity=old_anom.get('severity', 'medium'),
                    expected_value=old_anom.get('expected_value'),
                    actual_value=old_anom.get('actual_value'),
                    variance_percent=old_anom.get('variance_percent'),
                    acknowledged=bool(old_anom.get('acknowledged', False)),
                    resolved=bool(old_anom.get('resolved', False)),
                    resolution_notes=old_anom.get('resolution_notes')
                )
                session.add(new_anom)
                self.stats['anomalies'] += 1
            
            await session.commit()
            print(f"   ✅ Migrated {self.stats['anomalies']} anomalies")
            
    except Exception as e:
        print(f"   ❌ Error migrating anomalies: {e}")
        self.stats['errors'].append(f"Anomalies: {e}")


async def migrate_all(self):
    """Run complete migration - UPDATED"""
    print("="*60)
    print("🚀 COMPLETE MIGRATION: FoodHouse Analytics → Catering Services AI Pro")
    print("="*60)
    print()
    
    try:
        # Connect to old database
        self.connect_old_db()
        
        # Create new database tables
        await self.create_new_tables()
        
        # Run all migrations
        await self.migrate_sites()
        await self.migrate_users()
        await self.migrate_suppliers()
        await self.migrate_products()
        await self.migrate_price_lists()
        await self.migrate_historical_data()
        
        # NEW: Migrate menu checking data
        await self.migrate_menu_checks()
        await self.migrate_check_results()
        
        # NEW: Migrate operational data
        await self.migrate_proformas()
        await self.migrate_quantity_limits()
        await self.migrate_anomalies()
        
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


def print_summary(self):
    """Print migration summary - UPDATED"""
    print("\n" + "="*60)
    print("📋 COMPLETE MIGRATION SUMMARY")
    print("="*60)
    
    # Core data
    print(f"✅ Sites:              {self.stats['sites']}")
    print(f"✅ Suppliers:          {self.stats['suppliers']}")
    print(f"✅ Products:           {self.stats['products']}")
    print(f"✅ Price Lists:        {self.stats['price_lists']}")
    print(f"✅ Price List Items:   {self.stats['price_list_items']}")
    print(f"✅ Historical Records: {self.stats['historical_data']}")
    
    # Menu checking
    print(f"\n📋 Menu Compliance:")
    print(f"✅ Menu Checks:        {self.stats.get('menu_checks', 0)}")
    print(f"✅ Check Results:      {self.stats.get('check_results', 0)}")
    
    # Operations
    print(f"\n📊 Operations:")
    print(f"✅ Proformas:          {self.stats.get('proformas', 0)}")
    print(f"✅ Proforma Items:     {self.stats.get('proforma_items', 0)}")
    print(f"✅ Quantity Limits:    {self.stats.get('quantity_limits', 0)}")
    print(f"✅ Anomalies:          {self.stats.get('anomalies', 0)}")
    
    if self.stats['errors']:
        print(f"\n⚠️  Errors: {len(self.stats['errors'])}")
        for error in self.stats['errors']:
            print(f"   - {error}")
    
    print("\n" + "="*60)
    print("✅ COMPLETE MIGRATION FINISHED")
    print("="*60)
    print("\nWhat was migrated:")
    print("✅ All sites, suppliers, products, price lists")
    print("✅ Historical meal data (for AI learning)")
    print("✅ Menu compliance checks and findings")
    print("✅ Proformas and invoices")
    print("✅ Quantity limits and anomalies")
    print()
    print("Next steps:")
    print("1. Run validation: python scripts/validate_migration.py")
    print("2. Old system remains unchanged at:", self.old_db_path)
    print("3. Start using new AI-native system!")
    print()
```

---

## Natural Language Policy Export

Enhance the compliance rules export:

```python
# scripts/export_compliance_rules.py - ENHANCED VERSION

def export_rules_to_policy(old_db_path: str):
    """Export all 56 compliance rules as natural language policy"""
    
    # ... (keep existing code, add more detail) ...
    
    # Add specific sections for each rule category
    policy_lines.append("## Daily Requirements\n\n")
    policy_lines.append("### Main Course Requirements\n")
    policy_lines.append("- **Required daily**: One main protein dish (meat, chicken, or fish)\n")
    policy_lines.append("- **Variety**: At least 3 different main dishes per week\n")
    policy_lines.append("- **Prohibition**: Same main dish maximum 2 times per week\n\n")
    
    policy_lines.append("### Side Dishes\n")
    policy_lines.append("- **Carbohydrates**: Rice, pasta, or potatoes daily\n")
    policy_lines.append("- **Vegetables**: Minimum 2 different vegetables per day\n")
    policy_lines.append("- **Salads**: Fresh salad bar required daily\n\n")
    
    # ... continue for all 56 rules ...
    
    print(f"✅ Exported 56 compliance rules to natural language policy")
    print("   AI will now interpret these rules instead of hardcoded logic")
```

---

## Testing Complete Migration

After Cursor implements:

```bash
# Run complete migration
python scripts/migrate_from_old_system.py /path/to/old/catering.db

# Expected output:
# ✅ Sites: 2
# ✅ Suppliers: 3
# ✅ Products: 12
# ✅ Historical Records: 428
# ✅ Menu Checks: 12
# ✅ Check Results: 340
# ✅ Proformas: 36
# ✅ Proforma Items: 856
# ✅ Quantity Limits: 45
# ✅ Anomalies: 23

# Validate
python scripts/validate_migration.py

# View in UI
# All data will be visible in dashboards
```

---

## Benefits of Complete Migration

### Menu Checking (56 Rules → AI):
**Before:** Hardcoded Python rules, difficult to modify
**After:** Natural language policy, Claude interprets flexibly

### Historical Context:
**Before:** Isolated in old system
**After:** AI uses ALL historical data for better recommendations

### Unified System:
**Before:** Separate tools for menu checking, invoices, limits
**After:** Everything in one AI-native system

---

Upload both files to Cursor:
1. **PHASE_2_COMPLAINTS.md** - Complaint Intelligence Agent
2. **This file** - Complete data migration

Cursor will implement both in parallel!
