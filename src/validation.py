from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from .io_utils import numeric, safe_divide


QUALITY_COLUMNS = [
    "dataset",
    "period",
    "geography",
    "field",
    "issue_type",
    "issue_severity",
    "missingness",
    "suppression",
    "mapping_status",
    "reliability_flag",
    "explanatory_note",
]


@dataclass(frozen=True)
class ValidationSpec:
    """Validation settings for one output table."""

    name: str
    key_columns: list[str]
    non_negative_columns: list[str]
    rate_columns: list[str]
    bounded_columns: list[str]


VALIDATION_SPECS = {
    "tableau_market_quarter": ValidationSpec(
        name="tableau_market_quarter",
        key_columns=["quarter", "geography_type", "geography_code"],
        non_negative_columns=[
            "population_count",
            "participant_count",
            "funded_plan_count",
            "payment_amount",
            "active_provider_count",
            "registered_provider_count",
        ],
        rate_columns=["funded_plans_per_1000", "participants_per_1000", "payments_per_1000_population"],
        bounded_columns=["mean_plan_utilisation", "funding_conversion_rate"],
    ),
    "tableau_support_type_quarter": ValidationSpec(
        name="tableau_support_type_quarter",
        key_columns=["quarter", "geography_type", "geography_code", "support_type"],
        non_negative_columns=["payments", "funded_plan_count", "population_count"],
        rate_columns=["payments_per_1000_population"],
        bounded_columns=["local_support_share", "national_support_share"],
    ),
    "tableau_participant_profile": ValidationSpec(
        name="tableau_participant_profile",
        key_columns=["quarter", "geography_type", "geography_code", "profile_dimension", "profile_category"],
        non_negative_columns=["count"],
        rate_columns=[],
        bounded_columns=["proportion"],
    ),
    "tableau_community_context": ValidationSpec(
        name="tableau_community_context",
        key_columns=["geography_type", "geography_code", "reference_year"],
        non_negative_columns=["population_count"],
        rate_columns=[],
        bounded_columns=[],
    ),
    "tableau_market_classification": ValidationSpec(
        name="tableau_market_classification",
        key_columns=["quarter", "geography_type", "geography_code"],
        non_negative_columns=["consecutive_quarters_below_national_benchmark", "consecutive_quarters_below_remoteness_benchmark"],
        rate_columns=[],
        bounded_columns=["demand_score", "purchasing_score", "capacity_score", "performance_score"],
    ),
    "tableau_geography_lookup": ValidationSpec(
        name="tableau_geography_lookup",
        key_columns=["geography_type", "geography_code"],
        non_negative_columns=["area_sqkm", "population"],
        rate_columns=[],
        bounded_columns=[],
    ),
}


def validate_outputs(outputs: dict[str, pd.DataFrame], extra_rows: list[dict] | None = None) -> pd.DataFrame:
    """Validate Tableau outputs and return data-quality rows."""

    rows: list[dict] = []
    for name, frame in outputs.items():
        spec = VALIDATION_SPECS.get(name)
        if spec is None:
            continue
        rows.extend(_validate_schema(frame, spec))
        rows.extend(_validate_duplicate_keys(frame, spec))
        rows.extend(_validate_quarters(frame, spec))
        rows.extend(_validate_missing_geographies(frame, spec))
        rows.extend(_validate_non_negative(frame, spec))
        rows.extend(_validate_bounded(frame, spec))
        rows.extend(_validate_zero_denominators(frame, spec))

    if "tableau_support_type_quarter" in outputs:
        rows.extend(_validate_support_type_reconciliation(outputs["tableau_support_type_quarter"]))

    if extra_rows:
        rows.extend(extra_rows)

    quality = pd.DataFrame(rows)
    if quality.empty:
        return pd.DataFrame(columns=QUALITY_COLUMNS)
    for col in QUALITY_COLUMNS:
        if col not in quality.columns:
            quality[col] = pd.NA
    return quality[QUALITY_COLUMNS]


def raise_for_critical_failures(quality: pd.DataFrame) -> None:
    """Raise an exception if any critical validation failure exists."""

    if quality.empty:
        return
    critical = quality[
        (quality["issue_severity"].isin(["critical", "fail"]))
        & (~quality["issue_type"].isin(["missingness"]))
    ]
    if not critical.empty:
        summary = critical[["dataset", "field", "issue_type", "explanatory_note"]].head(10).to_dict("records")
        raise ValueError(f"Critical validation failures: {summary}")


def _row(dataset: str, field: str, issue_type: str, severity: str, note: str, **kwargs) -> dict:
    row = {
        "dataset": dataset,
        "period": kwargs.pop("period", ""),
        "geography": kwargs.pop("geography", ""),
        "field": field,
        "issue_type": issue_type,
        "issue_severity": severity,
        "missingness": kwargs.pop("missingness", pd.NA),
        "suppression": kwargs.pop("suppression", ""),
        "mapping_status": kwargs.pop("mapping_status", ""),
        "reliability_flag": kwargs.pop("reliability_flag", ""),
        "explanatory_note": note,
    }
    row.update(kwargs)
    return row


