from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from . import config


WORKBOOK_PATH = config.OUTPUTS_DIR / "tableau" / "NDIS-Saturation-Atlas.twb"
REPORT_PATH = config.AUDIT_DIR / "tableau_dashboard_implementation_review.md"
CSV_PATH = config.AUDIT_DIR / "tableau_dashboard_implementation_review.csv"

REQUIRED_WORKSHEETS = {
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
}

OPPORTUNITY_WORKSHEETS = {
    "Opportunity Priority",
    "Advocacy Gaps",
    "Provider Underservice",
    "Service Type Opportunities",
    "Opportunity Matrix",
}

REQUIRED_DASHBOARDS = {
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
}

ATLAS_DASHBOARDS = {
    "NDIS Saturation Atlas Monitor",
    "NDIS Saturation Atlas Tablet",
    "NDIS Saturation Atlas Phone",
}

ATLAS_ONLY_DASHBOARDS = {
    "NDIS Saturation Atlas Monitor",
    "NDIS Saturation Atlas Tablet",
    "NDIS Saturation Atlas Phone",
}

SERVICE_AREA_DASHBOARDS = {
    "NDIS Saturation Service Area Monitor",
    "NDIS Saturation Service Area Tablet",
    "NDIS Saturation Service Area Phone",
}

NATIONAL_DASHBOARDS = {
    "NDIS Saturation National Monitor",
    "NDIS Saturation National Tablet",
    "NDIS Saturation National Phone",
}

OPPORTUNITY_DASHBOARDS = {
    "NDIS Saturation Opportunities Monitor",
    "NDIS Saturation Opportunities Tablet",
    "NDIS Saturation Opportunities Phone",
}


@dataclass(frozen=True)
class ReviewFinding:
    status: str
    severity: str
    check: str
    detail: str


def review_workbook(path: Path = WORKBOOK_PATH) -> list[ReviewFinding]:
    """Review the Tableau workbook against the gmdata publication standard."""

    tree = ET.parse(path)
    root = tree.getroot()
    workbook_xml = ET.tostring(root, encoding="unicode")
    worksheets = {node.attrib.get("name", "") for node in root.findall(".//worksheets/worksheet")}
    dashboards = {node.attrib.get("name", "") for node in root.findall(".//dashboards/dashboard")}
    dashboard_sheets = {
        dashboard.attrib.get("name", ""): {
            zone.attrib["name"]
            for zone in dashboard.findall(".//zone")
            if zone.attrib.get("name") in worksheets
        }
        for dashboard in root.findall(".//dashboards/dashboard")
    }

    findings: list[ReviewFinding] = []
    findings.extend(_presence_findings("worksheet", REQUIRED_WORKSHEETS, worksheets, "critical"))
    findings.extend(_presence_findings("opportunity worksheet", OPPORTUNITY_WORKSHEETS, worksheets, "critical"))
    findings.extend(_presence_findings("dashboard", REQUIRED_DASHBOARDS, dashboards, "critical"))
    findings.extend(_schema_findings(root, workbook_xml))
    findings.extend(_dashboard_findings(dashboard_sheets))
    findings.extend(_opportunity_findings(dashboard_sheets))
    findings.extend(_atlas_findings(root, worksheets, dashboard_sheets))
    return findings


