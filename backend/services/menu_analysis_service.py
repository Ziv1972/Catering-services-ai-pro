"""
Menu compliance analysis engine.
Parses uploaded menu files and runs compliance rules against them.
Handles Hebrew rule types: item_frequency_weekly, item_frequency_monthly,
count_min, count_max, item_present, no_repeat_weekly, no_repeat_daily,
no_consecutive, frequency, mandatory.
"""
import re
import csv
import io
import json
import logging
from datetime import date, timedelta
from typing import Optional
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models.menu_compliance import MenuCheck, MenuDay, CheckResult, ComplianceRule
from backend.models.dish_catalog import DishCatalog
from backend.services.claude_service import claude_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Month name → number mapping (English + Hebrew)
# ---------------------------------------------------------------------------
MONTH_NAME_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
    # Hebrew month names
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "אפריל": 4,
    "מאי": 5, "יוני": 6, "יולי": 7, "אוגוסט": 8,
    "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}

# Hebrew plural → singular stems for category matching
HEBREW_PLURAL_MAP = {
    "סלטים": "סלט",
    "מרקים": "מרק",
    "ירקות": "ירק",
    "קינוחים": "קינוח",
    "תוספות": "תוספת",
    "פירות": "פרי",
    "עוגות": "עוגה",
    "לחמים": "לחם",
    "מנות": "מנה",
    "שתיות": "שתיה",
    "דגים": "דג",
    "עופות": "עוף",
    "בשרים": "בשר",
    "קטניות": "קטנית",
    "פחמימות": "פחמימה",
}


def _parse_month_number(month: str) -> int:
    """Convert month string (name or number, possibly with prefix) to int.

    Examples:
        "3" → 3, "03" → 3, "March" → 3, "march" → 3,
        "2025-03" → 3, "מרץ" → 3
    """
    if not month:
        return 1

    # Try "YYYY-MM" format
    if "-" in month:
        part = month.split("-")[-1].strip()
        try:
            return int(part)
        except ValueError:
            pass

    # Try direct int
    try:
        return int(month)
    except ValueError:
        pass

    # Try month name lookup
    cleaned = month.strip().lower()
    if cleaned in MONTH_NAME_MAP:
        return MONTH_NAME_MAP[cleaned]

    # Try Hebrew (no lowering needed — already in map)
    if month.strip() in MONTH_NAME_MAP:
        return MONTH_NAME_MAP[month.strip()]

    logger.warning(f"Could not parse month '{month}', defaulting to 1")
    return 1


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


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

def _read_file_raw(file_path: str) -> str:
    """Read raw text from a file (CSV, Excel, PDF, or text)."""
    raw_text = ""
    try:
        if file_path.endswith(".csv"):
            for enc in ("utf-8-sig", "cp1255", "latin-1"):
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        raw_text = f.read()
                    if raw_text.strip():
                        break
                except (UnicodeDecodeError, UnicodeError):
                    continue
        elif file_path.endswith((".xlsx", ".xls")):
            raw_text = _read_excel_structured(file_path)
        elif file_path.endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
                    raw_text = "\n".join(pages)
            except ImportError:
                logger.warning("pdfplumber not installed — cannot parse PDF")
        else:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                raw_text = f.read()
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")

    return raw_text


def _read_excel_structured(file_path: str) -> str:
    """Read Excel file preserving column/row structure for AI parsing."""
    try:
        import openpyxl
    except ImportError:
        logger.warning("openpyxl not installed — cannot parse Excel")
        return ""

    try:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        all_text_parts = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if not hasattr(ws, "iter_rows"):
                continue
            all_text_parts.append(f"=== Sheet: {sheet_name} ===")
            for row in ws.iter_rows(values_only=True):
                cells = []
                for c in row:
                    if c is not None:
                        val = str(c).strip()
                        if val:
                            cells.append(val)
                if cells:
                    all_text_parts.append(" | ".join(cells))

        wb.close()
        return "\n".join(all_text_parts)
    except Exception as e:
        logger.error(f"Excel parsing error: {e}")
        return ""


def extract_all_dishes_from_file(file_path: str) -> list[str]:
    """Extract all unique dish-like text values directly from a menu file.
    Returns a flat list of unique Hebrew dish names — no AI needed."""
    dishes: set[str] = set()

    try:
        if file_path.endswith((".xlsx", ".xls")):
            dishes = _extract_dishes_from_excel(file_path)
        elif file_path.endswith(".csv"):
            dishes = _extract_dishes_from_csv(file_path)
        else:
            # Plain text — extract Hebrew words/phrases
            raw = _read_file_raw(file_path)
            for line in raw.split("\n"):
                line = line.strip()
                if _is_dish_name(line):
                    dishes.add(line)
    except Exception as e:
        logger.error(f"Dish extraction error: {e}")

    return sorted(dishes)


def _extract_dishes_from_excel(file_path: str) -> set[str]:
    """Extract dish names from Excel cells directly."""
    import openpyxl

    dishes: set[str] = set()
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        if not hasattr(ws, "iter_rows"):
            continue
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if cell is None:
                    continue
                val = str(cell).strip()
                if _is_dish_name(val):
                    dishes.add(val)

    wb.close()
    return dishes


def _extract_dishes_from_csv(file_path: str) -> set[str]:
    """Extract dish names from CSV cells."""
    dishes: set[str] = set()
    for enc in ("utf-8-sig", "cp1255", "latin-1"):
        try:
            with open(file_path, "r", encoding=enc) as f:
                reader = csv.reader(f)
                for row in reader:
                    for cell in row:
                        val = cell.strip()
                        if _is_dish_name(val):
                            dishes.add(val)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    return dishes


