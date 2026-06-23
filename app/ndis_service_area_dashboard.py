from __future__ import annotations

from pathlib import Path
import json
import re
import html as html_lib

import altair as alt
import branca.colormap as cm
import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import box as shapely_box
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_all_available.csv"
SERVICE_TYPE_PATH = PROJECT_ROOT / "data" / "published" / "master_ndis_service_area_quarter_custom_service_type.csv"
GEO_PATH = PROJECT_ROOT / "outputs" / "powerbi_map" / "ndis_service_area_boundaries_simplified.geojson"

BASELINE_QUARTER_DEFAULT = "2024Q2"

METRIC_LABELS = {
    "funded_plans_per_1000_gap_from_national": "Funded plans per 1,000 population: gap from national",
    "mean_plan_utilisation_gap_from_national": "Mean plan utilisation: gap from national",
    "plans_per_1000_change_from_baseline": "Change in funded plans per 1,000 population",
    "mean_plan_utilisation_change_from_baseline": "Change in mean plan utilisation",
}

METRIC_SHORT_LABELS = {
    "funded_plans_per_1000_gap_from_national": "Plans per 1,000 gap",
    "mean_plan_utilisation_gap_from_national": "Utilisation gap",
    "plans_per_1000_change_from_baseline": "Plans per 1,000 change",
    "mean_plan_utilisation_change_from_baseline": "Utilisation change",
}

GM_NAVY = "#071B33"
GM_NAVY_2 = "#0B2A4A"
GM_ORANGE = "#F5A400"
GM_ORANGE_2 = "#FFB82E"
GM_YELLOW = "#FFD166"
GM_BG = "#FFFFFF"
GM_SOFT_BG = "#FFF7E6"
GM_GREY = "#D9D9D9"
GM_FONT = "Segoe UI"
GM_DIVERGING = [GM_NAVY, "#F8F6EF", GM_ORANGE]

GM_REMOTENESS_SCALE = alt.Scale(
    domain=[
        "Major Cities of Australia",
        "Inner Regional Australia",
        "Outer Regional Australia",
        "Remote Australia",
        "Very Remote Australia",
        "Unknown",
    ],
    range=[
        GM_NAVY,
        "#174A7A",
        "#3B6F9E",
        GM_ORANGE,
        GM_YELLOW,
        GM_GREY,
    ],
)

METRIC_HELP = {
    "funded_plans_per_1000_gap_from_national": "National benchmark minus service-area funded plans per 1,000 population.",
    "mean_plan_utilisation_gap_from_national": "National benchmark minus service-area mean plan utilisation.",
    "plans_per_1000_change_from_baseline": "Selected quarter minus baseline quarter for funded plans per 1,000 population.",
    "mean_plan_utilisation_change_from_baseline": "Selected quarter minus baseline quarter for mean plan utilisation.",
}

REMOTENESS_ORDER = [
    "Major Cities of Australia",
    "Inner Regional Australia",
    "Outer Regional Australia",
    "Remote Australia",
    "Very Remote Australia",
    "Unknown",
]

SERVICE_TYPE_ORDER = [
    "Capital",
    "Community Participation Care",
    "Early Childhood Supports",
    "Group Centre Care",
    "High Needs Personal Care",
    "Other Capacity Building",
    "Other Core",
    "Personal Care",
    "Plan Management",
    "Shared Accommodation Supports",
    "Support Coordination",
    "Therapy",
]

TOOLTIP_FIELDS = [
    "ndis_service_area",
    "quarter",
    "remoteness_category",
    "service_type_filter_label",
    "included_service_type_share",
    "population_2025_erp",
    "funded_plans_count",
    "service_area_funded_plans_per_1000_population_2025_erp",
    "funded_plans_per_1000_gap_from_national",
    "service_area_mean_plan_utilisation",
    "mean_plan_utilisation_gap_from_national",
    "plans_per_1000_change_from_baseline",
    "mean_plan_utilisation_change_from_baseline",
    "benchmark_position",
]

TOOLTIP_ALIASES = [
    "Service area",
    "Quarter",
    "Remoteness",
    "Service type filter",
    "Included payment share",
    "Population 2025 ERP",
    "Proxy funded plans",
    "Plans per 1,000",
    "Plans per 1,000 gap",
    "Mean utilisation",
    "Utilisation gap",
    "Plans per 1,000 change",
    "Utilisation change",
    "Benchmark position",
]

AUSTRALIA_BOUNDS = [[-43.4, 112.9], [-9.8, 154.4]]

INSET_BOUNDS = {
    "Brisbane / Sunshine Coast": [[-28.15, 152.45], [-26.10, 153.45]],
    "Sydney / Illawarra / Hunter": [[-35.05, 150.00], [-32.20, 152.05]],
    "Melbourne / Geelong": [[-38.55, 143.95], [-37.25, 145.75]],
    "Adelaide": [[-35.40, 138.30], [-34.35, 138.95]],
    "Perth": [[-32.60, 115.45], [-31.35, 116.25]],
}

