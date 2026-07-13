from __future__ import annotations

import pandas as pd

from . import config
from .io_utils import numeric, read_csv, write_dataset


def build_population() -> dict[str, pd.DataFrame]:
    """Prepare currently available population denominator tables."""

    service_area = read_csv(config.SERVICE_AREA_POPULATION_SOURCE, required=False)
    if not service_area.empty:
        service_area["geography_type"] = "ndia_service_area"
        service_area["geography_code"] = service_area["ndis_service_area"].astype(str)
        service_area["reference_year"] = 2025
        service_area["population_count"] = numeric(service_area["population_2025_erp"])
        service_area["population_method_note"] = service_area.get("population_denominator_method", "local processed 2025 ERP")

    lga = read_csv(config.LGA_POPULATION_SOURCE, required=False)
    if not lga.empty:
        lga["geography_type"] = "lga_2021"
        lga["geography_code"] = lga["lga_code_2021"].astype(str).str.zfill(5)
        lga["reference_year"] = 2025
        lga["population_count"] = numeric(lga["population_2025_erp"])
        lga["population_method_note"] = lga.get("population_denominator_method", "local processed 2025 ERP")

    return {"service_area_population": service_area, "lga_population": lga}


def write_population_outputs(outputs: dict[str, pd.DataFrame]) -> None:
    """Persist population tables for reuse."""

    for name, frame in outputs.items():
        if not frame.empty:
            write_dataset(frame, config.PROCESSED_DIR / f"{name}.csv", config.PROCESSED_DIR / f"{name}.parquet")

