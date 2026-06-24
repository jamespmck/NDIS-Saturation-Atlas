from __future__ import annotations

import numpy as np
import pandas as pd


PLAN_COL = "service_area_funded_plans_per_1000_population_2025_erp"
UTIL_COL = "service_area_mean_plan_utilisation"
PLAN_COUNT_COL = "funded_plans_count"
POP_COL = "population_2025_erp"

PLAN_GAP_METRIC = "funded_plans_per_1000_gap_from_national"
UTIL_GAP_METRIC = "mean_plan_utilisation_gap_from_national"

PLAN_BENCHMARK_COL = "plans_per_1000_benchmark_value"
UTIL_BENCHMARK_COL = "mean_utilisation_benchmark_value"

DISABILITY_ESTIMATE = 0.214
DISABILITY_ESTIMATE_PER_1000 = DISABILITY_ESTIMATE * 1000

BENCHMARK_NATIONAL = "National mean"
BENCHMARK_REMOTENESS = "Remoteness category mean"
BENCHMARK_HISTORICAL = "Selected historical quarter"
BENCHMARK_DISABILITY = "Service-area disability estimate (0.214)"

BENCHMARK_BASIS_OPTIONS = [
    BENCHMARK_NATIONAL,
    BENCHMARK_REMOTENESS,
    BENCHMARK_HISTORICAL,
    BENCHMARK_DISABILITY,
]


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _weighted_mean(values: pd.Series, weights: pd.Series | None = None) -> float:
    values = _numeric(values)

    if weights is None:
        return float(values.mean()) if values.notna().any() else np.nan

    weights = _numeric(weights)
    valid = values.notna() & weights.notna() & (weights > 0)

    if not valid.any():
        return float(values.mean()) if values.notna().any() else np.nan

    return float(np.average(values.loc[valid], weights=weights.loc[valid]))


def _plan_rate_from_counts(group: pd.DataFrame) -> float:
    plans = _numeric(group[PLAN_COUNT_COL]).sum() if PLAN_COUNT_COL in group.columns else np.nan
    pop = _numeric(group[POP_COL]).sum() if POP_COL in group.columns else np.nan

    if pd.notna(plans) and pd.notna(pop) and pop > 0:
        return float((plans / pop) * 1000)

    weights = group[POP_COL] if POP_COL in group.columns else None
    return _weighted_mean(group[PLAN_COL], weights)


def _utilisation_weighted(group: pd.DataFrame) -> float:
    weights = group[PLAN_COUNT_COL] if PLAN_COUNT_COL in group.columns else None
    return _weighted_mean(group[UTIL_COL], weights)


def _reference_by_group(data: pd.DataFrame, group_cols: list[str], basis_label: str) -> pd.DataFrame:
    rows = []

    for key, group in data.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)

        row = {col: value for col, value in zip(group_cols, key)}
        row[PLAN_BENCHMARK_COL] = _plan_rate_from_counts(group)
        row[UTIL_BENCHMARK_COL] = _utilisation_weighted(group)
        rows.append(row)

    reference = pd.DataFrame(rows)

    out = data.merge(reference, on=group_cols, how="left")
    out["benchmark_basis_label"] = basis_label
    out["benchmark_reference_quarter"] = out["quarter"].astype(str)
    return out


def _reference_from_historical_quarter(data: pd.DataFrame, historical_quarter: str | None) -> pd.DataFrame:
    out = data.copy()

    if historical_quarter is None:
        quarters = out["quarter"].dropna().astype(str).unique().tolist()
        historical_quarter = quarters[0] if quarters else None

    quarter_text = str(historical_quarter)

    reference = out.loc[out["quarter"].astype(str) == quarter_text, ["map_key", PLAN_COL, UTIL_COL]].copy()

    if reference.empty:
        out[PLAN_BENCHMARK_COL] = np.nan
        out[UTIL_BENCHMARK_COL] = np.nan
    else:
        reference = (
            reference
            .drop_duplicates("map_key")
            .rename(columns={
                PLAN_COL: PLAN_BENCHMARK_COL,
                UTIL_COL: UTIL_BENCHMARK_COL,
            })
        )
        out = out.merge(reference, on="map_key", how="left")

    out["benchmark_basis_label"] = f"historical quarter {quarter_text}"
    out["benchmark_reference_quarter"] = quarter_text
    return out


