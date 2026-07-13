from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config
from .io_utils import configure_logging, ensure_directories, numeric, safe_divide, write_dataset


LOGGER = logging.getLogger(__name__)


def run_analysis() -> dict[str, pd.DataFrame]:
    """Run analysis over Tableau-ready outputs and write publication review tables."""

    ensure_directories()
    market = pd.read_csv(config.TABLEAU_OUTPUTS["tableau_market_quarter"], low_memory=False)
    support = pd.read_csv(config.TABLEAU_OUTPUTS["tableau_support_type_quarter"], low_memory=False)
    classifications = pd.read_csv(config.TABLEAU_OUTPUTS["tableau_market_classification"], low_memory=False)

    outputs = {
        "analysis_latest_market_rankings": latest_market_rankings(market),
        "analysis_opportunity_rankings": opportunity_rankings(market),
        "analysis_market_trends": market_trends(market),
        "analysis_support_type_hotspots": support_type_hotspots(support),
        "analysis_service_type_opportunities": service_type_opportunities(support),
        "analysis_remoteness_summary": remoteness_summary(market),
        "analysis_classification_summary": classification_summary(classifications),
        "analysis_website_kpis": website_kpis(market),
    }

    for name, frame in outputs.items():
        write_dataset(frame, config.ANALYSIS_DIR / f"{name}.csv", config.ANALYSIS_DIR / f"{name}.parquet")

    write_analysis_summary(outputs, market)
    return outputs


