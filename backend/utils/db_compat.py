"""
Database compatibility helpers for SQLite and PostgreSQL.
"""
from sqlalchemy import func, extract, cast, String
from backend.database import is_sqlite


def extract_year(column):
    """Extract year from a date column (works with both SQLite and PostgreSQL)."""
    if is_sqlite:
        return func.strftime("%Y", column)
    return cast(extract("year", column), String)


def extract_month(column):
    """Extract zero-padded month from a date column."""
    if is_sqlite:
        return func.strftime("%m", column)
    return func.lpad(cast(extract("month", column), String), 2, "0")


def extract_year_month(column):
    """Extract YYYY-MM from a date column."""
    if is_sqlite:
        return func.strftime("%Y-%m", column)
    return func.to_char(column, "YYYY-MM")


def year_equals(column, year: int):
    """Filter: date column's year equals given year."""
    if is_sqlite:
        return func.strftime("%Y", column) == str(year)
    return extract("year", column) == year


def month_equals(column, month: int):
    """Filter: date column's month equals given month."""
    if is_sqlite:
        return func.strftime("%m", column) == f"{month:02d}"
    return extract("month", column) == month


def month_between(column, start_month: int, end_month: int):
    """Filter: date column's month is between start and end (inclusive)."""
    if is_sqlite:
        month_expr = cast(func.strftime("%m", column), type_=None)
        return month_expr.between(str(start_month).zfill(2), str(end_month).zfill(2))
    month_expr = extract("month", column)
    return month_expr.between(start_month, end_month)
