from __future__ import annotations

import argparse
import copy
import shutil
import xml.etree.ElementTree as ET
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
    _simplify_atlas_dashboards(stable_root)
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
