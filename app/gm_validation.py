from __future__ import annotations

import pandas as pd


def _check(rows: list[dict], area: str, check: str, status: str, detail: str) -> None:
    rows.append({"area": area, "check": check, "status": status, "detail": detail})


def validate_main_data(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    required = [
        "quarter",
        "map_key",
        "ndis_service_area",
        "remoteness_category",
        "population_2025_erp",
        "funded_plans_count",
        "service_area_funded_plans_per_1000_population_2025_erp",
        "service_area_mean_plan_utilisation",
    ]

    missing = [col for col in required if col not in data.columns]
    _check(
        rows,
        "schema",
        "required main columns present",
        "fail" if missing else "pass",
        "Missing: " + ", ".join(missing) if missing else "All required main columns are present.",
    )

    if {"quarter", "map_key"}.issubset(data.columns):
        duplicates = int(data.duplicated(["quarter", "map_key"]).sum())
        _check(rows, "uniqueness", "one row per service area per quarter", "fail" if duplicates else "pass", f"{duplicates} duplicate rows found.")

    if "quarter" in data.columns and "ndis_service_area" in data.columns:
        counts = data.groupby("quarter")["ndis_service_area"].nunique().to_dict()
        _check(rows, "coverage", "service-area count by quarter", "pass", "; ".join(f"{k}: {v}" for k, v in counts.items()))

    for col in [
        "population_2025_erp",
        "funded_plans_count",
        "service_area_funded_plans_per_1000_population_2025_erp",
        "service_area_mean_plan_utilisation",
    ]:
        if col in data.columns:
            missing_count = int(pd.to_numeric(data[col], errors="coerce").isna().sum())
            _check(rows, "missingness", f"{col} numeric completeness", "warning" if missing_count else "pass", f"{missing_count} missing or non-numeric values.")

    if {
        "funded_plans_per_1000_gap_from_national",
        "national_funded_plans_per_1000_population_2025_erp",
        "service_area_funded_plans_per_1000_population_2025_erp",
    }.issubset(data.columns):
        calculated = data["national_funded_plans_per_1000_population_2025_erp"] - data["service_area_funded_plans_per_1000_population_2025_erp"]
        delta = (calculated - data["funded_plans_per_1000_gap_from_national"]).abs().max()
        ok = pd.isna(delta) or delta < 0.0001
        _check(rows, "metric reconciliation", "plan coverage gap equals national minus service-area value", "pass" if ok else "fail", f"Maximum absolute difference: {delta}")

    return pd.DataFrame(rows)


def validate_service_type_data(service_type_data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    if service_type_data.empty:
        _check(rows, "service type", "service-type data available", "warning", "No service-type file loaded.")
        return pd.DataFrame(rows)

    required = ["quarter", "ndis_service_area", "service_type", "service_type_payment_share_of_area_total"]
    missing = [col for col in required if col not in service_type_data.columns]
    _check(
        rows,
        "schema",
        "required service-type columns present",
        "fail" if missing else "pass",
        "Missing: " + ", ".join(missing) if missing else "All required service-type columns are present.",
    )

    if {"quarter", "ndis_service_area", "service_type"}.issubset(service_type_data.columns):
        duplicates = int(service_type_data.duplicated(["quarter", "ndis_service_area", "service_type"]).sum())
        _check(rows, "uniqueness", "one row per service area, quarter and service type", "fail" if duplicates else "pass", f"{duplicates} duplicate service-type rows found.")

    if "service_type_payment_share_of_area_total" in service_type_data.columns:
        shares = pd.to_numeric(service_type_data["service_type_payment_share_of_area_total"], errors="coerce")
        out_of_range = int(((shares < 0) | (shares > 1)).sum())
        _check(rows, "proxy method", "payment shares between 0 and 1", "fail" if out_of_range else "pass", f"{out_of_range} rows outside [0, 1].")

        share_sum = (
            service_type_data.groupby(["quarter", "ndis_service_area"], dropna=False)["service_type_payment_share_of_area_total"]
            .sum()
            .reset_index(name="share_sum")
        )
        outside = int(((share_sum["share_sum"] < 0.98) | (share_sum["share_sum"] > 1.02)).sum())
        _check(rows, "proxy method", "payment shares sum close to 1 by service area and quarter", "warning" if outside else "pass", f"{outside} service-area-quarter groups outside 0.98 to 1.02.")

    return pd.DataFrame(rows)


def validation_summary(main_data: pd.DataFrame, service_type_data: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([validate_main_data(main_data), validate_service_type_data(service_type_data)], ignore_index=True)