def latest_market_rankings(market: pd.DataFrame) -> pd.DataFrame:
    """Create a compact latest-quarter ranked issue table for dashboard QA."""

    latest = _latest_quarter_frame(market)
    metrics = [
        ("lowest_utilisation", "mean_plan_utilisation", True),
        ("largest_utilisation_gap_from_national", "mean_plan_utilisation_gap_from_national", False),
        ("highest_unspent_funding_per_plan", "unspent_funding_per_funded_plan", False),
        ("highest_participants_per_provider", "participants_per_active_provider", False),
        ("largest_supply_response_gap", "supply_response_gap", False),
        ("highest_payments_per_plan", "payments_per_funded_plan", False),
        ("highest_funded_plan_density", "funded_plans_per_1000", False),
    ]

    latest = latest.copy()
    latest["unspent_funding_per_funded_plan"] = safe_divide(latest["unspent_committed_funding"], latest["funded_plan_count"])

    rows: list[pd.DataFrame] = []
    for ranking_name, field, ascending in metrics:
        if field not in latest.columns:
            continue
        ranked = latest.loc[numeric(latest[field]).notna()].copy()
        ranked[field] = numeric(ranked[field])
        ranked = ranked.sort_values(field, ascending=ascending).head(15)
        ranked["ranking_name"] = ranking_name
        ranked["ranking_field"] = field
        ranked["ranking_value"] = ranked[field]
        ranked["rank"] = range(1, len(ranked) + 1)
        rows.append(
            ranked[
                [
                    "ranking_name",
                    "rank",
                    "quarter",
                    "quarter_label",
                    "geography_code",
                    "geography_name",
                    "state",
                    "remoteness",
                    "ranking_field",
                    "ranking_value",
                    "funded_plan_count",
                    "population_count",
                    "mean_plan_utilisation",
                    "payment_amount",
                    "active_provider_count",
                    "reliability_flag",
                ]
            ]
        )

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def opportunity_rankings(market: pd.DataFrame) -> pd.DataFrame:
    """Rank latest service areas by opportunity and advocacy proxy signals."""

    latest = _latest_quarter_frame(market)
    metrics = [
        ("combined_opportunity", "combined_opportunity_score"),
        ("business_opportunity", "business_opportunity_score"),
        ("advocacy_opportunity", "advocacy_opportunity_score"),
        ("underfunded_advocacy", "underfunded_advocacy_score"),
        ("underserviced_provider", "underserviced_provider_score"),
        ("utilisation_barrier", "utilisation_barrier_score"),
    ]
    rows: list[pd.DataFrame] = []
    for ranking_name, field in metrics:
        if field not in latest.columns:
            continue
        ranked = latest.loc[numeric(latest[field]).notna()].copy()
        ranked[field] = numeric(ranked[field])
        ranked = ranked.sort_values(field, ascending=False).head(20)
        ranked["ranking_name"] = ranking_name
        ranked["ranking_field"] = field
        ranked["ranking_value"] = ranked[field]
        ranked["rank"] = range(1, len(ranked) + 1)
        keep = [
            "ranking_name",
            "rank",
            "quarter",
            "quarter_label",
            "geography_code",
            "geography_name",
            "state",
            "remoteness",
            "ranking_field",
            "ranking_value",
            "opportunity_segment",
            "business_opportunity_score",
            "advocacy_opportunity_score",
            "underfunded_advocacy_score",
            "underserviced_provider_score",
            "funded_plan_count",
            "payment_amount",
            "active_provider_count",
            "reliability_flag",
        ]
        rows.append(ranked[[col for col in keep if col in ranked.columns]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def market_trends(market: pd.DataFrame) -> pd.DataFrame:
    """Compare first and latest quarter for each geography."""

    ordered = market.sort_values(["geography_type", "geography_code", "quarter"])
    first = ordered.groupby(["geography_type", "geography_code"], dropna=False).first().reset_index()
    latest = ordered.groupby(["geography_type", "geography_code"], dropna=False).last().reset_index()
    keep = [
        "geography_type",
        "geography_code",
        "geography_name",
        "state",
        "remoteness",
        "quarter",
        "funded_plan_count",
        "funded_plans_per_1000",
        "mean_plan_utilisation",
        "payment_amount",
        "active_provider_count",
    ]
    merged = latest[keep].merge(first[keep], on=["geography_type", "geography_code"], suffixes=("_latest", "_first"))
    merged["funded_plan_count_change"] = numeric(merged["funded_plan_count_latest"]) - numeric(merged["funded_plan_count_first"])
    merged["funded_plan_count_growth_rate"] = safe_divide(merged["funded_plan_count_change"], merged["funded_plan_count_first"])
    merged["funded_plans_per_1000_change"] = numeric(merged["funded_plans_per_1000_latest"]) - numeric(merged["funded_plans_per_1000_first"])
    merged["utilisation_change"] = numeric(merged["mean_plan_utilisation_latest"]) - numeric(merged["mean_plan_utilisation_first"])
    merged["payment_amount_change"] = numeric(merged["payment_amount_latest"]) - numeric(merged["payment_amount_first"])
    merged["provider_count_change"] = numeric(merged["active_provider_count_latest"]) - numeric(merged["active_provider_count_first"])
    return merged.sort_values("funded_plan_count_growth_rate", ascending=False)


def support_type_hotspots(support: pd.DataFrame) -> pd.DataFrame:
    """Rank latest-quarter support-type location quotient hotspots."""

    latest = _latest_quarter_frame(support)
    latest = latest.loc[
        numeric(latest["support_location_quotient"]).notna()
        & numeric(latest["payments"]).gt(0)
    ].copy()
    latest["support_location_quotient"] = numeric(latest["support_location_quotient"])
    latest["payments"] = numeric(latest["payments"])
    latest["payments_rank_within_support"] = latest.groupby("support_type")["payments"].rank(ascending=False, method="dense")
    latest["location_quotient_rank_within_support"] = latest.groupby("support_type")["support_location_quotient"].rank(ascending=False, method="dense")
    return latest.sort_values(["support_type", "location_quotient_rank_within_support"]).groupby("support_type").head(10)[
        [
            "quarter",
            "quarter_label",
            "geography_code",
            "geography_name",
            "remoteness",
            "support_class",
            "support_type",
            "payments",
            "local_support_share",
            "national_support_share",
            "support_location_quotient",
            "remoteness_support_location_quotient",
            "payments_rank_within_support",
            "location_quotient_rank_within_support",
            "reliability_flag",
        ]
    ]


def service_type_opportunities(support: pd.DataFrame) -> pd.DataFrame:
    """Rank latest service-area support-type opportunities."""

    latest = _latest_quarter_frame(support)
    if "service_type_opportunity_score" not in latest.columns:
        return pd.DataFrame()
    ranked = latest.loc[numeric(latest["service_type_opportunity_score"]).notna()].copy()
    ranked["service_type_opportunity_score"] = numeric(ranked["service_type_opportunity_score"])
    ranked["rank_within_support_type"] = ranked.groupby("support_type")["service_type_opportunity_score"].rank(ascending=False, method="dense")
    ranked["overall_rank"] = ranked["service_type_opportunity_score"].rank(ascending=False, method="dense")
    return ranked.sort_values(["support_type", "rank_within_support_type"]).groupby("support_type").head(10)[
        [
            "quarter",
            "quarter_label",
            "geography_code",
            "geography_name",
            "remoteness",
            "support_class",
            "support_type",
            "support_type_group",
            "service_type_opportunity_score",
            "rank_within_support_type",
            "overall_rank",
            "service_type_opportunity_segment",
            "support_undersupply_score",
            "support_payment_gap_from_remoteness_benchmark",
            "support_share_gap_from_remoteness",
            "projected_next_quarter_payments",
            "payments",
            "local_support_share",
            "remoteness_benchmark",
            "reliability_flag",
        ]
    ]


def remoteness_summary(market: pd.DataFrame) -> pd.DataFrame:
    """Aggregate latest market measures by remoteness using numerator/denominator logic."""

    latest = _latest_quarter_frame(market)
    grouped = latest.groupby(["quarter", "quarter_label", "remoteness"], dropna=False)
    rows = []
    for key, group in grouped:
        quarter, quarter_label, remoteness = key
        population = numeric(group["population_count"]).sum()
        funded_plans = numeric(group["funded_plan_count"]).sum()
        payments = numeric(group["payment_amount"]).sum()
        providers = numeric(group["active_provider_count"]).sum(min_count=1)
        weighted_util = np.average(
            numeric(group["mean_plan_utilisation"]).dropna(),
            weights=numeric(group.loc[numeric(group["mean_plan_utilisation"]).notna(), "funded_plan_count"]).clip(lower=0),
        ) if numeric(group["mean_plan_utilisation"]).notna().any() else np.nan
        rows.append(
            {
                "quarter": quarter,
                "quarter_label": quarter_label,
                "remoteness": remoteness,
                "geography_count": group["geography_code"].nunique(),
                "population_count": population,
                "funded_plan_count": funded_plans,
                "funded_plans_per_1000": funded_plans / population * 1000 if population else np.nan,
                "payment_amount": payments,
                "payments_per_funded_plan": payments / funded_plans if funded_plans else np.nan,
                "active_provider_count": providers,
                "active_providers_per_1000_funded_plans": providers / funded_plans * 1000 if pd.notna(providers) and funded_plans else np.nan,
                "weighted_mean_plan_utilisation": weighted_util,
            }
        )
    return pd.DataFrame(rows)


def classification_summary(classifications: pd.DataFrame) -> pd.DataFrame:
    """Summarise latest-quarter classification counts."""

    latest = _latest_quarter_frame(classifications)
    rows = []
    for field in [
        "persistent_utilisation_classification",
        "participant_provider_growth_quadrant",
        "payment_provider_growth_quadrant",
    ]:
        if field not in latest.columns:
            continue
        counts = latest.groupby(field, dropna=False).size().reset_index(name="geography_count")
        counts["classification_field"] = field
        counts = counts.rename(columns={field: "classification_value"})
        rows.append(counts[["classification_field", "classification_value", "geography_count"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def website_kpis(market: pd.DataFrame) -> pd.DataFrame:
    """Create headline KPIs for website copy and Tableau QA."""

    latest = _latest_quarter_frame(market)
    population = numeric(latest["population_count"]).sum()
    funded_plans = numeric(latest["funded_plan_count"]).sum()
    payments = numeric(latest["payment_amount"]).sum()
    providers = numeric(latest["active_provider_count"]).sum(min_count=1)
    weights = numeric(latest["funded_plan_count"]).fillna(0)
    util_values = numeric(latest["mean_plan_utilisation"])
    valid = util_values.notna() & weights.gt(0)
    weighted_util = np.average(util_values[valid], weights=weights[valid]) if valid.any() else np.nan
    rows = [
        ("latest_quarter", np.nan, str(latest["quarter_label"].iloc[0]), "label"),
        ("service_area_count", latest["geography_code"].nunique(), "", "count"),
        ("population_count", population, "", "count"),
        ("funded_plan_count", funded_plans, "", "count"),
        ("funded_plans_per_1000", funded_plans / population * 1000 if population else np.nan, "", "per_1000"),
        ("payment_amount", payments, "", "aud"),
        ("payments_per_funded_plan", payments / funded_plans if funded_plans else np.nan, "", "aud"),
        ("active_provider_count", providers, "", "count"),
        ("weighted_mean_plan_utilisation", weighted_util, "", "decimal"),
    ]
    return pd.DataFrame(rows, columns=["kpi", "value_number", "value_text", "unit"])


def write_analysis_summary(outputs: dict[str, pd.DataFrame], market: pd.DataFrame) -> None:
    """Write a concise markdown analysis summary for review."""

    kpi_frame = outputs["analysis_website_kpis"].set_index("kpi")
    kpis = kpi_frame["value_number"].to_dict()
    kpi_text = kpi_frame["value_text"].to_dict()
    ranking = outputs["analysis_latest_market_rankings"]
    opportunity = outputs.get("analysis_opportunity_rankings", pd.DataFrame())
    service_opportunity = outputs.get("analysis_service_type_opportunities", pd.DataFrame())
    class_summary = outputs["analysis_classification_summary"]
    latest_label = kpi_text.get("latest_quarter", "")

    top_low_util = ranking.loc[ranking["ranking_name"].eq("lowest_utilisation")].head(5)
    low_util_lines = [
        f"- {row.geography_name}: {row.ranking_value:.3f}"
        for row in top_low_util.itertuples()
        if pd.notna(row.ranking_value)
    ]

    classification_lines = []
    if not class_summary.empty:
        latest_classes = class_summary.loc[class_summary["classification_field"].eq("persistent_utilisation_classification")]
        classification_lines = [
            f"- {row.classification_value}: {int(row.geography_count)} service areas"
            for row in latest_classes.itertuples()
        ]

    top_opportunities = opportunity.loc[opportunity["ranking_name"].eq("combined_opportunity")].head(5) if not opportunity.empty else pd.DataFrame()
    opportunity_lines = [
        f"- {row.geography_name}: {row.ranking_value:.3f} ({row.opportunity_segment})"
        for row in top_opportunities.itertuples()
        if pd.notna(row.ranking_value)
    ]
    top_service_opportunities = service_opportunity.sort_values("overall_rank").head(5) if not service_opportunity.empty else pd.DataFrame()
    service_lines = [
        f"- {row.geography_name} / {row.support_type}: {row.service_type_opportunity_score:.3f} ({row.service_type_opportunity_segment})"
        for row in top_service_opportunities.itertuples()
        if pd.notna(row.service_type_opportunity_score)
    ]

    text = f"""# Tableau Output Analysis Summary

## Latest Period

Latest quarter: {latest_label}

## Headline KPIs

- Service areas: {int(float(kpis.get("service_area_count", 0))):,}
- Funded plans: {float(kpis.get("funded_plan_count", 0)):,.0f}
- Funded plans per 1,000 population: {float(kpis.get("funded_plans_per_1000", np.nan)):.2f}
- Payments: ${float(kpis.get("payment_amount", 0)):,.0f}
- Payments per funded plan: ${float(kpis.get("payments_per_funded_plan", 0)):,.0f}
- Weighted mean utilisation: {float(kpis.get("weighted_mean_plan_utilisation", np.nan)):.3f}

## Lowest Utilisation Review List

{chr(10).join(low_util_lines) if low_util_lines else "- No ranked utilisation rows available."}

## Top Opportunity Review List

{chr(10).join(opportunity_lines) if opportunity_lines else "- No opportunity ranking rows available."}

## Top Service-Type Opportunity Review List

{chr(10).join(service_lines) if service_lines else "- No service-type opportunity rows available."}

## Persistent Utilisation Classifications

{chr(10).join(classification_lines) if classification_lines else "- No classification rows available."}

## Interpretation Notes

- These are analysis prompts for Tableau authoring and review, not causal findings.
- Low utilisation does not prove provider shortage.
- Provider counts are provider-activity context and should not be described as workforce capacity.
- Participant-profile, Census, SEIFA, DSS, PHIDU, workforce and broader housing/SDA domains remain source gaps until official local extracts are supplied.
"""
    path = config.ANALYSIS_DIR / "analysis_summary.md"
    path.write_text(text, encoding="utf-8")
    LOGGER.info("Wrote %s", path)


def _latest_quarter_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if "quarter" not in frame.columns:
        return frame.copy()
    quarters = frame["quarter"].dropna().astype(str)
    latest = quarters.sort_values().iloc[-1]
    return frame.loc[frame["quarter"].astype(str).eq(latest)].copy()


if __name__ == "__main__":
    configure_logging()
    run_analysis()
