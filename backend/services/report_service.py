"""
HTML report generation for violation analytics.
Generates self-contained inline-CSS email-compatible HTML reports.
"""
from datetime import datetime
from typing import Dict, Any


def generate_violation_report_html(analytics: Dict[str, Any]) -> str:
    """Generate a professional HTML report from violation analytics data."""
    period = analytics["period"]
    summary = analytics["summary"]
    by_site = analytics.get("by_site", [])
    by_category = analytics.get("by_category", [])
    top_fine_rules = analytics.get("top_fine_rules", [])
    violations_list = analytics.get("violations_list", [])

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── KPI cards ──
    kpi_cards = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
      <tr>
        <td width="25%" style="padding:0 6px 0 0;">
          <table width="100%" cellpadding="12" cellspacing="0"
                 style="background:#eff6ff;border-radius:8px;border:1px solid #bfdbfe;">
            <tr>
              <td style="text-align:center;">
                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">
                  Total Violations</div>
                <div style="font-size:28px;font-weight:700;color:#1e40af;margin-top:4px;">
                  {summary['total_violations']}</div>
              </td>
            </tr>
          </table>
        </td>
        <td width="25%" style="padding:0 6px;">
          <table width="100%" cellpadding="12" cellspacing="0"
                 style="background:#fef3c7;border-radius:8px;border:1px solid #fcd34d;">
            <tr>
              <td style="text-align:center;">
                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">
                  Total Fines</div>
                <div style="font-size:28px;font-weight:700;color:#92400e;margin-top:4px;">
                  {summary['total_fines']}</div>
              </td>
            </tr>
          </table>
        </td>
        <td width="25%" style="padding:0 6px;">
          <table width="100%" cellpadding="12" cellspacing="0"
                 style="background:#f3e8ff;border-radius:8px;border:1px solid #c4b5fd;">
            <tr>
              <td style="text-align:center;">
                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">
                  Fine Amount</div>
                <div style="font-size:28px;font-weight:700;color:#7c3aed;margin-top:4px;">
                  ₪{summary['total_fine_amount']:,.0f}</div>
              </td>
            </tr>
          </table>
        </td>
        <td width="25%" style="padding:0 0 0 6px;">
          <table width="100%" cellpadding="12" cellspacing="0"
                 style="background:#ecfdf5;border-radius:8px;border:1px solid #6ee7b7;">
            <tr>
              <td style="text-align:center;">
                <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">
                  Avg Resolution</div>
                <div style="font-size:28px;font-weight:700;color:#059669;margin-top:4px;">
                  {summary['avg_resolution_time_hours']:.0f}h</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """

    # ── By Site table ──
    site_rows = ""
    for s in by_site:
        site_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;">
            {s['site_name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:center;">
            {s['violations']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:center;">
            {s['fines']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:right;">
            ₪{s['fine_amount']:,.0f}</td>
        </tr>"""

    site_table = f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:20px;">
      <tr style="background:#f9fafb;">
        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Site</th>
        <th style="padding:10px 12px;text-align:center;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Violations</th>
        <th style="padding:10px 12px;text-align:center;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Fines</th>
        <th style="padding:10px 12px;text-align:right;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Amount (NIS)</th>
      </tr>
      {site_rows}
    </table>
    """ if by_site else ""

    # ── By Category table ──
    cat_rows = ""
    for cat in by_category:
        cat_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-transform:capitalize;">
            {cat['category'].replace('_', ' ')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:center;">
            {cat['count']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:center;">
            {cat['fines']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:right;">
            ₪{cat['fine_amount']:,.0f}</td>
        </tr>"""

    category_table = f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:20px;">
      <tr style="background:#f9fafb;">
        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Category</th>
        <th style="padding:10px 12px;text-align:center;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Count</th>
        <th style="padding:10px 12px;text-align:center;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Fines</th>
        <th style="padding:10px 12px;text-align:right;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Amount (NIS)</th>
      </tr>
      {cat_rows}
    </table>
    """ if by_category else ""

    # ── Top Fine Rules table ──
    fine_rows = ""
    for rule in top_fine_rules[:10]:
        fine_rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;">
            {rule['rule_name']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:center;">
            {rule['times_applied']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;font-size:13px;text-align:right;">
            ₪{rule['total_amount']:,.0f}</td>
        </tr>"""

    fine_rules_table = f"""
    <h3 style="font-size:15px;font-weight:600;color:#1f2937;margin:20px 0 10px 0;">
      Top Fine Rules Applied</h3>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:20px;">
      <tr style="background:#f9fafb;">
        <th style="padding:10px 12px;text-align:left;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Rule Name</th>
        <th style="padding:10px 12px;text-align:center;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Times Applied</th>
        <th style="padding:10px 12px;text-align:right;font-size:12px;color:#374151;
                   font-weight:600;border-bottom:2px solid #e5e7eb;">Total Amount</th>
      </tr>
      {fine_rows}
    </table>
    """ if top_fine_rules else ""

    # ── Violation details table ──
    severity_colors = {
        "critical": "#dc2626", "high": "#ea580c",
        "medium": "#ca8a04", "low": "#6b7280",
    }
    detail_rows = ""
    for item in violations_list[:50]:
        sev_color = severity_colors.get(item.get("severity", ""), "#6b7280")
        fine_display = f"₪{item['fine_amount']:,.0f}" if item.get("fine_amount") else "-"
        detail_rows += f"""
        <tr>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;white-space:nowrap;">
            {item['date'][:10]}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;">
            {item.get('site_name', '-')}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;text-transform:capitalize;">
            {(item.get('category') or '-').replace('_', ' ')}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;">
            <span style="color:{sev_color};font-weight:600;text-transform:capitalize;">
              {item.get('severity', '-')}</span></td>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;">
            {item.get('fine_rule_name') or '-'}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;text-align:right;">
            {fine_display}</td>
          <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;font-size:12px;text-transform:capitalize;">
            {item.get('status', '-')}</td>
        </tr>"""

    details_table = f"""
    <h3 style="font-size:15px;font-weight:600;color:#1f2937;margin:20px 0 10px 0;">
      Violation Details ({min(len(violations_list), 50)} of {len(violations_list)})</h3>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:20px;
                  font-size:12px;">
      <tr style="background:#f9fafb;">
        <th style="padding:8px;text-align:left;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Date</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Site</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Category</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Severity</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Fine Rule</th>
        <th style="padding:8px;text-align:right;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Amount</th>
        <th style="padding:8px;text-align:left;font-size:11px;color:#374151;font-weight:600;
                   border-bottom:2px solid #e5e7eb;">Status</th>
      </tr>
      {detail_rows}
    </table>
    """ if violations_list else ""

    # ── Full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Violation &amp; Fine Report</title>
