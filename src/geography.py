from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from shapely import affinity
from shapely.geometry import mapping, shape

from . import config
from .io_utils import numeric, read_csv, safe_divide


FISCAL_QUARTER_END_MONTH_DAY = {
    1: (9, 30),
    2: (12, 31),
    3: (3, 31),
    4: (6, 30),
}

EXCLUDED_ATLAS_GEOGRAPHIES = {"lord howe island", "norfolk island"}

ATLAS_CANVAS_BOUNDS = (0.0, -60.0, 100.0, 20.0)
ATLAS_MAIN_BOUNDS = (24.0, -38.0, 72.0, 16.0)

METRO_INSET_GROUPS = {
    "Perth inset": {
        "areas": {"Central North Metro", "Central South Metro", "North Metro", "South East Metro", "South Metro"},
        "target_bounds": (3.0, -34.0, 21.0, -16.0),
    },
    "Adelaide inset": {
        "areas": {"Adelaide Hills", "Barossa, Light and Lower North", "Eastern Adelaide", "Northern Adelaide", "Southern Adelaide", "Western Adelaide"},
        "target_bounds": (25.0, -58.0, 64.0, -43.0),
    },
    "Melbourne inset": {
        "areas": {
            "Bayside Peninsula",
            "Brimbank Melton",
            "Hume Moreland",
            "Inner East Melbourne",
            "North East Melbourne",
            "Outer East Melbourne",
            "Southern Melbourne",
            "Western Melbourne",
        },
        "target_bounds": (77.0, -38.0, 97.0, -22.0),
    },
    "Sydney inset": {
        "areas": {"Central Coast", "North Sydney", "South Eastern Sydney", "South Western Sydney", "Sydney", "Western Sydney"},
        "target_bounds": (77.0, -19.0, 97.0, -3.0),
    },
    "Brisbane inset": {
        "areas": {"Beenleigh", "Brisbane", "Caboolture/Strathpine", "Robina"},
        "target_bounds": (77.0, 0.0, 97.0, 16.0),
    },
}


def standardise_code(value: object, width: int | None = None) -> str | pd.NA:
    """Standardise a geography code as a string while preserving leading zeros."""

    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if width and text.isdigit():
        text = text.zfill(width)
    return text


def quarter_label(value: object) -> str:
    """Convert 2025Q4-style values to Tableau label format."""

    match = re.fullmatch(r"(\d{4})Q([1-4])", str(value).strip())
    if not match:
        return str(value)
    return f"{match.group(1)} Q{match.group(2)}"


def quarter_end_date(value: object) -> str | pd.NA:
    """Return the fiscal quarter end date used by NDIA-style financial years."""

    match = re.fullmatch(r"(\d{4})Q([1-4])", str(value).strip())
    if not match:
        return pd.NA
    year = int(match.group(1))
    quarter = int(match.group(2))
    month, day = FISCAL_QUARTER_END_MONTH_DAY[quarter]
    calendar_year = year - 1 if quarter in {1, 2} else year
    return f"{calendar_year:04d}-{month:02d}-{day:02d}"


def quarter_sort_value(value: object) -> int:
    """Return a sortable integer for 2025Q4-style quarter labels."""

    match = re.fullmatch(r"(\d{4})Q([1-4])", str(value).strip())
    if not match:
        return 999999
    return int(match.group(1)) * 10 + int(match.group(2))


def add_quarter_fields(frame: pd.DataFrame, quarter_col: str = "quarter") -> pd.DataFrame:
    """Add Tableau quarter label, end date and sort fields."""

    out = frame.copy()
    out[quarter_col] = out[quarter_col].astype(str)
    out["quarter_label"] = out[quarter_col].map(quarter_label)
    out["quarter_end_date"] = out[quarter_col].map(quarter_end_date)
    out["quarter_sort"] = out[quarter_col].map(quarter_sort_value)
    return out


