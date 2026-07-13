from __future__ import annotations

import argparse
import copy
import shutil
import xml.etree.ElementTree as ET
import uuid
from pathlib import Path

from . import config
from .tableau_workbook_review import WORKBOOK_PATH, is_website_ready, write_review


LAYOUT_SOURCE_PATH = WORKBOOK_PATH
CANDIDATE_PATH = config.OUTPUTS_DIR / "tableau" / "NDIS-Saturation-Atlas.website-ready-candidate.twb"
BACKUP_PATH = config.OUTPUTS_DIR / "tableau" / "NDIS-Saturation-Atlas.before-atlas-only-implementation.twb"

ATLAS_ONLY_DASHBOARDS = {
    "NDIS Saturation Atlas Monitor": {"maxwidth": "1600", "minwidth": "1600", "maxheight": "940", "minheight": "940"},
    "NDIS Saturation Atlas Tablet": {"maxwidth": "900", "minwidth": "900", "maxheight": "760", "minheight": "760"},
    "NDIS Saturation Atlas Phone": {"maxwidth": "390", "minwidth": "390", "maxheight": "520", "minheight": "520"},
}

ATLAS_FIXED_EXTENT_DEGREES = {
    "cols": {"min": "0.0", "max": "100.0"},
    "rows": {"min": "-60.0", "max": "20.0"},
}

STREAMLIT_STYLE_DASHBOARDS = [
    ("NDIS Saturation Atlas Monitor", (1600, 940), ["Atlas Map"]),
    ("NDIS Saturation Atlas Tablet", (900, 760), ["Atlas Map"]),
    ("NDIS Saturation Atlas Phone", (390, 520), ["Atlas Map"]),
    ("NDIS Saturation National Monitor", (1600, 1120), ["Headline KPIs", "Utilisation Trend", "Funded Plan Saturation Trend", "Support Type Mix", "Remoteness Summary", "Data Quality Flags"]),
    ("NDIS Saturation National Tablet", (900, 1580), ["Headline KPIs", "Utilisation Trend", "Funded Plan Saturation Trend", "Support Type Mix", "Remoteness Summary", "Data Quality Flags"]),
    ("NDIS Saturation National Phone", (390, 2260), ["Headline KPIs", "Utilisation Trend", "Funded Plan Saturation Trend", "Support Type Mix", "Remoteness Summary", "Data Quality Flags"]),
    ("NDIS Saturation Service Area Monitor", (1600, 1180), ["Utilisation Trend", "Funded Plan Saturation Trend", "Benchmark Gaps", "Support Type Mix", "Provider Data Availability", "Evidence Table", "Data Quality Flags"]),
    ("NDIS Saturation Service Area Tablet", (900, 1780), ["Utilisation Trend", "Funded Plan Saturation Trend", "Benchmark Gaps", "Support Type Mix", "Provider Data Availability", "Evidence Table", "Data Quality Flags"]),
    ("NDIS Saturation Service Area Phone", (390, 2500), ["Utilisation Trend", "Funded Plan Saturation Trend", "Benchmark Gaps", "Support Type Mix", "Provider Data Availability", "Evidence Table", "Data Quality Flags"]),
    ("NDIS Saturation Opportunities Monitor", (1600, 1280), ["Opportunity Priority", "Opportunity Matrix", "Advocacy Gaps", "Provider Underservice", "Service Type Opportunities", "Evidence Table"]),
    ("NDIS Saturation Opportunities Tablet", (900, 1960), ["Opportunity Priority", "Opportunity Matrix", "Advocacy Gaps", "Provider Underservice", "Service Type Opportunities", "Evidence Table"]),
    ("NDIS Saturation Opportunities Phone", (390, 2760), ["Opportunity Priority", "Opportunity Matrix", "Advocacy Gaps", "Provider Underservice", "Service Type Opportunities", "Evidence Table"]),
]


