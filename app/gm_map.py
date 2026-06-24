from __future__ import annotations

"""Custom SVG atlas renderer for NDIS service-area geographies.

The renderer separates dense metropolitan regions into insets so the national
view remains readable while still preserving clickable service-area polygons.
It is intentionally deterministic and dependency-light once the GeoDataFrame is
loaded, which makes the map easier to audit than a client-side tile workflow.
"""

import html
import math
from pathlib import Path
from urllib.parse import urlencode

import geopandas as gpd
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


GM_NAVY = "#061A2E"
GM_BORDER = "#D9D9D9"
GM_MUTED = "#566575"
GM_MISSING = "#D9D9D9"

LOW_COLOUR = "#B3261E"
MID_COLOUR = "#FFF7E6"
HIGH_COLOUR = "#2E7D32"


RIGHT_INSETS = {
    "Brisbane": [
        "Brisbane",
        "Beenleigh",
        "Caboolture/Strathpine",
        "Robina",
    ],
    "Sydney": [
        "Sydney",
        "North Sydney",
        "South Eastern Sydney",
        "Western Sydney",
        "Central Coast",
    ],
    "Melbourne": [
        "Inner East Melbourne",
        "Outer East Melbourne",
        "North East Melbourne",
        "Western Melbourne",
        "Brimbank Melton",
        "Hume Moreland",
        "Southern Melbourne",
        "Bayside Peninsula",
    ],
}

LEFT_INSETS = {
    "Perth": [
        "North Metro",
        "Central North Metro",
        "Central South Metro",
        "South East Metro",
        "South Metro",
    ],
}

BOTTOM_INSETS = {
    "Adelaide": [
        "Eastern Adelaide",
        "Northern Adelaide",
        "Southern Adelaide",
        "Western Adelaide",
        "Adelaide Hills",
        "Barossa, Light and Lower North",
    ],
}


def _safe_float(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except Exception:
        return None


def _format_number(value, digits: int = 2) -> str:
    value = _safe_float(value)
    if value is None:
        return "no data"
    return f"{value:,.{digits}f}"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(v)))):02x}" for v in rgb)


def _lerp_colour(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)

    return _rgb_to_hex(
        (
            ar + (br - ar) * t,
            ag + (bg - ag) * t,
            ab + (bb - ab) * t,
        )
    )


def _colour_for_score(value, domain: float) -> str:
    score = _safe_float(value)

    if score is None:
        return GM_MISSING

    if domain <= 0:
        domain = 1.0

    clipped = max(-domain, min(domain, score))

    if clipped < 0:
        return _lerp_colour(LOW_COLOUR, MID_COLOUR, (clipped + domain) / domain)

    if clipped > 0:
        return _lerp_colour(MID_COLOUR, HIGH_COLOUR, clipped / domain)

    return MID_COLOUR


def _metric_domain(values: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    numeric = numeric[numeric.notna()]
    numeric = numeric[~numeric.isin([float("inf"), float("-inf")])]

    if numeric.empty:
        return 1.0

    q = float(numeric.abs().quantile(0.96))

    if q <= 0 or math.isnan(q) or math.isinf(q):
        q = float(numeric.abs().max())

    if q <= 0 or math.isnan(q) or math.isinf(q):
        q = 1.0

    return q


def _padding_bounds(bounds, pad_ratio: float = 0.006):
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 1)
    height = max(max_y - min_y, 1)

    return (
        min_x - (width * pad_ratio),
        min_y - (height * pad_ratio),
        max_x + (width * pad_ratio),
        max_y + (height * pad_ratio),
    )