def _reference_from_disability_estimate(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()

    util_reference = []
    for quarter, group in out.groupby("quarter", dropna=False):
        util_reference.append({
            "quarter": quarter,
            UTIL_BENCHMARK_COL: _utilisation_weighted(group),
        })

    util_reference = pd.DataFrame(util_reference)

    out = out.merge(util_reference, on="quarter", how="left")
    out[PLAN_BENCHMARK_COL] = DISABILITY_ESTIMATE_PER_1000
    out["benchmark_basis_label"] = "service-area disability estimate 0.214"
    out["benchmark_reference_quarter"] = out["quarter"].astype(str)
    return out


def _add_gap_metrics(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()

    out[PLAN_COL] = _numeric(out[PLAN_COL])
    out[UTIL_COL] = _numeric(out[UTIL_COL])
    out[PLAN_BENCHMARK_COL] = _numeric(out[PLAN_BENCHMARK_COL])
    out[UTIL_BENCHMARK_COL] = _numeric(out[UTIL_BENCHMARK_COL])

    # Existing convention retained:
    # positive gap = service area is below benchmark
    # negative gap = service area is above benchmark
    out[PLAN_GAP_METRIC] = out[PLAN_BENCHMARK_COL] - out[PLAN_COL]
    out[UTIL_GAP_METRIC] = out[UTIL_BENCHMARK_COL] - out[UTIL_COL]

    plan_lower = out[PLAN_GAP_METRIC] > 0
    util_lower = out[UTIL_GAP_METRIC] > 0

    out["market_position_typology"] = np.select(
        [
            plan_lower & util_lower,
            plan_lower & ~util_lower,
            ~plan_lower & util_lower,
            ~plan_lower & ~util_lower,
        ],
        [
            "Lower coverage / lower utilisation",
            "Lower coverage / higher utilisation",
            "Higher coverage / lower utilisation",
            "Higher coverage / higher utilisation",
        ],
        default="Insufficient benchmark data",
    )

    return out


def apply_selected_benchmark_basis(
    data: pd.DataFrame,
    benchmark_basis: str,
    historical_quarter: str | None = None,
) -> pd.DataFrame:
    out = data.copy()

    if out.empty:
        return out

    required = ["quarter", "map_key", PLAN_COL, UTIL_COL]
    missing = [col for col in required if col not in out.columns]

    if missing:
        out["benchmark_basis_selected"] = benchmark_basis
        out["benchmark_basis_label"] = "benchmark unavailable"
        out["benchmark_reference_quarter"] = historical_quarter
        return out

    for col in [PLAN_BENCHMARK_COL, UTIL_BENCHMARK_COL]:
        if col in out.columns:
            out = out.drop(columns=[col])

    if benchmark_basis == BENCHMARK_REMOTENESS:
        out = _reference_by_group(
            data=out,
            group_cols=["quarter", "remoteness_category"],
            basis_label="remoteness-category mean",
        )

    elif benchmark_basis == BENCHMARK_HISTORICAL:
        out = _reference_from_historical_quarter(
            data=out,
            historical_quarter=historical_quarter,
        )

    elif benchmark_basis == BENCHMARK_DISABILITY:
        out = _reference_from_disability_estimate(out)

    else:
        out = _reference_by_group(
            data=out,
            group_cols=["quarter"],
            basis_label="national mean",
        )

    out["benchmark_basis_selected"] = benchmark_basis
    return _add_gap_metrics(out)


def update_metric_info_for_benchmark(
    metric_info: dict,
    benchmark_basis_label: str,
    historical_quarter: str | None = None,
) -> None:
    if benchmark_basis_label == BENCHMARK_NATIONAL:
        label = "national mean"
    elif benchmark_basis_label == BENCHMARK_REMOTENESS:
        label = "remoteness-category mean"
    elif benchmark_basis_label == BENCHMARK_HISTORICAL:
        label = f"historical quarter {historical_quarter}"
    elif benchmark_basis_label == BENCHMARK_DISABILITY:
        label = "service-area disability estimate 0.214"
    else:
        label = "selected benchmark"

    if PLAN_GAP_METRIC in metric_info:
        metric_info[PLAN_GAP_METRIC]["label"] = f"Is plan coverage above or below the {label}?"
        metric_info[PLAN_GAP_METRIC]["short"] = f"Plan coverage gap vs {label}"
        metric_info[PLAN_GAP_METRIC]["definition"] = (
            f"Selected benchmark plans per 1,000 population minus service-area funded plans per 1,000 population. "
            f"Benchmark basis: {label}."
        )
        metric_info[PLAN_GAP_METRIC]["positive"] = f"Below {label}"
        metric_info[PLAN_GAP_METRIC]["negative"] = f"Above {label}"

    if UTIL_GAP_METRIC in metric_info:
        metric_info[UTIL_GAP_METRIC]["label"] = f"Is utilisation above or below the {label}?"
        metric_info[UTIL_GAP_METRIC]["short"] = f"Utilisation gap vs {label}"
        metric_info[UTIL_GAP_METRIC]["definition"] = (
            f"Selected benchmark mean plan utilisation minus service-area mean utilisation. Benchmark basis: {label}."
        )
        metric_info[UTIL_GAP_METRIC]["positive"] = f"Below {label}"
        metric_info[UTIL_GAP_METRIC]["negative"] = f"Above {label}"