def build_geography_lookup() -> pd.DataFrame:
    """Create a service-area geography lookup from local context and GeoJSON."""

    context = read_csv(config.SERVICE_AREA_CONTEXT_SOURCE, required=False)
    population = read_csv(config.SERVICE_AREA_POPULATION_SOURCE, required=False)
    remoteness = read_csv(config.SERVICE_AREA_REMOTENESS_SOURCE, required=False)

    if context.empty and not population.empty:
        context = population.copy()
    if context.empty and not remoteness.empty:
        context = remoteness.copy()

    if context.empty:
        return pd.DataFrame(
            columns=[
                "geography_type",
                "geography_code",
                "geography_name",
                "state",
                "remoteness",
                "parent_geography_codes",
                "latitude",
                "longitude",
                "area_sqkm",
                "population",
                "geography_vintage",
                "reliability_flag",
            ]
        )

    if "ndis_service_area" not in context.columns:
        raise ValueError("Service area geography context must include ndis_service_area.")

    out = context.drop_duplicates("ndis_service_area").copy()
    if "population_2025_erp" not in out.columns and "population_2025_erp" in population.columns:
        out = out.merge(population, on="ndis_service_area", how="left", suffixes=("", "_population"))

    out["geography_type"] = "ndia_service_area"
    out["geography_code"] = out["ndis_service_area"].astype(str)
    out["geography_name"] = out["ndis_service_area"].astype(str)
    out["state"] = pd.NA
    if "remoteness_category" in out.columns:
        out["remoteness"] = out["remoteness_category"]
    else:
        out["remoteness"] = pd.NA
    out["parent_geography_codes"] = pd.NA
    out["latitude"] = pd.NA
    out["longitude"] = pd.NA
    out["area_sqkm"] = numeric(out.get("total_mapped_area_sqkm", pd.Series(pd.NA, index=out.index)))
    out["population"] = numeric(out.get("population_2025_erp", pd.Series(pd.NA, index=out.index)))
    out["population"] = out["population"].where(out["population"] > 0)
    out["geography_vintage"] = "NDIA Service Area assembled from LGA 2021 context; population 2025 ERP"
    out["reliability_flag"] = config.RELIABILITY_FLAGS["derived"]

    if config.SERVICE_AREA_GEOJSON_SOURCE.exists():
        centroids = _centroids_from_geojson(config.SERVICE_AREA_GEOJSON_SOURCE)
        if not centroids.empty:
            out = out.merge(centroids, on="geography_code", how="left", suffixes=("", "_geometry"))
            out["latitude"] = out["latitude_geometry"].combine_first(out["latitude"])
            out["longitude"] = out["longitude_geometry"].combine_first(out["longitude"])
            out = out.drop(columns=[col for col in ["latitude_geometry", "longitude_geometry"] if col in out.columns])

    return out[
        [
            "geography_type",
            "geography_code",
            "geography_name",
            "state",
            "remoteness",
            "parent_geography_codes",
            "latitude",
            "longitude",
            "area_sqkm",
            "population",
            "geography_vintage",
            "reliability_flag",
        ]
    ].sort_values(["geography_type", "geography_code"])


def _centroids_from_geojson(path: Path) -> pd.DataFrame:
    """Extract approximate centroids from GeoJSON feature bounding boxes."""

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    rows: list[dict] = []
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        coords = list(_iter_coordinates(feature.get("geometry", {})))
        if not coords:
            continue
        xs = [x for x, _ in coords]
        ys = [y for _, y in coords]
        rows.append(
            {
                "geography_code": str(props.get("ndis_service_area") or props.get("map_key") or props.get("name")),
                "longitude": sum(xs) / len(xs),
                "latitude": sum(ys) / len(ys),
            }
        )
    return pd.DataFrame(rows).drop_duplicates("geography_code") if rows else pd.DataFrame()


def _iter_coordinates(geometry: dict):
    coords = geometry.get("coordinates", [])
    geom_type = geometry.get("type")
    if geom_type == "Point":
        yield tuple(coords[:2])
    elif geom_type in {"LineString", "MultiPoint"}:
        for point in coords:
            yield tuple(point[:2])
    elif geom_type in {"Polygon", "MultiLineString"}:
        for line in coords:
            for point in line:
                yield tuple(point[:2])
    elif geom_type == "MultiPolygon":
        for polygon in coords:
            for ring in polygon:
                for point in ring:
                    yield tuple(point[:2])


def write_geometry_outputs() -> list[dict]:
    """Copy available simplified spatial files to the Tableau output folder."""

    rows: list[dict] = []
    target = config.GEOMETRY_OUTPUTS["ndia_service_area_geojson"]
    if config.SERVICE_AREA_GEOJSON_SOURCE.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_atlas_geojson(config.SERVICE_AREA_GEOJSON_SOURCE, target)
        rows.append(
            {
                "dataset": "geometry_ndia_service_area",
                "period": "",
                "geography": "ndia_service_area",
                "field": "geometry",
                "issue_type": "available",
                "issue_severity": "info",
                "missingness": 0,
                "suppression": "",
                "mapping_status": "atlas_geojson_with_metro_insets",
                "reliability_flag": config.RELIABILITY_FLAGS["derived"],
                "explanatory_note": (
                    f"Built from {config.SERVICE_AREA_GEOJSON_SOURCE}. Service-area polygons are transformed into a custom "
                    "Tableau atlas canvas with separate metro inset panels; Lord Howe Island and Norfolk Island are excluded if present."
                ),
            }
        )
    else:
        rows.append(
            {
                "dataset": "geometry_ndia_service_area",
                "period": "",
                "geography": "ndia_service_area",
                "field": "geometry",
                "issue_type": "missing_source",
                "issue_severity": "warning",
                "missingness": 1,
                "suppression": "",
                "mapping_status": "unavailable",
                "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
                "explanatory_note": "No local service-area GeoJSON was found.",
            }
        )
    return rows


def _write_atlas_geojson(source: Path, target: Path) -> None:
    with source.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    features = [_atlas_feature(feature) for feature in payload.get("features", [])]
    features = [feature for feature in features if feature is not None]
    features = _apply_metro_insets(features)
    out = dict(payload)
    out["features"] = features
    target.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


