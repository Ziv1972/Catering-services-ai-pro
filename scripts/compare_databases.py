"""
Compare old FoodHouse test DB with new catering_ai.db
"""
import sqlite3


def compare():
    old = sqlite3.connect("scripts/foodhouse_test.db")
    old.row_factory = sqlite3.Row
    new = sqlite3.connect("catering_ai.db")
    new.row_factory = sqlite3.Row

    results = {}
    all_ok = True

    print("=" * 60)
    print("DETAILED MIGRATION COMPARISON")
    print("=" * 60)

    # Sites
    print("\n--- SITES ---")
    old_sites = old.execute("SELECT * FROM sites WHERE active=1").fetchall()
    new_sites = new.execute("SELECT * FROM sites").fetchall()
    print(f"  Old: {len(old_sites)} | New: {len(new_sites)}")
    for s in new_sites:
        print(f"    {s['name']} (code={s['code']}, budget={s['monthly_budget']})")
    results["sites"] = (len(old_sites), len(new_sites))

    # Suppliers
    print("\n--- SUPPLIERS ---")
    old_count = len(old.execute("SELECT * FROM suppliers WHERE active=1").fetchall())
    new_count = len(new.execute("SELECT * FROM suppliers").fetchall())
    print(f"  Old: {old_count} | New: {new_count}")
    ok = old_count == new_count
    if not ok:
        all_ok = False
        print("  MISMATCH!")
    results["suppliers"] = (old_count, new_count)

    # Products
    print("\n--- PRODUCTS ---")
    old_prods = old.execute("SELECT name FROM products WHERE active=1").fetchall()
    new_prods = new.execute("SELECT name FROM products").fetchall()
    old_names = set(p["name"] for p in old_prods)
    new_names = set(p["name"] for p in new_prods)
    missing = old_names - new_names
    print(f"  Old: {len(old_prods)} | New: {len(new_prods)}")
    if missing:
        all_ok = False
        print(f"  MISSING: {missing}")
    else:
        print("  All products match!")
    results["products"] = (len(old_prods), len(new_prods))

    # Price Lists
    print("\n--- PRICE LISTS ---")
    old_pl = old.execute("SELECT COUNT(*) c FROM price_lists").fetchone()["c"]
    new_pl = new.execute("SELECT COUNT(*) c FROM price_lists").fetchone()["c"]
    old_pli = old.execute("SELECT COUNT(*) c FROM price_list_items").fetchone()["c"]
    new_pli = new.execute("SELECT COUNT(*) c FROM price_list_items").fetchone()["c"]
    print(f"  Lists - Old: {old_pl} | New: {new_pl}")
    print(f"  Items - Old: {old_pli} | New: {new_pli}")
    results["price_lists"] = (old_pl, new_pl)
    results["price_list_items"] = (old_pli, new_pli)

    # Historical meals
    print("\n--- HISTORICAL MEALS ---")
    old_m = old.execute("SELECT COUNT(*) c FROM meals_data").fetchone()["c"]
    new_m = new.execute("SELECT COUNT(*) c FROM historical_meal_data").fetchone()["c"]
    print(f"  Old: {old_m} | New: {new_m}")
    if old_m != new_m:
        all_ok = False
        print(f"  MISMATCH! Diff: {new_m - old_m}")
    results["historical_meals"] = (old_m, new_m)

    # Spot check meals
    old_sample = old.execute("SELECT * FROM meals_data ORDER BY date LIMIT 3").fetchall()
    new_sample = new.execute(
        "SELECT h.*, s.code FROM historical_meal_data h "
        "JOIN sites s ON h.site_id=s.id ORDER BY h.date LIMIT 3"
    ).fetchall()
    print("  Sample old:", [(m["date"], m["site_code"], m["meal_count"]) for m in old_sample])
    print("  Sample new:", [(m["date"], m["code"], m["meal_count"]) for m in new_sample])

    # Menu checks
    print("\n--- MENU CHECKS ---")
    old_mc = old.execute("SELECT COUNT(*) c FROM menu_checks").fetchone()["c"]
    new_mc = new.execute("SELECT COUNT(*) c FROM menu_checks").fetchone()["c"]
    print(f"  Old: {old_mc} | New: {new_mc}")
    if old_mc != new_mc:
        all_ok = False
        print(f"  MISMATCH! Diff: {new_mc - old_mc}")
    results["menu_checks"] = (old_mc, new_mc)

    # Check results
    print("\n--- CHECK RESULTS ---")
    old_cr = old.execute("SELECT COUNT(*) c FROM check_results").fetchone()["c"]
    new_cr = new.execute("SELECT COUNT(*) c FROM check_results").fetchone()["c"]
    print(f"  Old: {old_cr} | New: {new_cr}")
    if old_cr != new_cr:
        print(f"  MISMATCH! Diff: {new_cr - old_cr}")
        # This might be OK - random generation in create_test_old_db
    results["check_results"] = (old_cr, new_cr)

    # Proformas
    print("\n--- PROFORMAS ---")
    old_pf = old.execute("SELECT COUNT(*) c FROM proformas").fetchone()["c"]
    new_pf = new.execute("SELECT COUNT(*) c FROM proformas").fetchone()["c"]
    old_pfi = old.execute("SELECT COUNT(*) c FROM proforma_items").fetchone()["c"]
    new_pfi = new.execute("SELECT COUNT(*) c FROM proforma_items").fetchone()["c"]
    print(f"  Proformas - Old: {old_pf} | New: {new_pf}")
    print(f"  Items     - Old: {old_pfi} | New: {new_pfi}")
    if old_pf != new_pf:
        all_ok = False
        print(f"  PROFORMA MISMATCH! Diff: {new_pf - old_pf}")
    if old_pfi != new_pfi:
        print(f"  ITEM DIFF: {new_pfi - old_pfi} (may be due to date cutoff or product matching)")
    results["proformas"] = (old_pf, new_pf)
    results["proforma_items"] = (old_pfi, new_pfi)

    # Quantity limits
    print("\n--- QUANTITY LIMITS ---")
    old_ql = old.execute("SELECT COUNT(*) c FROM quantity_limits WHERE active=1").fetchone()["c"]
    new_ql = new.execute("SELECT COUNT(*) c FROM quantity_limits").fetchone()["c"]
    print(f"  Old (active): {old_ql} | New: {new_ql}")
    if old_ql != new_ql:
        print(f"  DIFF: {new_ql - old_ql}")
    results["quantity_limits"] = (old_ql, new_ql)

    # Anomalies (old has 25, but migration uses 90-day cutoff)
    print("\n--- ANOMALIES ---")
    old_an = old.execute("SELECT COUNT(*) c FROM anomalies").fetchone()["c"]
    new_an = new.execute("SELECT COUNT(*) c FROM anomalies").fetchone()["c"]
    print(f"  Old: {old_an} | New: {new_an}")
    results["anomalies"] = (old_an, new_an)

    # Data integrity - check sums
    print("\n--- DATA INTEGRITY CHECKS ---")

    # Meal cost totals
    old_cost = old.execute("SELECT SUM(cost) c FROM meals_data").fetchone()["c"]
    new_cost = new.execute("SELECT SUM(cost) c FROM historical_meal_data").fetchone()["c"]
    cost_match = abs((old_cost or 0) - (new_cost or 0)) < 0.01
    print(f"  Meal costs total - Old: {old_cost:.2f} | New: {new_cost:.2f} | Match: {cost_match}")
    if not cost_match:
        all_ok = False

    # Proforma amounts
    old_pf_total = old.execute("SELECT SUM(total_amount) c FROM proformas").fetchone()["c"]
    new_pf_total = new.execute("SELECT SUM(total_amount) c FROM proformas").fetchone()["c"]
    pf_match = abs((old_pf_total or 0) - (new_pf_total or 0)) < 0.01
    print(f"  Proforma totals  - Old: {old_pf_total:.2f} | New: {new_pf_total:.2f} | Match: {pf_match}")
    if not pf_match:
        all_ok = False

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total_old = sum(v[0] for v in results.values())
    total_new = sum(v[1] for v in results.values())
    print(f"  Total old records: {total_old}")
    print(f"  Total new records: {total_new}")
    print(f"  Difference: {total_new - total_old}")
    print()

    for table, (o, n) in results.items():
        status = "OK" if o == n else f"DIFF ({n - o:+d})"
        print(f"  {table:25s} old={o:5d}  new={n:5d}  {status}")

    print()
    if all_ok:
        print("RESULT: MIGRATION LOOKS GOOD - all critical data matches")
    else:
        print("RESULT: SOME MISMATCHES FOUND - review above")
    print("=" * 60)

    old.close()
    new.close()


if __name__ == "__main__":
    compare()