# Hebrew character range check
_HEBREW_RE = re.compile(r'[\u0590-\u05FF]')
# Skip patterns: dates, day names, headers, numbers-only, single chars
_SKIP_PATTERNS = re.compile(
    r'^(?:\d{1,2}[./]\d{1,2}[./]?\d{0,4}|'  # dates
    r'יום\s+[א-ת]|'                           # day names like יום ראשון
    r'None|'
    r'\d+$|'                                    # numbers only
    r'.{0,2}$)'                                 # too short
)
_HEADER_KEYWORDS = {
    "תפריט", "חודש", "שבוע", "תאריך", "הערות", "עמדת שף",
    "sheet", "page", "menu", "date", "week",
}


def _is_dish_name(val: str) -> bool:
    """Heuristic: is this cell value likely a dish name?"""
    if not val or len(val) < 3 or len(val) > 80:
        return False
    if not _HEBREW_RE.search(val):
        return False
    if _SKIP_PATTERNS.match(val):
        return False
    val_lower = val.lower()
    if any(kw in val_lower for kw in _HEADER_KEYWORDS):
        return False
    # Must have at least 2 Hebrew characters
    hebrew_chars = sum(1 for c in val if '\u0590' <= c <= '\u05FF')
    if hebrew_chars < 2:
        return False
    return True


async def parse_menu_file(file_path: str, month: str, year: int) -> list[dict]:
    """Parse a menu file (CSV, Excel, or text) into structured day data."""
    raw_text = _read_file_raw(file_path)

    if not raw_text.strip():
        logger.warning(f"Empty raw text from file: {file_path}")
        return _generate_placeholder_days(month, year)

    logger.info(f"Menu raw text: {len(raw_text)} chars from {file_path}")

    # Send full text to Claude (up to 50K chars — Claude handles large context)
    try:
        parse_prompt = f"""Month: {month}, Year: {year}

Raw menu text:
{raw_text[:50000]}"""

        result = await claude_service.generate_structured_response(
            prompt=parse_prompt,
            system_prompt=AI_MENU_PARSE_PROMPT,
            response_format={"type": "array", "items": {"type": "object"}}
        )

        if isinstance(result, list) and len(result) > 0:
            # Verify the parsed data actually has items
            items_count = sum(
                len(items)
                for day in result
                for items in (day.get("items", {}).values())
                if isinstance(items, list)
            )
            logger.info(f"Claude parsed {len(result)} days with {items_count} total items")
            if items_count > 0:
                return result
            logger.warning("Claude returned days but with 0 items — falling back")
    except Exception as e:
        logger.error(f"Claude menu parsing failed: {e}")

    # Fallback: build days from direct extraction
    logger.info("Using direct extraction fallback")
    return _build_days_from_direct_extraction(file_path, month, year)


def _build_days_from_direct_extraction(
    file_path: str, month: str, year: int
) -> list[dict]:
    """Build day structures by extracting dishes directly from the file.
    Distributes all found dishes across weekdays in the month."""
    all_dishes = extract_all_dishes_from_file(file_path)
    logger.info(f"Direct extraction found {len(all_dishes)} unique dishes")

    if not all_dishes:
        return _generate_placeholder_days(month, year)

    # Generate weekdays for the month
    days = _generate_placeholder_days(month, year)

    # Try to detect column-based day structure from Excel
    if file_path.endswith((".xlsx", ".xls")):
        structured = _extract_days_from_excel_columns(file_path, month, year)
        if structured and any(d.get("items") for d in structured):
            return structured

    # Fallback: put all dishes under "עיקרית" for each day
    # (compliance engine uses substring matching across all items)
    for day in days:
        day["items"] = {"עיקרית": all_dishes}

    return days