</head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;">
    <tr>
      <td align="center" style="padding:24px 16px;">
        <table width="700" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:12px;overflow:hidden;
                      box-shadow:0 1px 3px rgba(0,0,0,0.1);">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1e40af,#3b82f6);padding:28px 32px;">
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;">
                Violation &amp; Fine Report</h1>
              <p style="margin:6px 0 0 0;color:#bfdbfe;font-size:13px;">
                HP Israel &mdash; Catering AI Pro</p>
            </td>
          </tr>

          <!-- Period -->
          <tr>
            <td style="padding:20px 32px 8px 32px;">
              <p style="margin:0;font-size:14px;color:#6b7280;">
                Period: <strong style="color:#1f2937;">{period['from']}</strong>
                to <strong style="color:#1f2937;">{period['to']}</strong></p>
            </td>
          </tr>

          <!-- KPIs -->
          <tr>
            <td style="padding:16px 32px;">
              {kpi_cards}
            </td>
          </tr>

          <!-- By Site -->
          <tr>
            <td style="padding:0 32px;">
              <h3 style="font-size:15px;font-weight:600;color:#1f2937;margin:0 0 10px 0;">
                Breakdown by Site</h3>
              {site_table}
            </td>
          </tr>

          <!-- By Category -->
          <tr>
            <td style="padding:0 32px;">
              <h3 style="font-size:15px;font-weight:600;color:#1f2937;margin:0 0 10px 0;">
                Breakdown by Category</h3>
              {category_table}
            </td>
          </tr>

          <!-- Top Fine Rules -->
          <tr>
            <td style="padding:0 32px;">
              {fine_rules_table}
            </td>
          </tr>

          <!-- Details -->
          <tr>
            <td style="padding:0 32px;">
              {details_table}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px;border-top:1px solid #e5e7eb;">
              <p style="margin:0;font-size:11px;color:#9ca3af;text-align:center;">
                Generated on {generated_at} &bull; Catering AI Pro &bull; HP Israel</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return html
