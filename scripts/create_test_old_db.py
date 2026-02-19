"""
Create a mock FoodHouse Analytics SQLite database for testing migration.
Includes ALL tables: sites, suppliers, products, price lists, meals,
menu checks, check results, proformas, quantity limits, anomalies.
"""
import sqlite3
import json
import random
from datetime import date, timedelta

DB_PATH = "scripts/foodhouse_test.db"


def create_test_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Sites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            budget REAL,
            active INTEGER DEFAULT 1
        )
    """)
    cursor.executemany("INSERT INTO sites (name, budget, active) VALUES (?, ?, ?)", [
        ("Nes Ziona", 60000, 1),
        ("Kiryat Gat", 60000, 1),
    ])

    # Categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    """)
    categories = ["Meat", "Dairy", "Vegetables", "Beverages", "Bread", "Desserts"]
    cursor.executemany("INSERT INTO categories (name) VALUES (?)", [(c,) for c in categories])

    # Suppliers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            contract_start TEXT,
            contract_end TEXT,
            payment_terms TEXT,
            notes TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    cursor.executemany(
        "INSERT INTO suppliers (name, contact_name, email, phone, contract_start, contract_end, payment_terms, notes, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("Fresh Foods Ltd", "David Levi", "david@freshfoods.co.il", "050-1234567",
             "2025-01-01", "2025-12-31", "Net 30", "Primary meat supplier", 1),
            ("Green Valley Produce", "Sarah Cohen", "sarah@greenvalley.co.il", "052-7654321",
             "2025-03-01", "2026-02-28", "Net 15", "Organic vegetables", 1),
            ("Bakery Plus", "Moshe Katz", "moshe@bakeryplus.co.il", "054-1112233",
             "2025-06-01", "2026-05-31", "Net 7", "Bread and pastries", 1),
        ]
    )

    # Products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            hebrew_name TEXT,
            unit TEXT,
            category_id INTEGER REFERENCES categories(id),
            active INTEGER DEFAULT 1
        )
    """)
    products = [
        ("Chicken Breast", "kg", 1),
        ("Ground Beef", "kg", 1),
        ("Salmon Fillet", "kg", 1),
        ("Cottage Cheese", "unit", 2),
        ("Tomatoes", "kg", 3),
        ("Cucumbers", "kg", 3),
        ("Lettuce", "unit", 3),
        ("Orange Juice", "L", 4),
        ("Challah Bread", "unit", 5),
        ("Pita", "unit", 5),
        ("Chocolate Cake", "unit", 6),
        ("Fruit Salad", "kg", 6),
    ]
    cursor.executemany(
        "INSERT INTO products (name, unit, category_id, active) VALUES (?, ?, ?, 1)",
        products
    )

    # Price lists table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_lists (
            id INTEGER PRIMARY KEY,
            supplier_id INTEGER REFERENCES suppliers(id),
            effective_date TEXT NOT NULL,
            file_path TEXT
        )
    """)
    cursor.executemany("INSERT INTO price_lists (supplier_id, effective_date, file_path) VALUES (?, ?, ?)", [
        (1, "2025-07-01", "/uploads/fresh_foods_july_2025.xlsx"),
        (2, "2025-07-01", "/uploads/green_valley_july_2025.xlsx"),
        (3, "2025-08-01", "/uploads/bakery_plus_aug_2025.xlsx"),
    ])

    # Price list items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_list_items (
            id INTEGER PRIMARY KEY,
            price_list_id INTEGER REFERENCES price_lists(id),
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            unit TEXT
        )
    """)
    cursor.executemany(
        "INSERT INTO price_list_items (price_list_id, product_name, price, unit) VALUES (?, ?, ?, ?)",
        [
            (1, "Chicken Breast", 32.90, "kg"),
            (1, "Ground Beef", 45.00, "kg"),
            (1, "Salmon Fillet", 79.90, "kg"),
            (2, "Tomatoes", 8.90, "kg"),
            (2, "Cucumbers", 6.50, "kg"),
            (2, "Lettuce", 4.90, "unit"),
            (3, "Challah Bread", 12.00, "unit"),
            (3, "Pita", 2.50, "unit"),
        ]
    )

    # Historical meals data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meals_data (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            site_code TEXT NOT NULL,
            meal_count INTEGER NOT NULL,
            cost REAL,
            notes TEXT
        )
    """)

    start_date = date.today() - timedelta(days=300)
    meals_data = []
    for day_offset in range(300):
        d = start_date + timedelta(days=day_offset)
        if d.weekday() >= 5:
            continue
        for site_code in ["NZ", "KG"]:
            base_count = 450 if site_code == "NZ" else 320
            meal_count = base_count + random.randint(-50, 50)
            cost = meal_count * random.uniform(28, 35)
            notes = None
            if random.random() < 0.05:
                notes = random.choice(["Holiday menu", "Special event", "Low attendance", "VIP visit"])
            meals_data.append((d.isoformat(), site_code, meal_count, round(cost, 2), notes))

    cursor.executemany(
        "INSERT INTO meals_data (date, site_code, meal_count, cost, notes) VALUES (?, ?, ?, ?, ?)",
        meals_data
    )

    # Compliance rules table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_rules (
            id INTEGER PRIMARY KEY,
            rule_name TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            description TEXT,
            category TEXT,
            parameters TEXT,
            priority INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    """)
    cursor.executemany(
        "INSERT INTO compliance_rules (rule_name, rule_type, description, category, parameters, priority, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("Daily Vegan Option", "mandatory", "A vegan main dish must be available every day",
             "Dietary", '{"frequency": "daily"}', 1, 1),
            ("Schnitzel Limit", "frequency", "Schnitzel should not appear more than twice per week",
             "Menu Variety", '{"max_per_week": 2}', 2, 1),
            ("Fresh Salad Bar", "mandatory", "Fresh salad bar must be available at every lunch service",
             "Daily Requirements", '{"frequency": "daily"}', 1, 1),
            ("Fish Day", "mandatory", "Fish must be served at least once per week",
             "Menu Variety", '{"frequency": "weekly", "min_per_week": 1}', 2, 1),
        ]
    )

    # ===== NEW TABLES FOR COMPLETE MIGRATION =====

    # Menu checks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menu_checks (
            id INTEGER PRIMARY KEY,
            site_id INTEGER REFERENCES sites(id),
            file_path TEXT,
            month TEXT NOT NULL,
            year INTEGER NOT NULL,
            total_findings INTEGER DEFAULT 0,
            critical_findings INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            passed_rules INTEGER DEFAULT 0,
            checked_at TEXT NOT NULL
        )
    """)

    menu_checks_data = []
    for site_id in [1, 2]:
        for month_offset in range(12):
            d = date.today().replace(day=1) - timedelta(days=30 * month_offset)
            month_str = d.strftime("%Y-%m")
            total = random.randint(40, 56)
            critical = random.randint(0, 3)
            warns = random.randint(2, 8)
            passed = total - critical - warns
            menu_checks_data.append((
                site_id,
                f"/uploads/menu_{month_str}_site{site_id}.xlsx",
                month_str,
                d.year,
                total, critical, warns, passed,
                d.isoformat()
            ))

    cursor.executemany(
        "INSERT INTO menu_checks (site_id, file_path, month, year, total_findings, critical_findings, warnings, passed_rules, checked_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        menu_checks_data
    )

    # Check results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS check_results (
            id INTEGER PRIMARY KEY,
            menu_check_id INTEGER REFERENCES menu_checks(id),
            rule_name TEXT NOT NULL,
            rule_category TEXT,
            passed INTEGER NOT NULL,
            severity TEXT NOT NULL,
            finding_text TEXT,
            evidence TEXT,
            reviewed INTEGER DEFAULT 0,
            review_status TEXT,
            review_notes TEXT
        )
    """)

    rule_names = [
        "Daily Vegan Option", "Schnitzel Limit", "Fresh Salad Bar", "Fish Day",
        "Protein Variety", "Carb Side Required", "Vegetable Minimum", "Fruit Dessert",
        "Allergen Labeling", "Kosher Certification", "Temperature Control", "Portion Size",
        "Bread Variety", "Soup Availability", "Beverage Selection"
    ]
    check_results_data = []
    for check_idx in range(1, len(menu_checks_data) + 1):
        num_results = random.randint(10, 20)
        for _ in range(num_results):
            rule = random.choice(rule_names)
            passed = random.random() > 0.25
            sev = "info" if passed else random.choice(["critical", "warning"])
            finding = None if passed else f"Rule '{rule}' not met for this period"
            evidence = None if passed else json.dumps({"days_affected": random.randint(1, 5)})
            reviewed = random.random() > 0.4
            review_status = None
            if reviewed and not passed:
                review_status = random.choice(["approved", "parser_error", "supplier_note"])
            check_results_data.append((
                check_idx, rule, "Menu Compliance", int(passed), sev,
                finding, evidence, int(reviewed), review_status, None
            ))

    cursor.executemany(
        "INSERT INTO check_results (menu_check_id, rule_name, rule_category, passed, severity, finding_text, evidence, reviewed, review_status, review_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        check_results_data
    )

    # Proformas table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proformas (
            id INTEGER PRIMARY KEY,
            supplier_id INTEGER REFERENCES suppliers(id),
            site_id INTEGER REFERENCES sites(id),
            proforma_number TEXT,
            invoice_date TEXT NOT NULL,
            delivery_date TEXT,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'ILS',
            status TEXT NOT NULL,
            file_path TEXT,
            notes TEXT
        )
    """)

    proformas_data = []
    proforma_id = 1
    for month_offset in range(12):
        for supplier_id in [1, 2, 3]:
            d = date.today().replace(day=1) - timedelta(days=30 * month_offset)
            inv_date = d + timedelta(days=random.randint(0, 15))
            del_date = inv_date + timedelta(days=random.randint(1, 5))
            amount = round(random.uniform(5000, 25000), 2)
            status = random.choice(["paid", "approved", "validated", "pending"])
            site_id = random.choice([1, 2])
            proformas_data.append((
                supplier_id, site_id,
                f"PF-{inv_date.year}-{proforma_id:04d}",
                inv_date.isoformat(), del_date.isoformat(),
                amount, "ILS", status,
                f"/uploads/proforma_{proforma_id}.pdf", None
            ))
            proforma_id += 1

    cursor.executemany(
        "INSERT INTO proformas (supplier_id, site_id, proforma_number, invoice_date, delivery_date, total_amount, currency, status, file_path, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        proformas_data
    )

    # Proforma items table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proforma_items (
            id INTEGER PRIMARY KEY,
            proforma_id INTEGER REFERENCES proformas(id),
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            price_variance REAL,
            flagged INTEGER DEFAULT 0
        )
    """)

    product_names = [p[0] for p in products]
    proforma_items_data = []
    for pf_idx in range(1, len(proformas_data) + 1):
        num_items = random.randint(3, 8)
        selected = random.sample(product_names, min(num_items, len(product_names)))
        for prod_name in selected:
            qty = round(random.uniform(5, 100), 1)
            unit_price = round(random.uniform(5, 80), 2)
            total = round(qty * unit_price, 2)
            variance = round(random.uniform(-15, 15), 1) if random.random() > 0.7 else None
            flagged = 1 if variance and abs(variance) > 10 else 0
            proforma_items_data.append((
                pf_idx, prod_name, qty, "kg", unit_price, total, variance, flagged
            ))

    cursor.executemany(
        "INSERT INTO proforma_items (proforma_id, product_name, quantity, unit, unit_price, total_price, price_variance, flagged) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        proforma_items_data
    )

    # Quantity limits table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quantity_limits (
            id INTEGER PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            site_id INTEGER REFERENCES sites(id),
            min_quantity REAL,
            max_quantity REAL,
            unit TEXT NOT NULL,
            period TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
    """)

    quantity_limits_data = []
    for prod_idx in range(1, len(products) + 1):
        for site_id in [1, 2, None]:
            if random.random() > 0.4:
                continue
            min_q = round(random.uniform(5, 20), 1)
            max_q = round(min_q * random.uniform(2, 5), 1)
            period = random.choice(["daily", "weekly", "monthly"])
            quantity_limits_data.append((
                prod_idx, site_id, min_q, max_q, "kg", period, 1
            ))

    cursor.executemany(
        "INSERT INTO quantity_limits (product_id, site_id, min_quantity, max_quantity, unit, period, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        quantity_limits_data
    )

    # Anomalies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id INTEGER PRIMARY KEY,
            anomaly_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            detected_at TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL,
            expected_value REAL,
            actual_value REAL,
            variance_percent REAL,
            acknowledged INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0,
            resolution_notes TEXT
        )
    """)

    anomaly_types = ["price_spike", "usage_spike", "quality_drop", "delivery_delay", "budget_overrun"]
    anomalies_data = []
    for _ in range(25):
        d = date.today() - timedelta(days=random.randint(1, 80))
        a_type = random.choice(anomaly_types)
        entity_type = random.choice(["product", "supplier", "site"])
        entity_id = random.randint(1, 3)
        expected = round(random.uniform(100, 1000), 2)
        actual = round(expected * random.uniform(1.1, 1.8), 2)
        variance = round(((actual - expected) / expected) * 100, 1)
        severity = "high" if variance > 40 else ("medium" if variance > 20 else "low")
        desc = f"{a_type.replace('_', ' ').title()}: {entity_type} #{entity_id} - {variance}% deviation"
        ack = random.random() > 0.3
        resolved = ack and random.random() > 0.4
        notes = "Investigated and resolved" if resolved else None
        anomalies_data.append((
            a_type, entity_type, entity_id, d.isoformat(),
            desc, severity, expected, actual, variance,
            int(ack), int(resolved), notes
        ))

    cursor.executemany(
        "INSERT INTO anomalies (anomaly_type, entity_type, entity_id, detected_at, description, severity, expected_value, actual_value, variance_percent, acknowledged, resolved, resolution_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        anomalies_data
    )

    conn.commit()
    conn.close()

    print(f"Test FoodHouse Analytics database created: {DB_PATH}")
    print(f"  Sites: 2")
    print(f"  Suppliers: 3")
    print(f"  Products: {len(products)}")
    print(f"  Price lists: 3 (with 8 items)")
    print(f"  Historical records: {len(meals_data)}")
    print(f"  Compliance rules: 4")
    print(f"  Menu checks: {len(menu_checks_data)}")
    print(f"  Check results: {len(check_results_data)}")
    print(f"  Proformas: {len(proformas_data)}")
    print(f"  Proforma items: {len(proforma_items_data)}")
    print(f"  Quantity limits: {len(quantity_limits_data)}")
    print(f"  Anomalies: {len(anomalies_data)}")


if __name__ == "__main__":
    create_test_db()
