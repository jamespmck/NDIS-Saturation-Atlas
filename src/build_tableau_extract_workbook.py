"""Build a Tableau Public-friendly Hyper-backed workbook copy."""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(".codex/pydeps").resolve()))

from tableauhyperapi import (  # type: ignore[import-not-found]
    Connection,
    CreateMode,
    HyperProcess,
    Inserter,
    SqlType,
    TableDefinition,
    TableName,
    Telemetry,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "tableau"
WORKBOOK_PATH = ROOT / "outputs" / "tableau" / "NDIS-Saturation-Atlas.twb"
EXTRACT_WORKBOOK_PATH = ROOT / "outputs" / "tableau" / "NDIS-Saturation-Atlas.extract.twb"
HYPER_PATH = ROOT / "outputs" / "tableau" / "NDIS-Saturation-Atlas.hyper"
HYPERD_DIR = Path(r"C:\Program Files\Tableau\Tableau Public 2026.2\bin\hyper")


CSV_TABLES = [
    "tableau_market_quarter.csv",
    "tableau_community_context.csv",
    "tableau_data_quality.csv",
    "tableau_geography_lookup.csv",
    "tableau_support_type_quarter.csv",
    "tableau_market_classification.csv",
]
GEOMETRY_TABLE = "geometry_ndia_service_area.geojson"

TABLE_REPLACEMENTS = {
    "[tableau_market_quarter#csv]": "[public].[tableau_market_quarter.csv]",
    "[tableau_community_context#csv]": "[public].[tableau_community_context.csv]",
    "[tableau_data_quality#csv]": "[public].[tableau_data_quality.csv]",
    "[tableau_geography_lookup#csv]": "[public].[tableau_geography_lookup.csv]",
    "[tableau_support_type_quarter#csv]": "[public].[tableau_support_type_quarter.csv]",
    "[tableau_market_classification#csv]": "[public].[tableau_market_classification.csv]",
    "[geometry_ndia_service_area.geojson]": "[public].[geometry_ndia_service_area.geojson]",
}


def main() -> None:
    table_columns = _read_table_columns(WORKBOOK_PATH)
    build_hyper(table_columns)
    build_extract_workbook(table_columns)
    print(EXTRACT_WORKBOOK_PATH)


def build_hyper(table_columns: dict[str, list[tuple[str, str]]]) -> None:
    HYPER_PATH.unlink(missing_ok=True)
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU, hyper_path=str(HYPERD_DIR)) as hyper:
        with Connection(hyper.endpoint, str(HYPER_PATH), CreateMode.CREATE_AND_REPLACE) as connection:
            for table in CSV_TABLES:
                _create_csv_table(connection, table, table_columns[table])
            _create_geometry_table(connection, table_columns[GEOMETRY_TABLE])


def build_extract_workbook(table_columns: dict[str, list[tuple[str, str]]]) -> None:
    tree = ET.parse(WORKBOOK_PATH)
    root = tree.getroot()
    datasource = root.find("./datasources/datasource")
    if datasource is None:
        raise ValueError("Workbook has no datasource.")
    connection = datasource.find("./connection")
    if connection is None:
        raise ValueError("Datasource has no connection.")

    connection.clear()
    connection.attrib.clear()
    connection.attrib.update(
        {
            "access_mode": "readonly",
            "class": "hyper",
            "dbname": str(HYPER_PATH).replace("\\", "/"),
            "default-settings": "yes",
            "schema": "public",
            "username": "tableau_internal_user",
        }
    )
    relations = ET.SubElement(connection, "relation", {"type": "collection"})
    for table in CSV_TABLES + [GEOMETRY_TABLE]:
        relation = ET.SubElement(
            relations,
            "relation",
            {"name": table, "table": f"[public].[{table}]", "type": "table"},
        )
        ET.SubElement(relation, "columns")
        columns = relation.find("columns")
        if columns is not None:
            for column_name, tableau_type in table_columns[table]:
                ET.SubElement(columns, "column", {"datatype": tableau_type, "name": column_name})

    for relation in root.findall(".//relation"):
        table = relation.attrib.get("table")
        if table in TABLE_REPLACEMENTS:
            relation.attrib["table"] = TABLE_REPLACEMENTS[table]
            relation.attrib.pop("connection", None)
        for columns in list(relation.findall("columns")):
            if relation.attrib.get("table", "").startswith("[public]."):
                relation.remove(columns)

    ET.indent(tree, space="  ")
    tree.write(EXTRACT_WORKBOOK_PATH, encoding="utf-8", xml_declaration=True)


def _create_csv_table(connection: Connection, table: str, columns: list[tuple[str, str]]) -> None:
    definition = TableDefinition(TableName("public", table), [_hyper_column(name, tableau_type) for name, tableau_type in columns])
    connection.catalog.create_table(definition)
    with (DATA_DIR / table).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        with Inserter(connection, definition) as inserter:
            for row in reader:
                inserter.add_row([_convert(row.get(name), tableau_type) for name, tableau_type in columns])
            inserter.execute()


