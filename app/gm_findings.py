from __future__ import annotations

import html
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from gm_config import METRIC_INFO


PLAN_COL = "service_area_funded_plans_per_1000_population_2025_erp"
UTIL_COL = "service_area_mean_plan_utilisation"
PLAN_GAP_COL = "funded_plans_per_1000_gap_from_national"
UTIL_GAP_COL = "mean_plan_utilisation_gap_from_national"
PLAN_BENCHMARK_COL = "plans_per_1000_benchmark_value"
UTIL_BENCHMARK_COL = "mean_utilisation_benchmark_value"
PAYMENT_SHARE_COL = "included_service_type_share"


def _num(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        value = float(value)
        if np.isnan(value) or np.isinf(value):
            return None
        return value
    except Exception:
        return None


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    number = _num(value)
    if number is None:
        return "not available"
    return f"{number:,.{digits}f}{suffix}"


def _median(data: pd.DataFrame, col: str) -> float | None:
    if col not in data.columns or data.empty:
        return None
    values = pd.to_numeric(data[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if not values.notna().any():
        return None
    return float(values.median())


def _mean(data: pd.DataFrame, col: str) -> float | None:
    if col not in data.columns or data.empty:
        return None
    values = pd.to_numeric(data[col], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if not values.notna().any():
        return None
    return float(values.mean())


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value))


def _service_type_label(
    filtered: pd.DataFrame,
    selected_service_types: list[str] | None,
    exclude_selected: bool,
) -> str:
    selected_service_types = selected_service_types or []

    if "service_type_filter_label" in filtered.columns and not filtered.empty:
        labels = filtered["service_type_filter_label"].dropna().astype(str).unique().tolist()
        if labels:
            return labels[0] if len(labels) == 1 else "mixed service-type filters"

    if selected_service_types:
        joined = ", ".join(selected_service_types)
        return f"all except {joined}" if exclude_selected else joined

    return "all service types"


def _uses_service_type_proxy(
    filtered: pd.DataFrame,
    selected_service_types: list[str] | None,
    exclude_selected: bool,
) -> bool:
    selected_service_types = selected_service_types or []

    if selected_service_types:
        return True

    if PAYMENT_SHARE_COL in filtered.columns:
        shares = pd.to_numeric(filtered[PAYMENT_SHARE_COL], errors="coerce")
        if shares.notna().any() and not np.isclose(float(shares.median()), 1.0):
            return True

    label = _service_type_label(filtered, selected_service_types, exclude_selected).lower()
    return label not in {"all service types", "all service categories", ""}


def _benchmark_label(filtered: pd.DataFrame) -> str:
    for col in ["benchmark_basis_label", "benchmark_basis_selected"]:
        if col in filtered.columns and not filtered.empty:
            values = filtered[col].dropna().astype(str).unique().tolist()
            if values:
                return values[0] if len(values) == 1 else "mixed benchmark basis"
    return "selected benchmark"


def _benchmark_quarter(filtered: pd.DataFrame, quarter: str) -> str:
    if "benchmark_reference_quarter" in filtered.columns and not filtered.empty:
        values = filtered["benchmark_reference_quarter"].dropna().astype(str).unique().tolist()
        if values:
            return values[0] if len(values) == 1 else "multiple quarters"
    return str(quarter)


def _remoteness_label(selected_remoteness: list[str] | None) -> str:
    selected_remoteness = selected_remoteness or []
    if not selected_remoteness:
        return "all remoteness categories"
    if len(selected_remoteness) >= 5:
        return "all remoteness categories"
    return ", ".join(selected_remoteness)


def _metric_label(metric: str) -> str:
    return METRIC_INFO.get(metric, {}).get("short", metric)


def _metric_definition(metric: str) -> str:
    return METRIC_INFO.get(metric, {}).get("definition", "")


def _direction_from_gap(value: Any, benchmark_label: str) -> str:
    number = _num(value)
    if number is None:
        return "cannot be interpreted because the benchmark gap is not available"
    if number > 0:
        return f"below the {benchmark_label}"
    if number < 0:
        return f"above the {benchmark_label}"
    return f"at the {benchmark_label}"


def _pattern(plan_gap: Any, util_gap: Any, benchmark_label: str) -> tuple[str, str]:
    plan = _num(plan_gap)
    util = _num(util_gap)

    if plan is None or util is None:
        return (
            "Insufficient benchmark data",
            "The current filter set does not contain enough benchmark data to classify the position reliably.",
        )

    plan_below = plan > 0
    util_below = util > 0

    if plan_below and util_below:
        return (
            "Lower coverage and lower utilisation",
            f"The filtered result is below the {benchmark_label} on both plan coverage and utilisation. This points to an access and implementation question.",
        )

    if plan_below and not util_below:
        return (
            "Lower coverage with stronger utilisation",
            f"The filtered result is below the {benchmark_label} on plan coverage but near or above benchmark on utilisation. This points to an access, eligibility, referral or entry-to-Scheme question.",
        )

    if not plan_below and util_below:
        return (
            "Higher coverage with lower utilisation",
            f"The filtered result is above the {benchmark_label} on plan coverage but below benchmark on utilisation. This points to a plan implementation, provider availability, workforce or service-fit question.",
        )

    return (
        "Higher coverage and stronger utilisation",
        f"The filtered result is above the {benchmark_label} on both plan coverage and utilisation. This indicates high observed Scheme engagement relative to the selected benchmark.",
    )


def _calculation_text(uses_proxy: bool, benchmark_label: str) -> str:
    if uses_proxy:
        plan_calc = (
            "For selected service categories, the plan benchmark is a payment-share-weighted proxy: "
            "whole-area funded plans per 1,000 population multiplied by the selected service category payment share."
        )
    else:
        plan_calc = (
            "Plan coverage is calculated as funded plans divided by 2025 estimated resident population, multiplied by 1,000."
        )

    return (
        f"{plan_calc} Benchmark gaps are calculated as benchmark value minus observed value. "
        f"Positive values mean below the {benchmark_label}; negative values mean above it."
    )


def _metric_interpretation(metric: str, uses_proxy: bool) -> str:
    if metric == PLAN_GAP_COL:
        if uses_proxy:
            return (
                "The selected metric is a service-type proxy plan-coverage gap. It is not the percentage of plans with that support type and it is not a unique participant count."
            )
        return (
            "The selected metric shows whether plan coverage per 1,000 population is above or below the selected benchmark."
        )

    if metric == UTIL_GAP_COL:
        return (
            "The selected metric shows whether mean plan utilisation is above or below the selected benchmark. In service-type filtered views, utilisation remains a whole-area context measure."
        )

    if metric == "plans_per_1000_change_from_baseline":
        if uses_proxy:
            return (
                "The selected metric shows change in the service-type proxy plan-coverage rate since the selected baseline quarter."
            )
        return (
            "The selected metric shows change in funded plans per 1,000 population since the selected baseline quarter."
        )

    if metric == "mean_plan_utilisation_change_from_baseline":
        return (
            "The selected metric shows change in mean plan utilisation since the selected baseline quarter."
        )

    return _metric_definition(metric)


def _method_caveat(uses_proxy: bool) -> str:
    if uses_proxy:
        return (
            "Service-type findings are payment-share-based proxy findings. They should be described as funding intensity or proxy funded-plan equivalents, not as the proportion of plans with the selected support category."
        )

    return (
        "Whole-area findings describe public administrative data patterns. They should be interpreted with local context, workforce insight, service user voice and knowledge of commissioning conditions."
    )


def _render_card(title: str, lines: list[tuple[str, str]]) -> None:
    """Render a compact key finding with progressive disclosure."""
    values = {label: value for label, value in lines}

    with st.container():
        st.markdown(f"### {title}")

        if values.get("Finding"):
            st.info(values["Finding"])

        c1, c2, c3 = st.columns([1, 1, 1.2])

        with c1:
            st.markdown("**Metric**")
            st.write(values.get("Metric", "not available"))

        with c2:
            st.markdown("**Benchmark**")
            st.write(values.get("Benchmark", "not available"))

        with c3:
            st.markdown("**Filter scope**")
            st.write(values.get("Filter scope", "not available"))

        if values.get("Observed values"):
            st.markdown("**Observed values**")
            st.write(values["Observed values"])

        with st.expander("Calculation, interpretation and method caveat", expanded=False):
            for label in ["Calculation", "Interpretation", "Implication", "Method caveat"]:
                if values.get(label):
                    st.markdown(f"**{label}**")
                    st.write(values[label])

        st.caption(
            "Generated from active filters, selected metric, benchmark basis and published data. "
            "This is a structured interpretation aid, not a causal finding."
        )

def render_key_finding(
    filtered: pd.DataFrame,
    metric: str,
    quarter: str,
    selected_remoteness: list[str] | None = None,
    selected_service_types: list[str] | None = None,
    exclude_selected: bool = False,
    scope: str = "national",
    service_area_label: str | None = None,
) -> None:
    """Render a deterministic key finding from the active filter state."""
    if filtered is None or filtered.empty:
        st.info("No key finding can be generated because the current filter set has no rows.")
        return

    selected_remoteness = selected_remoteness or []
    selected_service_types = selected_service_types or []

    benchmark_label = _benchmark_label(filtered)
    benchmark_quarter = _benchmark_quarter(filtered, str(quarter))
    service_type_label = _service_type_label(filtered, selected_service_types, exclude_selected)
    uses_proxy = _uses_service_type_proxy(filtered, selected_service_types, exclude_selected)

    plan_value = _median(filtered, PLAN_COL)
    util_value = _median(filtered, UTIL_COL)
    plan_benchmark = _median(filtered, PLAN_BENCHMARK_COL)
    util_benchmark = _median(filtered, UTIL_BENCHMARK_COL)
    plan_gap = _median(filtered, PLAN_GAP_COL)
    util_gap = _median(filtered, UTIL_GAP_COL)
    metric_value = _median(filtered, metric)

    pattern_title, pattern_text = _pattern(plan_gap, util_gap, benchmark_label)

    metric_values = pd.to_numeric(filtered.get(metric), errors="coerce") if metric in filtered.columns else pd.Series(dtype=float)
    below_count = int((metric_values > 0).sum()) if not metric_values.empty else 0
    above_count = int((metric_values < 0).sum()) if not metric_values.empty else 0
    valid_count = int(metric_values.notna().sum()) if not metric_values.empty else 0

    if scope == "service_area" and service_area_label:
        title = f"Key finding: {service_area_label}"
        finding = (
            f"In {quarter}, {service_area_label} is {_direction_from_gap(plan_gap, benchmark_label)} on plan coverage "
            f"and {_direction_from_gap(util_gap, benchmark_label)} on mean utilisation."
        )
        spread = (
            f"Observed plan value: {_fmt(plan_value)} per 1,000. "
            f"Plan benchmark: {_fmt(plan_benchmark)}. "
            f"Plan gap: {_fmt(plan_gap)}. "
            f"Observed utilisation: {_fmt(util_value)}%. "
            f"Utilisation benchmark: {_fmt(util_benchmark)}%. "
            f"Utilisation gap: {_fmt(util_gap)}."
        )
    else:
        title = "Key finding for current filters"
        finding = (
            f"In {quarter}, the current filter set has {below_count:,} of {valid_count:,} service areas below the selected metric benchmark "
            f"and {above_count:,} above it. The median selected metric value is {_fmt(metric_value)}."
        )
        spread = (
            f"Median plan value: {_fmt(plan_value)} per 1,000. "
            f"Median plan benchmark: {_fmt(plan_benchmark)}. "
            f"Median plan gap: {_fmt(plan_gap)}. "
            f"Median utilisation: {_fmt(util_value)}%. "
            f"Median utilisation benchmark: {_fmt(util_benchmark)}%. "
            f"Median utilisation gap: {_fmt(util_gap)}."
        )

    if uses_proxy:
        metric_name = "Service-type proxy funded-plan equivalents per 1,000 population"
    else:
        metric_name = _metric_label(metric)

    lines = [
        ("Finding", finding),
        ("Metric", metric_name),
        ("Calculation", _calculation_text(uses_proxy, benchmark_label)),
        ("Benchmark", f"{benchmark_label}; reference quarter: {benchmark_quarter}."),
        ("Filter scope", f"Service categories: {service_type_label}. Remoteness: {_remoteness_label(selected_remoteness)}."),
        ("Observed values", spread),
        ("Interpretation", f"{pattern_title}. {pattern_text} {_metric_interpretation(metric, uses_proxy)}"),
        ("Implication", _implication_text(pattern_title, uses_proxy)),
        ("Method caveat", _method_caveat(uses_proxy)),
    ]

    _render_card(title, lines)


def _implication_text(pattern_title: str, uses_proxy: bool) -> str:
    base = {
        "Lower coverage and lower utilisation": (
            "Use this as a prompt to examine access pathways, referral patterns, local provider availability, workforce constraints and plan implementation conditions."
        ),
        "Lower coverage with stronger utilisation": (
            "Use this as a prompt to examine Scheme access, eligibility pathways, local identification of need and whether people are entering the Scheme at comparable rates."
        ),
        "Higher coverage with lower utilisation": (
            "Use this as a prompt to examine plan implementation, provider mix, support coordination, thin markets and whether funding is translating into usable supports."
        ),
        "Higher coverage and stronger utilisation": (
            "Use this as evidence of comparatively high Scheme engagement, while still checking whether the pattern is equitable across population groups and service types."
        ),
    }.get(
        pattern_title,
        "Use this as a screening result that points to where further interpretation is required.",
    )

    if uses_proxy:
        return base + " Because a service type is selected, the finding should be framed as a funding-pattern and market-intensity signal."

    return base
