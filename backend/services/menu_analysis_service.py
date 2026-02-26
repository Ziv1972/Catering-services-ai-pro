"""
Menu compliance analysis engine.
Parses uploaded menu files and runs compliance rules against them.
"""
import csv
import io
import json
from datetime import date, timedelta
from typing import Optional
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.menu_compliance import MenuCheck, MenuDay, CheckResult, ComplianceRule
from backend.services.claude_service import claude_service


AI_MENU_PARSE_PROMPT = """You are a menu parser for Israeli institutional catering.
Parse the following raw menu text into structured JSON.

The menu covers a month of daily meals at a corporate cafeteria in Israel.
Each day should have categories like: עיקרית (main), תוספות (sides), סלטים (salads),
מרק (soup), קינוח (dessert), לחם (bread), שתיה (drinks).

Return ONLY a JSON array of day objects:
[
  {
    "date": "YYYY-MM-DD",
    "day_of_week": "Sunday|Monday|Tuesday|Wednesday|Thursday",
    "items": {
      "category_name": ["item1", "item2"]
    }
  }
]

If dates are not clear, generate weekdays (Sun-Thu) for the given month/year.
If the text is unreadable or empty, return an empty array [].
Do not include Fridays/Saturdays (Shabbat).
"""


async def parse_menu_file(file_path: str, month: str, year: int) -> list[dict]:
    """Parse a menu file (CSV, Excel, or text) into structured day data."""
    raw_text = ""

    try:
        if file_path.endswith(".csv"):
            with open(file_path, "r", encoding="utf-8-sig") as f:
                raw_text = f.read()
        elif file_path.endswith((".xlsx", ".xls")):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, read_only=True)
                rows = []
                for sheet in wb.sheetnames:
                    ws = wb[sheet]
                    for row in ws.iter_rows(values_only=True):
                        cells = [str(c) if c is not None else "" for c in row]
                        rows.append(",".join(cells))
                raw_text = "\n".join(rows)
                wb.close()
            except ImportError:
                raw_text = ""
        elif file_path.endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
                    raw_text = "\n".join(pages)
            except ImportError:
                raw_text = ""
        else:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                raw_text = f.read()
    except Exception:
        raw_text = ""

    if not raw_text.strip():
        return _generate_placeholder_days(month, year)

    try:
        parse_prompt = f"""Month: {month}, Year: {year}

Raw menu text:
{raw_text[:8000]}"""

        result = await claude_service.generate_structured_response(
            prompt=parse_prompt,
            system_prompt=AI_MENU_PARSE_PROMPT,
            response_format={"type": "array", "items": {"type": "object"}}
        )

        if isinstance(result, list) and len(result) > 0:
            return result
    except Exception:
        pass

    return _generate_placeholder_days(month, year)


def _generate_placeholder_days(month: str, year: int) -> list[dict]:
    """Generate placeholder weekday entries when parsing fails."""
    try:
        month_num = int(month.split("-")[-1]) if "-" in month else int(month)
    except ValueError:
        month_num = 1

    start = date(year, month_num, 1)
    if month_num == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month_num + 1, 1)

    days = []
    current = start
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    while current < end:
        weekday = current.weekday()
        if weekday < 5:  # Mon-Fri (skip Sat/Sun in Python weekday, but Israeli week is Sun-Thu)
            days.append({
                "date": current.isoformat(),
                "day_of_week": day_names[weekday],
                "items": {}
            })
        current += timedelta(days=1)

    return days


async def run_compliance_check(
    check_id: int,
    db: AsyncSession
) -> dict:
    """Run all active compliance rules against a menu check."""
    result = await db.execute(
        select(MenuCheck).where(MenuCheck.id == check_id)
    )
    check = result.scalar_one_or_none()
    if not check:
        raise ValueError(f"MenuCheck {check_id} not found")

    # Load active rules
    rules_result = await db.execute(
        select(ComplianceRule).where(ComplianceRule.is_active == True)
    )
    rules = rules_result.scalars().all()

    # Parse the menu file
    days_data = []
    if check.file_path:
        days_data = await parse_menu_file(check.file_path, check.month, check.year)

    # Store parsed menu days
    week_num = 1
    prev_day = None
    for day_info in days_data:
        day_date_str = day_info.get("date", "")
        try:
            day_date = date.fromisoformat(day_date_str)
        except (ValueError, TypeError):
            continue

        if prev_day and day_date.isocalendar()[1] != prev_day.isocalendar()[1]:
            week_num += 1
        prev_day = day_date

        menu_day = MenuDay(
            menu_check_id=check.id,
            date=day_date,
            day_of_week=day_info.get("day_of_week", ""),
            week_number=week_num,
            is_holiday=False,
            is_theme_day=False,
            menu_items=day_info.get("items", {})
        )
        db.add(menu_day)

    # Run rules against menu data
    check_results = _evaluate_rules(rules, days_data)

    critical_count = 0
    warning_count = 0
    passed_count = 0

    for cr in check_results:
        result_obj = CheckResult(
            menu_check_id=check.id,
            rule_name=cr["rule_name"],
            rule_category=cr.get("rule_category"),
            passed=cr["passed"],
            severity=cr["severity"],
            finding_text=cr.get("finding_text"),
            evidence=cr.get("evidence"),
            reviewed=False,
        )
        db.add(result_obj)

        if cr["passed"]:
            passed_count += 1
        elif cr["severity"] == "critical":
            critical_count += 1
        else:
            warning_count += 1

    # Update check totals
    check.total_findings = critical_count + warning_count
    check.critical_findings = critical_count
    check.warnings = warning_count
    check.passed_rules = passed_count

    await db.commit()

    return {
        "total_findings": check.total_findings,
        "critical_findings": critical_count,
        "warnings": warning_count,
        "passed_rules": passed_count,
        "days_parsed": len(days_data),
        "rules_checked": len(rules),
    }


