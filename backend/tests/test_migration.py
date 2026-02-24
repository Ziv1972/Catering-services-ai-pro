"""
Migration tests - verify data integrity between source and target databases.
Uses the existing databases on disk (created by create_test_old_db.py + migrate_from_old_system.py).
"""
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SOURCE_DB = PROJECT_ROOT / "scripts" / "foodhouse_test.db"
TARGET_DB = PROJECT_ROOT / "catering_ai.db"


@pytest.fixture(scope="module")
def src():
    conn = sqlite3.connect(str(SOURCE_DB))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def tgt():
    conn = sqlite3.connect(str(TARGET_DB))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def count(conn, table, where=None):
    q = f"SELECT COUNT(*) c FROM {table}"
    if where:
        q += f" WHERE {where}"
    return conn.execute(q).fetchone()["c"]


def total(conn, table, col):
    return conn.execute(f"SELECT SUM({col}) c FROM {table}").fetchone()["c"]


# ===================== ROW COUNT TESTS =====================


class TestRowCounts:

    def test_sites(self, src, tgt):
        assert count(tgt, "sites") == count(src, "sites", "active=1")

    def test_suppliers(self, src, tgt):
        assert count(tgt, "suppliers") == count(src, "suppliers", "active=1")

    def test_products(self, src, tgt):
        assert count(tgt, "products") == count(src, "products", "active=1")

    def test_price_lists(self, src, tgt):
        assert count(tgt, "price_lists") == count(src, "price_lists")

    def test_price_list_items(self, src, tgt):
        assert count(tgt, "price_list_items") == count(src, "price_list_items")

    def test_historical_meals(self, src, tgt):
        assert count(tgt, "historical_meal_data") == count(src, "meals_data")

    def test_menu_checks(self, src, tgt):
        assert count(tgt, "menu_checks") == count(src, "menu_checks")

    def test_check_results(self, src, tgt):
        assert count(tgt, "check_results") == count(src, "check_results")

    def test_proformas(self, src, tgt):
        assert count(tgt, "proformas") == count(src, "proformas")

    def test_proforma_items(self, src, tgt):
        assert count(tgt, "proforma_items") == count(src, "proforma_items")

    def test_quantity_limits(self, src, tgt):
        assert count(tgt, "quantity_limits") == count(src, "quantity_limits", "active=1")

    def test_anomalies(self, src, tgt):
        assert count(tgt, "anomalies") == count(src, "anomalies")

    def test_total_zero_difference(self, src, tgt):
        old = (
            count(src, "sites", "active=1") + count(src, "suppliers", "active=1") +
            count(src, "products", "active=1") + count(src, "price_lists") +
            count(src, "price_list_items") + count(src, "meals_data") +
            count(src, "menu_checks") + count(src, "check_results") +
            count(src, "proformas") + count(src, "proforma_items") +
            count(src, "quantity_limits", "active=1") + count(src, "anomalies")
        )
        new = (
            count(tgt, "sites") + count(tgt, "suppliers") + count(tgt, "products") +
            count(tgt, "price_lists") + count(tgt, "price_list_items") +
            count(tgt, "historical_meal_data") + count(tgt, "menu_checks") +
            count(tgt, "check_results") + count(tgt, "proformas") +
            count(tgt, "proforma_items") + count(tgt, "quantity_limits") +
            count(tgt, "anomalies")
        )
        assert new == old


# ===================== DATA INTEGRITY TESTS =====================


