from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .io_utils import numeric, safe_divide


def build_market_classification(market: pd.DataFrame) -> pd.DataFrame:
    """Create market classification fields from the market-quarter table."""

    out = market.copy().sort_values(["geography_type", "geography_code", "quarter_sort"])
    grouped = out.groupby(["geography_type", "geography_code"], dropna=False)

    out["rolling_four_quarter_mean_utilisation"] = grouped["mean_plan_utilisation"].transform(lambda s: numeric(s).rolling(4, min_periods=2).mean())
    out["rolling_eight_quarter_mean_utilisation"] = grouped["mean_plan_utilisation"].transform(lambda s: numeric(s).rolling(8, min_periods=4).mean())
    out["utilisation_volatility"] = grouped["mean_plan_utilisation"].transform(lambda s: numeric(s).rolling(4, min_periods=2).std())
    out["utilisation_trend_slope"] = grouped["mean_plan_utilisation"].transform(_rolling_slope)
    out["consecutive_quarters_below_national_benchmark"] = grouped["mean_plan_utilisation_gap_from_national"].transform(_consecutive_positive)
    out["consecutive_quarters_below_remoteness_benchmark"] = grouped["mean_plan_utilisation_gap_from_remoteness"].transform(_consecutive_positive)
    out["persistent_utilisation_classification"] = out.apply(_classify_utilisation, axis=1)

    growth_basis = out["participant_growth_rate"].where(out["participant_growth_rate"].notna(), out["funded_plan_growth_rate"])
    out["participant_provider_growth_quadrant"] = _growth_quadrant(growth_basis, out["provider_growth_rate"], "demand", "supply")
    out["payment_provider_growth_quadrant"] = _growth_quadrant(out["payment_growth_rate"], out["provider_growth_rate"], "payments", "supply")

    out["demand_score"] = _percentile_score(out["funded_plans_per_1000"])
    out["purchasing_score"] = _percentile_score(out["payments_per_funded_plan"])
    out["capacity_score"] = _percentile_score(out["active_providers_per_1000_funded_plans"])
    out["performance_score"] = _percentile_score(out["mean_plan_utilisation"])
    out["optional_cluster"] = pd.NA
    out["cluster_diagnostic_note"] = "Cluster modelling was not run because the currently available feature set lacks the requested community, SEIFA and workforce inputs."
    out["reliability_flag"] = np.where(
        out["persistent_utilisation_classification"].eq("insufficient history"),
        config.RELIABILITY_FLAGS["insufficient_history"],
        out.get("reliability_flag", config.RELIABILITY_FLAGS["derived"]),
    )

    return out[
        [
            "quarter",
            "quarter_label",
            "quarter_end_date",
            "geography_type",
            "geography_code",
            "rolling_four_quarter_mean_utilisation",
            "rolling_eight_quarter_mean_utilisation",
            "utilisation_trend_slope",
            "utilisation_volatility",
            "consecutive_quarters_below_national_benchmark",
            "consecutive_quarters_below_remoteness_benchmark",
            "persistent_utilisation_classification",
            "participant_provider_growth_quadrant",
            "payment_provider_growth_quadrant",
            "demand_score",
            "purchasing_score",
            "capacity_score",
            "performance_score",
            "optional_cluster",
            "cluster_diagnostic_note",
            "reliability_flag",
        ]
    ].reset_index(drop=True)


def build_participant_profile() -> pd.DataFrame:
    """Return a schema-valid participant profile output when profile sources are absent."""

    return pd.DataFrame(
        columns=[
            "quarter",
            "quarter_label",
            "quarter_end_date",
            "geography_type",
            "geography_code",
            "profile_dimension",
            "profile_category",
            "count",
            "proportion",
            "average_value",
            "source_name",
            "reliability_flag",
            "limitation_note",
        ]
    )


def participant_profile_quality_rows() -> list[dict]:
    return [
        {
            "dataset": "tableau_participant_profile",
            "period": "2024Q2-2026Q1",
            "geography": "ndia_service_area",
            "field": "profile_dimension",
            "issue_type": "missing_source",
            "issue_severity": "warning",
            "missingness": 1,
            "suppression": "",
            "mapping_status": "not_processed",
            "reliability_flag": config.RELIABILITY_FLAGS["unavailable"],
            "explanatory_note": "No local participant profile source by age, disability, plan management or support class is available.",
        }
    ]


def _rolling_slope(series: pd.Series) -> pd.Series:
    values = numeric(series)

    def slope(window: pd.Series) -> float:
        valid = window.dropna()
        if len(valid) < 3:
            return np.nan
        x = np.arange(len(valid))
        return float(np.polyfit(x, valid.to_numpy(dtype=float), 1)[0])

    return values.rolling(4, min_periods=3).apply(slope, raw=False)


def _consecutive_positive(series: pd.Series) -> pd.Series:
    counts: list[int] = []
    current = 0
    for value in numeric(series):
        if pd.notna(value) and value > 0:
            current += 1
        else:
            current = 0
        counts.append(current)
    return pd.Series(counts, index=series.index)


def _classify_utilisation(row: pd.Series) -> str:
    thresholds = config.PERSISTENT_UTILISATION_THRESHOLDS
    if pd.isna(row.get("rolling_four_quarter_mean_utilisation")):
        return "insufficient history"
    volatility = _float_or_nan(row.get("utilisation_volatility"))
    consecutive_national = _float_or_nan(row.get("consecutive_quarters_below_national_benchmark"))
    slope = _float_or_nan(row.get("utilisation_trend_slope"))
    national_gap = _float_or_nan(row.get("mean_plan_utilisation_gap_from_national"))
    if pd.notna(volatility) and volatility >= thresholds["volatile_std_min"]:
        return "volatile"
    if pd.notna(consecutive_national) and consecutive_national >= thresholds["minimum_quarters"]:
        return "persistently low"
    if pd.notna(slope) and slope <= thresholds["deteriorating_slope_max"]:
        return "deteriorating"
    if pd.notna(slope) and slope >= thresholds["recovering_slope_min"]:
        return "recovering"
    if pd.notna(national_gap) and national_gap <= thresholds["high_gap_max"]:
        return "consistently high"
    return "stable"


def _float_or_nan(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _growth_quadrant(first: pd.Series, second: pd.Series, first_label: str, second_label: str) -> pd.Series:
    first_num = numeric(first)
    second_num = numeric(second)
    labels = pd.Series(pd.NA, index=first.index, dtype="object")
    labels[(first_num >= 0) & (second_num >= 0)] = f"expanding {first_label} and expanding {second_label}"
    labels[(first_num >= 0) & (second_num < 0)] = f"expanding {first_label} and contracting {second_label}"
    labels[(first_num < 0) & (second_num >= 0)] = f"contracting {first_label} and expanding {second_label}"
    labels[(first_num < 0) & (second_num < 0)] = f"contracting {first_label} and contracting {second_label}"
    return labels.fillna("insufficient history")


def _percentile_score(series: pd.Series) -> pd.Series:
    values = numeric(series)
    return values.rank(pct=True)
