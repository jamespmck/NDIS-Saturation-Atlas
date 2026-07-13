from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .build_features import build_market_classification, build_participant_profile
from .geography import build_geography_lookup, write_geometry_outputs
from .io_utils import numeric, safe_divide, write_dataset


def build_community_context(geography_lookup: pd.DataFrame) -> pd.DataFrame:
    """Build currently available static community context for Tableau."""

    if geography_lookup.empty:
        return pd.DataFrame(
            columns=[
                "geography_type",
                "geography_code",
                "reference_year",
                "population_count",
                "remoteness",
                "area_sqkm",
                "population_density_per_sqkm",
                "available_context_note",
                "reliability_flag",
            ]
        )

    out = geography_lookup.copy()
    out["reference_year"] = 2025
    out["population_count"] = out["population"]
    out["population_density_per_sqkm"] = out["population"] / out["area_sqkm"].replace({0: pd.NA})
    out["available_context_note"] = "Currently limited to local population, remoteness and area context. Census, SEIFA, DSS, PHIDU, workforce and housing sources are not available locally."
    return out[
        [
            "geography_type",
            "geography_code",
            "reference_year",
            "population_count",
            "remoteness",
            "area_sqkm",
            "population_density_per_sqkm",
            "available_context_note",
            "reliability_flag",
        ]
    ]