def write_review(path: Path = WORKBOOK_PATH, report_path: Path = REPORT_PATH, csv_path: Path = CSV_PATH) -> list[ReviewFinding]:
    """Write markdown and CSV review artifacts for the workbook."""

    findings = review_workbook(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text("", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status", "severity", "check", "detail"])
        writer.writeheader()
        writer.writerows(finding.__dict__ for finding in findings)
    report_path.write_text(_markdown_report(path, findings), encoding="utf-8")
    return findings


def is_website_ready(findings: list[ReviewFinding]) -> bool:
    return not any(f.status == "fail" and f.severity in {"critical", "high"} for f in findings)


def _presence_findings(label: str, required: set[str], actual: set[str], severity: str) -> list[ReviewFinding]:
    missing = sorted(required - actual)
    if missing:
        return [
            ReviewFinding(
                "fail",
                severity,
                f"required_{label.replace(' ', '_')}s",
                f"Missing {label}s: {', '.join(missing)}.",
            )
        ]
    return [ReviewFinding("pass", "info", f"required_{label.replace(' ', '_')}s", f"All {len(required)} required {label}s are present.")]


def _schema_findings(root: ET.Element, workbook_xml: str) -> list[ReviewFinding]:
    findings = []
    simple_ids = [
        node.attrib.get("uuid")
        for node in root.findall(".//simple-id")
        if node.attrib.get("uuid")
    ]
    duplicate_ids = sorted({value for value in simple_ids if simple_ids.count(value) > 1})
    forbidden_tags = {
        "grid": len(root.findall(".//grid")),
        "map_navigation": len(root.findall(".//map-navigation")),
        "nested_devicelayouts": len(root.findall(".//devicelayouts/devicelayouts")),
        "stale_extract": len(root.findall(".//extract")),
    }
    autogenerated_layouts = [
        node.attrib.get("name", "")
        for node in root.findall(".//devicelayout")
        if "auto-generated" in node.attrib
    ]

    if duplicate_ids:
        findings.append(ReviewFinding("fail", "critical", "unique_simple_ids", f"Duplicate simple-id UUIDs: {', '.join(duplicate_ids[:10])}."))
    else:
        findings.append(ReviewFinding("pass", "info", "unique_simple_ids", "No duplicate simple-id UUIDs found."))

    for tag, count in forbidden_tags.items():
        if count:
            if tag == "stale_extract":
                detail = f"Found {count} embedded extract element(s), which can make Tableau render stale cached geometry instead of the regenerated atlas GeoJSON."
            else:
                detail = f"Found {count} invalid <{tag}> element(s), which have caused Tableau load errors."
            findings.append(ReviewFinding("fail", "critical", f"forbidden_{tag}", detail))
        else:
            if tag == "stale_extract":
                detail = "No embedded extract elements found."
            else:
                detail = f"No invalid <{tag}> elements found."
            findings.append(ReviewFinding("pass", "info", f"forbidden_{tag}", detail))

    if "TableauTemp" in workbook_xml or 'class="hyper"' in workbook_xml:
        findings.append(ReviewFinding("fail", "critical", "forbidden_temp_hyper_extract", "Workbook references a temporary Hyper extract, which can mask the regenerated atlas GeoJSON."))
    else:
        findings.append(ReviewFinding("pass", "info", "forbidden_temp_hyper_extract", "No temporary Hyper extract references found."))

    if autogenerated_layouts:
        findings.append(ReviewFinding("fail", "critical", "devicelayout_auto_generated_attribute", "Device layouts include unsupported auto-generated attributes."))
    else:
        findings.append(ReviewFinding("pass", "info", "devicelayout_auto_generated_attribute", "No unsupported devicelayout auto-generated attributes found."))
    return findings


def _dashboard_findings(dashboard_sheets: dict[str, set[str]]) -> list[ReviewFinding]:
    findings = []
    empty = sorted(name for name, sheets in dashboard_sheets.items() if not sheets)
    if empty:
        findings.append(ReviewFinding("fail", "critical", "dashboard_sheet_zones", f"Dashboards with no worksheet zones: {', '.join(empty)}."))
    else:
        findings.append(ReviewFinding("pass", "info", "dashboard_sheet_zones", "Every dashboard contains worksheet zones."))

    missing_atlas = sorted(name for name in ATLAS_DASHBOARDS if "Atlas Map" not in dashboard_sheets.get(name, set()))
    if missing_atlas:
        findings.append(ReviewFinding("fail", "high", "atlas_first_view", f"Atlas dashboards missing Atlas Map: {', '.join(missing_atlas)}."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_first_view", "Atlas/overview dashboards include the Atlas Map worksheet."))

    crowded_atlas = {
        name: sorted(dashboard_sheets.get(name, set()) - {"Atlas Map"})
        for name in ATLAS_ONLY_DASHBOARDS
        if dashboard_sheets.get(name, set()) != {"Atlas Map"}
    }
    if crowded_atlas:
        detail = "; ".join(f"{name}: {', '.join(extra) if extra else 'missing Atlas Map'}" for name, extra in sorted(crowded_atlas.items()))
        findings.append(ReviewFinding("fail", "high", "atlas_only_dashboard_focus", f"Standalone atlas dashboards should contain only Atlas Map. Extra sheets: {detail}."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_only_dashboard_focus", "Standalone atlas dashboards contain only the Atlas Map worksheet."))

    missing_detail = sorted(
        name
        for name in SERVICE_AREA_DASHBOARDS
        if not {"Utilisation Trend", "Funded Plan Saturation Trend", "Evidence Table"}.issubset(dashboard_sheets.get(name, set()))
    )
    if missing_detail:
        findings.append(ReviewFinding("fail", "high", "service_area_detail", f"Service-area dashboards missing core detail sheets: {', '.join(missing_detail)}."))
    else:
        findings.append(ReviewFinding("pass", "info", "service_area_detail", "Service-area dashboards include utilisation, saturation and evidence detail sheets."))

    missing_national = sorted(
        name
        for name in NATIONAL_DASHBOARDS
        if not {"Headline KPIs", "Utilisation Trend", "Funded Plan Saturation Trend"}.issubset(dashboard_sheets.get(name, set()))
    )
    if missing_national:
        findings.append(ReviewFinding("fail", "high", "national_dashboard_kpis", f"National dashboards missing KPI/trend sheets: {', '.join(missing_national)}."))
    else:
        findings.append(ReviewFinding("pass", "info", "national_dashboard_kpis", "National dashboards contain headline KPIs and national trend context."))
    return findings


def _opportunity_findings(dashboard_sheets: dict[str, set[str]]) -> list[ReviewFinding]:
    embedded = {sheet for sheets in dashboard_sheets.values() for sheet in sheets}
    missing_from_dashboards = sorted(OPPORTUNITY_WORKSHEETS - embedded)
    findings = []
    if missing_from_dashboards:
        findings.append(
            ReviewFinding(
                "fail",
                "critical",
                "opportunity_dashboard_coverage",
                "Opportunity worksheets exist but are not embedded in dashboard shells: "
                + ", ".join(missing_from_dashboards)
                + ".",
            )
        )
    else:
        findings.append(ReviewFinding("pass", "info", "opportunity_dashboard_coverage", "All opportunity worksheets are embedded in at least one dashboard."))

    ranking_coverage = set().union(*(dashboard_sheets.get(name, set()) for name in OPPORTUNITY_DASHBOARDS))
    missing_ranking_opportunity = sorted(OPPORTUNITY_WORKSHEETS - ranking_coverage)
    if missing_ranking_opportunity:
        findings.append(
            ReviewFinding(
                "fail",
                "high",
                "opportunity_ranking_dashboard",
                "Opportunity dashboards do not cover: " + ", ".join(missing_ranking_opportunity) + ".",
            )
        )
    else:
        findings.append(ReviewFinding("pass", "info", "opportunity_ranking_dashboard", "Opportunity dashboards cover opportunity, advocacy, provider and service-type views."))
    return findings


def _atlas_findings(root: ET.Element, worksheets: set[str], dashboard_sheets: dict[str, set[str]]) -> list[ReviewFinding]:
    if "Atlas Map" not in worksheets:
        return []
    atlas = next(node for node in root.findall(".//worksheets/worksheet") if node.attrib.get("name") == "Atlas Map")
    atlas_xml = ET.tostring(atlas, encoding="unicode")
    findings = []
    if "<geometry" not in atlas_xml:
        findings.append(ReviewFinding("fail", "critical", "atlas_geometry_encoding", "Atlas Map does not contain a geometry encoding."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_geometry_encoding", "Atlas Map contains a geometry encoding."))
    if "<color" not in atlas_xml:
        findings.append(ReviewFinding("fail", "high", "atlas_color_encoding", "Atlas Map does not contain a color encoding."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_color_encoding", "Atlas Map contains a color encoding."))

    fixed_space_encodings = [
        node
        for node in atlas.findall(".//encoding")
        if node.attrib.get("type") == "space" and node.attrib.get("range-type") == "fixed"
    ]
    if len(fixed_space_encodings) < 2:
        findings.append(ReviewFinding("fail", "high", "atlas_fixed_extent", "Atlas Map does not have fixed x/y ranges for the custom atlas canvas."))
    elif not _atlas_extent_covers_insets(fixed_space_encodings):
        findings.append(ReviewFinding("fail", "high", "atlas_fixed_extent", "Atlas Map fixed extent is too narrow to include the custom atlas canvas and metro inset panels."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_fixed_extent", "Atlas Map has fixed x/y ranges covering the custom atlas canvas and metro inset panels."))

    for field in [
        "none:persistent_utilisation_classification:nk",
        "avg:funded_plans_per_1000_gap_from_national:qk",
        "avg:mean_plan_utilisation_gap_from_national:qk",
        "avg:active_providers_per_1000_funded_plans:qk",
    ]:
        if field not in atlas_xml:
            findings.append(ReviewFinding("fail", "high", "atlas_metric_contract", f"Atlas Map is missing field `{field}`."))
            break
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_metric_contract", "Atlas Map uses render-safe workbook fields for utilisation classification, funded-plan gap, utilisation gap and provider rate."))

    forbidden_atlas_tokens = [
        "atlas_default_metric_value",
        "funded_plans_per_1000_delta_from_national_mean",
        "mean_plan_utilisation_delta_from_national_median",
        "provider_saturation_delta_from_national_mean",
        "none:support_type:nk",
        "avg:supply_response_gap:qk",
    ]
    leaked_tokens = [token for token in forbidden_atlas_tokens if token in atlas_xml]
    if leaked_tokens:
        findings.append(ReviewFinding("fail", "high", "atlas_render_safe_field_contract", "Atlas Map references fields that are unsafe for the current Tableau datasource/geometry grain: " + ", ".join(leaked_tokens) + "."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_render_safe_field_contract", "Atlas Map avoids CSV-only fields and support-type grain fields that can prevent Tableau from rendering the geometry."))

    if "quarter_label" not in atlas_xml:
        findings.append(ReviewFinding("fail", "high", "atlas_quarter_filter_contract", "Atlas Map is missing the quarter label field needed for quarter filtering."))
    else:
        findings.append(ReviewFinding("pass", "info", "atlas_quarter_filter_contract", "Atlas Map includes quarter label context for quarter filtering."))

    atlas_dashboards = sorted(name for name, sheets in dashboard_sheets.items() if "Atlas Map" in sheets)
    if atlas_dashboards:
        findings.append(ReviewFinding("pass", "info", "atlas_dashboard_presence", f"Atlas Map appears in {len(atlas_dashboards)} dashboard(s)."))
    else:
        findings.append(ReviewFinding("fail", "critical", "atlas_dashboard_presence", "Atlas Map is not embedded in any dashboard."))

    return findings


def _atlas_extent_covers_insets(space_encodings: list[ET.Element]) -> bool:
    by_scope = {node.attrib.get("scope"): node for node in space_encodings}
    try:
        cols_min = float(by_scope["cols"].attrib["min"])
        cols_max = float(by_scope["cols"].attrib["max"])
        rows_min = float(by_scope["rows"].attrib["min"])
        rows_max = float(by_scope["rows"].attrib["max"])
    except (KeyError, TypeError, ValueError):
        return False
    if any(node.attrib.get("projection") == "EPSG:3857" for node in space_encodings):
        return False
    return cols_min <= 0 and cols_max >= 98 and rows_min <= -44 and rows_max >= 16


def _markdown_report(path: Path, findings: list[ReviewFinding]) -> str:
    verdict = "WEBSITE READY" if is_website_ready(findings) else "NOT WEBSITE READY"
    counts = {
        status: sum(1 for finding in findings if finding.status == status)
        for status in ["pass", "warn", "fail"]
    }
    lines = [
        "# Tableau Dashboard Implementation Review",
        "",
        f"Workbook: `{path}`",
        "",
        f"Verdict: **{verdict}**",
        "",
        f"- Pass: {counts['pass']}",
        f"- Warn: {counts['warn']}",
        f"- Fail: {counts['fail']}",
        "",
        "## Findings",
        "",
        "| Status | Severity | Check | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for finding in findings:
        detail = finding.detail.replace("|", "\\|")
        lines.append(f"| {finding.status} | {finding.severity} | `{finding.check}` | {detail} |")
    lines.extend(
        [
            "",
            "## Review Standard",
            "",
            "A website-ready workbook must open reliably, show a standalone atlas with render-safe benchmark gap context as the first geospatial view, move headline KPIs to national dashboards, support service-area detail review, and embed opportunity, advocacy, provider and service-type worksheets away from the atlas.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review the Tableau workbook against the gmdata publication standard.")
    parser.add_argument("workbook", nargs="?", default=str(WORKBOOK_PATH))
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args()

    findings = write_review(Path(args.workbook))
    if args.fail_on_critical and not is_website_ready(findings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