def rebuild_website_ready_candidate(
    stable_workbook: Path = WORKBOOK_PATH,
    layout_source: Path = LAYOUT_SOURCE_PATH,
    output_path: Path = CANDIDATE_PATH,
) -> Path:
    """Combine stable worksheet definitions with the website-ready dashboard layout."""

    stable_tree = ET.parse(stable_workbook)
    stable_root = stable_tree.getroot()
    layout_root = ET.parse(layout_source).getroot()

    _replace_child(stable_root, "dashboards", layout_root.find("dashboards"))
    _replace_dashboard_windows(stable_root.find("windows"), layout_root.find("windows"))
    _rebuild_streamlit_style_dashboards(stable_root)
    _configure_atlas_worksheet(stable_root)
    _remove_map_navigation_elements(stable_root)
    ET.indent(stable_tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stable_tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def promote_candidate(candidate_path: Path = CANDIDATE_PATH, workbook_path: Path = WORKBOOK_PATH) -> Path:
    """Promote a reviewed candidate workbook to the main Tableau workbook path."""

    if not candidate_path.exists():
        raise FileNotFoundError(candidate_path)
    findings = write_review(candidate_path)
    if not is_website_ready(findings):
        failed = [finding for finding in findings if finding.status == "fail" and finding.severity in {"critical", "high"}]
        details = "; ".join(f"{finding.check}: {finding.detail}" for finding in failed[:5])
        raise RuntimeError(f"Candidate is not website-ready: {details}")
    if workbook_path.exists():
        shutil.copy2(workbook_path, BACKUP_PATH)
    shutil.copy2(candidate_path, workbook_path)
    return workbook_path


def _replace_child(root: ET.Element, tag: str, replacement: ET.Element | None) -> None:
    if replacement is None:
        raise ValueError(f"Replacement <{tag}> element is missing.")
    current = root.find(tag)
    if current is None:
        raise ValueError(f"Stable workbook has no <{tag}> element.")
    children = list(root)
    index = children.index(current)
    root.remove(current)
    root.insert(index, copy.deepcopy(replacement))


def _replace_dashboard_windows(stable_windows: ET.Element | None, layout_windows: ET.Element | None) -> None:
    if stable_windows is None or layout_windows is None:
        raise ValueError("Both workbooks must contain a <windows> element.")
    for window in list(stable_windows):
        if window.attrib.get("class") == "dashboard":
            stable_windows.remove(window)
    for window in layout_windows.findall("window"):
        if window.attrib.get("class") == "dashboard":
            stable_windows.append(copy.deepcopy(window))


def _simplify_atlas_dashboards(root: ET.Element) -> None:
    """Keep standalone atlas dashboards focused on the map only."""

    dashboards = root.find("dashboards")
    windows = root.find("windows")
    if dashboards is None or windows is None:
        raise ValueError("Workbook is missing dashboards or windows.")

    for dashboard in dashboards.findall("dashboard"):
        name = dashboard.attrib.get("name", "")
        if name not in ATLAS_ONLY_DASHBOARDS:
            continue
        size = dashboard.find("size")
        if size is None:
            raise ValueError(f"Dashboard {name} is missing a <size> element.")
        size.attrib.update(ATLAS_ONLY_DASHBOARDS[name])
        _replace_child(dashboard, "zones", _atlas_only_zones(name))

    for window in windows.findall("window"):
        name = window.attrib.get("name", "")
        if window.attrib.get("class") != "dashboard" or name not in ATLAS_ONLY_DASHBOARDS:
            continue
        viewpoints = window.find("viewpoints")
        if viewpoints is not None:
            for viewpoint in list(viewpoints):
                if viewpoint.attrib.get("name") != "Atlas Map":
                    viewpoints.remove(viewpoint)
            if not list(viewpoints):
                viewpoints.append(_atlas_viewpoint())
        active = window.find("active")
        if active is not None:
            active.attrib["id"] = "2"


def _atlas_only_zones(name: str) -> ET.Element:
    zones = ET.Element("zones")
    canvas = ET.SubElement(
        zones,
        "zone",
        {
            "id": "1",
            "x": "0",
            "y": "0",
            "w": "100000",
            "h": "100000",
            "type-v2": "layout-basic",
            "friendly-name": f"{name} Canvas",
        },
    )
    ET.SubElement(canvas, "layout-cache", {"minheight": "100", "minwidth": "100", "type-h": "scalable", "type-w": "scalable"})
    atlas = ET.SubElement(canvas, "zone", {"id": "2", "name": "Atlas Map", "x": "0", "y": "0", "w": "100000", "h": "100000", "show-title": "false"})
    ET.SubElement(atlas, "layout-cache", {"minheight": "100", "minwidth": "100", "type-h": "scalable", "type-w": "scalable"})
    return zones


def _atlas_viewpoint() -> ET.Element:
    viewpoint = ET.Element("viewpoint", {"name": "Atlas Map"})
    highlight = ET.SubElement(viewpoint, "highlight")
    ET.SubElement(highlight, "color-one-way")
    return viewpoint


def _rebuild_streamlit_style_dashboards(root: ET.Element) -> None:
    dashboards = root.find("dashboards")
    windows = root.find("windows")
    if dashboards is None or windows is None:
        raise ValueError("Workbook is missing dashboards or windows.")
    source_dashboard = dashboards.find("dashboard")
    if source_dashboard is None:
        raise ValueError("Workbook has no dashboard template.")
    datasource_block = source_dashboard.find("datasources")
    devicelayouts = source_dashboard.find("devicelayouts")

    dashboards.clear()
    for name, size, sheets in STREAMLIT_STYLE_DASHBOARDS:
        dashboards.append(_dashboard(name, size, sheets, datasource_block, devicelayouts))

    for window in list(windows):
        if window.attrib.get("class") == "dashboard":
            windows.remove(window)
    for name, _, sheets in STREAMLIT_STYLE_DASHBOARDS:
        windows.append(_dashboard_window(name, sheets))


def _dashboard(name: str, size: tuple[int, int], sheets: list[str], datasource_block: ET.Element | None, devicelayouts: ET.Element | None) -> ET.Element:
    width, height = size
    dashboard = ET.Element("dashboard", {"name": name})
    style = ET.SubElement(dashboard, "style")
    style_rule = ET.SubElement(style, "style-rule", {"element": "dashboard"})
    ET.SubElement(style_rule, "format", {"attr": "background-color", "value": "#f5f7fb"})
    ET.SubElement(dashboard, "size", {"maxheight": str(height), "maxwidth": str(width), "minheight": str(height), "minwidth": str(width)})
    if datasource_block is not None:
        dashboard.append(copy.deepcopy(datasource_block))
    dashboard.append(_dashboard_zones(name, sheets))
    if devicelayouts is not None:
        dashboard.append(copy.deepcopy(devicelayouts))
    else:
        layouts = ET.SubElement(dashboard, "devicelayouts")
        ET.SubElement(layouts, "devicelayout", {"name": "Desktop"})
    ET.SubElement(dashboard, "simple-id", {"uuid": _stable_uuid(f"dashboard:{name}")})
    return dashboard


def _dashboard_zones(name: str, sheets: list[str]) -> ET.Element:
    zones = ET.Element("zones")
    canvas = ET.SubElement(
        zones,
        "zone",
        {
            "id": "1",
            "x": "0",
            "y": "0",
            "w": "100000",
            "h": "100000",
            "type-v2": "layout-basic",
            "friendly-name": f"{name} Canvas",
        },
    )
    ET.SubElement(canvas, "layout-cache", {"minheight": "100", "minwidth": "100", "type-h": "scalable", "type-w": "scalable"})
    if sheets == ["Atlas Map"]:
        ET.SubElement(canvas, "zone", {"id": "2", "name": "Atlas Map", "x": "0", "y": "0", "w": "100000", "h": "100000", "show-title": "false"})
        return zones

    columns = 2 if len(sheets) > 3 else 1
    gap = 1500
    margin = 1500
    available_w = 100000 - 2 * margin - (columns - 1) * gap
    zone_w = available_w // columns
    rows = (len(sheets) + columns - 1) // columns
    available_h = 100000 - 2 * margin - (rows - 1) * gap
    zone_h = available_h // rows
    for index, sheet in enumerate(sheets):
        row = index // columns
        col = index % columns
        attrs = {
            "id": str(index + 2),
            "name": sheet,
            "x": str(margin + col * (zone_w + gap)),
            "y": str(margin + row * (zone_h + gap)),
            "w": str(zone_w),
            "h": str(zone_h),
            "show-title": "true",
        }
        zone = ET.SubElement(canvas, "zone", attrs)
        ET.SubElement(zone, "layout-cache", {"minheight": "100", "minwidth": "100", "type-h": "scalable", "type-w": "scalable"})
        zone_style = ET.SubElement(zone, "zone-style")
        ET.SubElement(zone_style, "format", {"attr": "background-color", "value": "#ffffff"})
        ET.SubElement(zone_style, "format", {"attr": "border-color", "value": "#d7dde8"})
        ET.SubElement(zone_style, "format", {"attr": "border-style", "value": "solid"})
        ET.SubElement(zone_style, "format", {"attr": "border-width", "value": "1"})
        ET.SubElement(zone_style, "format", {"attr": "margin", "value": "8"})
        ET.SubElement(zone_style, "format", {"attr": "padding", "value": "8"})
    return zones


def _dashboard_window(name: str, sheets: list[str]) -> ET.Element:
    window = ET.Element("window", {"class": "dashboard", "name": name})
    viewpoints = ET.SubElement(window, "viewpoints")
    for sheet in sheets:
        viewpoints.append(_viewpoint(sheet))
    ET.SubElement(window, "active", {"id": "2"})
    ET.SubElement(window, "device-preview")
    ET.SubElement(window, "simple-id", {"uuid": _stable_uuid(f"window:{name}")})
    return window


def _viewpoint(name: str) -> ET.Element:
    viewpoint = ET.Element("viewpoint", {"name": name})
    highlight = ET.SubElement(viewpoint, "highlight")
    ET.SubElement(highlight, "color-one-way")
    return viewpoint


def _configure_atlas_worksheet(root: ET.Element) -> None:
    worksheet = next((node for node in root.findall(".//worksheets/worksheet") if node.attrib.get("name") == "Atlas Map"), None)
    if worksheet is None:
        return
    dependencies = worksheet.find(".//datasource-dependencies")
    encodings = worksheet.find(".//encodings")
    if dependencies is None or encodings is None:
        return

    _remove_dependency_fields(
        dependencies,
        [
            "[atlas_default_metric_value]",
            "[funded_plans_per_1000_delta_from_national_mean]",
            "[mean_plan_utilisation_delta_from_national_median]",
            "[provider_saturation_delta_from_national_mean]",
            "[support_type]",
            "[supply_response_gap]",
        ],
    )

    _ensure_column(dependencies, "Funded Plans Per 1000 Gap From National", "real", "[funded_plans_per_1000_gap_from_national]", "measure", "quantitative")
    _ensure_column(dependencies, "Mean Plan Utilisation Gap From National", "real", "[mean_plan_utilisation_gap_from_national]", "measure", "quantitative")
    _ensure_column(dependencies, "Active Providers Per 1000 Funded Plans", "real", "[active_providers_per_1000_funded_plans]", "measure", "quantitative")
    _ensure_column_instance(dependencies, "[funded_plans_per_1000_gap_from_national]", "Avg", "[avg:funded_plans_per_1000_gap_from_national:qk]", "quantitative")
    _ensure_column_instance(dependencies, "[mean_plan_utilisation_gap_from_national]", "Avg", "[avg:mean_plan_utilisation_gap_from_national:qk]", "quantitative")
    _ensure_column_instance(dependencies, "[active_providers_per_1000_funded_plans]", "Avg", "[avg:active_providers_per_1000_funded_plans:qk]", "quantitative")

    for color in encodings.findall("color"):
        encodings.remove(color)
    color = ET.Element("color", {"column": "[federated.0t2pdsf1ugut8y1dop0ji1sbsjij].[none:persistent_utilisation_classification:nk]"})
    encodings.insert(0, color)
    _remove_encoding_references(
        encodings,
        [
            "atlas_default_metric_value",
            "funded_plans_per_1000_delta_from_national_mean",
            "mean_plan_utilisation_delta_from_national_median",
            "provider_saturation_delta_from_national_mean",
            "support_type",
            "supply_response_gap",
        ],
    )
    for column in [
        "[federated.0t2pdsf1ugut8y1dop0ji1sbsjij].[avg:funded_plans_per_1000_gap_from_national:qk]",
        "[federated.0t2pdsf1ugut8y1dop0ji1sbsjij].[avg:mean_plan_utilisation_gap_from_national:qk]",
        "[federated.0t2pdsf1ugut8y1dop0ji1sbsjij].[avg:active_providers_per_1000_funded_plans:qk]",
    ]:
        if not any(node.attrib.get("column") == column for node in encodings.findall("tooltip")):
            ET.SubElement(encodings, "tooltip", {"column": column})
    _set_atlas_fixed_extent(worksheet)
    _set_atlas_map_washout(worksheet)


def _remove_map_navigation_elements(root: ET.Element) -> None:
    for parent in root.iter():
        for child in list(parent):
            if child.tag == "map-navigation":
                parent.remove(child)


def _ensure_column(dependencies: ET.Element, caption: str, datatype: str, name: str, role: str, col_type: str) -> None:
    if dependencies.find(f"./column[@name='{name}']") is None:
        ET.SubElement(dependencies, "column", {"caption": caption, "datatype": datatype, "name": name, "role": role, "type": col_type})


def _ensure_column_instance(dependencies: ET.Element, column: str, derivation: str, name: str, instance_type: str) -> None:
    if dependencies.find(f"./column-instance[@name='{name}']") is None:
        ET.SubElement(dependencies, "column-instance", {"column": column, "derivation": derivation, "name": name, "pivot": "key", "type": instance_type})


def _remove_dependency_fields(dependencies: ET.Element, columns: list[str]) -> None:
    for node in list(dependencies):
        if node.tag == "column" and node.attrib.get("name") in columns:
            dependencies.remove(node)
        elif node.tag == "column-instance" and node.attrib.get("column") in columns:
            dependencies.remove(node)


def _remove_encoding_references(encodings: ET.Element, tokens: list[str]) -> None:
    for node in list(encodings):
        column = node.attrib.get("column", "")
        if any(token in column for token in tokens):
            encodings.remove(node)


def _set_atlas_fixed_extent(worksheet: ET.Element) -> None:
    for encoding in worksheet.findall(".//encoding"):
        if encoding.attrib.get("type") != "space":
            continue
        scope = encoding.attrib.get("scope")
        if scope not in ATLAS_FIXED_EXTENT_DEGREES:
            continue
        encoding.attrib["range-type"] = "fixed"
        encoding.attrib.pop("projection", None)
        encoding.attrib["min"] = ATLAS_FIXED_EXTENT_DEGREES[scope]["min"]
        encoding.attrib["max"] = ATLAS_FIXED_EXTENT_DEGREES[scope]["max"]


def _set_atlas_map_washout(worksheet: ET.Element) -> None:
    style = worksheet.find(".//style")
    if style is None:
        return
    map_rule = style.find("./style-rule[@element='map']")
    if map_rule is None:
        map_rule = ET.SubElement(style, "style-rule", {"element": "map"})
    washout = map_rule.find("./format[@attr='washout']")
    if washout is None:
        washout = ET.SubElement(map_rule, "format", {"attr": "washout"})
    washout.attrib["value"] = "1.0"


def _stable_uuid(value: str) -> str:
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, value)).upper() + "}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the Tableau workbook using stable worksheets and website-ready dashboard layout.")
    parser.add_argument("--stable-workbook", default=str(WORKBOOK_PATH))
    parser.add_argument("--layout-source", default=str(LAYOUT_SOURCE_PATH))
    parser.add_argument("--output", default=str(CANDIDATE_PATH))
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    candidate = rebuild_website_ready_candidate(Path(args.stable_workbook), Path(args.layout_source), Path(args.output))
    write_review(candidate)
    if args.promote:
        promote_candidate(candidate)


if __name__ == "__main__":
    main()