class TestDataIntegrity:

    def test_meal_cost_totals(self, src, tgt):
        assert abs(total(src, "meals_data", "cost") - total(tgt, "historical_meal_data", "cost")) < 0.01

    def test_meal_count_totals(self, src, tgt):
        assert total(src, "meals_data", "meal_count") == total(tgt, "historical_meal_data", "meal_count")

    def test_proforma_amount_totals(self, src, tgt):
        assert abs(total(src, "proformas", "total_amount") - total(tgt, "proformas", "total_amount")) < 0.01

    def test_proforma_item_totals(self, src, tgt):
        assert abs(total(src, "proforma_items", "total_price") - total(tgt, "proforma_items", "total_price")) < 0.01

    def test_product_names_preserved(self, src, tgt):
        old = {r["name"] for r in src.execute("SELECT name FROM products WHERE active=1")}
        new = {r["name"] for r in tgt.execute("SELECT name FROM products")}
        assert old == new

    def test_supplier_names_preserved(self, src, tgt):
        old = {r["name"] for r in src.execute("SELECT name FROM suppliers WHERE active=1")}
        new = {r["name"] for r in tgt.execute("SELECT name FROM suppliers")}
        assert old == new

    def test_site_codes(self, tgt):
        sites = {r["name"]: r["code"] for r in tgt.execute("SELECT name, code FROM sites")}
        assert sites["Nes Ziona"] == "NZ"
        assert sites["Kiryat Gat"] == "KG"

    def test_site_budgets(self, src, tgt):
        old = {r["name"]: r["budget"] for r in src.execute("SELECT name, budget FROM sites WHERE active=1")}
        new = {r["name"]: r["monthly_budget"] for r in tgt.execute("SELECT name, monthly_budget FROM sites")}
        for name in old:
            assert abs(old[name] - new[name]) < 0.01

    def test_anomaly_severities(self, src, tgt):
        old = sorted(r["severity"] for r in src.execute("SELECT severity FROM anomalies ORDER BY id"))
        new = sorted(r["severity"] for r in tgt.execute("SELECT severity FROM anomalies ORDER BY id"))
        assert old == new

    def test_admin_user_exists(self, tgt):
        user = tgt.execute("SELECT * FROM users WHERE email='ziv@hp.com'").fetchone()
        assert user is not None
        assert user["is_admin"] == 1


# ===================== FOREIGN KEY TESTS =====================


class TestForeignKeys:

    def _orphan_count(self, tgt, child_table, child_fk, parent_table):
        return tgt.execute(
            f"SELECT COUNT(*) c FROM {child_table} c "
            f"LEFT JOIN {parent_table} p ON c.{child_fk} = p.id "
            f"WHERE p.id IS NULL"
        ).fetchone()["c"]

    def test_meals_have_valid_sites(self, tgt):
        assert self._orphan_count(tgt, "historical_meal_data", "site_id", "sites") == 0

    def test_menu_checks_have_valid_sites(self, tgt):
        assert self._orphan_count(tgt, "menu_checks", "site_id", "sites") == 0

    def test_check_results_have_valid_checks(self, tgt):
        assert self._orphan_count(tgt, "check_results", "menu_check_id", "menu_checks") == 0

    def test_proformas_have_valid_suppliers(self, tgt):
        assert self._orphan_count(tgt, "proformas", "supplier_id", "suppliers") == 0

    def test_proforma_items_have_valid_proformas(self, tgt):
        assert self._orphan_count(tgt, "proforma_items", "proforma_id", "proformas") == 0

    def test_price_lists_have_valid_suppliers(self, tgt):
        assert self._orphan_count(tgt, "price_lists", "supplier_id", "suppliers") == 0


# ===================== SCHEMA TESTS =====================


class TestSchema:

    def test_all_expected_tables_exist(self, tgt):
        tables = {r[0] for r in tgt.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        expected = {
            "users", "sites", "suppliers", "products", "meetings",
            "price_lists", "price_list_items", "historical_meal_data",
            "menu_checks", "check_results", "proformas", "proforma_items",
            "quantity_limits", "anomalies", "complaints", "complaint_patterns",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_meetings_table_has_outlook_field(self, tgt):
        cols = {r[1] for r in tgt.execute("PRAGMA table_info(meetings)").fetchall()}
        assert "outlook_event_id" in cols
