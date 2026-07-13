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
    "NDIS Saturation Monitor",
    "NDIS Saturation Tablet",
    "NDIS Saturation Phone",
    "NDIS Saturation Atlas Monitor",
    "NDIS Saturation Atlas Tablet",
    "NDIS Saturation Atlas Phone",
    "NDIS Saturation Service Area Monitor",
    "NDIS Saturation Service Area Tablet",
    "NDIS Saturation Service Area Phone",
    "NDIS Saturation Rankings Monitor",
    "NDIS Saturation Rankings Tablet",
    "NDIS Saturation Rankings Phone",
}

ATLAS_DASHBOARDS = {
    "NDIS Saturation Monitor",
    "NDIS Saturation Tablet",
    "NDIS Saturation Phone",
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

RANKING_DASHBOARDS = {
    "NDIS Saturation Rankings Monitor",
    "NDIS Saturation Rankings Tablet",
    "NDIS Saturation Rankings Phone",
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
    findings.extend(_schema_findings(root))
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


def _schema_findings(root: ET.Element) -> list[ReviewFinding]:
    findings = []
    simple_ids = [
        node.attrib.get("uuid")
        for node in root.findall(".//simple-id")
        if node.attrib.get("uuid")
    ]
    duplicate_ids = sorted({value for value in simple_ids if simple_ids.count(value) > 1})
    forbidden_tags = {
        "grid": len(root.findall(".//grid")),
        "nested_devicelayouts": len(root.findall(".//devicelayouts/devicelayouts")),
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
            findings.append(ReviewFinding("fail", "critical", f"forbidden_{tag}", f"Found {count} invalid <{tag}> element(s), which have caused Tableau load errors."))
        else:
            findings.append(ReviewFinding("pass", "info", f"forbidden_{tag}", f"No invalid <{tag}> elements found."))

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

    missing_rankings = sorted(name for name in RANKING_DASHBOARDS if "Ranked Service Areas" not in dashboard_sheets.get(name, set()))
    if missing_rankings:
        findings.append(ReviewFinding("warn", "medium", "ranking_dashboard_legacy_rankings", f"Ranking dashboards do not include the legacy Ranked Service Areas sheet: {', '.join(missing_rankings)}. This is acceptable only if opportunity rankings replace it."))
    else:
        findings.append(ReviewFinding("pass", "info", "ranking_dashboard_legacy_rankings", "Ranking dashboards include Ranked Service Areas."))
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

    ranking_coverage = set().union(*(dashboard_sheets.get(name, set()) for name in RANKING_DASHBOARDS))
    missing_ranking_opportunity = sorted(OPPORTUNITY_WORKSHEETS - ranking_coverage)
    if missing_ranking_opportunity:
        findings.append(
            ReviewFinding(
                "fail",
                "high",
                "opportunity_ranking_dashboard",
                "Ranking dashboards do not cover: " + ", ".join(missing_ranking_opportunity) + ".",
            )
        )
    else:
        findings.append(ReviewFinding("pass", "info", "opportunity_ranking_dashboard", "Ranking dashboards cover opportunity, advocacy, provider and service-type views."))
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

    atlas_dashboards = sorted(name for name, sheets in dashboard_sheets.items() if "Atlas Map" in sheets)
    if atlas_dashboards:
        findings.append(ReviewFinding("pass", "info", "atlas_dashboard_presence", f"Atlas Map appears in {len(atlas_dashboards)} dashboard(s)."))
    else:
        findings.append(ReviewFinding("fail", "critical", "atlas_dashboard_presence", "Atlas Map is not embedded in any dashboard."))
    return findings


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
            "A website-ready workbook must open reliably, show the atlas as the first geospatial view, support service-area detail review, and embed the opportunity, advocacy, provider and service-type worksheets in dashboard shells suitable for Tableau Public and `gmdata.au` embedding.",
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