def _drop_remote_tasman_sea_island_parts(geo: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if geo.empty:
        return geo

    original_crs = geo.crs
    working = geo.copy()

    if working.crs is None:
        working = working.set_crs(epsg=4326)

    lonlat = working.to_crs(epsg=4326).copy()
    exploded = lonlat.explode(index_parts=False).reset_index(drop=True)

    if exploded.empty:
        return working

    centroids = exploded.geometry.representative_point()
    exploded["_centroid_lon"] = centroids.x
    exploded["_part_area_km2"] = exploded.to_crs(epsg=3577).geometry.area / 1_000_000

    remote_tasman_small_part = (
        (exploded["_centroid_lon"] > 154.5)
        & (exploded["_part_area_km2"] < 10000)
    )

    cleaned = exploded.loc[~remote_tasman_small_part, ["map_key", "geometry"]].copy()

    if cleaned.empty:
        return working

    cleaned = gpd.GeoDataFrame(cleaned, geometry="geometry", crs="EPSG:4326")

    if original_crs is not None:
        cleaned = cleaned.to_crs(original_crs)

    return cleaned


@st.cache_data(show_spinner=False)
def _load_projected_geo(geo_path_text: str) -> gpd.GeoDataFrame:
    geo = gpd.read_file(geo_path_text)

    if geo.crs is None:
        geo = geo.set_crs(epsg=4326)

    if "map_key" not in geo.columns:
        if "ndis_service_area" in geo.columns:
            geo["map_key"] = geo["ndis_service_area"].astype(str)
        else:
            raise ValueError("GeoJSON has no map_key or ndis_service_area column.")

    geo = geo[["map_key", "geometry"]].copy()
    geo["map_key"] = geo["map_key"].astype(str)
    geo = _drop_remote_tasman_sea_island_parts(geo)

    return geo.to_crs(epsg=3577)


def _project_geometry_to_path(geometry, bounds, map_x, map_y, map_w, map_h) -> str:
    min_x, min_y, max_x, max_y = bounds
    source_w = max(max_x - min_x, 1)
    source_h = max(max_y - min_y, 1)
    scale = min(map_w / source_w, map_h / source_h)

    rendered_w = source_w * scale
    rendered_h = source_h * scale
    offset_x = map_x + ((map_w - rendered_w) / 2)
    offset_y = map_y + ((map_h - rendered_h) / 2)

    def point_to_svg(x, y):
        sx = offset_x + ((x - min_x) * scale)
        sy = offset_y + ((max_y - y) * scale)
        return sx, sy

    def ring_to_path(coords):
        parts = []
        first = True

        for x, y in coords:
            sx, sy = point_to_svg(x, y)

            if first:
                parts.append(f"M {sx:.2f} {sy:.2f}")
                first = False
            else:
                parts.append(f"L {sx:.2f} {sy:.2f}")

        parts.append("Z")
        return " ".join(parts)

    def polygon_to_path(poly):
        pieces = [ring_to_path(poly.exterior.coords)]

        for interior in poly.interiors:
            pieces.append(ring_to_path(interior.coords))

        return " ".join(pieces)

    if geometry is None or geometry.is_empty:
        return ""

    if geometry.geom_type == "Polygon":
        return polygon_to_path(geometry)

    if geometry.geom_type == "MultiPolygon":
        return " ".join(
            polygon_to_path(poly)
            for poly in geometry.geoms
            if not poly.is_empty
        )

    if geometry.geom_type == "GeometryCollection":
        return " ".join(
            _project_geometry_to_path(part, bounds, map_x, map_y, map_w, map_h)
            for part in geometry.geoms
            if part.geom_type in {"Polygon", "MultiPolygon"}
        )

    return ""


def _query_for_service_area(service_area: str | None) -> str:
    if not service_area or str(service_area).lower() in {"nan", "none"}:
        return ""

    return urlencode(
        {
            "view": "Service area",
            "service_area": str(service_area),
        }
    )


def _legend_svg(metric_label: str, domain: float, x: int, y: int) -> str:
    steps = [
        (-1.00, "Lower relative position"),
        (-0.50, ""),
        (0.00, "Near benchmark"),
        (0.50, ""),
        (1.00, "Higher relative position"),
    ]

    rect_h = 34
    start_y = y + 88

    parts = [
        f"<text x='{x}' y='{y}' class='legend-title'>Legend</text>",
        f"<text x='{x}' y='{y + 28}' class='legend-subtitle'>{html.escape(metric_label)}</text>",
        f"<text x='{x}' y='{y + 54}' class='legend-note'>Tooltip values are benchmark differences.</text>",
    ]

    for index, (score, label) in enumerate(steps):
        value = score * domain
        colour = _colour_for_score(value, domain)
        yy = start_y + (index * rect_h)

        parts.append(
            f"<rect x='{x}' y='{yy}' width='48' height='{rect_h}' fill='{colour}' stroke='{GM_NAVY}' stroke-width='0.45'></rect>"
        )

        if label:
            parts.append(
                f"<text x='{x + 62}' y='{yy + 22}' class='legend-label'>{html.escape(label)}</text>"
            )

    no_data_y = start_y + (len(steps) * rect_h) + 24

    parts.append(
        f"<rect x='{x}' y='{no_data_y}' width='48' height='27' fill='{GM_MISSING}' stroke='{GM_NAVY}' stroke-width='0.45'></rect>"
    )
    parts.append(
        f"<text x='{x + 62}' y='{no_data_y + 20}' class='legend-label'>No data</text>"
    )
    parts.append(
        f"<text x='{x}' y='{no_data_y + 66}' class='legend-note'>Colour domain: ±{domain:,.2f}</text>"
    )
    parts.append(
        f"<text x='{x}' y='{no_data_y + 94}' class='legend-note'>Click any area for service-area page.</text>"
    )

    return "\n".join(parts)


def _path_elements_for_plot(
    plot,
    bounds,
    x,
    y,
    w,
    h,
    domain,
    metric,
    metric_label,
    stroke_width=1.05,
):
    elements = []

    for _, row in plot.iterrows():
        path = _project_geometry_to_path(row.geometry, bounds, x, y, w, h)

        if not path:
            continue

        fill = _colour_for_score(row.get("_map_score"), domain)

        service_area = row.get("ndis_service_area", row.get("map_key", ""))
        area_label = row.get("service_area_state_label", row.get("ndis_service_area", row.get("map_key", "")))
        remoteness = row.get("remoteness_category", "")
        position = row.get("benchmark_position", "")
        typology = row.get("market_position_typology", "")

        tooltip_lines = [
            str(area_label),
            f"Remoteness: {remoteness}",
            f"{metric_label}: {_format_number(row.get(metric))}",
            f"Plan coverage benchmark difference: {_format_number(row.get('funded_plans_per_1000_gap_from_national'))}",
            f"Utilisation benchmark difference: {_format_number(row.get('mean_plan_utilisation_gap_from_national'))}",
            f"Plan coverage change from reference: {_format_number(row.get('plans_per_1000_change_from_baseline'))}",
            f"Utilisation change from reference: {_format_number(row.get('mean_plan_utilisation_change_from_baseline'))}",
            f"Position: {position}",
            f"Typology: {typology}",
            "Click to open service-area page",
        ]

        tooltip = html.escape("\n".join(tooltip_lines))
        query = _query_for_service_area(str(service_area))

        if query:
            href = f"/?{query}"
            href_escaped = html.escape(href, quote=True)

            elements.append(
                f'<a href="{href_escaped}" target="_top">'
                f"<path d='{path}' fill='{fill}' stroke='{GM_NAVY}' stroke-width='{stroke_width}' "
                f"vector-effect='non-scaling-stroke' pointer-events='all'>"
                f"<title>{tooltip}</title>"
                f"</path>"
                f"</a>"
            )
        else:
            elements.append(
                f"<path d='{path}' fill='{fill}' stroke='{GM_NAVY}' stroke-width='{stroke_width}' "
                f"vector-effect='non-scaling-stroke' pointer-events='all'>"
                f"<title>{tooltip}</title>"
                f"</path>"
            )

    return "\n".join(elements)


def _inset_svg(name, plot, service_areas, x, y, w, h, domain, metric, metric_label, pad_ratio=0.0):
    subset = plot.loc[plot["ndis_service_area"].astype(str).isin(service_areas)].copy()

    if subset.empty:
        return f"""
        <g>
            <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" class="inset-panel"></rect>
            <text x="{x + 16}" y="{y + 32}" class="inset-title">{html.escape(name)}</text>
            <text x="{x + 16}" y="{y + 58}" class="inset-note">No matching service-area geometry</text>
        </g>
        """

    bounds = _padding_bounds(tuple(subset.total_bounds), pad_ratio=pad_ratio)

    paths = _path_elements_for_plot(
        subset,
        bounds,
        x + 8,
        y + 38,
        w - 16,
        h - 46,
        domain,
        metric,
        metric_label,
        stroke_width=2.05,
    )

    return f"""
    <g>
        <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" class="inset-panel"></rect>
        <text x="{x + 16}" y="{y + 31}" class="inset-title">{html.escape(name)}</text>
        {paths}
    </g>
    """


def render_australia_svg_map(
    filtered: pd.DataFrame,
    geo_path: Path,
    metric: str,
    metric_label: str,
    metric_info: dict,
    height: int = 1080,
) -> None:
    if filtered is None or filtered.empty:
        st.info("No data for selected filter.")
        return

    try:
        geo = _load_projected_geo(str(geo_path))
    except ValueError as exc:
        st.warning(str(exc))
        return

    plot = geo.merge(filtered.copy(), on="map_key", how="left", suffixes=("_boundary", ""))

    if "ndis_service_area" not in plot.columns:
        plot["ndis_service_area"] = plot["map_key"].astype(str)

    if plot.empty:
        st.warning("No matching geography rows for selected data.")
        return

    if "_map_score" not in plot.columns:
        plot["_map_score"] = pd.to_numeric(plot[metric], errors="coerce")

    plot["_map_score"] = pd.to_numeric(plot["_map_score"], errors="coerce")
    plot[metric] = pd.to_numeric(plot[metric], errors="coerce")

    matched_count = int(plot[metric].notna().sum())

    if matched_count == 0:
        st.warning("Boundary file loaded, but no rows matched current data values.")
        with st.expander("Atlas join diagnostic", expanded=False):
            st.write("Example boundary map_key values:", geo["map_key"].dropna().astype(str).head(20).tolist())
            st.write("Example filtered data map_key values:", filtered["map_key"].dropna().astype(str).head(20).tolist() if "map_key" in filtered.columns else "No map_key column")
        return

    domain = _metric_domain(plot["_map_score"])

    width = 2060
    svg_h = height

    legend_x = 24
    legend_y = 126

    main_x = 360
    main_y = 48
    main_w = 1040
    main_h = 815

    right_x = 1445
    right_w = 575
    right_y = 72
    right_gap = 22
    inset_bottom = svg_h - 30
    right_h = (inset_bottom - right_y - (right_gap * (len(RIGHT_INSETS) - 1))) / len(RIGHT_INSETS)

    bottom_gap = 20
    perth_x = 24
    perth_w = 290
    perth_h = 230
    perth_y = inset_bottom - perth_h

    adelaide_x = perth_x + perth_w + bottom_gap
    adelaide_y = perth_y
    adelaide_w = 430
    adelaide_h = perth_h

    national_excluded = set()
    for areas in RIGHT_INSETS.values():
        national_excluded.update(areas)
    for areas in LEFT_INSETS.values():
        national_excluded.update(areas)
    for areas in BOTTOM_INSETS.values():
        national_excluded.update(areas)

    national_plot = plot.loc[
        ~plot["ndis_service_area"].astype(str).isin(national_excluded)
    ].copy()

    if national_plot.empty:
        national_plot = plot.copy()

    bounds = _padding_bounds(tuple(national_plot.total_bounds), pad_ratio=0.012)

    national_paths = _path_elements_for_plot(
        national_plot,
        bounds,
        main_x,
        main_y,
        main_w,
        main_h,
        domain,
        metric,
        metric_label,
        stroke_width=1.15,
    )

    inset_parts = []

    for index, (name, areas) in enumerate(RIGHT_INSETS.items()):
        inset_parts.append(
            _inset_svg(
                name,
                plot,
                areas,
                right_x,
                right_y + index * (right_h + right_gap),
                right_w,
                right_h,
                domain,
                metric,
                metric_label,
                pad_ratio=0.10,
            )
        )

    for name, areas in LEFT_INSETS.items():
        inset_parts.append(
            _inset_svg(
                name,
                plot,
                areas,
                perth_x,
                perth_y,
                perth_w,
                perth_h,
                domain,
                metric,
                metric_label,
                pad_ratio=0.10,
            )
        )

    for name, areas in BOTTOM_INSETS.items():
        inset_parts.append(
            _inset_svg(
                name,
                plot,
                areas,
                adelaide_x,
                adelaide_y,
                adelaide_w,
                adelaide_h,
                domain,
                metric,
                metric_label,
                pad_ratio=0.08,
            )
        )

    legend = _legend_svg(metric_label, domain, legend_x, legend_y)

    description = html.escape(metric_info.get("definition", ""))

    svg = f"""
    <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 {width} {svg_h}"
        preserveAspectRatio="xMidYMin meet"
        class="atlas-svg"
    >
        <rect x="0" y="0" width="{width}" height="{svg_h}" rx="18" class="canvas"></rect>

        <text x="{width / 2}" y="44" text-anchor="middle" class="title">Australia service-area atlas: {html.escape(metric_label)}</text>
        <text x="{width / 2}" y="68" text-anchor="middle" class="subtitle">{description}</text>

        {legend}

        <g class="national-map">
            {national_paths}
        </g>

        {''.join(inset_parts)}
    </svg>
    """

    html_doc = f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                overflow: hidden;
                background: transparent;
                font-family: Arial, Helvetica, sans-serif;
            }}

            .atlas-frame {{
                width: 100%;
                max-width: 100%;
                margin: 0 auto;
            }}

            .atlas-svg {{
                width: 100%;
                height: auto;
                display: block;
            }}

            .canvas {{
                fill: #FFFFFF;
                stroke: {GM_BORDER};
                stroke-width: 1.2;
            }}

            .title {{
                fill: {GM_NAVY};
                font-size: 34px;
                font-weight: 850;
            }}

            .subtitle {{
                fill: {GM_MUTED};
                font-size: 12px;
                font-weight: 500;
            }}

            .legend-title {{
                fill: {GM_NAVY};
                font-size: 18px;
                font-weight: 850;
            }}

            .legend-subtitle {{
                fill: {GM_NAVY};
                font-size: 12px;
                font-weight: 850;
            }}

            .legend-label {{
                fill: {GM_NAVY};
                font-size: 11px;
                font-weight: 650;
            }}

            .legend-note {{
                fill: {GM_MUTED};
                font-size: 10px;
                font-weight: 520;
            }}

            .inset-panel {{
                fill: #FFFFFF;
                stroke: {GM_BORDER};
                stroke-width: 1.3;
            }}

            .inset-title {{
                fill: {GM_NAVY};
                font-size: 18px;
                font-weight: 850;
            }}

            .inset-note {{
                fill: {GM_MUTED};
                font-size: 10px;
            }}

            path {{
                cursor: pointer;
                transition: fill 120ms ease, stroke-width 120ms ease, opacity 120ms ease;
            }}

            a:hover path {{
                stroke-width: 3.2;
                stroke: #000000;
                opacity: 0.82;
            }}
        </style>
    </head>
    <body>
        <div class="atlas-frame">
            {svg}
        </div>
    </body>
    </html>
    """

    components.html(html_doc, height=height + 80, width=1720, scrolling=False)