def build_tableau_outputs(market: pd.DataFrame, support_type: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Build all Tableau CSV outputs and geometry quality rows."""

    geography_lookup = build_geography_lookup()
    market_opportunity = _add_market_opportunity_fields(market)
    outputs = {
        "tableau_market_quarter": _market_columns(market_opportunity),
        "tableau_support_type_quarter": _support_columns(support_type, market_opportunity),
        "tableau_participant_profile": build_participant_profile(),
        "tableau_community_context": build_community_context(geography_lookup),
        "tableau_market_classification": build_market_classification(market),
        "tableau_geography_lookup": geography_lookup,
    }
    geometry_quality_rows = write_geometry_outputs()
    return outputs, geometry_quality_rows


def write_tableau_outputs(outputs: dict[str, pd.DataFrame], data_quality: pd.DataFrame) -> None:
    """Write Tableau outputs as CSV and Parquet."""

    writable = dict(outputs)
    writable["tableau_data_quality"] = data_quality
    for name, frame in writable.items():
        csv_path = config.TABLEAU_OUTPUTS[name]
        parquet_path = config.PARQUET_OUTPUTS[name]
        write_dataset(frame, csv_path, parquet_path)


def _market_columns(market: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "quarter",
        "quarter_label",
        "quarter_end_date",
        "geography_type",
        "geography_code",
        "geography_name",
        "state",
        "remoteness",
        "population_count",
        "participant_count",
        "funded_plan_count",
        "participants_per_1000",
        "funded_plans_per_1000",
        "participant_growth_rate",
        "funded_plan_growth_rate",
        "mean_plan_funding",
        "median_plan_funding",
        "committed_supports",
        "payment_amount",
        "payments_per_funded_plan",
        "payments_per_participant",
        "payments_per_1000_population",
        "funding_conversion_rate",
        "unspent_committed_funding",
        "unspent_funding_per_funded_plan",
        "mean_plan_utilisation",
        "benchmark_national_funded_plans_per_1000",
        "benchmark_national_median_funded_plans_per_1000",
        "benchmark_national_mean_plan_utilisation",
        "benchmark_national_median_plan_utilisation",
        "benchmark_national_provider_saturation",
        "benchmark_national_median_provider_saturation",
        "benchmark_national_active_providers_per_1000_funded_plans",
        "benchmark_national_median_active_providers_per_1000_funded_plans",
        "benchmark_national_mean_plan_funding",
        "benchmark_national_payments_per_funded_plan",
        "benchmark_remoteness_funded_plans_per_1000",
        "benchmark_remoteness_mean_plan_utilisation",
        "benchmark_remoteness_mean_plan_funding",
        "benchmark_remoteness_payments_per_funded_plan",
        "funded_plans_per_1000_gap_from_national",
        "funded_plans_per_1000_delta_from_national_mean",
        "funded_plans_per_1000_delta_from_national_median",
        "mean_plan_utilisation_gap_from_national",
        "mean_plan_utilisation_delta_from_national_median",
        "mean_plan_funding_gap_from_national",
        "payments_per_funded_plan_gap_from_national",
        "funded_plans_per_1000_gap_from_remoteness",
        "mean_plan_utilisation_gap_from_remoteness",
        "mean_plan_funding_gap_from_remoteness",
        "payments_per_funded_plan_gap_from_remoteness",
        "active_provider_count",
        "registered_provider_count",
        "funded_plans_per_active_provider",
        "participants_per_active_provider",
        "active_providers_per_1000_funded_plans",
        "provider_saturation_delta_from_national_mean",
        "provider_saturation_delta_from_national_median",
        "active_provider_rate_delta_from_national_mean",
        "active_provider_rate_delta_from_national_median",
        "atlas_default_metric_value",
        "atlas_default_metric_label",
        "atlas_metric_interpretation",
        "atlas_utilisation_median_band",
        "provider_growth_rate",
        "payment_growth_rate",
        "plan_value_growth_rate",
        "supply_response_gap",
        "funding_conversion_gap",
        "funded_plan_volume_score",
        "funded_plan_density_score",
        "payment_intensity_score",
        "unspent_funding_score",
        "utilisation_gap_score",
        "funded_plan_coverage_gap_score",
        "mean_plan_funding_gap_score",
        "payment_intensity_gap_score",
        "provider_load_score",
        "growth_pressure_score",
        "funding_conversion_gap_score",
        "underfunded_advocacy_score",
        "utilisation_barrier_score",
        "underserviced_provider_score",
        "business_opportunity_score",
        "advocacy_opportunity_score",
        "combined_opportunity_score",
        "opportunity_rank",
        "opportunity_segment",
        "opportunity_reading_note",
        "market_density_indicator_note",
        "population_reference_year",
        "population_method",
        "reliability_flag",
    ]
    return market[[col for col in columns if col in market.columns]].copy()


def _support_columns(support: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    support = _add_support_opportunity_fields(support, market)
    columns = [
        "quarter",
        "quarter_label",
        "quarter_end_date",
        "geography_type",
        "geography_code",
        "geography_name",
        "remoteness",
        "support_class",
        "support_type",
        "support_type_group",
        "atlas_service_type_filter",
        "payments",
        "local_support_share",
        "payment_growth_rate",
        "payments_per_funded_plan",
        "payments_per_1000_population",
        "national_support_share",
        "remoteness_support_share",
        "support_location_quotient",
        "remoteness_support_location_quotient",
        "national_benchmark",
        "remoteness_benchmark",
        "support_payment_gap_from_national_benchmark",
        "support_payment_gap_from_remoteness_benchmark",
        "support_share_gap_from_national",
        "support_share_gap_from_remoteness",
        "support_lq_gap_from_remoteness",
        "projected_next_quarter_payments",
        "projected_next_quarter_payment_change",
        "support_undersupply_score",
        "support_growth_score",
        "support_payment_scale_score",
        "support_payment_intensity_score",
        "support_business_opportunity_score",
        "support_advocacy_opportunity_score",
        "service_type_opportunity_score",
        "service_type_opportunity_rank",
        "service_type_opportunity_segment",
        "business_opportunity_score",
        "advocacy_opportunity_score",
        "underfunded_advocacy_score",
        "underserviced_provider_score",
        "funded_plans_per_1000_delta_from_national_mean",
        "funded_plans_per_1000_delta_from_national_median",
        "mean_plan_utilisation_delta_from_national_median",
        "provider_saturation_delta_from_national_mean",
        "provider_saturation_delta_from_national_median",
        "active_provider_rate_delta_from_national_mean",
        "active_provider_rate_delta_from_national_median",
        "atlas_default_metric_value",
        "atlas_default_metric_label",
        "atlas_metric_interpretation",
        "atlas_utilisation_median_band",
        "payment_item_participant_count_sum_not_unique",
        "suppressed_payment_item_rows",
        "suppressed_participant_item_rows",
        "source_item_rows",
        "area_total_payments",
        "funded_plan_count",
        "population_count",
        "reliability_flag",
    ]
    return support[[col for col in columns if col in support.columns]].copy()


def _add_market_opportunity_fields(market: pd.DataFrame) -> pd.DataFrame:
    """Add transparent business and advocacy opportunity proxy fields."""

    out = market.copy()
    if out.empty:
        return out

    out["benchmark_national_mean_plan_funding"] = _weighted_average_by_group(out, ["quarter"], "mean_plan_funding", "funded_plan_count")
    out["benchmark_remoteness_mean_plan_funding"] = _weighted_average_by_group(out, ["quarter", "remoteness"], "mean_plan_funding", "funded_plan_count")
    out["benchmark_national_payments_per_funded_plan"] = _weighted_average_by_group(out, ["quarter"], "payments_per_funded_plan", "funded_plan_count")
    out["benchmark_remoteness_payments_per_funded_plan"] = _weighted_average_by_group(out, ["quarter", "remoteness"], "payments_per_funded_plan", "funded_plan_count")
    out["benchmark_national_median_funded_plans_per_1000"] = numeric(out.get("funded_plans_per_1000")).groupby(out["quarter"], dropna=False).transform("median")
    out["benchmark_national_median_plan_utilisation"] = numeric(out.get("mean_plan_utilisation")).groupby(out["quarter"], dropna=False).transform("median")
    out["benchmark_national_provider_saturation"] = _weighted_average_by_group(out, ["quarter"], "funded_plans_per_active_provider", "funded_plan_count")
    out["benchmark_national_median_provider_saturation"] = numeric(out.get("funded_plans_per_active_provider")).groupby(out["quarter"], dropna=False).transform("median")
    out["benchmark_national_active_providers_per_1000_funded_plans"] = _weighted_average_by_group(out, ["quarter"], "active_providers_per_1000_funded_plans", "funded_plan_count")
    out["benchmark_national_median_active_providers_per_1000_funded_plans"] = numeric(out.get("active_providers_per_1000_funded_plans")).groupby(out["quarter"], dropna=False).transform("median")

    out["mean_plan_funding_gap_from_national"] = numeric(out["benchmark_national_mean_plan_funding"]) - numeric(out.get("mean_plan_funding"))
    out["mean_plan_funding_gap_from_remoteness"] = numeric(out["benchmark_remoteness_mean_plan_funding"]) - numeric(out.get("mean_plan_funding"))
    out["payments_per_funded_plan_gap_from_national"] = numeric(out["benchmark_national_payments_per_funded_plan"]) - numeric(out.get("payments_per_funded_plan"))
    out["payments_per_funded_plan_gap_from_remoteness"] = numeric(out["benchmark_remoteness_payments_per_funded_plan"]) - numeric(out.get("payments_per_funded_plan"))
    out["funded_plans_per_1000_delta_from_national_mean"] = numeric(out.get("funded_plans_per_1000")) - numeric(out.get("benchmark_national_funded_plans_per_1000"))
    out["funded_plans_per_1000_delta_from_national_median"] = numeric(out.get("funded_plans_per_1000")) - numeric(out["benchmark_national_median_funded_plans_per_1000"])
    out["mean_plan_utilisation_delta_from_national_median"] = numeric(out.get("mean_plan_utilisation")) - numeric(out["benchmark_national_median_plan_utilisation"])
    out["provider_saturation_delta_from_national_mean"] = numeric(out.get("funded_plans_per_active_provider")) - numeric(out["benchmark_national_provider_saturation"])
    out["provider_saturation_delta_from_national_median"] = numeric(out.get("funded_plans_per_active_provider")) - numeric(out["benchmark_national_median_provider_saturation"])
    out["active_provider_rate_delta_from_national_mean"] = numeric(out.get("active_providers_per_1000_funded_plans")) - numeric(out["benchmark_national_active_providers_per_1000_funded_plans"])
    out["active_provider_rate_delta_from_national_median"] = numeric(out.get("active_providers_per_1000_funded_plans")) - numeric(out["benchmark_national_median_active_providers_per_1000_funded_plans"])
    out["atlas_utilisation_median_band"] = _utilisation_median_band(out["mean_plan_utilisation_delta_from_national_median"])
    out["unspent_funding_per_funded_plan"] = safe_divide(out.get("unspent_committed_funding"), out.get("funded_plan_count"))
    out["funding_conversion_gap"] = (1 - numeric(out.get("funding_conversion_rate"))).clip(lower=0)

    out["funded_plan_volume_score"] = _quarter_score(out, "funded_plan_count")
    out["funded_plan_density_score"] = _quarter_score(out, "funded_plans_per_1000")
    out["payment_intensity_score"] = _quarter_score(out, "payments_per_funded_plan")
    out["unspent_funding_score"] = _quarter_score(out, "unspent_funding_per_funded_plan", positive_only=True)
    out["utilisation_gap_score"] = _quarter_score(out, "mean_plan_utilisation_gap_from_remoteness", positive_only=True)
    out["funded_plan_coverage_gap_score"] = _quarter_score(out, "funded_plans_per_1000_gap_from_remoteness", positive_only=True)
    out["mean_plan_funding_gap_score"] = _quarter_score(out, "mean_plan_funding_gap_from_remoteness", positive_only=True)
    out["payment_intensity_gap_score"] = _quarter_score(out, "payments_per_funded_plan_gap_from_remoteness", positive_only=True)
    out["provider_load_score"] = _quarter_score(out, "funded_plans_per_active_provider")
    out["growth_pressure_score"] = _quarter_score(out, "supply_response_gap", positive_only=True)
    out["funding_conversion_gap_score"] = _quarter_score(out, "funding_conversion_gap", positive_only=True)

    out["underfunded_advocacy_score"] = _row_mean(
        out,
        [
            "funded_plan_coverage_gap_score",
            "mean_plan_funding_gap_score",
            "payment_intensity_gap_score",
        ],
    )
    out["utilisation_barrier_score"] = _row_mean(
        out,
        [
            "utilisation_gap_score",
            "unspent_funding_score",
            "funding_conversion_gap_score",
        ],
    )
    out["underserviced_provider_score"] = _row_mean(
        out,
        [
            "provider_load_score",
            "growth_pressure_score",
            "utilisation_gap_score",
        ],
    )
    out["business_opportunity_score"] = _row_mean(
        out,
        [
            "funded_plan_volume_score",
            "payment_intensity_score",
            "utilisation_barrier_score",
            "underserviced_provider_score",
            "unspent_funding_score",
        ],
    )
    out["advocacy_opportunity_score"] = _row_mean(
        out,
        [
            "underfunded_advocacy_score",
            "utilisation_barrier_score",
            "underserviced_provider_score",
        ],
    )
    out["combined_opportunity_score"] = _row_mean(out, ["business_opportunity_score", "advocacy_opportunity_score"])
    out["opportunity_rank"] = numeric(out["combined_opportunity_score"]).groupby(out["quarter"]).rank(ascending=False, method="dense")
    out["opportunity_segment"] = _market_opportunity_segment(out)
    out["atlas_default_metric_value"] = _row_mean(
        out,
        [
            "funded_plan_coverage_gap_score",
            "utilisation_gap_score",
            "underserviced_provider_score",
        ],
    )
    out["atlas_default_metric_label"] = "Benchmark opportunity index"
    out["atlas_metric_interpretation"] = (
        "Atlas benchmark fields compare each service area with the national service-area median for the same quarter. "
        "The map colour uses utilisation delta from the national median, where higher utilisation is greener and lower utilisation is redder."
    )
    out["opportunity_reading_note"] = (
        "Proxy score from public NDIA service-area data. It combines benchmark gaps, utilisation friction, "
        "unspent committed funding and provider-activity indicators; it is a triage signal, not proof of unmet need."
    )
    return out


def _add_support_opportunity_fields(support: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    """Add support-type opportunity signals and area-level context."""

    out = support.copy()
    if out.empty:
        return out

    context_cols = [
        "quarter",
        "geography_type",
        "geography_code",
        "business_opportunity_score",
        "advocacy_opportunity_score",
        "underfunded_advocacy_score",
        "underserviced_provider_score",
        "funded_plans_per_1000_delta_from_national_mean",
        "funded_plans_per_1000_delta_from_national_median",
        "mean_plan_utilisation_delta_from_national_median",
        "provider_saturation_delta_from_national_mean",
        "provider_saturation_delta_from_national_median",
        "active_provider_rate_delta_from_national_mean",
        "active_provider_rate_delta_from_national_median",
        "atlas_default_metric_value",
        "atlas_default_metric_label",
        "atlas_metric_interpretation",
        "atlas_utilisation_median_band",
    ]
    available_context = [col for col in context_cols if col in market.columns]
    if len(available_context) == len(context_cols):
        out = out.merge(
            market[context_cols].drop_duplicates(["quarter", "geography_type", "geography_code"]),
            on=["quarter", "geography_type", "geography_code"],
            how="left",
        )
    out["atlas_service_type_filter"] = out.get("support_type", pd.Series("All supports", index=out.index)).fillna("All supports")

    out["support_payment_gap_from_national_benchmark"] = numeric(out.get("area_total_payments")) * numeric(out.get("national_benchmark")) - numeric(out.get("payments"))
    out["support_payment_gap_from_remoteness_benchmark"] = numeric(out.get("area_total_payments")) * numeric(out.get("remoteness_benchmark")) - numeric(out.get("payments"))
    out["support_share_gap_from_national"] = numeric(out.get("national_benchmark")) - numeric(out.get("local_support_share"))
    out["support_share_gap_from_remoteness"] = numeric(out.get("remoteness_benchmark")) - numeric(out.get("local_support_share"))
    out["support_lq_gap_from_remoteness"] = (1 - numeric(out.get("remoteness_support_location_quotient"))).clip(lower=0)

    clipped_growth = numeric(out.get("payment_growth_rate")).clip(lower=-0.5, upper=0.5).fillna(0)
    out["projected_next_quarter_payments"] = numeric(out.get("payments")) * (1 + clipped_growth)
    out["projected_next_quarter_payment_change"] = out["projected_next_quarter_payments"] - numeric(out.get("payments"))

    out["support_undersupply_score"] = _row_mean(
        pd.DataFrame(
            {
                "payment_gap": _quarter_score(out, "support_payment_gap_from_remoteness_benchmark", positive_only=True),
                "share_gap": _quarter_score(out, "support_share_gap_from_remoteness", positive_only=True),
                "lq_gap": _quarter_score(out, "support_lq_gap_from_remoteness", positive_only=True),
            }
        ),
        ["payment_gap", "share_gap", "lq_gap"],
    )
    out["support_growth_score"] = _quarter_score(out, "payment_growth_rate", positive_only=True)
    out["support_payment_scale_score"] = _quarter_score(out, "payments")
    out["support_payment_intensity_score"] = _quarter_score(out, "payments_per_funded_plan")
    out["support_business_opportunity_score"] = _row_mean(
        out,
        [
            "support_undersupply_score",
            "support_growth_score",
            "support_payment_scale_score",
            "support_payment_intensity_score",
            "business_opportunity_score",
        ],
    )
    out["support_advocacy_opportunity_score"] = _row_mean(
        out,
        [
            "support_undersupply_score",
            "advocacy_opportunity_score",
            "underfunded_advocacy_score",
            "underserviced_provider_score",
        ],
    )
    out["service_type_opportunity_score"] = _row_mean(out, ["support_business_opportunity_score", "support_advocacy_opportunity_score"])
    rank_groups = [out["quarter"], out["support_type"] if "support_type" in out.columns else pd.Series("", index=out.index)]
    out["service_type_opportunity_rank"] = numeric(out["service_type_opportunity_score"]).groupby(rank_groups).rank(ascending=False, method="dense")
    out["service_type_opportunity_segment"] = _support_opportunity_segment(out)
    return out


def _utilisation_median_band(delta: pd.Series) -> pd.Series:
    values = numeric(delta)
    return pd.Series(
        np.select(
            [values.isna(), values < -0.02, values > 0.02],
            ["No data", "Below national median", "Above national median"],
            default="Near national median",
        ),
        index=values.index,
    )


def _weighted_average_by_group(frame: pd.DataFrame, group_cols: list[str], value_col: str, weight_col: str) -> pd.Series:
    if value_col not in frame.columns or weight_col not in frame.columns:
        return pd.Series(np.nan, index=frame.index)

    values = numeric(frame[value_col])
    weights = numeric(frame[weight_col]).clip(lower=0)
    result = pd.Series(np.nan, index=frame.index, dtype="float64")
    group_key = group_cols[0] if len(group_cols) == 1 else group_cols
    for _, index in frame.groupby(group_key, dropna=False).groups.items():
        group_values = values.loc[index]
        group_weights = weights.loc[index]
        valid = group_values.notna() & group_weights.gt(0)
        if valid.any():
            result.loc[index] = np.average(group_values.loc[valid], weights=group_weights.loc[valid])
        elif group_values.notna().any():
            result.loc[index] = group_values.mean()
    return result


def _quarter_score(frame: pd.DataFrame, field: str, *, positive_only: bool = False) -> pd.Series:
    if field not in frame.columns or "quarter" not in frame.columns:
        return pd.Series(np.nan, index=frame.index)

    values = numeric(frame[field])
    if positive_only:
        values = values.where(values > 0, 0)
    return values.groupby(frame["quarter"], dropna=False).rank(pct=True)


def _row_mean(frame: pd.DataFrame, fields: list[str]) -> pd.Series:
    available = [field for field in fields if field in frame.columns]
    if not available:
        return pd.Series(np.nan, index=frame.index)
    values = frame[available].apply(numeric)
    return values.mean(axis=1, skipna=True)


def _market_opportunity_segment(frame: pd.DataFrame) -> pd.Series:
    underfunded = numeric(frame.get("underfunded_advocacy_score"))
    underserved = numeric(frame.get("underserviced_provider_score"))
    business = numeric(frame.get("business_opportunity_score"))
    advocacy = numeric(frame.get("advocacy_opportunity_score"))
    conditions = [
        underfunded.ge(0.67) & underserved.ge(0.67),
        underfunded.ge(0.67),
        underserved.ge(0.67),
        business.ge(0.67),
        advocacy.ge(0.67),
    ]
    choices = [
        "under-funded and under-serviced",
        "advocacy: funding or access gap",
        "provider opportunity: under-serviced",
        "business opportunity: high demand friction",
        "advocacy watchlist",
    ]
    return pd.Series(np.select(conditions, choices, default="monitor"), index=frame.index)


def _support_opportunity_segment(frame: pd.DataFrame) -> pd.Series:
    undersupply = numeric(frame.get("support_undersupply_score"))
    growth = numeric(frame.get("support_growth_score"))
    scale = numeric(frame.get("support_payment_scale_score"))
    underserved = numeric(frame.get("underserviced_provider_score"))
    underfunded = numeric(frame.get("underfunded_advocacy_score"))
    lq = numeric(frame.get("remoteness_support_location_quotient"))
    conditions = [
        undersupply.ge(0.67) & underserved.ge(0.67),
        undersupply.ge(0.67) & underfunded.ge(0.67),
        growth.ge(0.67) & scale.ge(0.67),
        lq.ge(1.25),
        undersupply.ge(0.67),
    ]
    choices = [
        "under-serviced support gap",
        "advocacy support gap",
        "growth market",
        "local specialisation",
        "under-indexed support mix",
    ]
    return pd.Series(np.select(conditions, choices, default="monitor"), index=frame.index)