def _atlas_feature(feature: dict) -> dict | None:
    props = dict(feature.get("properties", {}))
    name = str(props.get("ndis_service_area") or props.get("map_key") or props.get("name") or "").strip()
    if name.lower() in EXCLUDED_ATLAS_GEOGRAPHIES:
        return None
    props["atlas_panel"] = "Main map"
    props["atlas_zoom_locked"] = True
    out = dict(feature)
    out["properties"] = props
    return out


def _apply_metro_insets(features: list[dict]) -> list[dict]:
    by_name = {
        str(feature.get("properties", {}).get("ndis_service_area") or feature.get("properties", {}).get("map_key") or feature.get("properties", {}).get("name")): feature
        for feature in features
    }
    inset_names = {
        name
        for spec in METRO_INSET_GROUPS.values()
        for name in spec["areas"]
        if name in by_name
    }
    transformed_names: set[str] = set()

    main_features = [feature for name, feature in by_name.items() if name not in inset_names]
    if main_features:
        for feature in _transform_features_to_bounds(main_features, ATLAS_MAIN_BOUNDS, "Main map"):
            name = str(feature["properties"].get("ndis_service_area") or feature["properties"].get("map_key") or feature["properties"].get("name"))
            by_name[name] = feature
            transformed_names.add(name)

    for panel_name, spec in METRO_INSET_GROUPS.items():
        names = set(spec["areas"])
        panel_features = [by_name[name] for name in names if name in by_name]
        if not panel_features:
            continue
        transformed = _transform_features_to_bounds(panel_features, spec["target_bounds"], panel_name)
        for feature in transformed:
            name = str(feature["properties"].get("ndis_service_area") or feature["properties"].get("map_key") or feature["properties"].get("name"))
            by_name[name] = feature
            transformed_names.add(name)

    ordered: list[dict] = []
    for feature in features:
        name = str(feature.get("properties", {}).get("ndis_service_area") or feature.get("properties", {}).get("map_key") or feature.get("properties", {}).get("name"))
        ordered.append(by_name[name] if name in transformed_names else feature)
    return ordered


def _transform_features_to_bounds(features: list[dict], target_bounds: tuple[float, float, float, float], panel_name: str) -> list[dict]:
    geometries = [shape(feature["geometry"]) for feature in features if feature.get("geometry")]
    if not geometries:
        return []
    minx = min(geom.bounds[0] for geom in geometries)
    miny = min(geom.bounds[1] for geom in geometries)
    maxx = max(geom.bounds[2] for geom in geometries)
    maxy = max(geom.bounds[3] for geom in geometries)
    source_w = max(maxx - minx, 0.000001)
    source_h = max(maxy - miny, 0.000001)
    target_minx, target_miny, target_maxx, target_maxy = target_bounds
    target_w = target_maxx - target_minx
    target_h = target_maxy - target_miny
    scale = min(target_w / source_w, target_h / source_h)
    scaled_w = source_w * scale
    scaled_h = source_h * scale
    offset_x = target_minx + (target_w - scaled_w) / 2
    offset_y = target_miny + (target_h - scaled_h) / 2

    transformed: list[dict] = []
    for feature in features:
        geom = shape(feature["geometry"])
        moved = affinity.scale(geom, xfact=scale, yfact=scale, origin=(minx, miny))
        moved = affinity.translate(moved, xoff=offset_x - minx, yoff=offset_y - miny)
        out = dict(feature)
        props = dict(feature.get("properties", {}))
        props["atlas_panel"] = panel_name
        out["properties"] = props
        out["geometry"] = mapping(moved)
        transformed.append(out)
    return transformed


def geography_audit(source_name: str, frame: pd.DataFrame, geography_col: str, lookup: pd.DataFrame) -> pd.DataFrame:
    """Create a geography matching audit against the lookup table."""

    if frame.empty or geography_col not in frame.columns:
        matched = 0
        total = 0
        unmatched = 0
    else:
        source_codes = frame[geography_col].dropna().astype(str).drop_duplicates()
        lookup_codes = set(lookup["geography_code"].dropna().astype(str)) if "geography_code" in lookup.columns else set()
        matched = int(source_codes.isin(lookup_codes).sum())
        total = int(len(source_codes))
        unmatched = total - matched

    return pd.DataFrame(
        [
            {
                "source_dataset": source_name,
                "source_geography": "NDIA Service Area",
                "source_geography_year": "source release / LGA 2021 context",
                "target_geography": "ndia_service_area",
                "matched_records": matched,
                "unmatched_records": unmatched,
                "percentage_matched": float(safe_divide(pd.Series([matched]), pd.Series([total])).iloc[0]) if total else pd.NA,
                "aggregation_method": "preserve source geography",
                "known_limitations": "Lookup currently covers local service-area context only; no forced conversion to other geographies.",
            }
        ]
    )