def _extract_days_from_excel_columns(
    file_path: str, month: str, year: int
) -> list[dict]:
    """Try to extract day-structured data from Excel where columns = days."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        if not hasattr(ws, "iter_rows"):
            wb.close()
            return []

        all_rows = []
        for row in ws.iter_rows(values_only=True):
            all_rows.append([str(c).strip() if c is not None else "" for c in row])
        wb.close()

        if not all_rows:
            return []

        # Detect header row with day names or dates
        day_col_indices: list[int] = []
        day_labels: list[str] = []
        hebrew_days = {"ראשון", "שני", "שלישי", "רביעי", "חמישי"}

        for row_idx, row in enumerate(all_rows[:5]):
            for col_idx, cell in enumerate(row):
                if any(d in cell for d in hebrew_days) or re.match(r'\d{1,2}[./]\d{1,2}', cell):
                    day_col_indices.append(col_idx)
                    day_labels.append(cell)
            if day_col_indices:
                break

        if not day_col_indices:
            return []

        # Extract dishes per column (day)
        days_data = []
        month_num = _parse_month_number(month)

        for i, col_idx in enumerate(day_col_indices):
            items: list[str] = []
            for row in all_rows:
                if col_idx < len(row):
                    val = row[col_idx].strip()
                    if _is_dish_name(val):
                        items.append(val)

            if items:
                # Try to determine date from label
                day_date = None
                label = day_labels[i] if i < len(day_labels) else ""
                date_match = re.search(r'(\d{1,2})[./](\d{1,2})', label)
                if date_match:
                    try:
                        d = int(date_match.group(1))
                        m = int(date_match.group(2))
                        day_date = date(year, m, d)
                    except (ValueError, TypeError):
                        pass

                if not day_date:
                    day_date = date(year, month_num, min(i + 1, 28))

                days_data.append({
                    "date": day_date.isoformat(),
                    "day_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][day_date.weekday()],
                    "items": {"עיקרית": items}
                })

        return days_data

    except Exception as e:
        logger.error(f"Excel column extraction error: {e}")
        return []


def _generate_placeholder_days(month: str, year: int) -> list[dict]:
    """Generate placeholder weekday entries when parsing fails."""
    try:
        month_num = _parse_month_number(month)
    except (ValueError, TypeError):
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
        if weekday < 5:
            days.append({
                "date": current.isoformat(),
                "day_of_week": day_names[weekday],
                "items": {}
            })
        current += timedelta(days=1)

    return days


# ---------------------------------------------------------------------------
# Hebrew rule name parsing
# ---------------------------------------------------------------------------

def _extract_item_and_freq(name: str) -> tuple:
    """Extract (item_keyword, frequency, is_max) from a Hebrew rule name.

    Examples:
        "אסאדו 3 פעמים בחודש"      → ("אסאדו", 3.0, False)
        "המבורגר פעם בשבוע"         → ("המבורגר", 1.0, False)
        "נקניקיות מקסימום פעם בשבוע" → ("נקניקיות", 1.0, True)
        "חזה עוף בגריל 5 פעמים בשבוע" → ("חזה עוף בגריל", 5.0, False)
        "כנאפה אסאדו"              → ("כנאפה", 1.0, False)  # split compound
    """
    is_max = "מקסימום" in name
    clean = name.replace("מקסימום", "").strip()

    # Pattern: "ITEM X.Y פעמ..."
    match = re.match(r'^(.+?)\s+(\d+(?:\.\d+)?)\s+פעמ', clean)
    if match:
        return _clean_keyword(match.group(1).strip()), float(match.group(2)), is_max

    # Pattern: "ITEM פעם ב..."
    match = re.match(r'^(.+?)\s+פעם\s+ב', clean)
    if match:
        return _clean_keyword(match.group(1).strip()), 1.0, is_max

    # No frequency pattern — extract meaningful keyword from compound name
    keyword = _extract_short_keyword(clean)
    return keyword, 1.0, is_max


def _clean_keyword(keyword: str) -> str:
    """Clean up extracted keyword — strip trailing noise words."""
    # Strip trailing "ביום" / "בשבוע" / "בחודש"
    keyword = re.sub(r'\s+(ביום|בשבוע|בחודש|בחודשי|בשבועי)$', '', keyword)
    # Strip trailing "סוגי" (e.g. "11 סוגי סלטים" → already handled by count)
    keyword = re.sub(r'\s+סוגי$', '', keyword)
    return keyword.strip()


def _extract_short_keyword(name: str) -> str:
    """Extract a meaningful short keyword from a compound rule name.

    When there's no frequency pattern, the rule name itself is compound.
    Split on common delimiters and extract the first meaningful Hebrew part.

    Examples:
        "כנאפה אסאדו"               → "כנאפה"  (first word)
        "אין חזרה על מרק"            → "מרק"    (last noun)
        "סלט חומוס יומי"            → "חומוס"   (after prefix strip)
        "לחם שום"                   → "לחם שום" (short enough, keep)
    """
    # Strip "ביום" suffix
    clean = re.sub(r'\s+(ביום|בשבוע|בחודש)$', '', name).strip()

    # Strip common rule prefixes
    prefix_patterns = [
        r'^אין\s+(לחזור|חזרה)\s+(על\s+)?',  # "אין לחזור על..."
        r'^אין\s+אותו\s+',                    # "אין אותו..."
        r'^אין\s+',                            # "אין..."
    ]
    for pattern in prefix_patterns:
        clean = re.sub(pattern, '', clean).strip()

    # If "או" (or) present, split and take first part
    if " או " in clean:
        clean = clean.split(" או ")[0].strip()

    # If "/" present, take first part
    if "/" in clean:
        clean = clean.split("/")[0].strip()

    # If still longer than 3 words, take first 2 meaningful words
    words = clean.split()
    if len(words) > 3:
        clean = " ".join(words[:2])

    return clean.strip() if clean.strip() else name


def _extract_daily_count(name: str) -> tuple:
    """Extract (count, category_keyword) from count_min/count_max names.

    Examples:
        "מינימום 11 סוגי סלטים ביום" → (11, "סלטים")
        "מינימום 2 סוגי מרק ביום"    → (2, "מרק")
        "מקסימום 2 מנות בשר טחון ביום" → (2, "בשר טחון")
    """
    # "מינימום X סוגי CATEGORY ביום"
    match = re.match(r'^מינימום\s+(\d+)\s+סוגי\s+(.+?)(?:\s+ביום)?$', name)
    if match:
        return int(match.group(1)), match.group(2).strip()

    # "מקסימום X מנות ITEM ביום"
    match = re.match(r'^מקסימום\s+(\d+)\s+מנות\s+(.+?)(?:\s+ביום)?$', name)
    if match:
        return int(match.group(1)), match.group(2).strip()

    # "מינימום X CATEGORY"
    match = re.match(r'^מינימום\s+(\d+)\s+(.+)', name)
    if match:
        return int(match.group(1)), match.group(2).strip()

    return 1, name


def _extract_item_present_keyword(name: str) -> str:
    """Extract item keyword from item_present / count_min daily-item rules.

    Examples:
        "סלט חומוס יומי"      → "חומוס"
        "מרק צח/ירקות יומי"   → "מרק צח"
        "גריל יומי"           → "גריל"
        "מנת בקר יומית"       → "בקר"
        "קרוטונים יומיים"     → "קרוטונים"
        "סלט ירקות ביום"      → "ירקות"
    """
    # Strip trailing "ביום", "יומי", "יומית", etc.
    clean = re.sub(r'\s+(יומי|יומית|יומיים|יומיות|ביום)$', '', name).strip()
    # Remove common prefixes like "סלט", "מנת", "מנה"
    for prefix in ["סלט ", "מנת ", "מנה "]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
            break
    # Take first part before "/" if compound
    if "/" in clean:
        clean = clean.split("/")[0].strip()
    return clean


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_comparison(actual: int, expected: int) -> str:
    """Derive comparison label: above, under, or even."""
    if actual > expected:
        return "above"
    if actual < expected:
        return "under"
    return "even"


# Mapping from Hebrew keywords in rules → dish catalog categories
KEYWORD_TO_CATALOG_CATEGORY = {
    "בקר": ["protein_beef"],
    "עוף": ["protein_chicken", "chicken_breast", "schnitzel"],
    "שניצל": ["schnitzel"],
    "חזה עוף": ["chicken_breast"],
    "דג": ["fish"],
    "מרק": ["soup"],
    "סלט": ["salads"],
    "סלטים": ["salads"],
    "קינוח": ["desserts"],
    "קינוחים": ["desserts"],
    "טבעוני": ["vegan"],
    "קטניות": ["legumes"],
    "פחמימ": ["carbs"],
    "תוספ": ["side_dish"],
}


def _count_catalog_matches(
    keyword: str,
    item_counter: Counter,
    catalog_map: dict[str, str],
) -> int:
    """Count items matching keyword via catalog category lookup.

    If keyword maps to known catalog categories, also count items
    whose catalog category matches — even if the keyword doesn't
    appear as a substring in the dish name."""
    # Find matching catalog categories
    matched_categories: list[str] = []
    for kw, cats in KEYWORD_TO_CATALOG_CATEGORY.items():
        if kw in keyword.lower() or keyword.lower() in kw:
            matched_categories.extend(cats)

    if not matched_categories:
        return 0

    # Count items whose catalog entry matches these categories
    extra = 0
    for item_name, count in item_counter.items():
        if item_name in catalog_map:
            if catalog_map[item_name] in matched_categories:
                extra += count

    return extra


def _normalize_hebrew(keyword: str) -> list[str]:
    """Return keyword + its singular/plural variants for matching.

    Examples:
        "סלטים" → ["סלטים", "סלט"]
        "סלט"   → ["סלט", "סלטים"]
        "בשר"   → ["בשר", "בשרים"]
        "מרק"   → ["מרק", "מרקים"]
    """
    variants = [keyword]

    # Check if keyword IS a plural form → add singular
    if keyword in HEBREW_PLURAL_MAP:
        variants.append(HEBREW_PLURAL_MAP[keyword])

    # Check if keyword IS a singular form → add plural
    for plural, singular in HEBREW_PLURAL_MAP.items():
        if keyword == singular and plural not in variants:
            variants.append(plural)

    # Common Hebrew plural suffixes heuristic
    if keyword.endswith("ים") and len(keyword) > 3:
        stem = keyword[:-2]
        if stem not in variants:
            variants.append(stem)
    elif keyword.endswith("ות") and len(keyword) > 3:
        stem = keyword[:-2]
        if stem not in variants:
            variants.append(stem)

    return variants


def _count_item_occurrences(
    item_keyword: str,
    item_counter: Counter,
    catalog_map: dict[str, str] | None = None,
) -> int:
    """Count how many times an item appears using substring match with plural/singular awareness.

    Also checks catalog categories for enhanced matching."""
    variants = _normalize_hebrew(item_keyword.lower())
    matched_items: set[str] = set()
    total = 0

    # 1. Substring match with variants
    for k, v in item_counter.items():
        if any(var in k for var in variants):
            total += v
            matched_items.add(k)

    # 2. Catalog-enhanced matching (only for items not already matched)
    if catalog_map:
        catalog_extra = 0
        for item_name, count in item_counter.items():
            if item_name in matched_items:
                continue  # already counted
            if item_name in catalog_map:
                cat = catalog_map[item_name]
                # Check if rule keyword maps to this catalog category
                for kw, cats in KEYWORD_TO_CATALOG_CATEGORY.items():
                    if (kw in item_keyword.lower() or item_keyword.lower() in kw) and cat in cats:
                        catalog_extra += count
                        break
        total += catalog_extra

    return total


def _matches_any_variant(variants: list[str], text: str) -> bool:
    """Check if any keyword variant appears in the text."""
    text_lower = text.lower()
    return any(var in text_lower for var in variants)


def _count_daily_item_presence(item_keyword: str, daily_categories: list) -> int:
    """Count how many days an item appears on (with plural/singular awareness)."""
    variants = _normalize_hebrew(item_keyword.lower())
    return sum(
        1 for dc in daily_categories
        if any(_matches_any_variant(variants, str(item)) for _, item in dc["items"])
    )


def _find_item_days(item_keyword: str, daily_categories: list) -> list[str]:
    """Return list of dates where the item appears."""
    variants = _normalize_hebrew(item_keyword.lower())
    return [
        dc["date"] for dc in daily_categories
        if any(_matches_any_variant(variants, str(item)) for _, item in dc["items"])
    ]


def _find_missing_days(item_keyword: str, daily_categories: list) -> list[str]:
    """Return list of dates where the item does NOT appear."""
    variants = _normalize_hebrew(item_keyword.lower())
    return [
        dc["date"] for dc in daily_categories
        if not any(_matches_any_variant(variants, str(item)) for _, item in dc["items"])
    ]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

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

    # Parse the menu file (or re-use existing days if file unavailable)
    days_data = []
    if check.file_path:
        try:
            days_data = await parse_menu_file(check.file_path, check.month, check.year)
        except Exception:
            days_data = []

    if days_data:
        # Fresh parse succeeded — delete old days and store new ones
        from sqlalchemy import delete as sql_delete
        await db.execute(
            sql_delete(MenuDay).where(MenuDay.menu_check_id == check.id)
        )

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
    else:
        # File unavailable — re-use existing stored MenuDay data
        existing_days = await db.execute(
            select(MenuDay).where(MenuDay.menu_check_id == check.id)
        )
        stored_days = existing_days.scalars().all()
        for md in stored_days:
            items = md.menu_items or {}
            day_info = {
                "date": md.date.isoformat() if md.date else "",
                "day_of_week": md.day_of_week or "",
                "items": items,
            }
            days_data.append(day_info)

    # Load dish catalog for enhanced matching
    catalog_result = await db.execute(
        select(DishCatalog).where(DishCatalog.category.isnot(None))
    )
    catalog_entries = catalog_result.scalars().all()
    catalog_map = {
        entry.dish_name.lower(): entry.category
        for entry in catalog_entries
        if entry.category
    }
    logger.info(f"Loaded {len(catalog_map)} categorized dishes from catalog")

    # Run rules against menu data (with catalog enhancement)
    check_results = _evaluate_rules(rules, days_data, catalog_map=catalog_map)

    critical_count = 0
    warning_count = 0
    passed_count = 0
    above_count = 0
    under_count = 0
    even_count = 0

    for cr in check_results:
        evidence = cr.get("evidence") or {}
        if cr.get("rule_id"):
            evidence = {**evidence, "rule_id": cr["rule_id"]}
        result_obj = CheckResult(
            menu_check_id=check.id,
            rule_name=cr["rule_name"],
            rule_category=cr.get("rule_category"),
            passed=cr["passed"],
            severity=cr["severity"],
            finding_text=cr.get("finding_text"),
            evidence=evidence,
            reviewed=False,
        )
        db.add(result_obj)

        if cr["passed"]:
            passed_count += 1
        elif cr["severity"] == "critical":
            critical_count += 1
        else:
            warning_count += 1

        evidence = cr.get("evidence") or {}
        comparison = evidence.get("comparison", "even")
        if comparison == "above":
            above_count += 1
        elif comparison == "under":
            under_count += 1
        else:
            even_count += 1

    # Update check totals
    check.total_findings = critical_count + warning_count
    check.critical_findings = critical_count
    check.warnings = warning_count
    check.passed_rules = passed_count
    check.dishes_above = above_count
    check.dishes_under = under_count
    check.dishes_even = even_count

    # Auto-extract all unique dishes to the catalog
    extracted = await _auto_extract_dishes_to_catalog(
        days_data, check.id, check_results, db, file_path=check.file_path
    )

    await db.commit()

    return {
        "total_findings": check.total_findings,
        "critical_findings": critical_count,
        "warnings": warning_count,
        "passed_rules": passed_count,
        "days_parsed": len(days_data),
        "rules_checked": len(rules),
        "dishes_above": above_count,
        "dishes_under": under_count,
        "dishes_even": even_count,
        "dishes_extracted": extracted,
    }


# ---------------------------------------------------------------------------
# Auto-extract dishes to catalog
# ---------------------------------------------------------------------------

async def _auto_extract_dishes_to_catalog(
    days_data: list[dict],
    check_id: int,
    check_results: list[dict],
    db: AsyncSession,
    file_path: str | None = None,
) -> int:
    """Extract all unique dish names and add to catalog.
    Uses direct file extraction first (most reliable), then falls back to parsed days.
    Dishes that passed compliance checks are marked as approved."""
    unique_dishes: set[str] = set()

    # 1. Try direct file extraction first (bypasses AI parsing issues)
    if file_path:
        import os
        if os.path.exists(file_path):
            file_dishes = extract_all_dishes_from_file(file_path)
            unique_dishes.update(file_dishes)
            logger.info(f"Direct file extraction: {len(file_dishes)} dishes from {file_path}")

    # 2. Also collect from parsed days_data (may have additional items from AI parsing)
    for day in days_data:
        items = day.get("items", {})
        for _category, item_list in items.items():
            if isinstance(item_list, list):
                for item in item_list:
                    name = str(item).strip()
                    if name and len(name) >= 3:
                        unique_dishes.add(name)
            elif isinstance(item_list, str):
                name = item_list.strip()
                if name and len(name) >= 3:
                    unique_dishes.add(name)

    if not unique_dishes:
        logger.warning(f"No dishes found for check {check_id}")
        return 0

    logger.info(f"Total unique dishes to catalog: {len(unique_dishes)}")

    # Get existing catalog entries
    existing_result = await db.execute(select(DishCatalog.dish_name))
    existing_names = {row[0] for row in existing_result.all()}

    # Collect items that passed compliance (approved)
    approved_keywords: set[str] = set()
    for cr in check_results:
        if cr.get("passed"):
            evidence = cr.get("evidence") or {}
            item = evidence.get("item_searched") or evidence.get("category_keyword", "")
            if item:
                approved_keywords.add(item.lower())

    new_count = 0
    for dish_name in sorted(unique_dishes):
        if dish_name not in existing_names:
            is_approved = any(
                kw in dish_name.lower() for kw in approved_keywords
            ) if approved_keywords else False

            db.add(DishCatalog(
                dish_name=dish_name,
                approved=is_approved,
                source_check_id=check_id,
            ))
            existing_names.add(dish_name)
            new_count += 1

    return new_count


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------

def _detect_fallback_mode(days_data: list[dict]) -> bool:
    """Detect if all days have identical items (fallback mode).

    When the direct extraction fallback is used, every day gets the same
    set of dishes. In this mode, no_repeat / no_consecutive rules should
    be treated as "not evaluable" rather than penalized."""
    if len(days_data) < 2:
        return False

    # Compare items of first two days
    items_0 = sorted(
        str(item)
        for item_list in days_data[0].get("items", {}).values()
        if isinstance(item_list, list)
        for item in item_list
    )
    items_1 = sorted(
        str(item)
        for item_list in days_data[1].get("items", {}).values()
        if isinstance(item_list, list)
        for item in item_list
    )

    return items_0 == items_1 and len(items_0) > 10


def _evaluate_rules(
    rules: list,
    days_data: list[dict],
    catalog_map: dict[str, str] | None = None,
) -> list[dict]:
    """Evaluate compliance rules against parsed menu days."""
    results = []
    is_fallback = _detect_fallback_mode(days_data)
    if catalog_map is None:
        catalog_map = {}

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
        rule_result = _check_single_rule(
            rule, days_data, daily_categories, item_counter, total_days,
            is_fallback=is_fallback,
            catalog_map=catalog_map,
        )
        results.append(rule_result)

    return results


def _check_single_rule(
    rule,
    days_data: list[dict],
    daily_categories: list[dict],
    item_counter: Counter,
    total_days: int,
    is_fallback: bool = False,
    catalog_map: dict[str, str] | None = None,
) -> dict:
    """Check a single compliance rule — handles all Hebrew rule types."""
    params = rule.parameters or {}
    rule_type = rule.rule_type or "mandatory"
    category = rule.category or ""
    name = rule.name or ""

    rule_id = getattr(rule, "id", None)
    base = {
        "rule_name": name,
        "rule_category": category,
        "severity": "critical" if rule.priority <= 1 else "warning",
        "rule_id": rule_id,
    }

    if total_days == 0:
        return {
            **base,
            "passed": False,
            "finding_text": "No menu days found to check against this rule.",
            "evidence": {
                "days_checked": 0,
                "expected_count": 0,
                "actual_count": 0,
                "comparison": "even",
            },
        }

    weeks_in_month = max(total_days / 5, 1)

    # =================================================================
    # item_frequency_weekly — "אטריות מרק 2 פעמים בשבוע"
    # =================================================================
    if rule_type == "item_frequency_weekly":
        item_keyword, freq, is_max = _extract_item_and_freq(name)
        if params.get("item"):
            item_keyword = params["item"]
        if params.get("min_per_week"):
            freq = params["min_per_week"]
            is_max = False
        if params.get("max_per_week"):
            freq = params["max_per_week"]
            is_max = True

        actual = _count_item_occurrences(item_keyword, item_counter, catalog_map)
        expected = round(freq * weeks_in_month)
        comparison = _derive_comparison(actual, expected)
        found_days = _find_item_days(item_keyword, daily_categories)

        if is_max:
            passed = actual <= expected
        else:
            passed = actual >= expected

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"'{item_keyword}': Expected {'≤' if is_max else '≥'}{expected}, "
                f"Actual {actual}"
            ),
            "evidence": {
                "item_searched": item_keyword,
                "expected_count": expected,
                "actual_count": actual,
                "comparison": comparison,
                "weekly_freq": freq,
                "is_max_rule": is_max,
                "found_on_days": found_days,
            },
        }

    # =================================================================
    # item_frequency_monthly — "אסאדו 3 פעמים בחודש"
    # =================================================================
    if rule_type == "item_frequency_monthly":
        item_keyword, freq, is_max = _extract_item_and_freq(name)
        if params.get("item"):
            item_keyword = params["item"]
        if params.get("min_per_month"):
            freq = params["min_per_month"]
            is_max = False
        if params.get("max_per_month"):
            freq = params["max_per_month"]
            is_max = True

        actual = _count_item_occurrences(item_keyword, item_counter, catalog_map)
        expected = round(freq)
        comparison = _derive_comparison(actual, expected)
        found_days = _find_item_days(item_keyword, daily_categories)

        if is_max:
            passed = actual <= expected
        else:
            passed = actual >= expected

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"'{item_keyword}': Expected {'≤' if is_max else '≥'}{expected}/month, "
                f"Actual {actual}"
            ),
            "evidence": {
                "item_searched": item_keyword,
                "expected_count": expected,
                "actual_count": actual,
                "comparison": comparison,
                "monthly_freq": freq,
                "is_max_rule": is_max,
                "found_on_days": found_days,
            },
        }

    # =================================================================
    # count_min — "מינימום 11 סוגי סלטים ביום" or "מנת בקר יומית"
    # =================================================================
    if rule_type == "count_min":
        # Check if it's a "מינימום X סוגי..." pattern
        min_count, cat_keyword = _extract_daily_count(name)
        has_min_pattern = name.startswith("מינימום")

        if has_min_pattern:
            # Daily variety check — how many distinct items per day match category
            cat_variants = _normalize_hebrew(cat_keyword.lower())
            daily_counts = []
            met_days = []
            unmet_days = []
            for dc in daily_categories:
                day_count = sum(
                    1 for _, item in dc["items"]
                    if _matches_any_variant(cat_variants, str(item))
                    or any(
                        any(var in c.lower() for var in cat_variants)
                        for c in dc["categories"]
                    )
                )
                daily_counts.append(day_count)
                if day_count >= min_count:
                    met_days.append(dc["date"])
                else:
                    unmet_days.append(dc["date"])

            avg_daily = round(sum(daily_counts) / max(len(daily_counts), 1), 1)
            expected = min_count
            actual = round(avg_daily)
            comparison = _derive_comparison(actual, expected)
            passed = avg_daily >= min_count

            return {
                **base,
                "passed": passed,
                "finding_text": (
                    f"'{cat_keyword}': Min {min_count}/day, "
                    f"Avg {avg_daily}/day"
                ),
                "evidence": {
                    "category_keyword": cat_keyword,
                    "expected_count": expected,
                    "actual_count": actual,
                    "comparison": comparison,
                    "avg_daily": avg_daily,
                    "min_required": min_count,
                    "found_on_days": met_days,
                    "missing_on_days": unmet_days[:10],
                },
            }
        else:
            # Daily item presence check — "גריל יומי", "מנת בקר יומית"
            item_keyword = _extract_item_present_keyword(name)
            if params.get("item"):
                item_keyword = params["item"]

            actual = _count_daily_item_presence(item_keyword, daily_categories)
            expected = total_days
            comparison = _derive_comparison(actual, expected)
            passed = actual >= expected
            found_days = _find_item_days(item_keyword, daily_categories)
            missing_days = _find_missing_days(item_keyword, daily_categories)

            return {
                **base,
                "passed": passed,
                "finding_text": (
                    f"'{item_keyword}': Present {actual}/{total_days} days"
                ),
                "evidence": {
                    "item_searched": item_keyword,
                    "expected_count": expected,
                    "actual_count": actual,
                    "comparison": comparison,
                    "found_on_days": found_days,
                    "missing_on_days": missing_days[:10],
                },
            }

    # =================================================================
    # count_max — "מקסימום 2 מנות בשר טחון ביום"
    # =================================================================
    if rule_type == "count_max":
        max_count, item_keyword = _extract_daily_count(name)
        if params.get("item"):
            item_keyword = params["item"]

        daily_counts = []
        exceeded_days = []
        for dc in daily_categories:
            day_count = sum(
                1 for _, item in dc["items"]
                if item_keyword.lower() in str(item).lower()
            )
            daily_counts.append(day_count)
            if day_count > max_count:
                exceeded_days.append(dc["date"])

        max_found = max(daily_counts) if daily_counts else 0
        avg_daily = round(sum(daily_counts) / max(len(daily_counts), 1), 1)
        expected = max_count
        actual = round(avg_daily)
        comparison = _derive_comparison(actual, expected)
        passed = max_found <= max_count

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"'{item_keyword}': Max {max_count}/day, "
                f"Peak {max_found}/day, Avg {avg_daily}/day"
            ),
            "evidence": {
                "item_searched": item_keyword,
                "expected_count": expected,
                "actual_count": actual,
                "comparison": comparison,
                "max_daily_found": max_found,
                "avg_daily": avg_daily,
                "found_on_days": exceeded_days,
            },
        }

    # =================================================================
    # item_present — "סלט חומוס יומי", "מרק צח/ירקות יומי"
    # =================================================================
    if rule_type == "item_present":
        item_keyword = _extract_item_present_keyword(name)
        if params.get("item"):
            item_keyword = params["item"]

        actual = _count_daily_item_presence(item_keyword, daily_categories)
        expected = total_days
        comparison = _derive_comparison(actual, expected)
        passed = actual >= expected
        found_days = _find_item_days(item_keyword, daily_categories)
        missing_days = _find_missing_days(item_keyword, daily_categories)

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"'{item_keyword}': Present {actual}/{total_days} days"
            ),
            "evidence": {
                "item_searched": item_keyword,
                "expected_count": expected,
                "actual_count": actual,
                "comparison": comparison,
                "found_on_days": found_days,
                "missing_on_days": missing_days[:10],
            },
        }

    # =================================================================
    # no_repeat_weekly — "אין אותו מרק פעמיים בשבוע"
    # =================================================================
    if rule_type == "no_repeat_weekly":
        if is_fallback:
            return {
                **base,
                "passed": True,
                "finding_text": "Cannot evaluate — menu parsed in fallback mode (same items on all days). Re-upload with structured data.",
                "evidence": {
                    "expected_count": 0,
                    "actual_count": 0,
                    "comparison": "even",
                    "note": "Skipped: fallback mode",
                },
            }
        repeats = 0
        weeks: dict[int, list] = {}
        for dc in daily_categories:
            d = dc.get("date", "")
            try:
                week = date.fromisoformat(d).isocalendar()[1]
            except (ValueError, TypeError):
                continue
            if week not in weeks:
                weeks[week] = []
            for _, item in dc["items"]:
                weeks[week].append(str(item).lower())

        for week_items in weeks.values():
            counter = Counter(week_items)
            repeats += sum(v - 1 for v in counter.values() if v > 1)

        expected = 0
        comparison = _derive_comparison(repeats, expected)
        passed = repeats == 0

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"Weekly repeats found: {repeats}"
                if repeats > 0 else "No weekly repeats"
            ),
            "evidence": {
                "expected_count": expected,
                "actual_count": repeats,
                "comparison": comparison,
            },
        }

    # =================================================================
    # no_repeat_daily — "אין לחזור על אותו סלט פעמיים ביום"
    # =================================================================
    if rule_type == "no_repeat_daily":
        if is_fallback:
            return {
                **base,
                "passed": True,
                "finding_text": "Cannot evaluate — menu parsed in fallback mode. Re-upload with structured data.",
                "evidence": {
                    "expected_count": 0,
                    "actual_count": 0,
                    "comparison": "even",
                    "note": "Skipped: fallback mode",
                },
            }
        repeats = 0
        for dc in daily_categories:
            items_lower = [str(item).lower() for _, item in dc["items"]]
            counter = Counter(items_lower)
            repeats += sum(v - 1 for v in counter.values() if v > 1)

        expected = 0
        comparison = _derive_comparison(repeats, expected)
        passed = repeats == 0

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"Daily repeats found: {repeats}"
                if repeats > 0 else "No daily repeats"
            ),
            "evidence": {
                "expected_count": expected,
                "actual_count": repeats,
                "comparison": comparison,
            },
        }

    # =================================================================
    # no_consecutive — "אין לחזור על אותו פריט יום אחר יום"
    # =================================================================
    if rule_type == "no_consecutive":
        if is_fallback:
            return {
                **base,
                "passed": True,
                "finding_text": "Cannot evaluate — menu parsed in fallback mode. Re-upload with structured data.",
                "evidence": {
                    "expected_count": 0,
                    "actual_count": 0,
                    "comparison": "even",
                    "note": "Skipped: fallback mode",
                },
            }
        consecutive_repeats = 0
        prev_items: set = set()
        for dc in daily_categories:
            current_items = {str(item).lower() for _, item in dc["items"]}
            overlap = prev_items & current_items
            consecutive_repeats += len(overlap)
            prev_items = current_items

        expected = 0
        comparison = _derive_comparison(consecutive_repeats, expected)
        passed = consecutive_repeats == 0

        return {
            **base,
            "passed": passed,
            "finding_text": (
                f"Consecutive-day repeats: {consecutive_repeats}"
                if consecutive_repeats > 0 else "No consecutive repeats"
            ),
            "evidence": {
                "expected_count": expected,
                "actual_count": consecutive_repeats,
                "comparison": comparison,
            },
        }

    # =================================================================
    # Legacy: frequency (old seeded rules with parameters)
    # =================================================================
    if rule_type == "frequency":
        max_per_week = params.get("max_per_week")
        min_per_week = params.get("min_per_week")
        target_item = params.get("item", "").lower()

        if target_item:
            actual = _count_item_occurrences(target_item, item_counter, catalog_map)
            weekly_avg = actual / weeks_in_month

            if min_per_week is not None:
                expected = round(min_per_week * weeks_in_month)
            elif max_per_week is not None:
                expected = round(max_per_week * weeks_in_month)
            else:
                expected = 0

            comparison = _derive_comparison(actual, expected)

            if max_per_week and weekly_avg > max_per_week:
                return {
                    **base, "passed": False,
                    "finding_text": (
                        f"'{target_item}': ~{weekly_avg:.1f}/week "
                        f"(max {max_per_week}). Expected ≤{expected}, Actual {actual}"
                    ),
                    "evidence": {
                        "expected_count": expected, "actual_count": actual,
                        "comparison": comparison,
                    },
                }
            if min_per_week and weekly_avg < min_per_week:
                return {
                    **base, "passed": False,
                    "finding_text": (
                        f"'{target_item}': ~{weekly_avg:.1f}/week "
                        f"(min {min_per_week}). Expected ≥{expected}, Actual {actual}"
                    ),
                    "evidence": {
                        "expected_count": expected, "actual_count": actual,
                        "comparison": comparison,
                    },
                }

            return {
                **base, "passed": True,
                "finding_text": f"Expected: {expected}, Actual: {actual}",
                "evidence": {
                    "expected_count": expected, "actual_count": actual,
                    "comparison": comparison,
                },
            }

        return {
            **base, "passed": True, "finding_text": None,
            "evidence": {"expected_count": 0, "actual_count": 0, "comparison": "even"},
        }

    # =================================================================
    # Legacy: mandatory (old seeded rules with parameters)
    # =================================================================
    if rule_type == "mandatory":
        required_category = params.get("required_category", "").lower()
        required_item = params.get("required_item", "").lower()

        if required_category:
            missing_days = []
            for dc in daily_categories:
                cats_lower = [c.lower() for c in dc["categories"]]
                if not any(required_category in c for c in cats_lower):
                    missing_days.append(dc["date"])

            expected = total_days
            actual = total_days - len(missing_days)
            comparison = _derive_comparison(actual, expected)

            if missing_days:
                return {
                    **base, "passed": False,
                    "finding_text": (
                        f"Category '{required_category}' missing on "
                        f"{len(missing_days)}/{total_days} days"
                    ),
                    "evidence": {
                        "expected_count": expected, "actual_count": actual,
                        "comparison": comparison, "missing_days": missing_days[:5],
                    },
                }
            return {
                **base, "passed": True,
                "finding_text": f"Present all {total_days} days",
                "evidence": {
                    "expected_count": expected, "actual_count": actual,
                    "comparison": comparison,
                },
            }

        if required_item:
            actual = _count_daily_item_presence(required_item, daily_categories)
            expected = total_days
            comparison = _derive_comparison(actual, expected)

            if actual == 0:
                return {
                    **base, "passed": False,
                    "finding_text": (
                        f"Required item '{required_item}' not found in any day"
                    ),
                    "evidence": {
                        "expected_count": expected, "actual_count": 0,
                        "comparison": comparison,
                    },
                }
            return {
                **base, "passed": True,
                "finding_text": f"Found on {actual}/{total_days} days",
                "evidence": {
                    "expected_count": expected, "actual_count": actual,
                    "comparison": comparison,
                },
            }

    # =================================================================
    # Unknown rule type — try to treat as item frequency using name parsing
    # =================================================================
    item_keyword, freq, is_max = _extract_item_and_freq(name)
    if freq > 0 and item_keyword:
        actual = _count_item_occurrences(item_keyword, item_counter, catalog_map)
        expected = round(freq)
        comparison = _derive_comparison(actual, expected)
        passed = actual <= expected if is_max else actual >= expected

        return {
            **base,
            "passed": passed,
            "finding_text": f"'{item_keyword}': Expected {expected}, Actual {actual}",
            "evidence": {
                "item_searched": item_keyword,
                "expected_count": expected,
                "actual_count": actual,
                "comparison": comparison,
            },
        }

    return {
        **base,
        "passed": True,
        "finding_text": None,
        "evidence": {
            "note": "Rule type not evaluable",
            "expected_count": 0,
            "actual_count": 0,
            "comparison": "even",
        },
    }
