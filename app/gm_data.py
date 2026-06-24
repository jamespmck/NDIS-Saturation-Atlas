from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

from gm_config import (
    PROJECT_ROOT,
    DATA_CANDIDATES,
    SERVICE_TYPE_CANDIDATES,
    SERVICE_TYPE_ORDER,
    METRIC_INFO,
    SERVICE_AREA_STATE_FALLBACK,
    MIN_QUARTER_DEFAULT,
)


def find_first_existing(candidates: list[Path]) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


def find_first_by_pattern(patterns: list[str]) -> Path | None:
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(PROJECT_ROOT.rglob(pattern))
    if not matches:
        return None
    return sorted(matches, key=lambda p: (0 if "published" in str(p).lower() else 1, len(str(p)), str(p)))[0]


def quarter_sort_key(value: object) -> tuple[int, int]:
    text = str(value)
    match = re.match(r"^(\d{4})Q([1-4])$", text)
    if not match:
        return (9999, 9)
    return (int(match.group(1)), int(match.group(2)))


# GOOD MEASURE Q2 2024 SCOPE HELPERS START

def is_quarter_in_scope(value: object, minimum: str = MIN_QUARTER_DEFAULT) -> bool:
    return quarter_sort_key(value) >= quarter_sort_key(minimum)

# GOOD MEASURE Q2 2024 SCOPE HELPERS END


