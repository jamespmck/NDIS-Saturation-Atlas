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
    assert panels["Barkly"] == "Main map"


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
