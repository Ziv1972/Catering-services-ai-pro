"""
Input validation utilities
"""
from datetime import datetime
from typing import Optional


def validate_meeting_date(scheduled_at: datetime) -> datetime:
    """Validate that a meeting date is in the future"""
    if scheduled_at < datetime.now(scheduled_at.tzinfo):
        raise ValueError("Meeting date must be in the future")
    return scheduled_at


def validate_budget_amount(amount: float) -> float:
    """Validate budget amount is positive"""
    if amount < 0:
        raise ValueError("Budget amount must be positive")
    return amount


def validate_site_code(code: str) -> str:
    """Validate site code format"""
    valid_codes = {"NZ", "KG"}
    if code.upper() not in valid_codes:
        raise ValueError(f"Invalid site code. Must be one of: {valid_codes}")
    return code.upper()