def weighted_mean(values: pd.Series, weights: pd.Series):
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")
    mask = values.notna() & weights.notna() & (weights > 0)
    if mask.sum() == 0:
        return pd.NA
    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def add_state_labels(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()

    if "ndis_service_area" not in out.columns:
        return out

    mapped_state = out["ndis_service_area"].astype(str).map(SERVICE_AREA_STATE_FALLBACK)

    if "state_acronym" not in out.columns:
        out["state_acronym"] = mapped_state
    else:
        existing = out["state_acronym"].astype("string")
        existing = existing.replace({
            "": pd.NA,
            "nan": pd.NA,
            "None": pd.NA,
            "UNK": pd.NA,
            "<NA>": pd.NA,
        })
        out["state_acronym"] = existing.fillna(mapped_state)

    out["state_acronym"] = out["state_acronym"].fillna("UNK").astype(str)
    out["service_area_state_label"] = (
        out["ndis_service_area"].astype(str)
        + " ("
        + out["state_acronym"].astype(str)
        + ")"
    )

    return out


def standardise_main_data(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()

    if "quarter" not in data.columns and "reporting_quarter" in data.columns:
        data["quarter"] = data["reporting_quarter"]

    if "ndis_service_area" not in data.columns and "map_key" in data.columns:
        data["ndis_service_area"] = data["map_key"].astype(str)

    if "map_key" not in data.columns and "ndis_service_area" in data.columns:
        data["map_key"] = data["ndis_service_area"].astype(str)

    aliases = {
        "funded_plans_per_1000_population_2025_erp": "service_area_funded_plans_per_1000_population_2025_erp",
        "funded_plans_per_1000": "service_area_funded_plans_per_1000_population_2025_erp",
        "mean_plan_utilisation": "service_area_mean_plan_utilisation",
        "service_area_funded_plans_count": "funded_plans_count",
        "proxy_funded_plans_count": "funded_plans_count",
    }

    for source, target in aliases.items():
        if target not in data.columns and source in data.columns:
            data[target] = data[source]

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
    if missing:
        raise ValueError("Main data missing required columns after standardisation: " + ", ".join(missing))

    # Preserve all columns from the rebuilt published dataset, including benchmark fields.

    for col in [
        "population_2025_erp",
        "funded_plans_count",
        "service_area_funded_plans_per_1000_population_2025_erp",
        "service_area_mean_plan_utilisation",
    ]:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # Keep rebuilt benchmark columns usable as numeric values where present.
    for col in data.columns:
        if (
            col.startswith("benchmark_")
            or col.startswith("baseline_")
            or col.endswith("_gap_from_national")
            or col.endswith("_gap_from_remoteness")
            or col.endswith("_gap_from_disability_estimate")
            or col.endswith("_gap_from_historical_baseline")
            or col.endswith("_change_from_baseline")
            or col in [
                "plans_per_1000_benchmark_value",
                "mean_utilisation_benchmark_value",
                "sdac_national_disability_rate_2022",
                "sdac_national_disability_per_1000_2022",
                "payment_amount_per_funded_plan",
                "service_area_payment_amount",
                "active_provider_count_quarter",
                "active_provider_count_ever",
            ]
        ):
            data[col] = pd.to_numeric(data[col], errors="coerce")

    data["quarter"] = data["quarter"].astype(str)

    # GOOD MEASURE Q2 2024 SCOPE MAIN START
    data = data.loc[data["quarter"].map(is_quarter_in_scope)].copy()
    # GOOD MEASURE Q2 2024 SCOPE MAIN END
    data["map_key"] = data["map_key"].astype(str)
    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    data["remoteness_category"] = data["remoteness_category"].fillna("Unknown").astype(str)

    data = data.loc[~data["ndis_service_area"].isin(["ALL", "Other", "nan", "None"])].copy()
    data = data.dropna(subset=["quarter", "map_key", "ndis_service_area"]).copy()
    data = data.drop_duplicates(["quarter", "map_key"]).copy()

    return add_state_labels(data)


def load_main_data() -> tuple[pd.DataFrame, Path]:
    path = find_first_existing(DATA_CANDIDATES)
    if path is None:
        path = find_first_by_pattern([
            "master_ndis_service_area_quarter_all_available.csv",
            "master_ndis_service_area_quarter_all_available_scoped.csv",
            "master_ndis_service_area_quarter*.csv",
        ])

    if path is None:
        raise FileNotFoundError("No master NDIS service-area CSV found under the project folder.")

    raw = pd.read_csv(path, low_memory=False)
    return standardise_main_data(raw), path


def standardise_service_type_data(raw: pd.DataFrame) -> pd.DataFrame:
    data = raw.copy()

    if "quarter" not in data.columns and "reporting_quarter" in data.columns:
        data["quarter"] = data["reporting_quarter"]

    if "map_key" not in data.columns and "ndis_service_area" in data.columns:
        data["map_key"] = data["ndis_service_area"].astype(str)

    required = ["quarter", "map_key", "ndis_service_area", "service_type", "service_type_payment_share_of_area_total"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError("Service-type data missing required columns: " + ", ".join(missing))

    for col in [
        "service_type_payment_share_of_area_total",
        "service_type_payment_amount",
        "service_type_payment_amount_per_1000_population_2025_erp",
        "service_type_proxy_plans_per_1000_population",
        "service_type_proxy_funded_plans_count",
        "population_2025_erp",
        "funded_plans_count",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    if "service_type_data_status" not in data.columns:
        data["service_type_data_status"] = "observed_or_unknown"

    data["quarter"] = data["quarter"].astype(str)

    # GOOD MEASURE Q2 2024 SCOPE SERVICE TYPE START
    data = data.loc[data["quarter"].map(is_quarter_in_scope)].copy()
    # GOOD MEASURE Q2 2024 SCOPE SERVICE TYPE END
    data["map_key"] = data["map_key"].astype(str)
    data["ndis_service_area"] = data["ndis_service_area"].astype(str)
    data["service_type"] = data["service_type"].astype(str)

    data = data.loc[~data["ndis_service_area"].isin(["ALL", "Other", "nan", "None"])].copy()
    return add_state_labels(data)


def load_service_type_data() -> tuple[pd.DataFrame, Path | None, str | None]:
    path = find_first_existing(SERVICE_TYPE_CANDIDATES)
    if path is None:
        path = find_first_by_pattern([
            "master_ndis_service_area_quarter_service_type_custom.csv",
            "master_ndis_service_area_quarter_service_type_benchmarks.csv",
        ])

    if path is None:
        return pd.DataFrame(), None, "No service-type file found. Service-type filtering is disabled."

    try:
        raw = pd.read_csv(path, low_memory=False)
        return standardise_service_type_data(raw), path, None
    except Exception as exc:
        return pd.DataFrame(), path, f"Service-type data could not be loaded: {exc}"


def service_types_available(service_type_data: pd.DataFrame) -> list[str]:
    if service_type_data.empty or "service_type" not in service_type_data.columns:
        return []
    present = set(service_type_data["service_type"].dropna().astype(str).unique())
    ordered = [item for item in SERVICE_TYPE_ORDER if item in present]
    extra = sorted(present - set(ordered))
    return ordered + extra


def compute_service_type_shares(
    service_type_data: pd.DataFrame,
    selected_service_types: list[str],
    exclude_selected: bool = False,
) -> pd.DataFrame:
    if service_type_data.empty:
        return pd.DataFrame()

    all_types = service_types_available(service_type_data)

    # Empty selection means "All service types" and no payment-share scaling.
    # A non-empty selection, even if it happens to include all currently available
    # service types, should be calculated explicitly so the method is testable and
    # transparent.
    if not selected_service_types:
        return pd.DataFrame()

    if exclude_selected:
        selected = set(selected_service_types)
        included = [item for item in all_types if item not in selected]
        label = "All except: " + ", ".join(selected_service_types)
    else:
        selected = set(selected_service_types)
        included = [item for item in all_types if item in selected]
        label = ", ".join(included) if included else "No selected service types"

    selected_rows = service_type_data.loc[service_type_data["service_type"].isin(included)].copy()

    if selected_rows.empty:
        out = service_type_data[["quarter", "ndis_service_area"]].drop_duplicates().copy()
        out["included_service_type_share"] = 0.0
        out["service_type_filter_label"] = label
        return out

    grouped = (
        selected_rows.groupby(["quarter", "ndis_service_area"], dropna=False)
        .agg(included_service_type_share=("service_type_payment_share_of_area_total", "sum"))
        .reset_index()
    )

    grouped["included_service_type_share"] = pd.to_numeric(grouped["included_service_type_share"], errors="coerce").fillna(0).clip(0, 1)
    grouped["service_type_filter_label"] = label
    grouped["service_types_included_count"] = len(included)
    return grouped


def add_national_benchmarks(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()

    national_plans = (
        out.groupby("quarter", dropna=False)
        .agg(
            national_proxy_funded_plans=("funded_plans_count", "sum"),
            national_population=("population_2025_erp", "sum"),
        )
        .reset_index()
    )

    national_plans["national_funded_plans_per_1000_population_2025_erp"] = (
        national_plans["national_proxy_funded_plans"]
        / national_plans["national_population"].replace({0: pd.NA})
        * 1000
    )

    national_util = (
        out.groupby("quarter", dropna=False)
        .apply(lambda g: weighted_mean(g["service_area_mean_plan_utilisation"], g["funded_plans_count"]))
        .rename("national_mean_plan_utilisation")
        .reset_index()
    )

    out = out.merge(
        national_plans[["quarter", "national_funded_plans_per_1000_population_2025_erp"]],
        on="quarter",
        how="left",
    )
    out = out.merge(national_util, on="quarter", how="left")

    out["funded_plans_per_1000_gap_from_national"] = (
        out["national_funded_plans_per_1000_population_2025_erp"]
        - out["service_area_funded_plans_per_1000_population_2025_erp"]
    )
    out["mean_plan_utilisation_gap_from_national"] = (
        out["national_mean_plan_utilisation"]
        - out["service_area_mean_plan_utilisation"]
    )

    return out


def apply_service_type_proxy(raw_data: pd.DataFrame, service_type_shares: pd.DataFrame) -> pd.DataFrame:
    data = raw_data.copy()

    data["funded_plans_count_raw"] = pd.to_numeric(data["funded_plans_count"], errors="coerce")
    data["plans_per_1000_raw"] = pd.to_numeric(data["service_area_funded_plans_per_1000_population_2025_erp"], errors="coerce")
    data["mean_plan_utilisation_raw"] = pd.to_numeric(data["service_area_mean_plan_utilisation"], errors="coerce")

    if service_type_shares.empty:
        data["included_service_type_share"] = 1.0
        data["service_type_filter_label"] = "All service types"
    else:
        data = data.merge(service_type_shares, on=["quarter", "ndis_service_area"], how="left")
        data["included_service_type_share"] = pd.to_numeric(data["included_service_type_share"], errors="coerce").fillna(0).clip(0, 1)
        data["service_type_filter_label"] = data["service_type_filter_label"].fillna("No selected service types")

    data["funded_plans_count"] = data["funded_plans_count_raw"] * data["included_service_type_share"]
    data["service_area_funded_plans_per_1000_population_2025_erp"] = data["plans_per_1000_raw"] * data["included_service_type_share"]

    data["service_area_mean_plan_utilisation"] = data["mean_plan_utilisation_raw"]

    data["statistical_method_note"] = (
        "Service-type filtering is a payment-share proxy. Funded-plan count and funded plans per 1,000 are scaled by selected service-type payment share. Mean utilisation is retained as a whole-area context measure and is not scaled."
    )

    return add_national_benchmarks(data)


def add_change_measures(data: pd.DataFrame, baseline_quarter: str) -> pd.DataFrame:
    """Add baseline change measures without colliding with rebuilt baseline columns.

    The rebuilt published dataset already includes baseline_* columns. When those
    columns are present, merging another baseline frame can create pandas suffixes
    such as baseline_mean_plan_utilisation_x/y. This function drops prior baseline
    columns and recalculates them cleanly from the selected baseline quarter.
    """
    out = data.copy()

    if "quarter" not in out.columns:
        raise ValueError("Cannot calculate baseline change measures because quarter is missing.")

    if "map_key" not in out.columns and "ndis_service_area" in out.columns:
        out["map_key"] = out["ndis_service_area"].astype(str)

    if "map_key" not in out.columns:
        raise ValueError("Cannot calculate baseline change measures because map_key is missing.")

    aliases = {
        "funded_plans_per_1000_population_2025_erp": "service_area_funded_plans_per_1000_population_2025_erp",
        "funded_plans_per_1000": "service_area_funded_plans_per_1000_population_2025_erp",
        "mean_plan_utilisation": "service_area_mean_plan_utilisation",
    }

    for source, target in aliases.items():
        if target not in out.columns and source in out.columns:
            out[target] = out[source]

    required = [
        "service_area_funded_plans_per_1000_population_2025_erp",
        "service_area_mean_plan_utilisation",
    ]

    missing = [col for col in required if col not in out.columns]
    if missing:
        raise ValueError(
            "Cannot calculate baseline change measures because required column(s) are missing: "
            + ", ".join(missing)
        )

    # Remove existing baseline/change columns from the rebuilt master before
    # recalculating from the current filtered analysis frame.
    drop_cols = [
        col for col in out.columns
        if col.startswith("baseline_")
        or col.endswith("_change_from_baseline")
        or re.match(r"baseline_.*_[xy]$", col)
    ]

    if drop_cols:
        out = out.drop(columns=drop_cols, errors="ignore")

    out["quarter"] = out["quarter"].astype(str)
    out["map_key"] = out["map_key"].astype(str)

    baseline_rows = out.loc[
        out["quarter"].astype(str) == str(baseline_quarter),
        [
            "map_key",
            "service_area_funded_plans_per_1000_population_2025_erp",
            "service_area_mean_plan_utilisation",
        ],
    ].copy()

    if baseline_rows.empty:
        out["baseline_plans_per_1000"] = pd.NA
        out["baseline_mean_plan_utilisation"] = pd.NA
    else:
        baseline_rows = (
            baseline_rows
            .drop_duplicates("map_key")
            .rename(
                columns={
                    "service_area_funded_plans_per_1000_population_2025_erp": "baseline_plans_per_1000",
                    "service_area_mean_plan_utilisation": "baseline_mean_plan_utilisation",
                }
            )
        )

        baseline_rows["baseline_plans_per_1000"] = pd.to_numeric(
            baseline_rows["baseline_plans_per_1000"],
            errors="coerce",
        )
        baseline_rows["baseline_mean_plan_utilisation"] = pd.to_numeric(
            baseline_rows["baseline_mean_plan_utilisation"],
            errors="coerce",
        )

        out = out.merge(baseline_rows, on="map_key", how="left", validate="many_to_one")

    out["service_area_funded_plans_per_1000_population_2025_erp"] = pd.to_numeric(
        out["service_area_funded_plans_per_1000_population_2025_erp"],
        errors="coerce",
    )
    out["service_area_mean_plan_utilisation"] = pd.to_numeric(
        out["service_area_mean_plan_utilisation"],
        errors="coerce",
    )

    out["plans_per_1000_change_from_baseline"] = (
        out["service_area_funded_plans_per_1000_population_2025_erp"]
        - out["baseline_plans_per_1000"]
    )

    out["mean_plan_utilisation_change_from_baseline"] = (
        out["service_area_mean_plan_utilisation"]
        - out["baseline_mean_plan_utilisation"]
    )

    out["baseline_quarter"] = str(baseline_quarter)

    return out

def classify_position(value: object, metric: str) -> str:
    val = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(val):
        return "No data"

    info = METRIC_INFO.get(metric, {})
    if val > 0:
        return info.get("positive", "Positive value")
    if val < 0:
        return info.get("negative", "Negative value")
    return "Near benchmark or no change"


def add_market_typology(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    coverage_gap = pd.to_numeric(out["funded_plans_per_1000_gap_from_national"], errors="coerce")
    utilisation_gap = pd.to_numeric(out["mean_plan_utilisation_gap_from_national"], errors="coerce")

    labels = []
    for cov_gap, util_gap in zip(coverage_gap, utilisation_gap):
        if pd.isna(cov_gap) or pd.isna(util_gap):
            labels.append("No data")
        elif cov_gap > 0 and util_gap > 0:
            labels.append("Lower coverage / lower utilisation")
        elif cov_gap > 0 and util_gap <= 0:
            labels.append("Lower coverage / higher utilisation")
        elif cov_gap <= 0 and util_gap > 0:
            labels.append("Higher coverage / lower utilisation")
        else:
            labels.append("Higher coverage / higher utilisation")

    out["market_position_typology"] = labels
    return out


def prepare_analysis_data(
    raw_data: pd.DataFrame,
    service_type_data: pd.DataFrame,
    selected_service_types: list[str],
    exclude_selected: bool,
    baseline_quarter: str,
) -> pd.DataFrame:
    shares = compute_service_type_shares(service_type_data, selected_service_types, exclude_selected)
    data = apply_service_type_proxy(raw_data, shares)
    data = add_change_measures(data, baseline_quarter)
    data = add_market_typology(data)
    return data


def filter_current(data: pd.DataFrame, quarter: str, selected_remoteness: list[str], metric: str) -> pd.DataFrame:
    out = data.loc[data["quarter"].astype(str) == str(quarter)].copy()

    if selected_remoteness:
        out = out.loc[out["remoteness_category"].isin(selected_remoteness)].copy()

    out["benchmark_position"] = out[metric].apply(lambda value: classify_position(value, metric))
    out["_map_score"] = pd.to_numeric(out[metric], errors="coerce")

    if METRIC_INFO.get(metric, {}).get("map_score") == "invert":
        out["_map_score"] = -out["_map_score"]

    return out


def format_data_for_display(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    text_cols = {
        "ndis_service_area", "map_key", "quarter", "baseline_quarter", "remoteness_category",
        "state_acronym", "service_area_state_label", "service_type_filter_label",
        "benchmark_position", "market_position_typology", "statistical_method_note",
    }

    for col in out.columns:
        if col in text_cols:
            continue
        converted = pd.to_numeric(out[col], errors="coerce")
        if converted.notna().any():
            out[col] = converted.round(3 if "share" in col else 2)
    return out