def _create_geometry_table(connection: Connection, columns: list[tuple[str, str]]) -> None:
    definition = TableDefinition(TableName("public", GEOMETRY_TABLE), [_hyper_column(name, tableau_type) for name, tableau_type in columns])
    connection.catalog.create_table(definition)
    with (DATA_DIR / GEOMETRY_TABLE).open("r", encoding="utf-8") as handle:
        geojson = json.load(handle)
    column_names = [name for name, _ in columns]
    quoted_columns = ", ".join(_quote_identifier(name) for name in column_names)
    for feature in geojson["features"]:
        properties = feature.get("properties", {})
        values: list[str] = []
        for column_name, tableau_type in columns:
            if column_name == "Geometry":
                values.append(f"CAST({_quote_literal(_geometry_to_wkt(feature['geometry']))} AS GEOGRAPHY)")
            else:
                values.append(_sql_literal(_convert(properties.get(column_name), tableau_type)))
        connection.execute_command(f"INSERT INTO {_qualified_table(GEOMETRY_TABLE)} ({quoted_columns}) VALUES ({', '.join(values)})")


def _read_table_columns(path: Path) -> dict[str, list[tuple[str, str]]]:
    root = ET.parse(path).getroot()
    columns: dict[str, list[tuple[str, str]]] = {}
    for relation in root.findall("./datasources/datasource/connection/relation/relation"):
        table = relation.attrib.get("name")
        column_parent = relation.find("columns")
        if not table or column_parent is None:
            continue
        table_columns = []
        for column in column_parent.findall("column"):
            name = column.attrib.get("name")
            datatype = column.attrib.get("datatype")
            if name and datatype:
                table_columns.append((name, datatype))
        columns[table] = table_columns
    missing = set(CSV_TABLES + [GEOMETRY_TABLE]) - set(columns)
    for table in sorted(missing):
        if table in CSV_TABLES:
            columns[table] = _infer_csv_columns(DATA_DIR / table)
    missing = set(CSV_TABLES + [GEOMETRY_TABLE]) - set(columns)
    if missing:
        raise ValueError(f"Missing workbook table metadata for {sorted(missing)}")
    return columns


def _infer_csv_columns(path: Path) -> list[tuple[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    columns = []
    for field in reader.fieldnames or []:
        values = [row.get(field, "").strip() for row in rows if row.get(field, "").strip()]
        columns.append((field, _infer_tableau_type(values)))
    return columns


def _infer_tableau_type(values: list[str]) -> str:
    if not values:
        return "string"
    if all(_looks_like_date(value) for value in values):
        return "date"
    if all(_looks_like_int(value) for value in values):
        return "integer"
    if all(_looks_like_float(value) for value in values):
        return "real"
    return "string"


def _looks_like_date(value: str) -> bool:
    parts = value[:10].split("-")
    if len(parts) != 3:
        return False
    try:
        date(int(parts[0]), int(parts[1]), int(parts[2]))
        return True
    except ValueError:
        return False


def _looks_like_int(value: str) -> bool:
    try:
        return float(value).is_integer()
    except ValueError:
        return False


def _looks_like_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _hyper_column(name: str, tableau_type: str) -> TableDefinition.Column:
    return TableDefinition.Column(name, _hyper_type(tableau_type))


def _hyper_type(tableau_type: str) -> SqlType:
    if tableau_type == "real":
        return SqlType.double()
    if tableau_type == "integer":
        return SqlType.big_int()
    if tableau_type == "date":
        return SqlType.date()
    if tableau_type == "boolean":
        return SqlType.bool()
    if tableau_type == "spatial":
        return SqlType.geography()
    return SqlType.text()


def _convert(value: object, tableau_type: str) -> object | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    if tableau_type == "real":
        return float(text)
    if tableau_type == "integer":
        return int(float(text))
    if tableau_type == "date":
        year, month, day = text[:10].split("-")
        return date(int(year), int(month), int(day))
    if tableau_type == "boolean":
        return text.lower() in {"true", "1", "yes"}
    return text


def _geometry_to_wkt(geometry: dict) -> str:
    geometry_type = geometry["type"]
    coordinates = geometry["coordinates"]
    if geometry_type == "Polygon":
        return f"POLYGON {_polygon_to_wkt(coordinates)}"
    if geometry_type == "MultiPolygon":
        polygons = ", ".join(_polygon_to_wkt(polygon) for polygon in coordinates)
        return f"MULTIPOLYGON ({polygons})"
    raise ValueError(f"Unsupported geometry type: {geometry_type}")


def _polygon_to_wkt(polygon: list) -> str:
    rings = []
    for ring in polygon:
        points = ", ".join(f"{point[0]} {point[1]}" for point in ring)
        rings.append(f"({points})")
    return f"({', '.join(rings)})"


def _qualified_table(table: str) -> str:
    return f'"public"."{table}"'


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_literal(value: object | None) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, date):
        return f"DATE {_quote_literal(value.isoformat())}"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return _quote_literal(str(value))


if __name__ == "__main__":
    main()