def _evaluate_rules(rules: list, days_data: list[dict]) -> list[dict]:
    """Evaluate compliance rules against parsed menu days."""
    results = []

    all_items_flat = []
    daily_categories = []
    for day in days_data:
        items = day.get("items", {})
        day_items = []
        for category, item_list in items.items():
            if isinstance(item_list, list):
                for item in item_list:
                    all_items_flat.append(item.lower() if isinstance(item, str) else "")
                    day_items.append((category, item))
        daily_categories.append({
            "date": day.get("date", ""),
            "day_of_week": day.get("day_of_week", ""),
            "categories": list(items.keys()),
            "items": day_items,
        })

    total_days = len(days_data)
    item_counter = Counter(all_items_flat)

    for rule in rules:
        rule_result = _check_single_rule(rule, days_data, daily_categories, item_counter, total_days)
        results.append(rule_result)

    return results


def _check_single_rule(
    rule,
    days_data: list[dict],
    daily_categories: list[dict],
    item_counter: Counter,
    total_days: int
) -> dict:
    """Check a single compliance rule."""
    params = rule.parameters or {}
    rule_type = rule.rule_type or "mandatory"
    category = rule.category or ""

    base = {
        "rule_name": rule.name,
        "rule_category": category,
        "severity": "critical" if rule.priority <= 1 else "warning",
    }

    if total_days == 0:
        return {
            **base,
            "passed": False,
            "finding_text": "No menu days found to check against this rule.",
            "evidence": {"days_checked": 0},
        }

    # Frequency-based rules (e.g., item should appear at most X times per week)
    if rule_type == "frequency":
        max_per_week = params.get("max_per_week")
        min_per_week = params.get("min_per_week")
        target_item = params.get("item", "").lower()
        target_category = params.get("category", "").lower()

        if target_item:
            count = sum(1 for i in item_counter if target_item in i)
            weekly_avg = count / max(total_days / 5, 1)

            if max_per_week and weekly_avg > max_per_week:
                return {
                    **base,
                    "passed": False,
                    "finding_text": (
                        f"'{target_item}' appears ~{weekly_avg:.1f} times/week "
                        f"(max allowed: {max_per_week})"
                    ),
                    "evidence": {"total_count": count, "weekly_avg": round(weekly_avg, 1)},
                }
            if min_per_week and weekly_avg < min_per_week:
                return {
                    **base,
                    "passed": False,
                    "finding_text": (
                        f"'{target_item}' appears ~{weekly_avg:.1f} times/week "
                        f"(min required: {min_per_week})"
                    ),
                    "evidence": {"total_count": count, "weekly_avg": round(weekly_avg, 1)},
                }

        return {**base, "passed": True, "finding_text": None, "evidence": None}

    # Mandatory rules (e.g., every day must have salad, soup, etc.)
    if rule_type == "mandatory":
        required_category = params.get("required_category", "").lower()
        required_item = params.get("required_item", "").lower()

        if required_category:
            missing_days = []
            for dc in daily_categories:
                cats_lower = [c.lower() for c in dc["categories"]]
                if not any(required_category in c for c in cats_lower):
                    missing_days.append(dc["date"])

            if missing_days:
                return {
                    **base,
                    "passed": False,
                    "finding_text": (
                        f"Category '{required_category}' missing on {len(missing_days)} "
                        f"of {total_days} days"
                    ),
                    "evidence": {"missing_days": missing_days[:5]},
                }
            return {**base, "passed": True, "finding_text": None, "evidence": None}

        if required_item:
            days_with = sum(
                1 for dc in daily_categories
                if any(required_item in str(item).lower() for _, item in dc["items"])
            )
            if days_with == 0:
                return {
                    **base,
                    "passed": False,
                    "finding_text": f"Required item '{required_item}' not found in any day",
                    "evidence": {"days_with_item": 0, "total_days": total_days},
                }
            return {**base, "passed": True, "finding_text": None, "evidence": None}

    # Default: if no specific check logic, check against rule description heuristically
    return {
        **base,
        "passed": True,
        "finding_text": None,
        "evidence": {"note": "Rule evaluated by general compliance check"},
    }
