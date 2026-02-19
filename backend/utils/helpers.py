"""
General helper utilities
"""
from datetime import datetime, timedelta
from typing import Any, Dict


def format_currency(amount: float) -> str:
    """Format amount as Israeli Shekel"""
    return f"\u20aa{amount:,.2f}"


def get_date_range(period: str = "week") -> tuple[datetime, datetime]:
    """Get start and end dates for a period"""
    now = datetime.now()
    if period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    elif period == "quarter":
        start = now - timedelta(days=90)
    else:
        start = now - timedelta(days=7)
    return start, now


def safe_json_parse(text: str, default: Any = None) -> Any:
    """Safely parse JSON string"""
    import json
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default