ATLAS_GAP = 14
ATLAS_COMPONENT_HEIGHT = 2200
SVG_CELL = 1000


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    data = pd.read_csv(DATA_PATH)

    if "quarter" not in data.columns and "reporting_quarter" in data.columns:
        data["quarter"] = data["reporting_quarter"]

    alias_map = {
        "ndis_service_area": "map_key",
        "funded_plans_per_1000_population_2025_erp": "service_area_funded_plans_per_1000_population_2025_erp",
        "mean_plan_utilisation": "service_area_mean_plan_utilisation",
        "mean_plan_funding": "service_area_mean_plan_funding",
        "funded_plans_count": "service_area_funded_plans_count",
    }

    for source_col, app_col in alias_map.items():
        if app_col not in data.columns and source_col in data.columns:
            data[app_col] = data[source_col]

    for col in [
        "service_area_funded_plans_per_1000_population_2025_erp",
        "service_area_mean_plan_utilisation",
        "funded_plans_count",
        "population_2025_erp",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    keep = [
        "quarter",
        "map_key",
        "ndis_service_area",
        "remoteness_category",
        "population_2025_erp",
        "funded_plans_count",
        "service_area_funded_plans_per_1000_population_2025_erp",
        "service_area_mean_plan_utilisation",
    ]
    keep = [c for c in keep if c in data.columns]

    data = data[keep].drop_duplicates(["quarter", "map_key"]).copy()
    data = data.loc[~data["ndis_service_area"].isin(["ALL", "Other"])].copy()

    return data


@st.cache_data(show_spinner=False)
def load_service_type_data() -> pd.DataFrame:
    if not SERVICE_TYPE_PATH.exists():
        raise FileNotFoundError(
            f"Service type file not found: {SERVICE_TYPE_PATH}. "
            f"Build master_ndis_service_area_quarter_custom_service_type.csv first."
        )

    st_data = pd.read_csv(SERVICE_TYPE_PATH, low_memory=False)

    required = {
        "quarter",
        "ndis_service_area",
        "service_type",
        "service_type_payment_share_of_area_total",
    }
    missing = required - set(st_data.columns)

    if missing:
        raise ValueError(
            "Service type file missing required columns: "
            + ", ".join(sorted(missing))
        )

    st_data = st_data.loc[~st_data["ndis_service_area"].isin(["ALL", "Other"])].copy()

    for col in [
        "service_type_payment_share_of_area_total",
        "service_type_payment_amount",
    ]:
        if col in st_data.columns:
            st_data[col] = pd.to_numeric(st_data[col], errors="coerce")

    return st_data


@st.cache_data(show_spinner=False)
def load_geo() -> gpd.GeoDataFrame:
    return gpd.read_file(GEO_PATH).to_crs(epsg=4326)


def compute_service_type_shares(
    service_type_data: pd.DataFrame,
    service_type_mode: str,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> pd.DataFrame:
    base = service_type_data.copy()

    all_service_types = sorted(
        [x for x in base["service_type"].dropna().astype(str).unique() if x not in {"", "nan"}],
        key=lambda x: SERVICE_TYPE_ORDER.index(x) if x in SERVICE_TYPE_ORDER else 999
    )

    if service_type_mode == "All service types" or not selected_service_types:
        included = all_service_types
    else:
        selected_set = set(selected_service_types)

        if exclude_selected:
            included = [x for x in all_service_types if x not in selected_set]
        else:
            included = [x for x in all_service_types if x in selected_set]

    included_set = set(included)

    selected = base.loc[base["service_type"].isin(included_set)].copy()

    grouped = (
        selected.groupby(["quarter", "ndis_service_area"], dropna=False)
        .agg(
            included_service_type_share=("service_type_payment_share_of_area_total", "sum"),
            included_service_type_payment_amount=("service_type_payment_amount", "sum")
                if "service_type_payment_amount" in selected.columns
                else ("service_type_payment_share_of_area_total", "size"),
        )
        .reset_index()
    )

    if "included_service_type_payment_amount" not in grouped.columns:
        grouped["included_service_type_payment_amount"] = pd.NA

    grouped["included_service_type_share"] = pd.to_numeric(
        grouped["included_service_type_share"],
        errors="coerce",
    ).clip(lower=0, upper=1)

    if service_type_mode == "All service types" or len(included) == len(all_service_types):
        label = "All service types"
    elif exclude_selected:
        label = "All except: " + ", ".join(selected_service_types)
    else:
        label = ", ".join(selected_service_types)

    grouped["service_type_filter_label"] = label
    grouped["service_types_included_count"] = len(included)

    return grouped


def apply_service_type_filter_to_metrics(
    raw_data: pd.DataFrame,
    service_type_shares: pd.DataFrame,
) -> pd.DataFrame:
    data = raw_data.merge(
        service_type_shares,
        on=["quarter", "ndis_service_area"],
        how="left",
    ).copy()

    data["included_service_type_share"] = pd.to_numeric(
        data["included_service_type_share"],
        errors="coerce",
    ).fillna(1.0).clip(lower=0, upper=1)

    data["service_type_filter_label"] = data["service_type_filter_label"].fillna("All service types")

    # Statistical correction:
    # Payment-share filtering can support a proxy for service-type payment intensity.
    # It should not be treated as a direct service-type participant denominator.
    # Plans per 1,000 and funded-plan count remain payment-share-weighted proxies.
    data["funded_plans_count"] = (
        pd.to_numeric(data["funded_plans_count"], errors="coerce")
        * data["included_service_type_share"]
    )

    data["service_area_funded_plans_per_1000_population_2025_erp"] = (
        pd.to_numeric(
            data["service_area_funded_plans_per_1000_population_2025_erp"],
            errors="coerce",
        )
        * data["included_service_type_share"]
    )

    # Do not multiply mean utilisation by payment share.
    # A mean utilisation rate scaled by payment share becomes a hybrid measure,
    # not a utilisation rate. Keep utilisation as whole-area context.
    data["service_area_mean_plan_utilisation_context"] = pd.to_numeric(
        data["service_area_mean_plan_utilisation"],
        errors="coerce",
    )

    data["service_area_mean_plan_utilisation"] = data[
        "service_area_mean_plan_utilisation_context"
    ]

    national_by_quarter = (
        data.dropna(subset=["funded_plans_count", "population_2025_erp"])
        .groupby("quarter", dropna=False)
        .apply(
            lambda g: (
                pd.to_numeric(g["funded_plans_count"], errors="coerce").sum()
                / pd.to_numeric(g["population_2025_erp"], errors="coerce").sum()
                * 1000
            )
            if pd.to_numeric(g["population_2025_erp"], errors="coerce").sum() > 0
            else pd.NA
        )
        .rename("national_funded_plans_per_1000_population_2025_erp")
        .reset_index()
    )

    data = data.merge(national_by_quarter, on="quarter", how="left")

    data["funded_plans_per_1000_gap_from_national"] = (
        data["national_funded_plans_per_1000_population_2025_erp"]
        - data["service_area_funded_plans_per_1000_population_2025_erp"]
    )

    # Utilisation benchmark is reweighted by the included service-type payment share,
    # but the service-area value remains the actual whole-area mean utilisation.
    def weighted_utilisation(g: pd.DataFrame):
        values = pd.to_numeric(
            g["service_area_mean_plan_utilisation_context"],
            errors="coerce",
        )
        weights = pd.to_numeric(g["funded_plans_count"], errors="coerce")
        mask = values.notna() & weights.notna() & (weights > 0)

        if mask.sum() == 0:
            return pd.NA

        return (values[mask] * weights[mask]).sum() / weights[mask].sum()

    national_util_by_quarter = (
        data.groupby("quarter", dropna=False)
        .apply(weighted_utilisation)
        .rename("national_mean_plan_utilisation")
        .reset_index()
    )

    data = data.merge(national_util_by_quarter, on="quarter", how="left")

    data["mean_plan_utilisation_gap_from_national"] = (
        data["national_mean_plan_utilisation"]
        - data["service_area_mean_plan_utilisation"]
    )

    data["statistical_method_note"] = (
        "Service-type filtering is payment-share based. Plans per 1,000 and funded-plan counts "
        "are payment-share-weighted proxies. Mean utilisation is retained as a whole-area "
        "context measure because multiplying a mean by payment share would not produce a "
        "valid utilisation rate."
    )

    return data


@st.cache_data(show_spinner=False)
def add_change_measures(data: pd.DataFrame, baseline_quarter: str) -> pd.DataFrame:
    data = data.copy()

    baseline = data.loc[data["quarter"] == baseline_quarter].copy()

    baseline = baseline[
        [
            "map_key",
            "service_area_funded_plans_per_1000_population_2025_erp",
            "service_area_mean_plan_utilisation",
        ]
    ].rename(
        columns={
            "service_area_funded_plans_per_1000_population_2025_erp": "baseline_plans_per_1000",
            "service_area_mean_plan_utilisation": "baseline_mean_plan_utilisation",
        }
    )

    data = data.merge(baseline, on="map_key", how="left")

    data["plans_per_1000_change_from_baseline"] = (
        data["service_area_funded_plans_per_1000_population_2025_erp"]
        - data["baseline_plans_per_1000"]
    )

    data["mean_plan_utilisation_change_from_baseline"] = (
        data["service_area_mean_plan_utilisation"]
        - data["baseline_mean_plan_utilisation"]
    )

    data["baseline_quarter"] = baseline_quarter

    return data


def classify_position(value: float, metric: str) -> str:
    if pd.isna(value):
        return "No data"

    if metric in [
        "funded_plans_per_1000_gap_from_national",
        "mean_plan_utilisation_gap_from_national",
    ]:
        if value > 0:
            return "Below national benchmark"
        if value < 0:
            return "Above national benchmark"
        return "At national benchmark"

    if value > 0:
        return "Increase since baseline"
    if value < 0:
        return "Decrease since baseline"
    return "No change since baseline"


@st.cache_data(show_spinner=False)
def prepare_filtered_data(
    data: pd.DataFrame,
    quarter: str,
    selected_remoteness: list[str],
    metric: str,
) -> pd.DataFrame:
    filtered = data.loc[data["quarter"] == quarter].copy()

    if selected_remoteness and "remoteness_category" in filtered.columns:
        filtered = filtered.loc[
            filtered["remoteness_category"].isin(selected_remoteness)
        ].copy()

    filtered["benchmark_position"] = filtered[metric].apply(
        lambda value: classify_position(value, metric)
    )

    return filtered


def merge_geo_data(
    geo: gpd.GeoDataFrame,
    filtered: pd.DataFrame,
) -> gpd.GeoDataFrame:
    merged = geo.merge(
        filtered,
        on="map_key",
        how="left",
        suffixes=("_boundary", ""),
    )

    if "ndis_service_area" not in merged.columns and "ndis_service_area_boundary" in merged.columns:
        merged["ndis_service_area"] = merged["ndis_service_area_boundary"]

    return merged


# GOOD MEASURE STATE LABEL PATCH
SERVICE_AREA_STATE_FALLBACK = {
    "ACT": "ACT",
    "Adelaide Hills": "SA",
    "Barkly": "NT",
    "Barossa, Light and Lower North": "SA",
    "Barwon": "VIC",
    "Bayside Peninsula": "VIC",
    "Beenleigh": "QLD",
    "Brimbank Melton": "VIC",
    "Brisbane": "QLD",
    "Bundaberg": "QLD",
    "Caboolture/Strathpine": "QLD",
    "Cairns": "QLD",
    "Central Australia": "NT",
    "Central Coast": "NSW",
    "Central Highlands": "VIC",
    "Central North Metro": "WA",
    "Central South Metro": "WA",
    "Darwin Remote": "NT",
    "Darwin Urban": "NT",
    "East Arnhem": "NT",
    "Eastern Adelaide": "SA",
    "Eyre and Western": "SA",
    "Far North (SA)": "SA",
    "Far West": "NSW",
    "Fleurieu and Kangaroo Island": "SA",
    "Goldfields-Esperance": "WA",
    "Goulburn": "VIC",
    "Great Southern": "WA",
    "Hume Moreland": "VIC",
    "Hunter New England": "NSW",
    "Illawarra Shoalhaven": "NSW",
    "Inner East Melbourne": "VIC",
    "Inner Gippsland": "VIC",
    "Ipswich": "QLD",
    "Katherine": "NT",
    "Kimberley-Pilbara": "WA",
    "Limestone Coast": "SA",
    "Loddon": "VIC",
    "Mackay": "QLD",
    "Mallee": "VIC",
    "Maroochydore": "QLD",
    "Maryborough": "QLD",
    "Mid North Coast": "NSW",
    "Midwest-Gascoyne": "WA",
    "Murray and Mallee": "SA",
    "Murrumbidgee": "NSW",
    "Nepean Blue Mountains": "NSW",
    "North East Melbourne": "VIC",
    "North East Metro": "WA",
    "North Metro": "WA",
    "North Sydney": "NSW",
    "Northern Adelaide": "SA",
    "Northern NSW": "NSW",
    "Outer East Melbourne": "VIC",
    "Outer Gippsland": "VIC",
    "Ovens Murray": "VIC",
    "Robina": "QLD",
    "Rockhampton": "QLD",
    "South East Metro": "WA",
    "South Eastern Sydney": "NSW",
    "South Metro": "WA",
    "South West": "WA",
    "South Western Sydney": "NSW",
    "Southern Adelaide": "SA",
    "Southern Melbourne": "VIC",
    "Southern NSW": "NSW",
    "Sydney": "NSW",
    "TAS North": "TAS",
    "TAS North West": "TAS",
    "TAS South East": "TAS",
    "TAS South West": "TAS",
    "Toowoomba": "QLD",
    "Townsville": "QLD",
    "Western Adelaide": "SA",
    "Western District": "VIC",
    "Western Melbourne": "VIC",
    "Western NSW": "NSW",
    "Western Sydney": "NSW",
    "Wheat Belt": "WA",
    "Yorke and Mid North": "SA",
}


def add_state_labels(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()

    if "ndis_service_area" not in data.columns:
        return data

    data["state_acronym"] = data["ndis_service_area"].map(SERVICE_AREA_STATE_FALLBACK)
    data["state_acronym"] = data["state_acronym"].fillna("UNK")

    data["service_area_state_label"] = (
        data["ndis_service_area"].astype(str)
        + " ("
        + data["state_acronym"].astype(str)
        + ")"
    )

    return data



def metric_domain(df: pd.DataFrame, metric: str) -> tuple[float, float]:
    values = pd.to_numeric(df[metric], errors="coerce")
    values = values[pd.notna(values)]
    values = values[values.apply(lambda x: x != float("inf") and x != float("-inf"))]

    if values.empty:
        return -1.0, 1.0

    min_observed = float(values.min())
    max_observed = float(values.max())
    max_abs = max(abs(min_observed), abs(max_observed))

    if pd.isna(max_abs) or max_abs == 0 or max_abs in [float("inf"), float("-inf")]:
        max_abs = 1.0

    return -float(max_abs), float(max_abs)


def svg_escape(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return html_lib.escape(str(value), quote=True)


def format_tooltip_number(value, digits: int = 2) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
        return f"{float(value):,.{digits}f}"
    except Exception:
        return ""


def format_tooltip_integer(value) -> str:
    try:
        if value is None or pd.isna(value):
            return ""
        return f"{float(value):,.0f}"
    except Exception:
        return ""


def hex_to_rgb(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(v))):02x}" for v in rgb)


def lerp_colour(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    return rgb_to_hex((
        ar + (br - ar) * t,
        ag + (bg - ag) * t,
        ab + (bb - ab) * t,
    ))


def svg_colour_for_value(value, min_val: float, max_val: float) -> str:
    try:
        if value is None or pd.isna(value):
            return GM_GREY
        value = float(value)
    except Exception:
        return GM_GREY

    if value == float("inf") or value == float("-inf"):
        return GM_GREY

    zero_colour = "#F8F6EF"

    if min_val < 0 and value < 0:
        return lerp_colour(GM_NAVY, zero_colour, (value - min_val) / (0 - min_val))

    if max_val > 0 and value > 0:
        return lerp_colour(zero_colour, GM_ORANGE, value / max_val)

    return zero_colour


def projected_bounds_from_lonlat(bounds: list[list[float]]) -> tuple[float, float, float, float]:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3577", always_xy=True)
    south, west = bounds[0]
    north, east = bounds[1]
    corners = [
        transformer.transform(west, south),
        transformer.transform(west, north),
        transformer.transform(east, south),
        transformer.transform(east, north),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


def projected_point_to_svg(
    x: float,
    y: float,
    bounds_projected: tuple[float, float, float, float],
    width: float,
    height: float,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bounds_projected
    source_width = max_x - min_x
    source_height = max_y - min_y

    if source_width == 0 or source_height == 0:
        return 0.0, 0.0

    padding = width * 0.018 if width >= height else height * 0.018
    target_width = max(width - (2 * padding), 1)
    target_height = max(height - (2 * padding), 1)

    scale = min(target_width / source_width, target_height / source_height)
    rendered_width = source_width * scale
    rendered_height = source_height * scale
    offset_x = (width - rendered_width) / 2
    offset_y = (height - rendered_height) / 2

    svg_x = offset_x + ((x - min_x) * scale)
    svg_y = offset_y + ((max_y - y) * scale)

    return svg_x, svg_y


def polygon_to_svg_path(
    polygon,
    bounds_projected: tuple[float, float, float, float],
    width: float,
    height: float,
) -> str:
    parts = []

    def ring_to_path(coords):
        ring_parts = []
        first = True

        for x, y in coords:
            sx, sy = projected_point_to_svg(x, y, bounds_projected, width, height)
            if first:
                ring_parts.append(f"M {sx:.2f} {sy:.2f}")
                first = False
            else:
                ring_parts.append(f"L {sx:.2f} {sy:.2f}")

        ring_parts.append("Z")
        return " ".join(ring_parts)

    if polygon.exterior is not None:
        parts.append(ring_to_path(polygon.exterior.coords))

    for interior in polygon.interiors:
        parts.append(ring_to_path(interior.coords))

    return " ".join(parts)


def geometry_to_svg_path(
    geometry,
    bounds_projected: tuple[float, float, float, float],
    width: float,
    height: float,
) -> str:
    if geometry is None or geometry.is_empty:
        return ""

    if geometry.geom_type == "Polygon":
        return polygon_to_svg_path(geometry, bounds_projected, width, height)

    if geometry.geom_type == "MultiPolygon":
        return " ".join(
            polygon_to_svg_path(poly, bounds_projected, width, height)
            for poly in geometry.geoms
            if poly is not None and not poly.is_empty
        )

    if geometry.geom_type == "GeometryCollection":
        return " ".join(
            geometry_to_svg_path(part, bounds_projected, width, height)
            for part in geometry.geoms
            if part is not None and not part.is_empty
        )

    return ""


def build_svg_tooltip(row: pd.Series, metric: str) -> str:
    rows = [
        ("Service area", row.get("ndis_service_area")),
        ("Quarter", row.get("quarter")),
        ("Remoteness", row.get("remoteness_category")),
        ("Service type filter", row.get("service_type_filter_label")),
        ("Included payment share", format_tooltip_number(row.get("included_service_type_share"), 3)),
        ("Population", format_tooltip_integer(row.get("population_2025_erp"))),
        ("Proxy funded plans", format_tooltip_integer(row.get("funded_plans_count"))),
        ("Plans per 1,000", format_tooltip_number(row.get("service_area_funded_plans_per_1000_population_2025_erp"))),
        ("Plans gap", format_tooltip_number(row.get("funded_plans_per_1000_gap_from_national"))),
        ("Mean utilisation", format_tooltip_number(row.get("service_area_mean_plan_utilisation"))),
        ("Utilisation gap", format_tooltip_number(row.get("mean_plan_utilisation_gap_from_national"))),
        ("Selected metric", format_tooltip_number(row.get(metric))),
        ("Click", "Open service-area dashboard"),
    ]

    html_rows = []

    for label, value in rows:
        if value is None or value == "":
            continue

        html_rows.append(
            f"<div class='tooltip-row'>"
            f"<span class='tooltip-label'>{svg_escape(label)}</span>"
            f"<span class='tooltip-value'>{svg_escape(value)}</span>"
            f"</div>"
        )

    return "".join(html_rows)


def make_svg_tile(
    gdf_projected: gpd.GeoDataFrame,
    metric: str,
    bounds: list[list[float]],
    width: int,
    height: int,
    tile_label: str | None = None,
) -> str:
    min_val, max_val = metric_domain(gdf_projected, metric)
    bounds_projected = projected_bounds_from_lonlat(bounds)
    min_x, min_y, max_x, max_y = bounds_projected
    tile_box = shapely_box(min_x, min_y, max_x, max_y)

    paths = []
    tile_gdf = gdf_projected.loc[gdf_projected.geometry.intersects(tile_box)].copy()

    for _, row in tile_gdf.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        try:
            geom = geom.intersection(tile_box)
        except Exception:
            continue

        if geom is None or geom.is_empty:
            continue

        path_data = geometry_to_svg_path(
            geometry=geom,
            bounds_projected=bounds_projected,
            width=width,
            height=height,
        )

        if not path_data:
            continue

        fill = gm_colour_for_metric(row.get(metric), min_val, max_val, metric)
        service_area_raw = row.get("ndis_service_area")
        service_area = svg_escape(service_area_raw)
        service_area_url = svg_escape(make_service_area_url(service_area_raw))
        tooltip = build_svg_tooltip(row, metric)

        service_href = make_service_area_href(row.get("ndis_service_area"))


        paths.append(
            f"<a href='{svg_escape(service_href)}' target='_blank' class='service-area-link'>"
            f"<path "
            f"d='{path_data}' "
            f"class='service-area-path' "
            f"fill='{fill}' "
            f"stroke='{GM_NAVY}' "
            f"stroke-width='1.1' "
            f"vector-effect='non-scaling-stroke' "
            f"data-service='{service_area}' "
            f"data-click-url='{service_area_url}' "
            f"onclick=\"window.parent.location.href=this.getAttribute('data-click-url')\" "
            f"data-tooltip='{svg_escape(tooltip)}'"
            f"></path>"
            f"</a>"


        )

    label_html = ""
    if tile_label:
        label_html = f"<div class='atlas-label'>{svg_escape(tile_label)}</div>"

    clip_id = "clip_" + re.sub(r"[^a-zA-Z0-9]+", "_", tile_label or "main").strip("_")

    return f"""
    {label_html}
    <svg class="atlas-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet">
        <defs>
            <clipPath id="{clip_id}">
                <rect x="0" y="0" width="{width}" height="{height}"></rect>
            </clipPath>
        </defs>
        <rect x="0" y="0" width="{width}" height="{height}" fill="transparent"></rect>
        <g clip-path="url(#{clip_id})">
            {''.join(paths)}
        </g>
    </svg>
    """


def render_map_atlas(
    merged: gpd.GeoDataFrame,
    metric: str,
) -> None:
    gdf = merged.copy()

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:3577")
    gdf[metric] = pd.to_numeric(gdf[metric], errors="coerce")

    main_svg = make_svg_tile(gdf, metric, AUSTRALIA_BOUNDS, SVG_CELL * 2, SVG_CELL * 2, None)
    brisbane_svg = make_svg_tile(gdf, metric, INSET_BOUNDS["Brisbane / Sunshine Coast"], SVG_CELL, SVG_CELL, "Brisbane / Sunshine Coast")
    sydney_svg = make_svg_tile(gdf, metric, INSET_BOUNDS["Sydney / Illawarra / Hunter"], SVG_CELL, SVG_CELL, "Sydney / Illawarra / Hunter")
    melbourne_svg = make_svg_tile(gdf, metric, INSET_BOUNDS["Melbourne / Geelong"], SVG_CELL, SVG_CELL, "Melbourne / Geelong")
    perth_svg = make_svg_tile(gdf, metric, INSET_BOUNDS["Perth"], SVG_CELL, SVG_CELL, "Perth")
    adelaide_svg = make_svg_tile(gdf, metric, INSET_BOUNDS["Adelaide"], SVG_CELL, SVG_CELL, "Adelaide")

    atlas_html = f"""
    <style>
    html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        overflow: visible;
        width: 100%;
        font-family: Segoe UI, Arial, Helvetica, sans-serif;
    }}
    .atlas-outer {{
        width: 100%;
        margin: 0;
        background: transparent;
        overflow: visible;
        padding-bottom: 80px;
        box-sizing: border-box;
        position: relative;
    }}
    .atlas-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        grid-template-rows: repeat(3, minmax(0, 1fr));
        gap: {ATLAS_GAP}px;
        width: 100%;
        height: auto;
        aspect-ratio: 1 / 1;
        position: relative;
    }}
    .atlas-tile {{
        position: relative;
        background: transparent;
        overflow: hidden;
        min-width: 0;
        min-height: 0;
        border: 2px solid #000000;
        box-sizing: border-box;
    }}
    .atlas-main {{ grid-column: 1 / span 2; grid-row: 1 / span 2; }}
    .atlas-brisbane {{ grid-column: 3; grid-row: 1; }}
    .atlas-sydney {{ grid-column: 3; grid-row: 2; }}
    .atlas-melbourne {{ grid-column: 3; grid-row: 3; }}
    .atlas-perth {{ grid-column: 1; grid-row: 3; }}
    .atlas-adelaide {{ grid-column: 2; grid-row: 3; }}
    .atlas-svg {{
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        display: block;
        overflow: hidden;
    }}
    .service-area-path {{
        cursor: pointer;
        transition: fill-opacity 0.08s ease, stroke-width 0.08s ease;
        fill-opacity: 0.84;
    }}
    .service-area-path:hover {{
        fill-opacity: 0.98;
        stroke: #000000;
        stroke-width: 3;
    }}
    .atlas-label {{
        position: absolute;
        top: 8px;
        left: 10px;
        z-index: 5;
        padding: 3px 7px;
        background: rgba(255, 247, 230, 0.92);
        border: 1px solid rgba(0, 0, 0, 0.35);
        border-radius: 3px;
        color: {GM_NAVY};
        font-size: 12px;
        font-weight: 700;
        pointer-events: none;
    }}
    #atlas-tooltip {{
        position: fixed !important;
        z-index: 2147483647 !important;
        display: none;
        width: max-content !important;
        min-width: 0 !important;
        max-width: min(760px, calc(100vw - 32px)) !important;
        background: rgba(255, 247, 230, 0.985) !important;
        color: {GM_NAVY} !important;
        border: 1px solid #000000 !important;
        border-radius: 5px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.30) !important;
        padding: 8px 10px !important;
        font-size: 12px !important;
        line-height: 1.3 !important;
        pointer-events: none !important;
        white-space: nowrap !important;
        box-sizing: border-box !important;
    }}
    .tooltip-row {{
        display: grid !important;
        grid-template-columns: max-content max-content !important;
        column-gap: 12px !important;
        align-items: baseline !important;
        width: max-content !important;
        max-width: 100% !important;
        white-space: nowrap !important;
        font-size: 12px !important;
        line-height: 1.3 !important;
    }}
    .tooltip-label {{
        font-weight: 700 !important;
        color: {GM_NAVY} !important;
        text-align: right !important;
        white-space: nowrap !important;
    }}
    .tooltip-value {{
        color: {GM_NAVY} !important;
        text-align: left !important;
        white-space: nowrap !important;
        overflow: visible !important;
    }}
    </style>

    <div class="atlas-outer" id="atlas-outer">
        <div class="atlas-grid" id="atlas-grid">
            <div class="atlas-tile atlas-main">{main_svg}</div>
            <div class="atlas-tile atlas-brisbane">{brisbane_svg}</div>
            <div class="atlas-tile atlas-sydney">{sydney_svg}</div>
            <div class="atlas-tile atlas-melbourne">{melbourne_svg}</div>
            <div class="atlas-tile atlas-perth">{perth_svg}</div>
            <div class="atlas-tile atlas-adelaide">{adelaide_svg}</div>
        </div>
        <div id="atlas-tooltip"></div>
    </div>

    <script>
    const tooltip = document.getElementById("atlas-tooltip");
    const outer = document.getElementById("atlas-outer");
    const grid = document.getElementById("atlas-grid");

    function showTooltip(event) {{
        const target = event.target;
        if (!target.classList.contains("service-area-path")) return;
        const html = target.getAttribute("data-tooltip");
        if (!html) return;
        tooltip.innerHTML = html;
        tooltip.style.display = "block";
        tooltip.getBoundingClientRect();
        moveTooltip(event);
    }}

    function moveTooltip(event) {{
        if (!tooltip || tooltip.style.display === "none") return;
        const pad = 16;
        const rect = tooltip.getBoundingClientRect();
        let x = event.clientX + 14;
        let y = event.clientY + 14;
        const maxX = window.innerWidth - rect.width - pad;
        const maxY = window.innerHeight - rect.height - pad;
        if (x > maxX) x = event.clientX - rect.width - 14;
        if (y > maxY) y = event.clientY - rect.height - 14;
        x = Math.max(pad, x);
        y = Math.max(pad, y);
        tooltip.style.left = x + "px";
        tooltip.style.top = y + "px";
    }}

    function hideTooltip() {{
        tooltip.style.display = "none";
    }}

    document.querySelectorAll(".service-area-path").forEach(function(path) {{
        path.addEventListener("mouseenter", showTooltip);
        path.addEventListener("mousemove", moveTooltip);
        path.addEventListener("mouseleave", hideTooltip);
    }});

    function resizeAtlasToCanvas() {{
        if (!outer || !grid) return;
        const availableWidth = outer.parentElement.getBoundingClientRect().width;
        grid.style.width = availableWidth + "px";
        grid.style.height = availableWidth + "px";
        const frameHeight = Math.ceil(availableWidth + 90);
        window.parent.postMessage({{ type: "streamlit:setFrameHeight", height: frameHeight }}, "*");
    }}

    window.addEventListener("load", resizeAtlasToCanvas);
    window.addEventListener("resize", resizeAtlasToCanvas);

    if (window.ResizeObserver) {{
        const observer = new ResizeObserver(function() {{
            resizeAtlasToCanvas();
        }});
        observer.observe(document.body);
        observer.observe(outer);
    }}

    setTimeout(resizeAtlasToCanvas, 50);
    setTimeout(resizeAtlasToCanvas, 250);
    setTimeout(resizeAtlasToCanvas, 750);
    setTimeout(resizeAtlasToCanvas, 1500);
    </script>
    """

    components.html(atlas_html, height=ATLAS_COMPONENT_HEIGHT, scrolling=False)


# GOOD MEASURE STACKED BAR PATCH
def make_service_type_stacked_bar_chart(
    service_type_data: pd.DataFrame,
    quarter: str,
    selected_remoteness: list[str],
    selected_service_types: list[str],
    exclude_selected: bool,
) -> alt.Chart:
    data = service_type_data.copy()
    data = add_state_labels(data) if "add_state_labels" in globals() else data

    if "service_area_state_label" not in data.columns:
        data["service_area_state_label"] = data["ndis_service_area"]

    data = data.loc[data["quarter"] == quarter].copy()

    if selected_remoteness and "remoteness_category" in data.columns:
        data = data.loc[data["remoteness_category"].isin(selected_remoteness)].copy()

    all_types = [
        x for x in SERVICE_TYPE_ORDER
        if x in set(data["service_type"].dropna().astype(str).unique())
    ]

    if selected_service_types:
        selected_set = set(selected_service_types)

        if exclude_selected:
            included_types = [x for x in all_types if x not in selected_set]
        else:
            included_types = [x for x in all_types if x in selected_set]
    else:
        included_types = all_types

    data = data.loc[data["service_type"].isin(included_types)].copy()

    if data.empty:
        data = pd.DataFrame(
            {
                "service_area_state_label": ["No service-type data"],
                "service_type": ["No data"],
                "service_type_payment_amount": [0],
                "service_type_payment_amount_per_1000_population_2025_erp": [0],
                "population_2025_erp": [pd.NA],
                "state_acronym": [""],
                "ndis_service_area": ["No service-type data"],
            }
        )

    data["service_type_payment_amount"] = pd.to_numeric(
        data.get("service_type_payment_amount", 0),
        errors="coerce",
    ).fillna(0)

    data["population_2025_erp"] = pd.to_numeric(
        data.get("population_2025_erp", pd.NA),
        errors="coerce",
    )

    if "service_type_payment_amount_per_1000_population_2025_erp" in data.columns:
        data["service_type_payment_amount_per_1000_population_2025_erp"] = pd.to_numeric(
            data["service_type_payment_amount_per_1000_population_2025_erp"],
            errors="coerce",
        )
    else:
        data["service_type_payment_amount_per_1000_population_2025_erp"] = (
            data["service_type_payment_amount"]
            / data["population_2025_erp"].replace({0: pd.NA})
            * 1000
        )

    data["service_type_payment_amount_per_1000_population_2025_erp"] = (
        data["service_type_payment_amount_per_1000_population_2025_erp"]
        .replace([float("inf"), float("-inf")], pd.NA)
        .fillna(0)
    )

    grouped = (
        data.groupby(
            [
                "service_area_state_label",
                "state_acronym",
                "ndis_service_area",
                "service_type",
            ],
            dropna=False,
        )
        .agg(
            service_type_payment_amount=("service_type_payment_amount", "sum"),
            service_type_payment_amount_per_1000_population_2025_erp=(
                "service_type_payment_amount_per_1000_population_2025_erp",
                "sum",
            ),
            service_type_payment_share_of_area_total=(
                "service_type_payment_share_of_area_total",
                "sum",
            )
            if "service_type_payment_share_of_area_total" in data.columns
            else ("service_type_payment_amount", "size"),
        )
        .reset_index()
    )

    totals = (
        grouped.groupby("service_area_state_label", dropna=False)[
            "service_type_payment_amount_per_1000_population_2025_erp"
        ]
        .sum()
        .sort_values(ascending=False)
    )

    y_order = totals.index.tolist()
    chart_height = max(700, len(y_order) * 22)

    total_labels = totals.reset_index()
    total_labels.columns = [
        "service_area_state_label",
        "total_payment_per_1000_population",
    ]
    total_labels["total_label"] = total_labels["total_payment_per_1000_population"].apply(
        lambda x: "" if pd.isna(x) else f"${float(x):,.0f}"
    )

    bars = (
        alt.Chart(grouped)
        .mark_bar(stroke=GM_NAVY, strokeWidth=0.15)
        .encode(
            y=alt.Y(
                "service_area_state_label:N",
                sort=y_order,
                title=None,
                axis=alt.Axis(
                    labelOverlap=False,
                    labelLimit=380,
                    labelFontSize=11,
                    labelPadding=4,
                    ticks=True,
                    domain=True,
                ),
            ),
            x=alt.X(
                "service_type_payment_amount_per_1000_population_2025_erp:Q",
                stack="zero",
                title="Service-type payment amount per 1,000 population",
                axis=alt.Axis(
                    labelFontSize=12,
                    titleFontSize=13,
                    format="$~s",
                ),
            ),
            color=alt.Color(
                "service_type:N",
                title="Service type",
                sort=SERVICE_TYPE_ORDER,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=2,
                    labelFontSize=11,
                    titleFontSize=12,
                    symbolSize=100,
                ),
            ),
            tooltip=[
                alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("state_acronym:N", title="State"),
                alt.Tooltip("service_type:N", title="Service type"),
                alt.Tooltip(
                    "service_type_payment_amount_per_1000_population_2025_erp:Q",
                    title="Payment per 1,000 population",
                    format="$,.0f",
                ),
                alt.Tooltip(
                    "service_type_payment_amount:Q",
                    title="Raw payment amount",
                    format="$,.0f",
                ),
                alt.Tooltip(
                    "service_type_payment_share_of_area_total:Q",
                    title="Area payment share",
                    format=".1%",
                ),
            ],
        )
        .properties(height=chart_height)
    )

    labels = (
        alt.Chart(total_labels)
        .mark_text(
            align="left",
            baseline="middle",
            dx=4,
            fontSize=10,
            color=GM_NAVY,
        )
        .encode(
            y=alt.Y("service_area_state_label:N", sort=y_order, title=None),
            x=alt.X("total_payment_per_1000_population:Q"),
            text=alt.Text("total_label:N"),
        )
    )

    return gm_chart_config(bars + labels)


def make_ranked_bar_chart(
    filtered: pd.DataFrame,
    metric: str,
    rank_direction: str,
) -> alt.Chart:
    data = filtered.copy()
    data = add_state_labels(data) if "add_state_labels" in globals() else data

    if "service_area_state_label" not in data.columns:
        data["service_area_state_label"] = data["ndis_service_area"]

    data[metric] = pd.to_numeric(data[metric], errors="coerce")

    if rank_direction == "Largest positive values":
        data = data.sort_values(metric, ascending=False)
    elif rank_direction == "Largest negative values":
        data = data.sort_values(metric, ascending=True)
    else:
        data["_abs_metric"] = data[metric].abs()
        data = data.sort_values("_abs_metric", ascending=False)

    # Preserve the selected ranking visually while drawing horizontal bars.
    data = data.reset_index(drop=True)
    y_order = data["service_area_state_label"].tolist()
    chart_height = max(700, len(y_order) * 19)

    data["_metric_label"] = data[metric].apply(
        lambda x: "" if pd.isna(x) else f"{float(x):,.2f}"
    )

    bars = (
        alt.Chart(data)
        .mark_bar(color=GM_ORANGE, stroke=GM_NAVY, strokeWidth=0.3)
        .encode(
            y=alt.Y(
                "service_area_state_label:N",
                sort=y_order,
                title=None,
                axis=alt.Axis(
                    labelLimit=360,
                    labelFontSize=11,
                    labelOverlap=False,
                    labelPadding=4,
                    ticks=True,
                    domain=True,
                ),
            ),
            x=alt.X(
                f"{metric}:Q",
                title=METRIC_SHORT_LABELS[metric],
                axis=alt.Axis(labelFontSize=13, titleFontSize=14),
            ),
            tooltip=[
                alt.Tooltip("ndis_service_area:N", title="Service area"),
                alt.Tooltip("state_acronym:N", title="State") if "state_acronym" in data.columns else alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip("service_type_filter_label:N", title="Service type filter") if "service_type_filter_label" in data.columns else alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip("included_service_type_share:Q", title="Included payment share", format=".3f") if "included_service_type_share" in data.columns else alt.Tooltip("service_area_state_label:N", title="Service area"),
                alt.Tooltip(f"{metric}:Q", title=METRIC_SHORT_LABELS[metric], format=".2f"),
            ],
        )
        .properties(height=chart_height)
    )

    positive_labels = (
        alt.Chart(data.loc[data[metric] >= 0].copy())
        .mark_text(
            align="left",
            baseline="middle",
            dx=4,
            fontSize=10,
            color=GM_NAVY,
        )
        .encode(
            y=alt.Y("service_area_state_label:N", sort=y_order, title=None),
            x=alt.X(f"{metric}:Q"),
            text=alt.Text("_metric_label:N"),
        )
    )

    negative_labels = (
        alt.Chart(data.loc[data[metric] < 0].copy())
        .mark_text(
            align="right",
            baseline="middle",
            dx=-4,
            fontSize=10,
            color=GM_NAVY,
        )
        .encode(
            y=alt.Y("service_area_state_label:N", sort=y_order, title=None),
            x=alt.X(f"{metric}:Q"),
            text=alt.Text("_metric_label:N"),
        )
    )

    rule = (
        alt.Chart(pd.DataFrame({"x": [0]}))
        .mark_rule(color=GM_NAVY, strokeDash=[4, 3])
        .encode(x="x:Q")
    )

    return gm_chart_config(bars + positive_labels + negative_labels + rule)


def make_remoteness_bar_chart(filtered: pd.DataFrame, metric: str) -> alt.Chart:
    data = filtered.copy()
    data[metric] = pd.to_numeric(data[metric], errors="coerce")

    grouped = data.groupby("remoteness_category", dropna=False)[metric].mean().reset_index()

    present_order = [
        item for item in REMOTENESS_ORDER
        if item in set(data["remoteness_category"].dropna().unique())
        or item in set(grouped["remoteness_category"].dropna().unique())
    ]

    grouped["remoteness_category"] = pd.Categorical(grouped["remoteness_category"], categories=present_order, ordered=True)
    grouped = grouped.sort_values("remoteness_category")

    chart = (
        alt.Chart(grouped)
        .mark_bar(color=GM_ORANGE, stroke=GM_NAVY, strokeWidth=0.3)
        .encode(
            y=alt.Y("remoteness_category:N", sort=present_order, title=None, axis=alt.Axis(labelLimit=280, labelFontSize=13)),
            x=alt.X(f"{metric}:Q", title=f"Mean {METRIC_SHORT_LABELS[metric]}", axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
            tooltip=[
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip(f"{metric}:Q", title=f"Mean {METRIC_SHORT_LABELS[metric]}", format=".2f"),
            ],
        )
        .properties(height=300)
    )

    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=GM_NAVY, strokeDash=[4, 3]).encode(x="x:Q")
    return gm_chart_config(chart + rule)


def make_change_over_time_chart(data: pd.DataFrame, metric: str, selected_remoteness: list[str]) -> alt.Chart:
    data = data.copy()

    if selected_remoteness and "remoteness_category" in data.columns:
        data = data.loc[data["remoteness_category"].isin(selected_remoteness)].copy()

    data[metric] = pd.to_numeric(data[metric], errors="coerce")

    grouped = data.groupby(["quarter", "remoteness_category"], dropna=False)[metric].mean().reset_index()

    chart = (
        alt.Chart(grouped)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("quarter:N", title=None, axis=alt.Axis(labelAngle=0, labelFontSize=13)),
            y=alt.Y(f"{metric}:Q", title=f"Mean {METRIC_SHORT_LABELS[metric]}", axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
            color=alt.Color(
                "remoteness_category:N",
                title=None,
                sort=REMOTENESS_ORDER,
                scale=GM_REMOTENESS_SCALE,
                legend=alt.Legend(orient="top", direction="horizontal", columns=2, labelFontSize=13, symbolSize=120, padding=0),
            ),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip(f"{metric}:Q", title=f"Mean {METRIC_SHORT_LABELS[metric]}", format=".2f"),
            ],
        )
        .properties(height=470)
        .configure_view(strokeWidth=0)
    )

    return gm_chart_config(chart)


def make_distribution_chart(filtered: pd.DataFrame) -> alt.Chart:
    data = filtered.copy()

    chart = (
        alt.Chart(data)
        .mark_circle(size=95, opacity=0.78, stroke=GM_NAVY, strokeWidth=0.4)
        .encode(
            x=alt.X("service_area_funded_plans_per_1000_population_2025_erp:Q", title="Funded plans per 1,000", axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
            y=alt.Y("service_area_mean_plan_utilisation:Q", title="Mean plan utilisation", axis=alt.Axis(labelFontSize=13, titleFontSize=14)),
            color=alt.Color(
                "remoteness_category:N",
                title=None,
                sort=REMOTENESS_ORDER,
                scale=GM_REMOTENESS_SCALE,
                legend=alt.Legend(orient="top", direction="horizontal", columns=2, labelFontSize=13, symbolSize=120, padding=0),
            ),
            tooltip=[
                alt.Tooltip("ndis_service_area:N", title="Service area"),
                alt.Tooltip("remoteness_category:N", title="Remoteness"),
                alt.Tooltip("service_type_filter_label:N", title="Service type filter"),
                alt.Tooltip("included_service_type_share:Q", title="Included payment share", format=".3f"),
                alt.Tooltip("service_area_funded_plans_per_1000_population_2025_erp:Q", title="Plans per 1,000", format=".2f"),
                alt.Tooltip("service_area_mean_plan_utilisation:Q", title="Utilisation", format=".2f"),
            ],
        )
        .properties(height=520)
        .configure_view(strokeWidth=0)
    )

    return chart


def gm_chart_config(chart: alt.Chart) -> alt.Chart:
    return (
        chart
        .configure(font=GM_FONT)
        .configure_axis(
            labelFont=GM_FONT,
            titleFont=GM_FONT,
            labelFontSize=13,
            titleFontSize=14,
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
            gridColor="#E8E1D2",
            domainColor=GM_NAVY,
            tickColor=GM_NAVY,
        )
        .configure_legend(
            labelFont=GM_FONT,
            titleFont=GM_FONT,
            labelFontSize=13,
            titleFontSize=14,
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
            orient="top",
            symbolSize=120,
        )
        .configure_title(font=GM_FONT, fontSize=16, color=GM_NAVY)
        .configure_header(
            labelFont=GM_FONT,
            titleFont=GM_FONT,
            labelFontSize=13,
            titleFontSize=14,
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
        )
        .configure_view(strokeWidth=0)
    )


def format_data(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    rounded_cols = [
        "included_service_type_share",
        "population_2025_erp",
        "funded_plans_count",
        "service_area_funded_plans_per_1000_population_2025_erp",
        "funded_plans_per_1000_gap_from_national",
        "service_area_mean_plan_utilisation",
        "mean_plan_utilisation_gap_from_national",
        "plans_per_1000_change_from_baseline",
        "mean_plan_utilisation_change_from_baseline",
    ]

    for col in rounded_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").round(3 if col == "included_service_type_share" else 1)

    return out


def apply_good_measure_theme() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --gm-navy: {GM_NAVY};
            --gm-navy-2: {GM_NAVY_2};
            --gm-orange: {GM_ORANGE};
            --gm-orange-2: {GM_ORANGE_2};
            --gm-yellow: {GM_YELLOW};
            --gm-soft-bg: {GM_SOFT_BG};
        }}
        .stApp {{
            background: {GM_BG};
            color: {GM_NAVY};
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: {GM_NAVY} !important;
        }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {GM_NAVY} 0%, {GM_NAVY_2} 100%);
        }}
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {{
            color: #FFFFFF !important;
        }}
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] div[data-baseweb="select"] *,
        [data-testid="stSidebar"] div[data-baseweb="input"] *,
        [data-testid="stSidebar"] div[data-baseweb="tag"] *,
        div[data-baseweb="popover"] *,
        ul[role="listbox"] *,
        li[role="option"] * {{
            color: {GM_NAVY} !important;
        }}
        [data-testid="stSidebar"] div[data-baseweb="select"] > div {{
            background-color: #FFFFFF !important;
            border: 1px solid {GM_ORANGE} !important;
        }}
        div[data-baseweb="popover"] {{
            background-color: #FFFFFF !important;
            color: {GM_NAVY} !important;
        }}
        ul[role="listbox"] {{
            background-color: #FFFFFF !important;
            color: {GM_NAVY} !important;
        }}
        li[role="option"] {{
            background-color: #FFFFFF !important;
            color: {GM_NAVY} !important;
        }}
        li[role="option"]:hover {{
            background-color: {GM_SOFT_BG} !important;
            color: {GM_NAVY} !important;
        }}
        div[data-testid="stMetric"] {{
            background: {GM_SOFT_BG};
            border-left: 5px solid {GM_ORANGE};
            border-radius: 8px;
            padding: 0.75rem 0.9rem;
        }}
        div[data-testid="stMetric"] label {{
            color: {GM_NAVY} !important;
            font-weight: 700 !important;
        }}
        div[data-testid="stMetricValue"] {{
            color: {GM_NAVY} !important;
        }}
        button[kind="primary"], .stDownloadButton button {{
            background: {GM_ORANGE} !important;
            color: {GM_NAVY} !important;
            border: 1px solid {GM_NAVY} !important;
            font-weight: 700 !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.25rem;
            border-bottom: 2px solid {GM_NAVY};
        }}
        .stTabs [data-baseweb="tab"] {{
            background: #FFFFFF;
            color: {GM_NAVY};
            border: 1px solid {GM_NAVY};
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            font-weight: 700;
        }}
        .stTabs [aria-selected="true"] {{
            background: {GM_NAVY} !important;
            color: #FFFFFF !important;
        }}
        .stDataFrame {{
            border: 1px solid {GM_NAVY};
            border-radius: 6px;
        }}
        hr {{
            border-color: {GM_ORANGE};
        }}

        /* GOOD MEASURE SIDEBAR HEADING PATCH */
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4,
        [data-testid="stSidebar"] h5,
        [data-testid="stSidebar"] h6,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h4,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h5,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h6 {{
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }}

        [data-testid="stSidebar"] hr {{
            border-color: rgba(255, 255, 255, 0.55) !important;
        }}

