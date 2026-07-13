import json

from src import config
from src.geography import quarter_end_date, quarter_label, quarter_sort_value, standardise_code, _write_atlas_geojson


def test_quarter_fields_use_ndia_financial_year_convention():
    assert quarter_label("2025Q4") == "2025 Q4"
    assert quarter_end_date("2025Q1") == "2024-09-30"
    assert quarter_end_date("2025Q2") == "2024-12-31"
    assert quarter_end_date("2025Q3") == "2025-03-31"
    assert quarter_end_date("2025Q4") == "2025-06-30"
    assert quarter_sort_value("2025Q4") > quarter_sort_value("2025Q3")


def test_standardise_code_preserves_leading_zeros():
    assert standardise_code("123", width=5) == "00123"
    assert standardise_code("00123", width=5) == "00123"
    assert standardise_code("123.0", width=5) == "00123"


def test_atlas_geojson_excludes_external_islands_and_tags_metro_insets():
    config.AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    source = config.AUDIT_DIR / "_test_atlas_source.geojson"
    target = config.AUDIT_DIR / "_test_atlas_target.geojson"
    payload = {
        "type": "FeatureCollection",
        "features": [
            _feature("Sydney", 151.0, -34.0),
            _feature("Central Coast", 151.2, -33.5),
            _feature("Beenleigh", 153.0, -27.8),
            _feature("Caboolture/Strathpine", 153.0, -27.1),
            _feature("Robina", 153.4, -28.1),
            _feature("Brimbank Melton", 144.5, -37.8),
            _feature("Hume Moreland", 144.9, -37.6),
            _feature("Bayside Peninsula", 145.0, -38.0),
            _feature("Barossa, Light and Lower North", 138.8, -34.4),
            _feature("Norfolk Island", 167.9, -29.0),
            _feature("Barkly", 134.0, -20.0),
        ],
    }
    source.write_text(json.dumps(payload), encoding="utf-8")

    _write_atlas_geojson(source, target)

    out = json.loads(target.read_text(encoding="utf-8"))
    names = {feature["properties"]["ndis_service_area"] for feature in out["features"]}
    panels = {feature["properties"]["ndis_service_area"]: feature["properties"]["atlas_panel"] for feature in out["features"]}
    assert "Norfolk Island" not in names
    assert panels["Sydney"] == "Sydney inset"
    assert panels["Central Coast"] == "Sydney inset"
    assert panels["Beenleigh"] == "Brisbane inset"
    assert panels["Caboolture/Strathpine"] == "Brisbane inset"
    assert panels["Robina"] == "Brisbane inset"
    assert panels["Brimbank Melton"] == "Melbourne inset"
    assert panels["Hume Moreland"] == "Melbourne inset"
    assert panels["Bayside Peninsula"] == "Melbourne inset"
    assert panels["Barossa, Light and Lower North"] == "Adelaide inset"
    assert panels["Barkly"] == "Main map"

    bounds = {
        feature["properties"]["ndis_service_area"]: _bounds(feature["geometry"])
        for feature in out["features"]
    }
    assert bounds["Barkly"][0] >= 24
    assert bounds["Barkly"][2] <= 72
    assert bounds["Sydney"][0] >= 77
    assert bounds["Sydney"][2] <= 97
    assert bounds["Barossa, Light and Lower North"][1] >= -58
    assert bounds["Barossa, Light and Lower North"][3] <= -42.999


def _feature(name: str, x: float, y: float) -> dict:
    return {
        "type": "Feature",
        "properties": {"ndis_service_area": name, "map_key": name, "name": name},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [x, y],
                [x + 0.1, y],
                [x + 0.1, y + 0.1],
                [x, y + 0.1],
                [x, y],
            ]],
        },
    }


def _bounds(geometry: dict) -> tuple[float, float, float, float]:
    coords = list(_coords(geometry))
    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    return min(xs), min(ys), max(xs), max(ys)


def _coords(geometry: dict):
    geom_type = geometry["type"]
    coordinates = geometry["coordinates"]
    if geom_type == "Polygon":
        for ring in coordinates:
            for x, y, *_ in ring:
                yield x, y
    elif geom_type == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon:
                for x, y, *_ in ring:
                    yield x, y
