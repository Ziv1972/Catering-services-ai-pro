"""
Export Compliance Rules: Convert hardcoded rules to natural language policy

Usage:
    python scripts/export_compliance_rules.py /path/to/old/catering.db
"""

import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime


def export_rules_to_policy(old_db_path: str):
    """Export compliance rules as natural language policy document"""
    print("=" * 60)
    print("EXPORTING COMPLIANCE RULES TO POLICY DOCUMENT")
    print("=" * 60)
    print()

    # Connect to old database
    conn = sqlite3.connect(old_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all active rules
    try:
        rules = cursor.execute("""
            SELECT rule_name, rule_type, description, category,
                   parameters, priority
            FROM compliance_rules
            WHERE active = 1
            ORDER BY category, priority, rule_name
        """).fetchall()
    except sqlite3.OperationalError:
        print("Table 'compliance_rules' not found in old database")
        print("   Creating template policy document instead...")
        rules = []

    # Build policy document
    policy_lines = []
    policy_lines.append("# HP Israel Catering Services - Menu Compliance Policy\n\n")
    policy_lines.append(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d')}\n\n")
    policy_lines.append("**Migrated from:** FoodHouse Analytics\n\n")
    policy_lines.append("---\n\n")

    policy_lines.append("## Introduction\n\n")
    policy_lines.append("This document defines the menu compliance policy for HP Israel ")
    policy_lines.append("catering services across Nes Ziona and Kiryat Gat sites. ")
    policy_lines.append("All menus must comply with these requirements.\n\n")

    if rules:
        # Group rules by category
        categories = {}
        for rule in rules:
            cat = rule['category'] or 'General'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(rule)

        # Write each category
        for category, cat_rules in categories.items():
            policy_lines.append(f"## {category}\n\n")

            for rule in cat_rules:
                policy_lines.append(f"### {rule['rule_name']}\n\n")

                if rule['description']:
                    policy_lines.append(f"{rule['description']}\n\n")

                if rule['parameters']:
                    try:
                        params = json.loads(rule['parameters'])
                        policy_lines.append("**Requirements:**\n\n")

                        if rule['rule_type'] == 'frequency':
                            max_freq = params.get('max_per_week', 'N/A')
                            policy_lines.append(f"- Maximum frequency: {max_freq} times per week\n")

                        elif rule['rule_type'] == 'mandatory':
                            freq = params.get('frequency', 'daily')
                            policy_lines.append(f"- Must appear: {freq}\n")

                        policy_lines.append("\n")
                    except (json.JSONDecodeError, TypeError):
                        pass

                policy_lines.append("---\n\n")
    else:
        # Create template
        policy_lines.append("## Daily Menu Requirements\n\n")
        policy_lines.append("### Main Dish\n")
        policy_lines.append("- Must be served daily\n")
        policy_lines.append("- Variety: At least 3 different main dishes per week\n\n")

        policy_lines.append("### Dietary Accommodations\n")
        policy_lines.append("- Vegan option: Required daily\n")
        policy_lines.append("- Gluten-free: Available on request\n\n")

    # Write to file
    output_path = Path("docs/CATERING_POLICY.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(policy_lines)

    conn.close()

    print(f"Policy document created: {output_path}")
    print(f"   Exported {len(rules)} rules as natural language policy")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_compliance_rules.py /path/to/old/catering.db")
        sys.exit(1)

    old_db_path = sys.argv[1]

    if not Path(old_db_path).exists():
        print(f"Database not found: {old_db_path}")
        sys.exit(1)

    export_rules_to_policy(old_db_path)
