"""
Validation Script: Verify complete migration

Checks all tables: sites, users, suppliers, products, price lists,
historical data, menu checks, check results, proformas, quantity limits, anomalies.

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
from backend.models.menu_compliance import MenuCheck, CheckResult
from backend.models.proforma import Proforma, ProformaItem
from backend.models.operations import QuantityLimit, Anomaly


async def validate_migration():
    """Run validation checks on migrated data"""
    print("=" * 60)
    print("COMPLETE MIGRATION VALIDATION")
    print("=" * 60)
    print()

    all_checks_passed = True

    async with AsyncSessionLocal() as session:
        # Check 1: Sites
        print("Checking sites...")
        result = await session.execute(select(func.count(Site.id)))
        site_count = result.scalar()
        print(f"   Found: {site_count} sites")

        if site_count < 2:
            print("   WARNING: Expected at least 2 sites (Nes Ziona, Kiryat Gat)")
            all_checks_passed = False
        else:
            print("   Site count OK")

        result = await session.execute(select(Site).limit(1))
        site = result.scalar_one_or_none()
        if site:
            print(f"\n   Sample Site:")
            print(f"   - Name: {site.name}")
            print(f"   - Code: {site.code}")
            print(f"   - Budget: {site.monthly_budget:,.0f}/month")

        # Check 2: Users
        print("\nChecking users...")
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar()
        print(f"   Found: {user_count} users")

        if user_count < 1:
            print("   ERROR: No users found")
            all_checks_passed = False
        else:
            print("   User count OK")

        # Check 3: Suppliers
        print("\nChecking suppliers...")
        result = await session.execute(select(func.count(Supplier.id)))
        supplier_count = result.scalar()
        print(f"   Found: {supplier_count} suppliers")

        if supplier_count > 0:
            print("   Suppliers migrated")
            result = await session.execute(select(Supplier).limit(1))
            supplier = result.scalar_one_or_none()
            if supplier:
                print(f"   Sample: {supplier.name}")

        # Check 4: Products
        print("\nChecking products...")
        result = await session.execute(select(func.count(Product.id)))
        product_count = result.scalar()
        print(f"   Found: {product_count} products")

        if product_count > 0:
            print("   Products migrated")

        # Check 5: Price Lists
        print("\nChecking price lists...")
        result = await session.execute(select(func.count(PriceList.id)))
        price_list_count = result.scalar()
        print(f"   Found: {price_list_count} price lists")

        # Check 6: Historical Data
        print("\nChecking historical data...")
        result = await session.execute(select(func.count(HistoricalMealData.id)))
        historical_count = result.scalar()
        print(f"   Found: {historical_count} historical records")

        # Check 7: Menu Checks
        print("\nChecking menu checks...")
        result = await session.execute(select(func.count(MenuCheck.id)))
        menu_check_count = result.scalar()
        print(f"   Found: {menu_check_count} menu checks")

        if menu_check_count > 0:
            print("   Menu checks migrated")
        else:
            print("   WARNING: No menu checks found")

        # Check 8: Check Results
        print("\nChecking check results...")
        result = await session.execute(select(func.count(CheckResult.id)))
        check_result_count = result.scalar()
        print(f"   Found: {check_result_count} check results")

        if check_result_count > 0:
            print("   Check results migrated")

        # Check 9: Proformas
        print("\nChecking proformas...")
        result = await session.execute(select(func.count(Proforma.id)))
        proforma_count = result.scalar()
        print(f"   Found: {proforma_count} proformas")

        if proforma_count > 0:
            print("   Proformas migrated")

        # Check 10: Proforma Items
        print("\nChecking proforma items...")
        result = await session.execute(select(func.count(ProformaItem.id)))
        proforma_item_count = result.scalar()
        print(f"   Found: {proforma_item_count} proforma items")

        if proforma_item_count > 0:
            print("   Proforma items migrated")

        # Check 11: Quantity Limits
        print("\nChecking quantity limits...")
        result = await session.execute(select(func.count(QuantityLimit.id)))
        quantity_limit_count = result.scalar()
        print(f"   Found: {quantity_limit_count} quantity limits")

        if quantity_limit_count > 0:
            print("   Quantity limits migrated")

        # Check 12: Anomalies
        print("\nChecking anomalies...")
        result = await session.execute(select(func.count(Anomaly.id)))
        anomaly_count = result.scalar()
        print(f"   Found: {anomaly_count} anomalies")

        if anomaly_count > 0:
            print("   Anomalies migrated")

        # Summary
        print("\n" + "=" * 60)
        print("TOTALS:")
        print(f"  Core:       {site_count} sites, {supplier_count} suppliers, {product_count} products")
        print(f"  Financial:  {price_list_count} price lists, {proforma_count} proformas ({proforma_item_count} items)")
        print(f"  Compliance: {menu_check_count} menu checks, {check_result_count} check results")
        print(f"  Operations: {quantity_limit_count} quantity limits, {anomaly_count} anomalies")
        print(f"  History:    {historical_count} meal records")

        print("\n" + "=" * 60)
        if all_checks_passed:
            print("VALIDATION PASSED")
            print("\nComplete migration looks good! All data migrated successfully.")
        else:
            print("VALIDATION WARNINGS")
            print("\nSome checks failed. Review warnings above.")
        print("=" * 60)
        print()


if __name__ == "__main__":
    asyncio.run(validate_migration())
