"""
Create new tables for dashboard features:
- supplier_budgets, supplier_product_budgets
- projects, project_tasks
- maintenance_budgets, maintenance_expenses
- todos
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "catering_ai.db")

TABLES = [
    """
    CREATE TABLE IF NOT EXISTS supplier_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
        site_id INTEGER NOT NULL REFERENCES sites(id),
        year INTEGER NOT NULL,
        yearly_amount REAL NOT NULL DEFAULT 0,
        jan REAL DEFAULT 0,
        feb REAL DEFAULT 0,
        mar REAL DEFAULT 0,
        apr REAL DEFAULT 0,
        may REAL DEFAULT 0,
        jun REAL DEFAULT 0,
        jul REAL DEFAULT 0,
        aug REAL DEFAULT 0,
        sep REAL DEFAULT 0,
        oct REAL DEFAULT 0,
        nov REAL DEFAULT 0,
        dec REAL DEFAULT 0,
        notes TEXT,
        is_active INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS supplier_product_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_budget_id INTEGER NOT NULL REFERENCES supplier_budgets(id),
        product_category TEXT NOT NULL,
        monthly_quantity_limit REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        monthly_amount_limit REAL,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        site_id INTEGER REFERENCES sites(id),
        status TEXT NOT NULL DEFAULT 'planning',
        priority TEXT NOT NULL DEFAULT 'medium',
        start_date DATE,
        target_end_date DATE,
        actual_end_date DATE,
        created_by INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL REFERENCES projects(id),
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        "order" INTEGER NOT NULL DEFAULT 0,
        assigned_to TEXT,
        due_date DATE,
        completed_at TIMESTAMP,
        linked_entity_type TEXT,
        linked_entity_id INTEGER,
        linked_entity_label TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS maintenance_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL REFERENCES sites(id),
        year INTEGER NOT NULL,
        quarter INTEGER NOT NULL,
        budget_amount REAL NOT NULL DEFAULT 0,
        notes TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS maintenance_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL REFERENCES sites(id),
        maintenance_budget_id INTEGER REFERENCES maintenance_budgets(id),
        date DATE NOT NULL,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        vendor TEXT,
        receipt_reference TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        title TEXT NOT NULL,
        description TEXT,
        assigned_to TEXT,
        priority TEXT NOT NULL DEFAULT 'medium',
        status TEXT NOT NULL DEFAULT 'pending',
        due_date DATE,
        completed_at TIMESTAMP,
        linked_entity_type TEXT,
        linked_entity_id INTEGER,
        linked_entity_label TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for sql in TABLES:
        table_name = sql.strip().split("IF NOT EXISTS")[1].strip().split()[0]
        cursor.execute(sql)
        print(f"Created table: {table_name}")

    conn.commit()

    # Verify tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\nAll tables ({len(tables)}): {', '.join(tables)}")

    conn.close()


if __name__ == "__main__":
    main()
