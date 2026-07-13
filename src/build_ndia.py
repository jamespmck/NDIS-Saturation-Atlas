from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .geography import add_quarter_fields
from .io_utils import numeric, read_csv, safe_divide, write_dataset


def load_main_ndia() -> pd.DataFrame:
    """Load and standardise the local NDIA service-area-quarter source."""

    data = read_csv(config.MAIN_NDIA_SOURCE)
    if "quarter" not in data.columns and "reporting_quarter" in data.columns:
        data["quarter"] = data["reporting_quarter"]
    required = ["quarter", "ndis_service_area", "funded_plans_count", "population_2025_erp"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Main NDIA source missing required columns: {', '.join(missing)}")
    data["quarter"] = data["quarter"].astype(str)
    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    data = data.loc[~data["ndis_service_area"].isin(EXCLUDED_SERVICE_AREAS)].copy()
    return data


def load_historical_ndia() -> pd.DataFrame:
    """Load the optional historical NDIA extract."""

    data = read_csv(config.HISTORICAL_NDIA_SOURCE, required=False)
    if data.empty:
        return data
    if "reporting_quarter" in data.columns and "quarter" not in data.columns:
        data["quarter"] = data["reporting_quarter"]
    data["quarter"] = data["quarter"].astype(str)
    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    return data


def build_market_quarter() -> pd.DataFrame:
    """Build the core service-area-quarter market table."""

    data = load_main_ndia()
    historical = load_historical_ndia()

    if not historical.empty and {"quarter", "ndis_service_area", "historical_o2_total_active_participants"}.issubset(historical.columns):
        participant_lookup = historical[
            ["quarter", "ndis_service_area", "historical_o2_total_active_participants", "median_plan_funding", "median_payments"]
        ].drop_duplicates(["quarter", "ndis_service_area"])
        data = data.merge(participant_lookup, on=["quarter", "ndis_service_area"], how="left")
    col = _column_getter(data)

    out = pd.DataFrame(
        {
            "quarter": data["quarter"],
            "geography_type": "ndia_service_area",
            "geography_code": data["ndis_service_area"].astype(str),
            "geography_name": data["ndis_service_area"].astype(str),
            "state": col("state_acronym"),
            "remoteness": col("remoteness_category"),
            "population_count": numeric(col("population_2025_erp")),
            "participant_count": numeric(col("historical_o2_total_active_participants")),
            "funded_plan_count": numeric(col("funded_plans_count")),
            "funded_plans_per_1000": numeric(col("service_area_funded_plans_per_1000_population_2025_erp", "funded_plans_per_1000")),
            "mean_plan_funding": numeric(col("mean_plan_funding", "service_area_mean_plan_funding")),
            "median_plan_funding": numeric(col("median_plan_funding")),
            "mean_plan_utilisation": numeric(col("mean_plan_utilisation", "service_area_mean_plan_utilisation")),
            "payment_amount": numeric(col("service_area_payment_amount")),
            "payments_per_funded_plan": numeric(col("payment_amount_per_funded_plan")),
            "median_payments": numeric(col("median_payments")),
            "active_provider_count": numeric(col("active_provider_count_quarter")),
            "registered_provider_count": numeric(col("active_provider_count_ever")),
            "benchmark_national_funded_plans_per_1000": numeric(col("benchmark_national_funded_plans_per_1000")),
            "benchmark_national_mean_plan_utilisation": numeric(col("benchmark_national_mean_plan_utilisation")),
            "benchmark_remoteness_funded_plans_per_1000": numeric(col("benchmark_remoteness_funded_plans_per_1000")),
            "benchmark_remoteness_mean_plan_utilisation": numeric(col("benchmark_remoteness_mean_plan_utilisation")),
            "funded_plans_per_1000_gap_from_national": numeric(col("funded_plans_per_1000_gap_from_national")),
            "mean_plan_utilisation_gap_from_national": numeric(col("mean_plan_utilisation_gap_from_national")),
            "funded_plans_per_1000_gap_from_remoteness": numeric(col("funded_plans_per_1000_gap_from_remoteness")),
            "mean_plan_utilisation_gap_from_remoteness": numeric(col("mean_plan_utilisation_gap_from_remoteness")),
        }
    )

    out = add_quarter_fields(out)
    out["population_count"] = out["population_count"].where(out["population_count"] > 0)
    utilisation_is_percent_scale = numeric(out["mean_plan_utilisation"]).abs().max() > 1.5
    for col_name in [
        "mean_plan_utilisation",
        "benchmark_national_mean_plan_utilisation",
        "benchmark_remoteness_mean_plan_utilisation",
        "mean_plan_utilisation_gap_from_national",
        "mean_plan_utilisation_gap_from_remoteness",
    ]:
        out[col_name] = _normalise_utilisation_decimal(out[col_name], source_is_percent_scale=utilisation_is_percent_scale)
    out["participants_per_1000"] = safe_divide(out["participant_count"], out["population_count"]) * 1000
    out["committed_supports"] = out["mean_plan_funding"] * out["funded_plan_count"]
    out["funding_conversion_rate"] = safe_divide(out["payment_amount"], out["committed_supports"])
    out["unspent_committed_funding"] = out["committed_supports"] - out["payment_amount"]
    out["committed_supports_per_funded_plan"] = safe_divide(out["committed_supports"], out["funded_plan_count"])
    out["payments_per_participant"] = safe_divide(out["payment_amount"], out["participant_count"])
    out["payments_per_1000_population"] = safe_divide(out["payment_amount"], out["population_count"]) * 1000
    out["funded_plans_per_active_provider"] = safe_divide(out["funded_plan_count"], out["active_provider_count"])
    out["participants_per_active_provider"] = safe_divide(out["participant_count"], out["active_provider_count"])
    out["active_providers_per_1000_funded_plans"] = safe_divide(out["active_provider_count"], out["funded_plan_count"]) * 1000

    out = _add_growth(out, "funded_plan_count", "funded_plan_growth_rate")
    out = _add_growth(out, "participant_count", "participant_growth_rate")
    out = _add_growth(out, "payment_amount", "payment_growth_rate")
    out = _add_growth(out, "mean_plan_funding", "plan_value_growth_rate")
    out = _add_growth(out, "active_provider_count", "provider_growth_rate")
    out["supply_response_gap"] = out["participant_growth_rate"] - out["provider_growth_rate"]
    out["market_density_indicator_note"] = "supply_response_gap is participant growth minus provider growth; it is not a provider caseload measure."
    out["population_reference_year"] = 2025
    out["population_method"] = "static 2025 ERP denominator from local processed file; quarterly interpolation unavailable without annual series"
    out["reliability_flag"] = np.where(out["participant_count"].notna(), config.RELIABILITY_FLAGS["derived"], "funded_plan_context_only")

    out = out.sort_values(["geography_type", "geography_code", "quarter_sort"]).reset_index(drop=True)
    return out


def _add_growth(frame: pd.DataFrame, value_col: str, output_col: str) -> pd.DataFrame:
    out = frame.sort_values(["geography_code", "quarter_sort"]).copy()
    out[output_col] = out.groupby(["geography_type", "geography_code"], dropna=False)[value_col].pct_change()
    return out


def build_support_type_quarter() -> pd.DataFrame:
    """Build the service-type-quarter Tableau table."""

    data = read_csv(config.SERVICE_TYPE_SOURCE)
    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    data = data.loc[~data["ndis_service_area"].isin(EXCLUDED_SERVICE_AREAS)].copy()
    col = _column_getter(data)
    required = ["quarter", "ndis_service_area", "service_type", "service_type_payment_amount"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Service-type source missing required columns: {', '.join(missing)}")

    out = pd.DataFrame(
        {
            "quarter": data["quarter"].astype(str),
            "geography_type": "ndia_service_area",
            "geography_code": data["ndis_service_area"].astype(str),
            "geography_name": data["ndis_service_area"].astype(str),
            "remoteness": col("remoteness_category"),
            "support_class": col("support_class"),
            "support_type": data["service_type"].astype(str),
            "support_type_group": col("service_type_group"),
            "payments": numeric(col("service_type_payment_amount")),
            "payment_item_participant_count_sum_not_unique": numeric(col("payment_item_participant_count_sum_not_unique")),
            "suppressed_payment_item_rows": numeric(col("suppressed_payment_item_rows")),
            "suppressed_participant_item_rows": numeric(col("suppressed_participant_item_rows")),
            "source_item_rows": numeric(col("source_item_rows")),
            "area_total_payments": numeric(col("service_area_payment_amount")),
            "funded_plan_count": numeric(col("funded_plans_count")),
            "population_count": numeric(col("population_2025_erp")),
            "local_support_share": numeric(col("service_type_payment_share_of_area_total")),
            "national_support_share": numeric(col("national_service_type_payment_share")),
            "national_service_type_payments": numeric(col("national_service_type_payment_amount")),
        }
    )
    out = add_quarter_fields(out)
    out["population_count"] = out["population_count"].where(out["population_count"] > 0)

    if out["local_support_share"].isna().all():
        out["local_support_share"] = safe_divide(out["payments"], out["area_total_payments"])

    out["payments_per_funded_plan"] = safe_divide(out["payments"], out["funded_plan_count"])
    out["payments_per_1000_population"] = safe_divide(out["payments"], out["population_count"]) * 1000
    out["support_location_quotient"] = safe_divide(out["local_support_share"], out["national_support_share"])
    out = _add_growth_for_keys(out, ["geography_type", "geography_code", "support_type"], "payments", "payment_growth_rate")

    remoteness_benchmark = _remoteness_support_benchmark(out)
    out = out.merge(remoteness_benchmark, on=["quarter", "remoteness", "support_type"], how="left")
    out["remoteness_support_location_quotient"] = safe_divide(out["local_support_share"], out["remoteness_support_share"])
    out["national_benchmark"] = out["national_support_share"]
    out["remoteness_benchmark"] = out["remoteness_support_share"]
    out["reliability_flag"] = np.where(
        (out["suppressed_payment_item_rows"].fillna(0) > 0) | (out["suppressed_participant_item_rows"].fillna(0) > 0),
        "suppression_present",
        config.RELIABILITY_FLAGS["derived"],
    )

    return out.sort_values(["geography_code", "support_type", "quarter_sort"]).reset_index(drop=True)


def _add_growth_for_keys(frame: pd.DataFrame, keys: list[str], value_col: str, output_col: str) -> pd.DataFrame:
    out = frame.sort_values(keys + ["quarter_sort"]).copy()
    out[output_col] = out.groupby(keys, dropna=False)[value_col].pct_change()
    return out


def _remoteness_support_benchmark(frame: pd.DataFrame) -> pd.DataFrame:
    service_area_totals = frame[
        ["quarter", "geography_code", "remoteness", "area_total_payments"]
    ].drop_duplicates(["quarter", "geography_code"])
    remoteness_totals = (
        service_area_totals.groupby(["quarter", "remoteness"], dropna=False)["area_total_payments"]
        .sum(min_count=1)
        .reset_index(name="remoteness_total_payments")
    )
    support_totals = (
        frame.groupby(["quarter", "remoteness", "support_type"], dropna=False)["payments"]
        .sum(min_count=1)
        .reset_index(name="remoteness_support_payments")
    )
    out = support_totals.merge(remoteness_totals, on=["quarter", "remoteness"], how="left")
    out["remoteness_support_share"] = safe_divide(out["remoteness_support_payments"], out["remoteness_total_payments"])
    return out[["quarter", "remoteness", "support_type", "remoteness_support_share"]]


def write_ndia_intermediates(market: pd.DataFrame, support_type: pd.DataFrame) -> None:
    """Persist NDIA processed equivalents for reuse outside Tableau."""

    write_dataset(market, config.PROCESSED_DIR / "ndia_market_quarter.csv", config.PROCESSED_DIR / "ndia_market_quarter.parquet")
    write_dataset(
        support_type,
        config.PROCESSED_DIR / "ndia_support_type_quarter.csv",
        config.PROCESSED_DIR / "ndia_support_type_quarter.parquet",
    )


def _column_getter(frame: pd.DataFrame):
    def get(*names: str) -> pd.Series:
        for name in names:
            if name in frame.columns:
                return frame[name]
        return pd.Series(pd.NA, index=frame.index)

    return get


EXCLUDED_SERVICE_AREAS = {"ALL", "All", "Other", "Missing", "Region_Missing", "nan", "None", "<NA>"}


def _normalise_utilisation_decimal(series: pd.Series, *, source_is_percent_scale: bool) -> pd.Series:
    values = numeric(series)
    if source_is_percent_scale:
        return values / 100
    return values