</style>
        """,
        unsafe_allow_html=True,
    )



# GOOD MEASURE SERVICE AREA PAGE PATCH
def make_service_area_href(value) -> str:
    from urllib.parse import quote

    if value is None or pd.isna(value):
        return "?"

    return "?view=service_area&service_area=" + quote(str(value), safe="")


def get_query_param(name: str):
    try:
        value = st.query_params.get(name, None)

        if isinstance(value, list):
            return value[0] if value else None

        return value

    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get(name, None)

            if isinstance(value, list):
                return value[0] if value else None

            return value

        except Exception:
            return None


def quarter_sort_key(value: str) -> tuple[int, int]:
    text = str(value)

    match = re.match(r"^(\d{4})Q([1-4])$", text)

    if not match:
        return (9999, 9)

    return (int(match.group(1)), int(match.group(2)))


def weighted_mean(values: pd.Series, weights: pd.Series):
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")

    mask = values.notna() & weights.notna() & (weights > 0)

    if mask.sum() == 0:
        return pd.NA

    return (values[mask] * weights[mask]).sum() / weights[mask].sum()


def service_area_remoteness(data: pd.DataFrame, service_area: str) -> str | None:
    rows = data.loc[data["ndis_service_area"] == service_area].copy()

    if rows.empty or "remoteness_category" not in rows.columns:
        return None

    values = rows["remoteness_category"].dropna().astype(str).unique().tolist()

    if not values:
        return None

    return values[0]


def build_benchmark_trend_frame(
    data: pd.DataFrame,
    service_area: str,
    value_col: str,
    metric_kind: str,
) -> pd.DataFrame:
    working = data.copy()
    remoteness = service_area_remoteness(working, service_area)

    area = (
        working.loc[working["ndis_service_area"] == service_area, ["quarter", value_col]]
        .copy()
        .rename(columns={value_col: "value"})
    )
    area["benchmark"] = "Selected service area"

    if metric_kind == "plans_per_1000":
        national = (
            working.groupby("quarter", dropna=False)
            .apply(
                lambda g: (
                    pd.to_numeric(g["funded_plans_count"], errors="coerce").sum()
                    / pd.to_numeric(g["population_2025_erp"], errors="coerce").sum()
                    * 1000
                )
                if pd.to_numeric(g["population_2025_erp"], errors="coerce").sum() > 0
                else pd.NA
            )
            .rename("value")
            .reset_index()
        )

        if remoteness is not None and "remoteness_category" in working.columns:
            remoteness_df = (
                working.loc[working["remoteness_category"] == remoteness]
                .groupby("quarter", dropna=False)
                .apply(
                    lambda g: (
                        pd.to_numeric(g["funded_plans_count"], errors="coerce").sum()
                        / pd.to_numeric(g["population_2025_erp"], errors="coerce").sum()
                        * 1000
                    )
                    if pd.to_numeric(g["population_2025_erp"], errors="coerce").sum() > 0
                    else pd.NA
                )
                .rename("value")
                .reset_index()
            )
        else:
            remoteness_df = pd.DataFrame(columns=["quarter", "value"])

    elif metric_kind == "utilisation":
        national = (
            working.groupby("quarter", dropna=False)
            .apply(
                lambda g: weighted_mean(
                    g["service_area_mean_plan_utilisation"],
                    g["funded_plans_count"],
                )
            )
            .rename("value")
            .reset_index()
        )

        if remoteness is not None and "remoteness_category" in working.columns:
            remoteness_df = (
                working.loc[working["remoteness_category"] == remoteness]
                .groupby("quarter", dropna=False)
                .apply(
                    lambda g: weighted_mean(
                        g["service_area_mean_plan_utilisation"],
                        g["funded_plans_count"],
                    )
                )
                .rename("value")
                .reset_index()
            )
        else:
            remoteness_df = pd.DataFrame(columns=["quarter", "value"])

    else:
        national = (
            working.groupby("quarter", dropna=False)[value_col]
            .mean()
            .rename("value")
            .reset_index()
        )

        if remoteness is not None and "remoteness_category" in working.columns:
            remoteness_df = (
                working.loc[working["remoteness_category"] == remoteness]
                .groupby("quarter", dropna=False)[value_col]
                .mean()
                .rename("value")
                .reset_index()
            )
        else:
            remoteness_df = pd.DataFrame(columns=["quarter", "value"])

    national["benchmark"] = "National mean"

    remoteness_label = "Remoteness category mean"
    if remoteness:
        remoteness_label = f"{remoteness} mean"

    remoteness_df["benchmark"] = remoteness_label

    out = pd.concat([area, national, remoteness_df], ignore_index=True)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["quarter", "value"]).copy()
    out["quarter_order"] = out["quarter"].map(quarter_sort_key)
    out = out.sort_values(["quarter_order", "benchmark"]).drop(columns=["quarter_order"])

    return out


def make_service_area_benchmark_trend_chart(
    data: pd.DataFrame,
    service_area: str,
    value_col: str,
    title: str,
    y_title: str,
    metric_kind: str,
    value_format: str = ".2f",
) -> alt.Chart:
    trend = build_benchmark_trend_frame(
        data=data,
        service_area=service_area,
        value_col=value_col,
        metric_kind=metric_kind,
    )

    if trend.empty:
        trend = pd.DataFrame(
            {
                "quarter": ["No data"],
                "value": [0],
                "benchmark": ["No data"],
            }
        )

    quarter_order = sorted(trend["quarter"].dropna().unique().tolist(), key=quarter_sort_key)

    chart = (
        alt.Chart(trend)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "quarter:N",
                sort=quarter_order,
                title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=12),
            ),
            y=alt.Y(
                "value:Q",
                title=y_title,
                axis=alt.Axis(labelFontSize=12, titleFontSize=13),
            ),
            color=alt.Color(
                "benchmark:N",
                title=None,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=1,
                    labelFontSize=12,
                    symbolSize=120,
                ),
            ),
            strokeDash=alt.StrokeDash(
                "benchmark:N",
                title=None,
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("benchmark:N", title="Benchmark"),
                alt.Tooltip("value:Q", title=y_title, format=value_format),
            ],
        )
        .properties(
            title=title,
            height=420,
        )
    )

    return gm_chart_config(chart)


def build_current_benchmark_summary(
    data: pd.DataFrame,
    service_area: str,
    quarter: str,
) -> pd.DataFrame:
    remoteness = service_area_remoteness(data, service_area)
    current = data.loc[
        (data["ndis_service_area"] == service_area)
        & (data["quarter"] == quarter)
    ].copy()

    if current.empty:
        return pd.DataFrame()

    area_row = current.iloc[0]

    qdata = data.loc[data["quarter"] == quarter].copy()
    rdata = qdata.loc[qdata["remoteness_category"] == remoteness].copy() if remoteness else qdata.iloc[0:0].copy()

    area_plans = pd.to_numeric(
        pd.Series([area_row.get("service_area_funded_plans_per_1000_population_2025_erp")]),
        errors="coerce",
    ).iloc[0]

    area_util = pd.to_numeric(
        pd.Series([area_row.get("service_area_mean_plan_utilisation")]),
        errors="coerce",
    ).iloc[0]

    national_plans = (
        pd.to_numeric(qdata["funded_plans_count"], errors="coerce").sum()
        / pd.to_numeric(qdata["population_2025_erp"], errors="coerce").sum()
        * 1000
        if pd.to_numeric(qdata["population_2025_erp"], errors="coerce").sum() > 0
        else pd.NA
    )

    remoteness_plans = (
        pd.to_numeric(rdata["funded_plans_count"], errors="coerce").sum()
        / pd.to_numeric(rdata["population_2025_erp"], errors="coerce").sum()
        * 1000
        if not rdata.empty and pd.to_numeric(rdata["population_2025_erp"], errors="coerce").sum() > 0
        else pd.NA
    )

    national_util = weighted_mean(
        qdata["service_area_mean_plan_utilisation"],
        qdata["funded_plans_count"],
    )

    remoteness_util = (
        weighted_mean(
            rdata["service_area_mean_plan_utilisation"],
            rdata["funded_plans_count"],
        )
        if not rdata.empty
        else pd.NA
    )

    summary = pd.DataFrame(
        [
            {
                "Metric": "Funded plans per 1,000 population",
                "Service area": area_plans,
                "National mean": national_plans,
                "Remoteness category mean": remoteness_plans,
                "Gap to national": area_plans - national_plans if pd.notna(area_plans) and pd.notna(national_plans) else pd.NA,
                "Gap to remoteness category": area_plans - remoteness_plans if pd.notna(area_plans) and pd.notna(remoteness_plans) else pd.NA,
            },
            {
                "Metric": "Mean plan utilisation",
                "Service area": area_util,
                "National mean": national_util,
                "Remoteness category mean": remoteness_util,
                "Gap to national": area_util - national_util if pd.notna(area_util) and pd.notna(national_util) else pd.NA,
                "Gap to remoteness category": area_util - remoteness_util if pd.notna(area_util) and pd.notna(remoteness_util) else pd.NA,
            },
        ]
    )

    for col in [
        "Service area",
        "National mean",
        "Remoteness category mean",
        "Gap to national",
        "Gap to remoteness category",
    ]:
        summary[col] = pd.to_numeric(summary[col], errors="coerce").round(2)

    return summary


def filter_service_type_rows_for_selection(
    data: pd.DataFrame,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> pd.DataFrame:
    out = data.copy()

    all_types = [
        x for x in SERVICE_TYPE_ORDER
        if x in set(out["service_type"].dropna().astype(str).unique())
    ]

    if selected_service_types:
        selected_set = set(selected_service_types)

        if exclude_selected:
            included_types = [x for x in all_types if x not in selected_set]
        else:
            included_types = [x for x in all_types if x in selected_set]
    else:
        included_types = all_types

    return out.loc[out["service_type"].isin(included_types)].copy()


def make_service_area_service_type_trend_chart(
    service_type_data: pd.DataFrame,
    service_area: str,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> alt.Chart:
    data = service_type_data.copy()
    data = filter_service_type_rows_for_selection(
        data=data,
        selected_service_types=selected_service_types,
        exclude_selected=exclude_selected,
    )

    data = data.loc[data["ndis_service_area"] == service_area].copy()

    if data.empty:
        data = pd.DataFrame(
            {
                "quarter": ["No data"],
                "service_type": ["No data"],
                "service_type_payment_amount_per_1000_population_2025_erp": [0],
            }
        )

    if "service_type_payment_amount_per_1000_population_2025_erp" not in data.columns:
        data["service_type_payment_amount_per_1000_population_2025_erp"] = (
            pd.to_numeric(data["service_type_payment_amount"], errors="coerce")
            / pd.to_numeric(data["population_2025_erp"], errors="coerce").replace({0: pd.NA})
            * 1000
        )

    data["service_type_payment_amount_per_1000_population_2025_erp"] = pd.to_numeric(
        data["service_type_payment_amount_per_1000_population_2025_erp"],
        errors="coerce",
    ).fillna(0)

    grouped = (
        data.groupby(["quarter", "service_type"], dropna=False)
        .agg(
            service_type_payment_amount_per_1000_population_2025_erp=(
                "service_type_payment_amount_per_1000_population_2025_erp",
                "sum",
            )
        )
        .reset_index()
    )

    quarter_order = sorted(grouped["quarter"].dropna().unique().tolist(), key=quarter_sort_key)

    chart = (
        alt.Chart(grouped)
        .mark_bar(stroke=GM_NAVY, strokeWidth=0.15)
        .encode(
            x=alt.X(
                "quarter:N",
                sort=quarter_order,
                title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=12),
            ),
            y=alt.Y(
                "service_type_payment_amount_per_1000_population_2025_erp:Q",
                stack="zero",
                title="Payment amount per 1,000 population",
                axis=alt.Axis(format="$~s", labelFontSize=12, titleFontSize=13),
            ),
            color=alt.Color(
                "service_type:N",
                title="Service type",
                sort=SERVICE_TYPE_ORDER,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=2,
                    labelFontSize=11,
                    titleFontSize=12,
                    symbolSize=100,
                ),
            ),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("service_type:N", title="Service type"),
                alt.Tooltip(
                    "service_type_payment_amount_per_1000_population_2025_erp:Q",
                    title="Payment per 1,000 population",
                    format="$,.0f",
                ),
            ],
        )
        .properties(
            title="Service-type payment mix over time",
            height=460,
        )
    )

    return gm_chart_config(chart)


def render_service_area_dashboard(
    data: pd.DataFrame,
    service_type_data: pd.DataFrame,
    service_area: str,
    quarter: str,
    baseline_quarter: str,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> None:
    area_rows = data.loc[data["ndis_service_area"] == service_area].copy()

    if area_rows.empty:
        st.warning(f"No dashboard data found for service area: {service_area}")
        st.markdown("[Back to atlas](?)")
        return

    area_label = service_area

    if "service_area_state_label" in area_rows.columns:
        labels = area_rows["service_area_state_label"].dropna().astype(str).unique().tolist()
        if labels:
            area_label = labels[0]

    remoteness = service_area_remoteness(data, service_area)

    st.markdown("[← Back to national atlas](?)")
    st.title(area_label)
    st.caption("Service-area dashboard with trend benchmarks to national and relevant remoteness category means.")

    if remoteness:
        st.write(f"**Remoteness category:** {remoteness}")

    current = area_rows.loc[area_rows["quarter"] == quarter].copy()

    if current.empty:
        current = area_rows.sort_values("quarter", key=lambda s: s.map(quarter_sort_key)).tail(1).copy()

    current_row = current.iloc[0]

    top = st.columns(5)

    with top[0]:
        st.metric("Quarter", current_row.get("quarter", quarter))

    with top[1]:
        population = pd.to_numeric(pd.Series([current_row.get("population_2025_erp")]), errors="coerce").iloc[0]
        st.metric("Population", f"{population:,.0f}" if pd.notna(population) else "n/a")

    with top[2]:
        funded = pd.to_numeric(pd.Series([current_row.get("funded_plans_count")]), errors="coerce").iloc[0]
        st.metric("Proxy funded plans", f"{funded:,.0f}" if pd.notna(funded) else "n/a")

    with top[3]:
        plans_rate = pd.to_numeric(
            pd.Series([current_row.get("service_area_funded_plans_per_1000_population_2025_erp")]),
            errors="coerce",
        ).iloc[0]
        st.metric("Plans per 1,000", f"{plans_rate:,.2f}" if pd.notna(plans_rate) else "n/a")

    with top[4]:
        utilisation = pd.to_numeric(
            pd.Series([current_row.get("service_area_mean_plan_utilisation")]),
            errors="coerce",
        ).iloc[0]
        st.metric("Mean utilisation", f"{utilisation:,.2f}" if pd.notna(utilisation) else "n/a")

    st.info(
        "Service-type filters use payment-share weighting for funded-plan intensity. "
        "Mean utilisation is retained as a whole-area context measure."
    )

    overview_tab, trend_tab, service_type_tab, data_tab = st.tabs(
        [
            "Benchmark summary",
            "Trends",
            "Service-type mix",
            "Data",
        ]
    )

    with overview_tab:
        st.subheader(f"Benchmark summary for {current_row.get('quarter', quarter)}")

        summary = build_current_benchmark_summary(
            data=data,
            service_area=service_area,
            quarter=current_row.get("quarter", quarter),
        )

        if summary.empty:
            st.write("No benchmark summary available.")
        else:
            st.dataframe(
                summary,
                use_container_width=True,
                hide_index=True,
            )

    with trend_tab:
        left, right = st.columns(2, gap="large")

        with left:
            plans_chart = make_service_area_benchmark_trend_chart(
                data=data,
                service_area=service_area,
                value_col="service_area_funded_plans_per_1000_population_2025_erp",
                title="Funded plans per 1,000 population",
                y_title="Plans per 1,000 population",
                metric_kind="plans_per_1000",
                value_format=".2f",
            )
            st.altair_chart(plans_chart, use_container_width=True)

        with right:
            utilisation_chart = make_service_area_benchmark_trend_chart(
                data=data,
                service_area=service_area,
                value_col="service_area_mean_plan_utilisation",
                title="Mean plan utilisation",
                y_title="Mean plan utilisation",
                metric_kind="utilisation",
                value_format=".2f",
            )
            st.altair_chart(utilisation_chart, use_container_width=True)

    with service_type_tab:
        st.subheader("Service-type payment mix")

        service_type_trend = make_service_area_service_type_trend_chart(
            service_type_data=service_type_data,
            service_area=service_area,
            selected_service_types=selected_service_types,
            exclude_selected=exclude_selected,
        )
        st.altair_chart(service_type_trend, use_container_width=True)

        st.subheader(f"Service-type table for {current_row.get('quarter', quarter)}")

        service_table = service_type_data.loc[
            (service_type_data["ndis_service_area"] == service_area)
            & (service_type_data["quarter"] == current_row.get("quarter", quarter))
        ].copy()

        service_table = filter_service_type_rows_for_selection(
            data=service_table,
            selected_service_types=selected_service_types,
            exclude_selected=exclude_selected,
        )

        table_cols = [
            "service_type",
            "service_type_payment_amount",
            "service_type_payment_amount_per_1000_population_2025_erp",
            "service_type_payment_share_of_area_total",
        ]
        table_cols = [c for c in table_cols if c in service_table.columns]

        if service_table.empty:
            st.write("No service-type rows available for this quarter.")
        else:
            service_table = service_table[table_cols].copy()

            for col in service_table.columns:
                if col != "service_type":
                    service_table[col] = pd.to_numeric(service_table[col], errors="coerce").round(3)

            st.dataframe(
                service_table,
                use_container_width=True,
                hide_index=True,
            )

    with data_tab:
        st.subheader("Full service-area time series")

        display_cols = [
            "quarter",
            "baseline_quarter",
            "remoteness_category",
            "service_type_filter_label",
            "included_service_type_share",
            "population_2025_erp",
            "funded_plans_count",
            "service_area_funded_plans_per_1000_population_2025_erp",
            "funded_plans_per_1000_gap_from_national",
            "service_area_mean_plan_utilisation",
            "mean_plan_utilisation_gap_from_national",
            "plans_per_1000_change_from_baseline",
            "mean_plan_utilisation_change_from_baseline",
            "statistical_method_note",
        ]

        display_cols = [c for c in display_cols if c in area_rows.columns]
        area_display = area_rows[display_cols].sort_values(
            "quarter",
            key=lambda s: s.map(quarter_sort_key),
        )

        st.dataframe(
            format_data(area_display),
            use_container_width=True,
            hide_index=True,
            height=640,
        )





# GOOD MEASURE SERVICE AREA ROUTING PATCH
def make_service_area_url(value) -> str:
    from urllib.parse import quote

    if value is None or pd.isna(value):
        return "?"

    return "?view=service_area&service_area=" + quote(str(value), safe="")


def get_query_param(name: str):
    try:
        value = st.query_params.get(name, None)
        if isinstance(value, list):
            return value[0] if value else None
        return value
    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get(name, None)
            if isinstance(value, list):
                return value[0] if value else None
            return value
        except Exception:
            return None


def quarter_sort_key(value: str) -> tuple[int, int]:
    text = str(value)

    if "Q" not in text:
        return (9999, 9)

    year, q = text.split("Q", 1)

    try:
        return (int(year), int(q))
    except Exception:
        return (9999, 9)


def weighted_mean(values: pd.Series, weights: pd.Series):
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")
    mask = values.notna() & weights.notna() & (weights > 0)

    if mask.sum() == 0:
        return pd.NA

    return (values[mask] * weights[mask]).sum() / weights[mask].sum()


def service_area_remoteness(data: pd.DataFrame, service_area: str) -> str | None:
    rows = data.loc[data["ndis_service_area"].astype(str) == str(service_area)].copy()

    if rows.empty or "remoteness_category" not in rows.columns:
        return None

    values = rows["remoteness_category"].dropna().astype(str).unique().tolist()
    return values[0] if values else None


def build_service_area_benchmark_frame(
    data: pd.DataFrame,
    service_area: str,
    metric_col: str,
    metric_kind: str,
) -> pd.DataFrame:
    working = data.copy()
    remoteness = service_area_remoteness(working, service_area)

    area = (
        working.loc[
            working["ndis_service_area"].astype(str) == str(service_area),
            ["quarter", metric_col],
        ]
        .copy()
        .rename(columns={metric_col: "value"})
    )
    area["benchmark"] = "Selected service area"

    if metric_kind == "plans_per_1000":
        national = (
            working.groupby("quarter", dropna=False)
            .apply(
                lambda g: (
                    pd.to_numeric(g["funded_plans_count"], errors="coerce").sum()
                    / pd.to_numeric(g["population_2025_erp"], errors="coerce").sum()
                    * 1000
                )
                if pd.to_numeric(g["population_2025_erp"], errors="coerce").sum() > 0
                else pd.NA
            )
            .rename("value")
            .reset_index()
        )

        if remoteness and "remoteness_category" in working.columns:
            rem = (
                working.loc[working["remoteness_category"] == remoteness]
                .groupby("quarter", dropna=False)
                .apply(
                    lambda g: (
                        pd.to_numeric(g["funded_plans_count"], errors="coerce").sum()
                        / pd.to_numeric(g["population_2025_erp"], errors="coerce").sum()
                        * 1000
                    )
                    if pd.to_numeric(g["population_2025_erp"], errors="coerce").sum() > 0
                    else pd.NA
                )
                .rename("value")
                .reset_index()
            )
        else:
            rem = pd.DataFrame(columns=["quarter", "value"])

    elif metric_kind == "utilisation":
        national = (
            working.groupby("quarter", dropna=False)
            .apply(
                lambda g: weighted_mean(
                    g["service_area_mean_plan_utilisation"],
                    g["funded_plans_count"],
                )
            )
            .rename("value")
            .reset_index()
        )

        if remoteness and "remoteness_category" in working.columns:
            rem = (
                working.loc[working["remoteness_category"] == remoteness]
                .groupby("quarter", dropna=False)
                .apply(
                    lambda g: weighted_mean(
                        g["service_area_mean_plan_utilisation"],
                        g["funded_plans_count"],
                    )
                )
                .rename("value")
                .reset_index()
            )
        else:
            rem = pd.DataFrame(columns=["quarter", "value"])

    else:
        national = (
            working.groupby("quarter", dropna=False)[metric_col]
            .mean()
            .rename("value")
            .reset_index()
        )
        rem = pd.DataFrame(columns=["quarter", "value"])

    national["benchmark"] = "National mean"
    rem["benchmark"] = f"{remoteness} mean" if remoteness else "Remoteness category mean"

    out = pd.concat([area, national, rem], ignore_index=True)
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    out = out.dropna(subset=["quarter", "value"]).copy()
    out["_quarter_sort"] = out["quarter"].astype(str).map(quarter_sort_key)

    return out.sort_values(["_quarter_sort", "benchmark"]).drop(columns=["_quarter_sort"])


def make_service_area_benchmark_line_chart(
    data: pd.DataFrame,
    service_area: str,
    metric_col: str,
    title: str,
    y_title: str,
    metric_kind: str,
    value_format: str = ".2f",
) -> alt.Chart:
    plot = build_service_area_benchmark_frame(
        data=data,
        service_area=service_area,
        metric_col=metric_col,
        metric_kind=metric_kind,
    )

    if plot.empty:
        plot = pd.DataFrame(
            {
                "quarter": ["No data"],
                "value": [0],
                "benchmark": ["No data"],
            }
        )

    quarter_order = sorted(plot["quarter"].dropna().astype(str).unique().tolist(), key=quarter_sort_key)

    chart = (
        alt.Chart(plot)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "quarter:N",
                sort=quarter_order,
                title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=12),
            ),
            y=alt.Y(
                "value:Q",
                title=y_title,
                axis=alt.Axis(labelFontSize=12, titleFontSize=13),
            ),
            color=alt.Color(
                "benchmark:N",
                title=None,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=1,
                    labelFontSize=12,
                    symbolSize=120,
                ),
            ),
            strokeDash=alt.StrokeDash("benchmark:N", title=None, legend=None),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("benchmark:N", title="Benchmark"),
                alt.Tooltip("value:Q", title=y_title, format=value_format),
            ],
        )
        .properties(title=title, height=430)
    )

    return gm_chart_config(chart)


def filter_service_type_rows_for_selection(
    data: pd.DataFrame,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> pd.DataFrame:
    out = data.copy()

    all_types = [
        x for x in SERVICE_TYPE_ORDER
        if x in set(out["service_type"].dropna().astype(str).unique())
    ]

    if selected_service_types:
        selected_set = set(selected_service_types)
        included_types = (
            [x for x in all_types if x not in selected_set]
            if exclude_selected
            else [x for x in all_types if x in selected_set]
        )
    else:
        included_types = all_types

    return out.loc[out["service_type"].isin(included_types)].copy()


def make_service_area_service_type_proxy_mix_chart(
    service_type_data: pd.DataFrame,
    service_area: str,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> alt.Chart:
    data = service_type_data.copy()
    data = filter_service_type_rows_for_selection(data, selected_service_types, exclude_selected)
    data = data.loc[data["ndis_service_area"].astype(str) == str(service_area)].copy()

    if data.empty:
        data = pd.DataFrame(
            {
                "quarter": ["No data"],
                "service_type": ["No data"],
                "service_type_proxy_plans_per_1000_population": [0],
                "service_type_data_status": ["No data"],
            }
        )

    if "service_type_proxy_plans_per_1000_population" not in data.columns:
        data["service_type_proxy_plans_per_1000_population"] = (
            pd.to_numeric(
                data.get("service_area_funded_plans_per_1000_population_2025_erp", 0),
                errors="coerce",
            )
            * pd.to_numeric(
                data.get("service_type_payment_share_of_area_total", 0),
                errors="coerce",
            )
        )

    if "service_type_data_status" not in data.columns:
        data["service_type_data_status"] = "observed_or_unknown"

    data["service_type_proxy_plans_per_1000_population"] = pd.to_numeric(
        data["service_type_proxy_plans_per_1000_population"],
        errors="coerce",
    ).fillna(0)

    grouped = (
        data.groupby(["quarter", "service_type", "service_type_data_status"], dropna=False)
        .agg(
            service_type_proxy_plans_per_1000_population=(
                "service_type_proxy_plans_per_1000_population",
                "sum",
            )
        )
        .reset_index()
    )

    quarter_order = sorted(grouped["quarter"].dropna().astype(str).unique().tolist(), key=quarter_sort_key)

    chart = (
        alt.Chart(grouped)
        .mark_bar(stroke=GM_NAVY, strokeWidth=0.15)
        .encode(
            x=alt.X(
                "quarter:N",
                sort=quarter_order,
                title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=12),
            ),
            y=alt.Y(
                "service_type_proxy_plans_per_1000_population:Q",
                stack="zero",
                title="Proxy funded plans per 1,000 population",
                axis=alt.Axis(labelFontSize=12, titleFontSize=13),
            ),
            color=alt.Color(
                "service_type:N",
                title="Service type",
                sort=SERVICE_TYPE_ORDER,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=2,
                    labelFontSize=11,
                    titleFontSize=12,
                    symbolSize=100,
                ),
            ),
            opacity=alt.condition(
                alt.datum.service_type_data_status == "backcast_filter_only",
                alt.value(0.45),
                alt.value(0.9),
            ),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("service_type:N", title="Service type"),
                alt.Tooltip("service_type_data_status:N", title="Data status"),
                alt.Tooltip(
                    "service_type_proxy_plans_per_1000_population:Q",
                    title="Proxy plans per 1,000",
                    format=".2f",
                ),
            ],
        )
        .properties(title="Service-type proxy mix over time", height=460)
    )

    return gm_chart_config(chart)


def make_service_area_proxy_benchmark_chart(
    service_type_data: pd.DataFrame,
    service_area: str,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> alt.Chart:
    data = service_type_data.copy()
    data = filter_service_type_rows_for_selection(data, selected_service_types, exclude_selected)

    if "service_type_proxy_funded_plans_count" not in data.columns:
        data["service_type_proxy_funded_plans_count"] = (
            pd.to_numeric(data.get("funded_plans_count", 0), errors="coerce")
            * pd.to_numeric(data.get("service_type_payment_share_of_area_total", 0), errors="coerce")
        )

    area_remoteness = service_area_remoteness(data, service_area)

    area = (
        data.loc[data["ndis_service_area"].astype(str) == str(service_area)]
        .groupby("quarter", dropna=False)
        .agg(
            proxy_funded_plans=("service_type_proxy_funded_plans_count", "sum"),
            population=("population_2025_erp", "first"),
        )
        .reset_index()
    )
    area["value"] = (
        pd.to_numeric(area["proxy_funded_plans"], errors="coerce")
        / pd.to_numeric(area["population"], errors="coerce").replace({0: pd.NA})
        * 1000
    )
    area["benchmark"] = "Selected service area"

    national = (
        data.groupby("quarter", dropna=False)
        .agg(
            proxy_funded_plans=("service_type_proxy_funded_plans_count", "sum"),
            population=("population_2025_erp", "sum"),
        )
        .reset_index()
    )
    national["value"] = (
        pd.to_numeric(national["proxy_funded_plans"], errors="coerce")
        / pd.to_numeric(national["population"], errors="coerce").replace({0: pd.NA})
        * 1000
    )
    national["benchmark"] = "National mean"

    if area_remoteness and "remoteness_category" in data.columns:
        rem = (
            data.loc[data["remoteness_category"] == area_remoteness]
            .groupby("quarter", dropna=False)
            .agg(
                proxy_funded_plans=("service_type_proxy_funded_plans_count", "sum"),
                population=("population_2025_erp", "sum"),
            )
            .reset_index()
        )
        rem["value"] = (
            pd.to_numeric(rem["proxy_funded_plans"], errors="coerce")
            / pd.to_numeric(rem["population"], errors="coerce").replace({0: pd.NA})
            * 1000
        )
        rem["benchmark"] = f"{area_remoteness} mean"
    else:
        rem = pd.DataFrame(columns=["quarter", "value", "benchmark"])

    plot = pd.concat(
        [
            area[["quarter", "value", "benchmark"]],
            national[["quarter", "value", "benchmark"]],
            rem[["quarter", "value", "benchmark"]],
        ],
        ignore_index=True,
    )

    plot["value"] = pd.to_numeric(plot["value"], errors="coerce")
    plot = plot.dropna(subset=["quarter", "value"]).copy()

    if plot.empty:
        plot = pd.DataFrame(
            {
                "quarter": ["No data"],
                "value": [0],
                "benchmark": ["No data"],
            }
        )

    quarter_order = sorted(plot["quarter"].dropna().astype(str).unique().tolist(), key=quarter_sort_key)

    chart = (
        alt.Chart(plot)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X(
                "quarter:N",
                sort=quarter_order,
                title=None,
                axis=alt.Axis(labelAngle=0, labelFontSize=12),
            ),
            y=alt.Y(
                "value:Q",
                title="Proxy funded plans per 1,000 population",
                axis=alt.Axis(labelFontSize=12, titleFontSize=13),
            ),
            color=alt.Color(
                "benchmark:N",
                title=None,
                legend=alt.Legend(
                    orient="top",
                    direction="horizontal",
                    columns=1,
                    labelFontSize=12,
                    symbolSize=120,
                ),
            ),
            strokeDash=alt.StrokeDash("benchmark:N", title=None, legend=None),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("benchmark:N", title="Benchmark"),
                alt.Tooltip("value:Q", title="Proxy plans per 1,000", format=".2f"),
            ],
        )
        .properties(title="Selected service-type intensity against benchmarks", height=430)
    )

    return gm_chart_config(chart)


def render_service_area_dashboard(
    data: pd.DataFrame,
    service_type_data: pd.DataFrame,
    service_area: str,
    quarter: str,
    baseline_quarter: str,
    selected_service_types: list[str],
    exclude_selected: bool,
) -> None:
    area_rows = data.loc[data["ndis_service_area"].astype(str) == str(service_area)].copy()

    if area_rows.empty:
        st.warning(f"No dashboard data found for service area: {service_area}")
        st.link_button("Back to national atlas", "?", use_container_width=True)
        return

    area_label = str(service_area)

    if "service_area_state_label" in area_rows.columns:
        labels = area_rows["service_area_state_label"].dropna().astype(str).unique().tolist()
        if labels:
            area_label = labels[0]

    remoteness = service_area_remoteness(data, service_area)

    st.link_button("← Back to national atlas", "?", use_container_width=False)
    st.title(area_label)
    st.caption("Service-area dashboard with trends from 2022 and benchmarks to national and remoteness category means.")

    if remoteness:
        st.write(f"**Remoteness category:** {remoteness}")

    current = area_rows.loc[area_rows["quarter"] == quarter].copy()

    if current.empty:
        current = area_rows.copy()
        current["_quarter_sort"] = current["quarter"].astype(str).map(quarter_sort_key)
        current = current.sort_values("_quarter_sort").tail(1).drop(columns=["_quarter_sort"])

    current_row = current.iloc[0]

    top = st.columns(5)

    with top[0]:
        st.metric("Quarter", current_row.get("quarter", quarter))

    with top[1]:
        population = pd.to_numeric(pd.Series([current_row.get("population_2025_erp")]), errors="coerce").iloc[0]
        st.metric("Population", f"{population:,.0f}" if pd.notna(population) else "n/a")

    with top[2]:
        funded = pd.to_numeric(pd.Series([current_row.get("funded_plans_count")]), errors="coerce").iloc[0]
        st.metric("Proxy funded plans", f"{funded:,.0f}" if pd.notna(funded) else "n/a")

    with top[3]:
        plans_rate = pd.to_numeric(
            pd.Series([current_row.get("service_area_funded_plans_per_1000_population_2025_erp")]),
            errors="coerce",
        ).iloc[0]
        st.metric("Plans per 1,000", f"{plans_rate:,.2f}" if pd.notna(plans_rate) else "n/a")

    with top[4]:
        utilisation = pd.to_numeric(
            pd.Series([current_row.get("service_area_mean_plan_utilisation")]),
            errors="coerce",
        ).iloc[0]
        st.metric("Mean utilisation", f"{utilisation:,.2f}" if pd.notna(utilisation) else "n/a")

    st.info(
        "Service-type filters use payment-share weighting for funded-plan intensity. "
        "Backcast rows before observed service-type payment data use the earliest available service-type mix. "
        "Mean utilisation remains a whole-area context measure."
    )

    overview_tab, trend_tab, service_type_tab, data_tab = st.tabs(
        ["Trends", "Benchmarks", "Service-type mix", "Data"]
    )

    with overview_tab:
        left, right = st.columns(2, gap="large")

        with left:
            plans_chart = make_service_area_benchmark_line_chart(
                data=data,
                service_area=service_area,
                metric_col="service_area_funded_plans_per_1000_population_2025_erp",
                title="Funded plans per 1,000 population",
                y_title="Plans per 1,000 population",
                metric_kind="plans_per_1000",
                value_format=".2f",
            )
            st.altair_chart(plans_chart, use_container_width=True)

        with right:
            utilisation_chart = make_service_area_benchmark_line_chart(
                data=data,
                service_area=service_area,
                metric_col="service_area_mean_plan_utilisation",
                title="Mean plan utilisation",
                y_title="Mean plan utilisation",
                metric_kind="utilisation",
                value_format=".2f",
            )
            st.altair_chart(utilisation_chart, use_container_width=True)

    with trend_tab:
        left, right = st.columns(2, gap="large")

        with left:
            gap_chart = make_service_area_benchmark_line_chart(
                data=data,
                service_area=service_area,
                metric_col="funded_plans_per_1000_gap_from_national",
                title="Plans per 1,000 gap from national benchmark",
                y_title="Gap from national",
                metric_kind="simple_mean",
                value_format=".2f",
            )
            st.altair_chart(gap_chart, use_container_width=True)

        with right:
            util_gap_chart = make_service_area_benchmark_line_chart(
                data=data,
                service_area=service_area,
                metric_col="mean_plan_utilisation_gap_from_national",
                title="Utilisation gap from national benchmark",
                y_title="Gap from national",
                metric_kind="simple_mean",
                value_format=".2f",
            )
            st.altair_chart(util_gap_chart, use_container_width=True)

    with service_type_tab:
        proxy_mix = make_service_area_service_type_proxy_mix_chart(
            service_type_data=service_type_data,
            service_area=service_area,
            selected_service_types=selected_service_types,
            exclude_selected=exclude_selected,
        )
        st.altair_chart(proxy_mix, use_container_width=True)

        proxy_benchmark = make_service_area_proxy_benchmark_chart(
            service_type_data=service_type_data,
            service_area=service_area,
            selected_service_types=selected_service_types,
            exclude_selected=exclude_selected,
        )
        st.altair_chart(proxy_benchmark, use_container_width=True)

        st.subheader("Service-type rows for selected quarter")

        service_table = service_type_data.loc[
            (service_type_data["ndis_service_area"].astype(str) == str(service_area))
            & (service_type_data["quarter"].astype(str) == str(current_row.get("quarter", quarter)))
        ].copy()

        service_table = filter_service_type_rows_for_selection(
            service_table,
            selected_service_types,
            exclude_selected,
        )

        table_cols = [
            "service_type",
            "service_type_data_status",
            "service_type_payment_share_of_area_total",
            "service_type_proxy_plans_per_1000_population",
            "service_type_proxy_funded_plans_count",
            "service_type_payment_amount",
            "service_type_backcast_source_quarter",
        ]
        table_cols = [c for c in table_cols if c in service_table.columns]

        if service_table.empty:
            st.write("No service-type rows available for this quarter.")
        else:
            st.dataframe(
                format_data(service_table[table_cols]),
                use_container_width=True,
                hide_index=True,
                height=520,
            )

    with data_tab:
        st.subheader("Full service-area time series")

        display_cols = [
            "quarter",
            "baseline_quarter",
            "remoteness_category",
            "service_type_filter_label",
            "included_service_type_share",
            "population_2025_erp",
            "funded_plans_count",
            "service_area_funded_plans_per_1000_population_2025_erp",
            "funded_plans_per_1000_gap_from_national",
            "service_area_mean_plan_utilisation",
            "mean_plan_utilisation_gap_from_national",
            "plans_per_1000_change_from_baseline",
            "mean_plan_utilisation_change_from_baseline",
            "statistical_method_note",
        ]
        display_cols = [c for c in display_cols if c in area_rows.columns]

        area_display = area_rows[display_cols].copy()
        area_display["_quarter_sort"] = area_display["quarter"].astype(str).map(quarter_sort_key)
        area_display = area_display.sort_values("_quarter_sort").drop(columns=["_quarter_sort"])

        st.dataframe(
            format_data(area_display),
            use_container_width=True,
            hide_index=True,
            height=640,
        )











# GOOD MEASURE CLEAN LEFT-MAP RIGHT-INSET ATLAS PATCH
# Fixed-size HTML/SVG atlas.
# Left: national Australia map.
# Right: Brisbane, Sydney, Melbourne, then Perth | Adelaide side by side.
# Custom tooltip only. Native SVG <title> deliberately removed to prevent duplicated tooltips.
# Labels are rendered for every service area whose label anchor falls within the visible tile.

import html as html_lib
import streamlit.components.v1 as components


GM_ATLAS_WIDTH = 1530
GM_ATLAS_HEIGHT = 900

GM_MAIN_TILE = {
    "x": 0,
    "y": 0,
    "w": 1125,
    "h": 900,
    "label": None,
    "draw_area_names": None,
    "focus_area_names": None,
    "cover": False,
    "pad": 0.000,
    "label_font": 7.4,
}

GM_RIGHT_X_NUM = 1140
GM_RIGHT_W_NUM = 380

GM_INSET_TILES = {
    "Brisbane": {
        "x": GM_RIGHT_X_NUM,
        "y": 0,
        "w": GM_RIGHT_W_NUM,
        "h": 165,
        "label": "Brisbane",
        "draw_area_names": [
            "Brisbane",
            "Beenleigh",
            "Ipswich",
            "Caboolture/Strathpine",
            "Maroochydore",
            "Toowoomba",
        ],
        "focus_area_names": [
            "Brisbane",
            "Beenleigh",
            "Ipswich",
            "Caboolture/Strathpine",
        ],
        "cover": True,
        "pad": 0.20,
        "label_font": 8.8,
    },
    "Sydney": {
        "x": GM_RIGHT_X_NUM,
        "y": 175,
        "w": GM_RIGHT_W_NUM,
        "h": 245,
        "label": "Sydney metro",
        "draw_area_names": [
            "Sydney",
            "North Sydney",
            "South Eastern Sydney",
            "South Western Sydney",
            "Western Sydney",
            "Nepean Blue Mountains",
            "Central Coast",
            "Illawarra Shoalhaven",
        ],
        "focus_area_names": [
            "Sydney",
            "North Sydney",
            "South Eastern Sydney",
        ],
        "cover": True,
        "pad": 0.42,
        "label_font": 8.8,
    },
    "Melbourne": {
        "x": GM_RIGHT_X_NUM,
        "y": 430,
        "w": GM_RIGHT_W_NUM,
        "h": 245,
        "label": "Melbourne metro",
        "draw_area_names": [
            "Inner East Melbourne",
            "North East Melbourne",
            "Hume Moreland",
            "Western Melbourne",
            "Southern Melbourne",
            "Outer East Melbourne",
            "Bayside Peninsula",
            "Brimbank Melton",
            "Barwon",
        ],
        # Tight metro focus. Outer East and Barwon are still drawn and clipped to the edges.
        "focus_area_names": [
            "Inner East Melbourne",
            "North East Melbourne",
            "Hume Moreland",
            "Western Melbourne",
            "Southern Melbourne",
            "Bayside Peninsula",
            "Brimbank Melton",
        ],
        "cover": True,
        "pad": 0.055,
        "label_font": 8.8,
    },
    "Perth": {
        "x": GM_RIGHT_X_NUM,
        "y": 685,
        "w": 185,
        "h": 215,
        "label": "Perth",
        "draw_area_names": [
            "Central North Metro",
            "Central South Metro",
            "North East Metro",
            "North Metro",
            "South East Metro",
            "South Metro",
        ],
        "focus_area_names": [
            "Central North Metro",
            "Central South Metro",
            "North East Metro",
            "North Metro",
            "South East Metro",
            "South Metro",
        ],
        "cover": True,
        "pad": 0.12,
        "label_font": 7.8,
    },
    "Adelaide": {
        "x": GM_RIGHT_X_NUM + 195,
        "y": 685,
        "w": 185,
        "h": 215,
        "label": "Adelaide",
        "draw_area_names": [
            "Northern Adelaide",
            "Western Adelaide",
            "Eastern Adelaide",
            "Southern Adelaide",
            "Adelaide Hills",
        ],
        "focus_area_names": [
            "Northern Adelaide",
            "Western Adelaide",
            "Eastern Adelaide",
            "Southern Adelaide",
            "Adelaide Hills",
        ],
        "cover": True,
        "pad": 0.12,
        "label_font": 7.8,
    },
}


def make_service_area_url(value) -> str:
    from urllib.parse import quote

    if value is None or pd.isna(value):
        return "?"

    return "?view=service_area&service_area=" + quote(str(value), safe="")


def get_query_param(name: str):
    try:
        value = st.query_params.get(name, None)

        if isinstance(value, list):
            return value[0] if value else None

        return value

    except Exception:
        try:
            params = st.experimental_get_query_params()
            value = params.get(name, None)

            if isinstance(value, list):
                return value[0] if value else None

            return value

        except Exception:
            return None


def gm_rows_for_names(
    gdf_projected: gpd.GeoDataFrame,
    area_names: list[str] | None,
) -> gpd.GeoDataFrame:
    if area_names is None:
        return gdf_projected.copy()

    rows = gdf_projected.loc[
        gdf_projected["ndis_service_area"].astype(str).isin(area_names)
    ].copy()

    if not rows.empty:
        return rows

    pattern = "|".join(re.escape(x) for x in area_names)

    if not pattern:
        return gdf_projected.iloc[0:0].copy()

    return gdf_projected.loc[
        gdf_projected["ndis_service_area"].astype(str).str.contains(pattern, case=False, na=False)
    ].copy()


def gm_expand_bounds(
    bounds: tuple[float, float, float, float],
    frac: float,
) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = bounds

    width = max_x - min_x
    height = max_y - min_y

    if width <= 0 or height <= 0:
        return bounds

    return (
        min_x - (width * frac),
        min_y - (height * frac),
        max_x + (width * frac),
        max_y + (height * frac),
    )


def gm_bounds_for_tile(
    draw_rows: gpd.GeoDataFrame,
    focus_rows: gpd.GeoDataFrame,
    fallback: gpd.GeoDataFrame,
    tile: dict,
) -> tuple[float, float, float, float]:
    pad = float(tile.get("pad", 0.025))

    # National map: use controlled Australia extent so the panel does not waste
    # space on stray or offshore bounds.
    if tile.get("draw_area_names") is None and tile.get("focus_area_names") is None:
        bounds = projected_bounds_from_lonlat(AUSTRALIA_BOUNDS)
        return gm_expand_bounds(bounds, frac=pad)

    if not focus_rows.empty:
        bounds = tuple(focus_rows.total_bounds)
    elif not draw_rows.empty:
        bounds = tuple(draw_rows.total_bounds)
    else:
        bounds = tuple(fallback.total_bounds)

    return gm_expand_bounds(bounds, frac=pad)


def gm_project_point(
    x: float,
    y: float,
    bounds: tuple[float, float, float, float],
    tile: dict,
    cover: bool,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bounds

    source_w = max_x - min_x
    source_h = max_y - min_y

    if source_w == 0 or source_h == 0:
        return tile["x"], tile["y"]

    tile_w = tile["w"]
    tile_h = tile["h"]

    if cover:
        scale = max(tile_w / source_w, tile_h / source_h)
    else:
        scale = min(tile_w / source_w, tile_h / source_h)

    rendered_w = source_w * scale
    rendered_h = source_h * scale

    offset_x = tile["x"] + ((tile_w - rendered_w) / 2)
    offset_y = tile["y"] + ((tile_h - rendered_h) / 2)

    svg_x = offset_x + ((x - min_x) * scale)
    svg_y = offset_y + ((max_y - y) * scale)

    return svg_x, svg_y


def gm_point_inside_tile(x: float, y: float, tile: dict) -> bool:
    return (
        x >= tile["x"]
        and x <= tile["x"] + tile["w"]
        and y >= tile["y"]
        and y <= tile["y"] + tile["h"]
    )


def gm_polygon_to_path(
    polygon,
    bounds: tuple[float, float, float, float],
    tile: dict,
    cover: bool,
) -> str:
    parts = []

    def ring_to_path(coords):
        ring = []
        first = True

        for x, y in coords:
            sx, sy = gm_project_point(
                x=x,
                y=y,
                bounds=bounds,
                tile=tile,
                cover=cover,
            )

            if first:
                ring.append(f"M {sx:.2f} {sy:.2f}")
                first = False
            else:
                ring.append(f"L {sx:.2f} {sy:.2f}")

        ring.append("Z")
        return " ".join(ring)

    if polygon.exterior is not None:
        parts.append(ring_to_path(polygon.exterior.coords))

    for interior in polygon.interiors:
        parts.append(ring_to_path(interior.coords))

    return " ".join(parts)


def gm_geometry_to_path(
    geometry,
    bounds: tuple[float, float, float, float],
    tile: dict,
    cover: bool,
) -> str:
    if geometry is None or geometry.is_empty:
        return ""

    if geometry.geom_type == "Polygon":
        return gm_polygon_to_path(
            polygon=geometry,
            bounds=bounds,
            tile=tile,
            cover=cover,
        )

    if geometry.geom_type == "MultiPolygon":
        return " ".join(
            gm_polygon_to_path(
                polygon=poly,
                bounds=bounds,
                tile=tile,
                cover=cover,
            )
            for poly in geometry.geoms
            if poly is not None and not poly.is_empty
        )

    if geometry.geom_type == "GeometryCollection":
        return " ".join(
            gm_geometry_to_path(
                geometry=part,
                bounds=bounds,
                tile=tile,
                cover=cover,
            )
            for part in geometry.geoms
            if part is not None and not part.is_empty
        )

    return ""


def gm_tooltip_attr(row: pd.Series, metric: str) -> str:
    return svg_escape(build_svg_tooltip(row, metric))


def gm_label_text(row: pd.Series) -> str:
    value = str(row.get("ndis_service_area", ""))

    replacements = {
        "South Eastern Sydney": "SE Sydney",
        "South Western Sydney": "SW Sydney",
        "Nepean Blue Mountains": "Nepean BM",
        "Illawarra Shoalhaven": "Illawarra",
        "Central North Metro": "Central N",
        "Central South Metro": "Central S",
        "North East Metro": "North East",
        "South East Metro": "South East",
        "Inner East Melbourne": "Inner East",
        "North East Melbourne": "North East",
        "Outer East Melbourne": "Outer East",
        "Western Melbourne": "Western",
        "Southern Melbourne": "Southern",
        "Bayside Peninsula": "Bayside",
        "Brimbank Melton": "Brimbank",
        "Caboolture/Strathpine": "Cab/Strath",
        "Northern Adelaide": "Northern",
        "Western Adelaide": "Western",
        "Eastern Adelaide": "Eastern",
        "Southern Adelaide": "Southern",
        "Adelaide Hills": "Hills",
    }

    return replacements.get(value, value)


def gm_label_for_row(
    row: pd.Series,
    bounds: tuple[float, float, float, float],
    tile: dict,
    cover: bool,
) -> str:
    geom = row.geometry

    if geom is None or geom.is_empty:
        return ""

    try:
        point = geom.representative_point()
    except Exception:
        return ""

    x, y = gm_project_point(
        x=point.x,
        y=point.y,
        bounds=bounds,
        tile=tile,
        cover=cover,
    )

    if not gm_point_inside_tile(x, y, tile):
        return ""

    label = svg_escape(gm_label_text(row))
    font_size = float(tile.get("label_font", 8.0))

    return (
        f"<text "
        f"x='{x:.2f}' "
        f"y='{y:.2f}' "
        f"class='gm-service-label' "
        f"font-size='{font_size}' "
        f"text-anchor='middle' "
        f"dominant-baseline='central'"
        f">{label}</text>"
    )


def gm_build_map_tile(
    gdf_projected: gpd.GeoDataFrame,
    metric: str,
    tile: dict,
    is_main: bool,
) -> str:
    draw_rows = gm_rows_for_names(gdf_projected, tile.get("draw_area_names"))
    focus_rows = gm_rows_for_names(gdf_projected, tile.get("focus_area_names"))

    bounds = gm_bounds_for_tile(
        draw_rows=draw_rows,
        focus_rows=focus_rows,
        fallback=gdf_projected,
        tile=tile,
    )

    min_val, max_val = metric_domain(gdf_projected, metric)

    parts = []

    parts.append(
        f"<rect "
        f"x='{tile['x']}' y='{tile['y']}' "
        f"width='{tile['w']}' height='{tile['h']}' "
        f"class='gm-tile-bg'"
        f"></rect>"
    )

    clip_id = "clip_" + re.sub(r"[^a-zA-Z0-9]+", "_", str(tile.get("label") or "Australia"))

    parts.append(
        f"<clipPath id='{clip_id}'>"
        f"<rect x='{tile['x']}' y='{tile['y']}' width='{tile['w']}' height='{tile['h']}'></rect>"
        f"</clipPath>"
    )

    path_parts = []
    label_parts = []

    for _, row in draw_rows.iterrows():
        geom = row.geometry

        if geom is None or geom.is_empty:
            continue

        path_data = gm_geometry_to_path(
            geometry=geom,
            bounds=bounds,
            tile=tile,
            cover=bool(tile.get("cover")),
        )

        if not path_data:
            continue

        fill = gm_colour_for_metric(row.get(metric), min_val, max_val, metric)
        service_area_raw = row.get("ndis_service_area")
        service_area = svg_escape(service_area_raw)
        service_area_url = svg_escape(make_service_area_url(service_area_raw))
        tooltip_attr = gm_tooltip_attr(row, metric)

        # No SVG <title>. The custom HTML tooltip is the only tooltip source.
        path_parts.append(
            f"<a href='{service_area_url}' target='_blank' class='service-area-link' data-url='{service_area_url}'>"
            f"<path "
            f"d='{path_data}' "
            f"class='service-area-path' "
            f"fill='{fill}' "
            f"stroke='{GM_NAVY}' "
            f"stroke-width='1.05' "
            f"vector-effect='non-scaling-stroke' "
            f"data-service='{service_area}' "
            f"data-url='{service_area_url}' "
            f"data-tooltip='{tooltip_attr}'"
            f"></path>"
            f"</a>"
        )

        label_markup = gm_label_for_row(
            row=row,
            bounds=bounds,
            tile=tile,
            cover=bool(tile.get("cover")),
        )

        if label_markup:
            label_parts.append(label_markup)

    parts.append(
        f"<g clip-path='url(#{clip_id})'>"
        f"{''.join(path_parts)}"
        f"<g class='gm-service-label-layer'>{''.join(label_parts)}</g>"
        f"</g>"
    )

    if tile.get("label"):
        parts.append(
            f"<text "
            f"x='{tile['x'] + 8}' "
            f"y='{tile['y'] + 19}' "
            f"class='gm-label-text'"
            f">{svg_escape(tile['label'])}</text>"
        )

    return "\n".join(parts)


def render_map_atlas(
    merged: gpd.GeoDataFrame,
    metric: str,
) -> None:
    """Render clean fixed atlas with labelled national map and right-side insets."""

    gdf = merged.copy()

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")

    gdf = gdf.to_crs("EPSG:3577")
    gdf[metric] = pd.to_numeric(gdf[metric], errors="coerce")

    svg_parts = []

    svg_parts.append(
        gm_build_map_tile(
            gdf_projected=gdf,
            metric=metric,
            tile=GM_MAIN_TILE,
            is_main=True,
        )
    )

    for _, tile in GM_INSET_TILES.items():
        svg_parts.append(
            gm_build_map_tile(
                gdf_projected=gdf,
                metric=metric,
                tile=tile,
                is_main=False,
            )
        )

    atlas_html = f"""
    <!doctype html>
    <html>
    <head>
    <base target="_blank">
    <style>
    html,
    body {{
        margin: 0;
        padding: 0;
        width: {GM_ATLAS_WIDTH}px;
        height: {GM_ATLAS_HEIGHT}px;
        background: transparent;
        overflow: hidden;
        font-family: Segoe UI, Arial, Helvetica, sans-serif;
    }}

    .gm-atlas {{
        width: {GM_ATLAS_WIDTH}px;
        height: {GM_ATLAS_HEIGHT}px;
        display: block;
        background: transparent;
    }}

    .gm-tile-bg {{
        fill: rgba(255,255,255,1);
        stroke: #000000;
        stroke-width: 2;
    }}

    .service-area-link,
    .service-area-link:visited,
    .service-area-link:hover,
    .service-area-link:active {{
        cursor: pointer;
        text-decoration: none;
    }}

    .service-area-path {{
        cursor: pointer;
        fill-opacity: 0.84;
        pointer-events: all;
        transition: fill-opacity 0.08s ease, stroke-width 0.08s ease;
    }}

    .service-area-path:hover {{
        fill-opacity: 0.98;
        stroke: #000000;
        stroke-width: 2.8;
    }}

    .gm-label-text {{
        font-size: 13px;
        font-weight: 700;
        fill: {GM_NAVY};
        paint-order: stroke;
        stroke: rgba(255,247,230,0.96);
        stroke-width: 5px;
        stroke-linejoin: round;
        pointer-events: none;
    }}

    .gm-service-label {{
        font-family: Segoe UI, Arial, Helvetica, sans-serif;
        font-weight: 700;
        fill: {GM_NAVY};
        paint-order: stroke;
        stroke: rgba(255,247,230,0.90);
        stroke-width: 3px;
        stroke-linejoin: round;
        pointer-events: auto;
        opacity: 0.88;
    }}

    .service-area-label-link,
    .service-area-label-link:visited,
    .service-area-label-link:hover,
    .service-area-label-link:active {{
        cursor: pointer;
        text-decoration: none;
    }}

    .gm-label-leader {{
        stroke: {GM_NAVY};
        stroke-width: 1.15;
        stroke-opacity: 0.78;
        vector-effect: non-scaling-stroke;
        pointer-events: none;
    }}

    .service-area-label-link .gm-service-label {{
        pointer-events: all;
        cursor: pointer;
    }}

    .service-area-label-link:hover .gm-service-label {{
        fill: #000000;
        opacity: 1.0;
    }}

    #gm-tooltip {{
        position: fixed;
        z-index: 2147483647;
        display: none;
        width: max-content;
        max-width: min(760px, calc(100vw - 32px));
        background: rgba(255, 247, 230, 0.985);
        color: {GM_NAVY};
        border: 1px solid #000000;
        border-radius: 5px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.30);
        padding: 8px 10px;
        font-size: 12px;
        line-height: 1.3;
        pointer-events: none;
        white-space: nowrap;
        box-sizing: border-box;
    }}

    .tooltip-row {{
        display: grid;
        grid-template-columns: max-content max-content;
        column-gap: 12px;
        align-items: baseline;
        width: max-content;
        white-space: nowrap;
        font-size: 12px;
        line-height: 1.3;
    }}

    .tooltip-label {{
        font-weight: 700;
        color: {GM_NAVY};
        text-align: right;
        white-space: nowrap;
    }}

    .tooltip-value {{
        color: {GM_NAVY};
        text-align: left;
        white-space: nowrap;
    }}
    </style>
    </head>
    <body>
        <svg
            class="gm-atlas"
            viewBox="0 0 {GM_ATLAS_WIDTH} {GM_ATLAS_HEIGHT}"
            preserveAspectRatio="xMinYMin meet"
            xmlns="http://www.w3.org/2000/svg"
        >
            {''.join(svg_parts)}
        </svg>
        <div id="gm-tooltip"></div>

        <script>
        const tooltip = document.getElementById("gm-tooltip");

        function parentBaseUrl() {{
            const referrer = document.referrer;

            if (referrer && referrer.length > 0) {{
                try {{
                    return new URL(referrer);
                }} catch (err) {{}}
            }}

            try {{
                return new URL(window.top.location.href);
            }} catch (err) {{}}

            try {{
                return new URL(window.parent.location.href);
            }} catch (err) {{}}

            return new URL(window.location.href);
        }}

        function absoluteTopUrl(relativeUrl) {{
            const base = parentBaseUrl();
            const target = new URL(relativeUrl, base.href);
            return target.toString();
        }}

        function openTop(relativeUrl) {{
            const target = absoluteTopUrl(relativeUrl);

            try {{
                window.open(target, "_blank", "noopener,noreferrer");
                return false;
            }} catch (err) {{}}

            try {{
                window.open(target, "_blank", "noopener,noreferrer");
                return false;
            }} catch (err) {{}}

            try {{
                window.open(target, "_blank", "noopener,noreferrer");
                return false;
            }} catch (err) {{}}

            window.open(target, "_blank", "noopener,noreferrer");
            return false;
        }}

        function showTooltip(event) {{
            const path = event.currentTarget;
            const html = path.getAttribute("data-tooltip");

            if (!html) {{
                return;
            }}

            tooltip.innerHTML = html;
            tooltip.style.display = "block";
            moveTooltip(event);
        }}

        function moveTooltip(event) {{
            if (!tooltip || tooltip.style.display === "none") {{
                return;
            }}

            const pad = 16;
            const rect = tooltip.getBoundingClientRect();

            let x = event.clientX + 14;
            let y = event.clientY + 14;

            const maxX = window.innerWidth - rect.width - pad;
            const maxY = window.innerHeight - rect.height - pad;

            if (x > maxX) {{
                x = event.clientX - rect.width - 14;
            }}

            if (y > maxY) {{
                y = event.clientY - rect.height - 14;
            }}

            x = Math.max(pad, x);
            y = Math.max(pad, y);

            tooltip.style.left = x + "px";
            tooltip.style.top = y + "px";
        }}

        function hideTooltip() {{
            tooltip.style.display = "none";
        }}

        document.querySelectorAll(".service-area-link").forEach(function(link) {{
            const relativeUrl = link.getAttribute("data-url");

            if (relativeUrl) {{
                link.setAttribute("href", absoluteTopUrl(relativeUrl));
                link.setAttribute("target", "_blank");
            }}

            link.addEventListener("click", function(event) {{
                event.preventDefault();
                event.stopPropagation();

                const url = link.getAttribute("data-url");

                if (url) {{
                    openTop(url);
                }}

                return false;
            }});
        }});

        document.querySelectorAll(".service-area-path").forEach(function(path) {{
            path.addEventListener("mouseenter", showTooltip);
            path.addEventListener("mousemove", moveTooltip);
            path.addEventListener("mouseleave", hideTooltip);

            path.addEventListener("click", function(event) {{
                event.preventDefault();
                event.stopPropagation();

                const url = path.getAttribute("data-url");

                if (url) {{
                    openTop(url);
                }}

                return false;
            }});
        }});
        </script>
    </body>
    </html>
    """

    components.html(
        atlas_html,
        width=GM_ATLAS_WIDTH,
        height=GM_ATLAS_HEIGHT,
        scrolling=False,
    )

    with st.expander("Open service-area dashboard manually"):
        manual_area = st.selectbox(
            "Service area",
            options=sorted(gdf["ndis_service_area"].dropna().astype(str).unique().tolist()),
            index=None,
            placeholder="Choose a service area",
        )

        if manual_area:
            st.link_button(
                "Open selected service-area dashboard",
                make_service_area_url(manual_area),
                use_container_width=True,
            )





# GOOD MEASURE LABEL DECLUTTER PATCH
# National map: no fixed labels. Hover and click remain.
# Insets: labels and leader lines remain, and labels are clickable.

GM_LABEL_OFFSETS = {
    # Sydney / NSW dense labels
    "Sydney": (0, -54),
    "North Sydney": (96, -34),
    "South Eastern Sydney": (104, 48),
    "South Western Sydney": (-118, 62),
    "Western Sydney": (-114, -12),
    "Nepean Blue Mountains": (-142, -54),
    "Central Coast": (104, -68),
    "Illawarra Shoalhaven": (122, 84),

    # Melbourne dense labels
    "Inner East Melbourne": (96, -58),
    "North East Melbourne": (122, -18),
    "Hume Moreland": (-110, -66),
    "Western Melbourne": (-120, 0),
    "Southern Melbourne": (68, 74),
    "Bayside Peninsula": (128, 50),
    "Brimbank Melton": (-126, 66),
    "Outer East Melbourne": (146, -46),
    "Barwon": (-132, 88),

    # Brisbane / SEQ dense labels
    "Brisbane": (94, -52),
    "Beenleigh": (108, 56),
    "Ipswich": (-104, 48),
    "Caboolture/Strathpine": (-130, -50),
    "Maroochydore": (122, -74),
    "Toowoomba": (-140, 72),

    # Perth
    "Central North Metro": (0, -68),
    "Central South Metro": (0, 68),
    "North East Metro": (96, -32),
    "North Metro": (-100, -42),
    "South East Metro": (104, 42),
    "South Metro": (-100, 54),

    # Adelaide
    "Northern Adelaide": (0, -70),
    "Western Adelaide": (-100, -4),
    "Eastern Adelaide": (104, -16),
    "Southern Adelaide": (0, 72),
    "Adelaide Hills": (116, 56),
}


def gm_label_text(row: pd.Series) -> str:
    value = str(row.get("ndis_service_area", ""))

    replacements = {
        "South Eastern Sydney": "SE Sydney",
        "South Western Sydney": "SW Sydney",
        "Nepean Blue Mountains": "Nepean BM",
        "Illawarra Shoalhaven": "Illawarra",
        "Central North Metro": "Central N",
        "Central South Metro": "Central S",
        "North East Metro": "North East",
        "South East Metro": "South East",
        "Inner East Melbourne": "Inner East",
        "North East Melbourne": "North East",
        "Outer East Melbourne": "Outer East",
        "Western Melbourne": "Western",
        "Southern Melbourne": "Southern",
        "Bayside Peninsula": "Bayside",
        "Brimbank Melton": "Brimbank",
        "Caboolture/Strathpine": "Cab/Strath",
        "Northern Adelaide": "Northern",
        "Western Adelaide": "Western",
        "Eastern Adelaide": "Eastern",
        "Southern Adelaide": "Southern",
        "Adelaide Hills": "Hills",
    }

    return replacements.get(value, value)


def gm_clamp_label_point(x: float, y: float, tile: dict, margin: float = 18) -> tuple[float, float]:
    x = max(tile["x"] + margin, min(tile["x"] + tile["w"] - margin, x))
    y = max(tile["y"] + margin, min(tile["y"] + tile["h"] - margin, y))
    return x, y


def gm_auto_offset(anchor_x: float, anchor_y: float, tile: dict) -> tuple[float, float]:
    centre_x = tile["x"] + (tile["w"] / 2)
    centre_y = tile["y"] + (tile["h"] / 2)

    dx = anchor_x - centre_x
    dy = anchor_y - centre_y

    if abs(dx) < 1 and abs(dy) < 1:
        return 0, -42

    scale = max((dx * dx + dy * dy) ** 0.5, 1)

    return (dx / scale) * 46, (dy / scale) * 46


def gm_label_for_row(
    row: pd.Series,
    bounds: tuple[float, float, float, float],
    tile: dict,
    cover: bool,
) -> str:
    # Do not label the national map. It is too dense and reduces usability.
    # National service areas remain clickable and available through hover.
    if not tile.get("label"):
        return ""

    geom = row.geometry

    if geom is None or geom.is_empty:
        return ""

    try:
        point = geom.representative_point()
    except Exception:
        return ""

    anchor_x, anchor_y = gm_project_point(
        x=point.x,
        y=point.y,
        bounds=bounds,
        tile=tile,
        cover=cover,
    )

    if not gm_point_inside_tile(anchor_x, anchor_y, tile):
        return ""

    area_name = str(row.get("ndis_service_area", ""))
    dx, dy = GM_LABEL_OFFSETS.get(area_name, gm_auto_offset(anchor_x, anchor_y, tile))

    label_x, label_y = gm_clamp_label_point(anchor_x + dx, anchor_y + dy, tile)

    label = svg_escape(gm_label_text(row))
    service_area_url = svg_escape(make_service_area_url(area_name))

    return (
        f"<a "
        f"href='{service_area_url}' "
        f"target='_blank' "
        f"class='service-area-label-link service-area-link' "
        f"data-url='{service_area_url}' "
        f"aria-label='Open dashboard for {svg_escape(area_name)}'>"
        f"<g class='gm-service-label-callout'>"
        f"<line "
        f"x1='{anchor_x:.2f}' y1='{anchor_y:.2f}' "
        f"x2='{label_x:.2f}' y2='{label_y:.2f}' "
        f"class='gm-label-leader'"
        f"></line>"
        f"<text "
        f"x='{label_x:.2f}' "
        f"y='{label_y:.2f}' "
        f"class='gm-service-label' "
        f"font-size='11.2' "
        f"text-anchor='middle' "
        f"dominant-baseline='central'"
        f">{label}</text>"
        f"</g>"
        f"</a>"
    )



# GOOD MEASURE COLOUR FUNCTION REPAIR PATCH
GM_DARK_NAVY = "#061A2E"
GM_NAVY = GM_DARK_NAVY
GM_AMBER = "#F2B705"
GM_ORANGE = GM_AMBER
GM_BG = "#FFFFFF"
GM_TEXT = GM_DARK_NAVY

GM_MAP_GREEN = "#2E7D32"
GM_MAP_RED = "#B3261E"
GM_MAP_NEUTRAL = "#FFFFFF"


def gm_hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = str(value).strip().lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def gm_rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def gm_lerp_colour(left: str, right: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))

    left_rgb = gm_hex_to_rgb(left)
    right_rgb = gm_hex_to_rgb(right)

    out = tuple(
        int(round(left_rgb[i] + ((right_rgb[i] - left_rgb[i]) * t)))
        for i in range(3)
    )

    return gm_rgb_to_hex(out)


def gm_base_diverging_colour(value, min_val, max_val) -> str:
    val = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]

    if pd.isna(val):
        return "#D9D9D9"

    min_num = pd.to_numeric(pd.Series([min_val]), errors="coerce").iloc[0]
    max_num = pd.to_numeric(pd.Series([max_val]), errors="coerce").iloc[0]

    if pd.isna(min_num) or pd.isna(max_num) or min_num == max_num:
        if val > 0:
            return GM_MAP_GREEN
        if val < 0:
            return GM_MAP_RED
        return GM_MAP_NEUTRAL

    # Diverging metric where zero is meaningful.
    if min_num < 0 and max_num > 0:
        max_abs = max(abs(min_num), abs(max_num), 1e-9)

        if val >= 0:
            return gm_lerp_colour(GM_MAP_NEUTRAL, GM_MAP_GREEN, abs(val) / max_abs)

        return gm_lerp_colour(GM_MAP_NEUTRAL, GM_MAP_RED, abs(val) / max_abs)

    # Positive-only metric. Larger positive value = greener.
    if min_num >= 0:
        t = (val - min_num) / max((max_num - min_num), 1e-9)
        return gm_lerp_colour(GM_MAP_NEUTRAL, GM_MAP_GREEN, t)

    # Negative-only metric. More negative = redder.
    if max_num <= 0:
        t = (max_num - val) / max((max_num - min_num), 1e-9)
        return gm_lerp_colour(GM_MAP_NEUTRAL, GM_MAP_RED, t)

    return GM_MAP_NEUTRAL


def gm_colour_for_metric(value, min_val, max_val, metric: str) -> str:
    metric_l = str(metric).lower()

    # For utilisation gap, under-utilisation should be red.
    # In the current dashboard convention, positive utilisation gap means below benchmark.
    if "mean_plan_utilisation_gap" in metric_l or "mean_plan_utilization_gap" in metric_l:
        val = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        min_num = pd.to_numeric(pd.Series([min_val]), errors="coerce").iloc[0]
        max_num = pd.to_numeric(pd.Series([max_val]), errors="coerce").iloc[0]

        if pd.isna(val):
            return "#D9D9D9"

        return gm_base_diverging_colour(
            value=-val,
            min_val=-max_num if pd.notna(max_num) else min_val,
            max_val=-min_num if pd.notna(min_num) else max_val,
        )

    return gm_base_diverging_colour(
        value=value,
        min_val=min_val,
        max_val=max_val,
    )


def svg_colour_for_value(value, min_val, max_val) -> str:
    # Backward-compatible wrapper for any older code paths still using this name.
    return gm_base_diverging_colour(value=value, min_val=min_val, max_val=max_val)



# GOOD MEASURE REMOVE ALL SERVICE-AREA LABELS PATCH
# Keep map panel titles. Remove permanent service-area labels from both the national map and inset maps.
# Hover tooltips and click-through paths remain active.

def gm_label_for_row(
    row: pd.Series,
    bounds: tuple[float, float, float, float],
    tile: dict,
    cover: bool,
) -> str:
    return ""


def main() -> None:
    st.set_page_config(
        page_title="Good Measure | NDIS service-area evidence map",
        layout="wide",
    )

    apply_good_measure_theme()

    st.title("Good Measure | NDIS service-area evidence map")
    st.caption("For community. Data beyond compliance. Evidence with purpose.")

    raw_data = load_data()
    raw_data = add_state_labels(raw_data)
    service_type_data = load_service_type_data()
    service_type_data = add_state_labels(service_type_data)
    geo = load_geo()

    quarters = sorted(raw_data["quarter"].dropna().unique())
    baseline_index = quarters.index(BASELINE_QUARTER_DEFAULT) if BASELINE_QUARTER_DEFAULT in quarters else 0

    sidebar = st.sidebar
    sidebar.header("Filters")

    quarter = sidebar.selectbox("Quarter", quarters, index=len(quarters) - 1)

    baseline_quarter = sidebar.selectbox(
        "Baseline quarter for change measures",
        quarters,
        index=baseline_index,
    )

    metric = sidebar.selectbox(
        "Primary metric",
        options=list(METRIC_LABELS.keys()),
        format_func=lambda x: METRIC_LABELS[x],
    )

    remoteness_values = sorted(raw_data["remoteness_category"].dropna().unique().tolist())

    remoteness_mode = sidebar.radio(
        "Remoteness",
        options=["All remoteness categories", "Select categories"],
        index=0,
    )

    if remoteness_mode == "All remoteness categories":
        selected_remoteness = remoteness_values
    else:
        selected_remoteness = sidebar.multiselect(
            "Select remoteness categories",
            options=remoteness_values,
            default=remoteness_values,
        )

    sidebar.markdown("---")
    sidebar.subheader("Service type filter")

    all_service_types = [x for x in SERVICE_TYPE_ORDER if x in set(service_type_data["service_type"].dropna().unique())]

    service_type_mode = sidebar.radio(
        "Service type mode",
        options=[
            "All service types",
            "Choose categories to include",
        ],
        index=0,
    )

    exclude_selected = False
    selected_service_types = all_service_types

    if service_type_mode == "Choose categories to include":
        exclude_selected = sidebar.checkbox(
            "Exclude selected categories instead of include",
            value=False,
        )

        selected_service_types = sidebar.multiselect(
            "Tick service types",
            options=all_service_types,
            default=all_service_types,
        )

        col_a, col_b = sidebar.columns(2)

        with col_a:
            if st.button("Select all service types", use_container_width=True):
                selected_service_types = all_service_types
        with col_b:
            if st.button("Clear service types", use_container_width=True):
                selected_service_types = []

    rank_direction = sidebar.radio(
        "Rank chart by",
        options=[
            "Largest positive values",
            "Largest negative values",
            "Largest absolute values",
        ],
        index=0,
    )

    service_type_shares = compute_service_type_shares(
        service_type_data=service_type_data,
        service_type_mode=service_type_mode,
        selected_service_types=selected_service_types,
        exclude_selected=exclude_selected,
    )

    weighted_data = apply_service_type_filter_to_metrics(
        raw_data=raw_data,
        service_type_shares=service_type_shares,
    )

    data = add_change_measures(weighted_data, baseline_quarter)

    service_area_param = get_query_param("service_area")
    view_param = get_query_param("view")

    if service_area_param and (view_param == "service_area" or view_param is None):
        render_service_area_dashboard(
            data=data,
            service_type_data=service_type_data,
            service_area=str(service_area_param),
            quarter=quarter,
            baseline_quarter=baseline_quarter,
            selected_service_types=selected_service_types,
            exclude_selected=exclude_selected,
        )
        return

    filtered = prepare_filtered_data(
        data=data,
        quarter=quarter,
        selected_remoteness=selected_remoteness,
        metric=metric,
    )

    merged = merge_geo_data(geo=geo, filtered=filtered)

    top_row = st.columns(5)

    with top_row[0]:
        st.metric("Quarter", quarter)

    with top_row[1]:
        st.metric("Baseline", baseline_quarter)

    with top_row[2]:
        st.metric("Positive values", int((pd.to_numeric(filtered[metric], errors="coerce") > 0).sum()))

    with top_row[3]:
        st.metric("Negative values", int((pd.to_numeric(filtered[metric], errors="coerce") < 0).sum()))

    with top_row[4]:
        mean_share = pd.to_numeric(filtered["included_service_type_share"], errors="coerce").mean()
        st.metric("Mean included share", f"{mean_share:.1%}" if pd.notna(mean_share) else "n/a")

    if service_type_mode == "All service types":
        st.info("Service type filter: all service types included. Metrics match whole-area values.")
    else:
        label = filtered["service_type_filter_label"].dropna().iloc[0] if not filtered.empty else ""
        st.warning(
            "Service-type filtering uses payment-share weighting. "
            "It scales whole-area funded plans per 1,000 and mean utilisation by the included service-type payment share. "
            f"Current filter: {label}"
        )

    if metric in [
        "funded_plans_per_1000_gap_from_national",
        "mean_plan_utilisation_gap_from_national",
    ]:
        st.markdown(
            """
            **Interpretation:** gap is calculated as **national benchmark minus service-area value**.
            Positive values indicate the service area is below the national benchmark.
            Negative values indicate the service area is above the national benchmark.
            """
        )
    else:
        st.markdown(
            """
            **Interpretation:** change is calculated as **selected quarter minus baseline quarter**.
            Positive values indicate an increase since baseline. Negative values indicate a decrease since baseline.
            """
        )

    st.caption(METRIC_HELP[metric])

    map_tab, dashboard_tab, data_tab = st.tabs(["Map", "Dashboard", "Data"])

    with map_tab:
        st.subheader("Static service-area map")
        st.write(
            "Hover over a service area for details. Click a service area to open its dashboard. Permanent service-area labels are hidden to keep the atlas readable."
        )
        render_map_atlas(merged=merged, metric=metric)

    with dashboard_tab:
        left, right = st.columns([1, 1], gap="large")

        with left:
            st.subheader("Ranked service areas")
            ranked_chart = make_ranked_bar_chart(
                filtered=filtered,
                metric=metric,
                rank_direction=rank_direction,
            )
            st.altair_chart(ranked_chart, use_container_width=True)

        with right:
            st.subheader("Mean by remoteness")
            remoteness_chart = make_remoteness_bar_chart(filtered, metric)
            st.altair_chart(remoteness_chart, use_container_width=True)

            st.subheader("Trend by remoteness")
            trend_chart = make_change_over_time_chart(
                data=data,
                metric=metric,
                selected_remoteness=selected_remoteness,
            )
            st.altair_chart(trend_chart, use_container_width=True)

            st.subheader("Plans per 1,000 and utilisation")
            distribution_chart = make_distribution_chart(filtered)
            st.altair_chart(distribution_chart, use_container_width=True)

            st.subheader("Service-type payment mix per 1,000 population")
            stacked_chart = make_service_type_stacked_bar_chart(
                service_type_data=service_type_data,
                quarter=quarter,
                selected_remoteness=selected_remoteness,
                selected_service_types=selected_service_types,
                exclude_selected=exclude_selected,
            )
            st.altair_chart(stacked_chart, use_container_width=True)

    with data_tab:
        st.subheader("Data behind selected view")

        display_cols = [
            "ndis_service_area",
            "state_acronym",
            "service_area_state_label",
            "quarter",
            "baseline_quarter",
            "remoteness_category",
            "service_type_filter_label",
            "included_service_type_share",
            "population_2025_erp",
            "funded_plans_count",
            "service_area_funded_plans_per_1000_population_2025_erp",
            "funded_plans_per_1000_gap_from_national",
            "service_area_mean_plan_utilisation",
            "mean_plan_utilisation_gap_from_national",
            "plans_per_1000_change_from_baseline",
            "mean_plan_utilisation_change_from_baseline",
            "benchmark_position",
        ]

        display_cols = [c for c in display_cols if c in filtered.columns]
        ranked_data = filtered[display_cols].sort_values(metric, ascending=False)
        ranked_data = format_data(ranked_data)

        st.dataframe(
            ranked_data,
            use_container_width=True,
            hide_index=True,
            height=680,
        )

    st.markdown("## Download")

    download_cols = [
        "ndis_service_area",
        "quarter",
        "baseline_quarter",
        "remoteness_category",
        "service_type_filter_label",
        "included_service_type_share",
        "population_2025_erp",
        "funded_plans_count",
        "service_area_funded_plans_per_1000_population_2025_erp",
        "funded_plans_per_1000_gap_from_national",
        "service_area_mean_plan_utilisation",
        "mean_plan_utilisation_gap_from_national",
        "plans_per_1000_change_from_baseline",
        "mean_plan_utilisation_change_from_baseline",
        "benchmark_position",
    ]
    download_cols = [c for c in download_cols if c in filtered.columns]

    st.download_button(
        label="Download filtered service-area table",
        data=filtered[download_cols].to_csv(index=False).encode("utf-8"),
        file_name=f"good_measure_ndis_service_area_{quarter}_{metric}_service_type_filtered.csv",
        mime="text/csv",
    )

    st.markdown("## Method note")

    st.write(
        "NDIS service-area boundaries are approximated by dissolving ABS LGA boundaries "
        "using NDIA service-district to LGA mapping. No usual address, offshore and other "
        "non-mappable special geography records are excluded from polygon construction. "
        "Metrics should be interpreted as service-market evidence, not as official NDIA "
        "boundary determinations."
    )

    st.write(
        "When service-type filtering is active, funded plans per 1,000 population and mean plan utilisation "
        "are payment-share-weighted proxies derived from the custom service-type payment mix. "
        "They are not direct NDIA service-type-specific participant and utilisation measures."
    )

    st.write(
        "This dashboard is an exploratory Good Measure evidence product. It is designed "
        "to support funding, advocacy, service design and discussion about market depth, "
        "equity and plan utilisation across NDIS service areas."
    )


if __name__ == "__main__":
    main()