def _validate_schema(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    missing = [col for col in spec.key_columns if col not in frame.columns]
    severity = "critical" if missing else "info"
    note = f"Missing key columns: {', '.join(missing)}" if missing else "Required key columns are present."
    return [_row(spec.name, ",".join(spec.key_columns), "schema", severity, note)]


def _validate_duplicate_keys(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    if frame.empty or any(col not in frame.columns for col in spec.key_columns):
        return []
    duplicates = int(frame.duplicated(spec.key_columns).sum())
    severity = "critical" if duplicates else "info"
    return [
        _row(
            spec.name,
            ",".join(spec.key_columns),
            "duplicate_keys",
            severity,
            f"{duplicates} duplicate key rows found.",
        )
    ]


def _validate_quarters(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    if "quarter" not in frame.columns or frame.empty:
        return []
    invalid = int((~frame["quarter"].astype(str).str.fullmatch(r"\d{4}Q[1-4]")).sum())
    severity = "critical" if invalid else "info"
    return [_row(spec.name, "quarter", "invalid_quarter", severity, f"{invalid} invalid quarter values found.")]


def _validate_missing_geographies(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    if "geography_code" not in frame.columns:
        return []
    missing = int(frame["geography_code"].isna().sum() + frame["geography_code"].astype(str).isin(["", "nan", "None", "<NA>"]).sum())
    severity = "critical" if missing else "info"
    return [_row(spec.name, "geography_code", "missing_geographic_code", severity, f"{missing} rows have missing geography codes.")]


def _validate_non_negative(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    rows: list[dict] = []
    for col in spec.non_negative_columns:
        if col not in frame.columns:
            continue
        values = numeric(frame[col])
        negatives = int((values < 0).sum())
        severity = "critical" if negatives else "info"
        rows.append(_row(spec.name, col, "negative_value", severity, f"{negatives} negative values found."))
    return rows


def _validate_bounded(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    rows: list[dict] = []
    for col in spec.bounded_columns:
        if col not in frame.columns:
            continue
        values = numeric(frame[col])
        if col in {"mean_plan_utilisation", "funding_conversion_rate"}:
            bad = int(((values < 0) | (values > 1.5)).sum())
            severity = "critical" if bad else "info"
            rows.append(_row(spec.name, col, "rate_outside_expected_bounds", severity, f"{bad} values outside [0, 1.5]."))
        else:
            bad = int(((values < 0) | (values > 1)).sum())
            severity = "critical" if bad else "info"
            rows.append(_row(spec.name, col, "share_outside_bounds", severity, f"{bad} values outside [0, 1]."))
    return rows


def _validate_zero_denominators(frame: pd.DataFrame, spec: ValidationSpec) -> list[dict]:
    rows: list[dict] = []
    if "population_count" in frame.columns:
        zero_pop = int((numeric(frame["population_count"]) == 0).sum())
        rows.append(_row(spec.name, "population_count", "zero_denominator", "critical" if zero_pop else "info", f"{zero_pop} zero population denominators found."))
    if "funded_plan_count" in frame.columns:
        zero_plans = int((numeric(frame["funded_plan_count"]) == 0).sum())
        rows.append(_row(spec.name, "funded_plan_count", "zero_denominator", "warning" if zero_plans else "info", f"{zero_plans} zero funded-plan denominators found."))
    return rows


def _validate_support_type_reconciliation(frame: pd.DataFrame) -> list[dict]:
    if frame.empty:
        return []
    required = {"quarter", "geography_code", "payments", "area_total_payments"}
    if not required.issubset(frame.columns):
        return [_row("tableau_support_type_quarter", "payments", "payment_reconciliation", "warning", "Required columns missing for support-type payment reconciliation.")]

    support_totals = frame.groupby(["quarter", "geography_code"], dropna=False)["payments"].sum(min_count=1)
    area_totals = frame.drop_duplicates(["quarter", "geography_code"]).set_index(["quarter", "geography_code"])["area_total_payments"]
    comparison = pd.concat([support_totals.rename("support_total"), area_totals.rename("area_total")], axis=1)
    comparison["relative_delta"] = (comparison["support_total"] - comparison["area_total"]).abs() / comparison["area_total"].replace({0: pd.NA})
    bad = int((comparison["relative_delta"] > 0.02).sum())
    severity = "warning" if bad else "info"
    return [
        _row(
            "tableau_support_type_quarter",
            "payments",
            "payment_reconciliation",
            severity,
            f"{bad} service-area-quarter groups have support-type payments more than 2 pct from area total.",
        )
    ]
