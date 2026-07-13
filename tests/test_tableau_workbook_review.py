from __future__ import annotations

from src import config
from src.tableau_workbook_review import is_website_ready, review_workbook


def test_review_flags_opportunity_worksheets_not_embedded():
    workbook = config.AUDIT_DIR / "_test_workbook_missing_opportunity_dashboard.twb"
    workbook.parent.mkdir(parents=True, exist_ok=True)
    workbook.write_text(_minimal_workbook(opportunity_dashboard=False), encoding="utf-8")

    findings = review_workbook(workbook)

    assert not is_website_ready(findings)
    assert any(finding.check == "opportunity_dashboard_coverage" and finding.status == "fail" for finding in findings)


def test_review_passes_when_required_story_surfaces_are_embedded():
    workbook = config.AUDIT_DIR / "_test_workbook_website_ready.twb"
    workbook.parent.mkdir(parents=True, exist_ok=True)
    workbook.write_text(_minimal_workbook(opportunity_dashboard=True), encoding="utf-8")

    findings = review_workbook(workbook)

    high_failures = [finding for finding in findings if finding.status == "fail" and finding.severity in {"critical", "high"}]
    assert high_failures == []
    assert is_website_ready(findings)


def _minimal_workbook(opportunity_dashboard: bool) -> str:
    required_worksheets = [
        "Atlas Map",
        "Headline KPIs",
        "Utilisation Trend",
        "Funded Plan Saturation Trend",
        "Support Type Mix",
        "Market Position",
        "Ranked Service Areas",
        "Benchmark Gaps",
        "Provider Data Availability",
        "Evidence Table",
        "Data Quality Flags",
        "Opportunity Priority",
        "Advocacy Gaps",
        "Provider Underservice",
        "Service Type Opportunities",
        "Opportunity Matrix",
    ]
    dashboards = [
        "NDIS Saturation Atlas Monitor",
        "NDIS Saturation Atlas Tablet",
        "NDIS Saturation Atlas Phone",
        "NDIS Saturation National Monitor",
        "NDIS Saturation National Tablet",
        "NDIS Saturation National Phone",
        "NDIS Saturation Service Area Monitor",
        "NDIS Saturation Service Area Tablet",
        "NDIS Saturation Service Area Phone",
        "NDIS Saturation Opportunities Monitor",
        "NDIS Saturation Opportunities Tablet",
        "NDIS Saturation Opportunities Phone",
    ]
    worksheet_xml = "\n".join(
        f'<worksheet name="{name}"><table><encodings>{"<geometry /><encoding type=\"space\" scope=\"cols\" range-type=\"fixed\" min=\"12245143\" max=\"18924314\" /><encoding type=\"space\" scope=\"rows\" range-type=\"fixed\" min=\"-5621522\" max=\"-893463\" /><color column=\"[none:persistent_utilisation_classification:nk]\" /><tooltip column=\"[avg:funded_plans_per_1000_gap_from_national:qk]\" /><tooltip column=\"[avg:mean_plan_utilisation_gap_from_national:qk]\" /><tooltip column=\"[avg:active_providers_per_1000_funded_plans:qk]\" /><tooltip column=\"[none:quarter_label:nk]\" />" if name == "Atlas Map" else "<color />"}</encodings></table><simple-id uuid="ws-{index}" /></worksheet>'
        for index, name in enumerate(required_worksheets)
    )
    dashboard_xml = "\n".join(
        f'<dashboard name="{name}"><zones>{_zones_for(name, opportunity_dashboard)}</zones><simple-id uuid="dash-{index}" /></dashboard>'
        for index, name in enumerate(dashboards)
    )
    window_xml = "\n".join(
        f'<window class="dashboard" name="{name}"><simple-id uuid="window-{index}" /></window>'
        for index, name in enumerate(dashboards)
    )
    return f"<workbook><worksheets>{worksheet_xml}</worksheets><dashboards>{dashboard_xml}</dashboards><windows>{window_xml}</windows></workbook>"


def _zones_for(dashboard_name: str, opportunity_dashboard: bool) -> str:
    if "Atlas" in dashboard_name:
        sheets = ["Atlas Map"]
    elif "National" in dashboard_name:
        sheets = ["Headline KPIs", "Utilisation Trend", "Funded Plan Saturation Trend"]
    elif "Service Area" in dashboard_name:
        sheets = ["Utilisation Trend", "Funded Plan Saturation Trend", "Evidence Table"]
    else:
        sheets = []
    if opportunity_dashboard and "Opportunities" in dashboard_name:
        sheets.extend(["Opportunity Priority", "Advocacy Gaps", "Provider Underservice", "Service Type Opportunities", "Opportunity Matrix"])
    return "".join(f'<zone name="{sheet}" />' for sheet in sheets)
