from __future__ import annotations

"""Presentation and interpretation helpers for the Streamlit atlas.

The functions in this module are deliberately free of Streamlit calls. They
provide reusable formatting, sign-convention interpretation and Altair theme
configuration so the dashboard file can stay focused on page composition.
"""

import math
from typing import Any

import altair as alt
import pandas as pd


GM_NAVY = "#061A2E"
GM_AMBER = "#F2B705"
GM_SKY = "#2F6F9F"
GM_GREEN = "#2E7D32"
GM_RED = "#B3261E"
GM_SOFT = "#FFF7E6"


def safe_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except Exception:
        return None


def fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    value = safe_float(value)
    if value is None:
        return "n/a"
    return f"{value:,.{digits}f}{suffix}"


def fmt_pct(value: Any, digits: int = 1) -> str:
    return fmt(value, digits=digits, suffix="%")


def metric_axis_title(
    metric: str,
    metric_info: dict[str, dict[str, str]],
    plan_gap_col: str,
    util_gap_col: str,
) -> str:
    if metric in {plan_gap_col, "plans_per_1000_change_from_baseline"}:
        return f"{metric_info[metric]['label']} (plans per 1,000 population)"
    if metric in {util_gap_col, "mean_plan_utilisation_change_from_baseline"}:
        return f"{metric_info[metric]['label']} (percentage points)"
    return metric_info.get(metric, {}).get("label", metric)


def selected_metric_interpretation(metric: str, value: Any, plan_gap_col: str, util_gap_col: str) -> str:
    value = safe_float(value)
    if value is None:
        return "Insufficient data"
    if abs(value) < 0.005:
        return "Near benchmark" if "gap" in metric else "No material change"
    if metric == plan_gap_col:
        return "Above selected benchmark" if value > 0 else "Below selected benchmark"
    if metric == util_gap_col:
        return "Below selected benchmark" if value > 0 else "Above selected benchmark"
    return "Increase since reference" if value > 0 else "Decrease since reference"

def benchmark_context_label(basis: str, benchmark_quarter: str) -> str:
    if basis == "Selected historical quarter":
        return f"historical {benchmark_quarter} benchmark"
    if basis == "Remoteness category mean":
        return "remoteness-category benchmark"
    if basis == "Service-area disability estimate (0.214)":
        return "service-area disability estimate benchmark"
    return "national mean benchmark"


def category_context_label(selected_categories: list[str], exclude_selected: bool) -> str:
    if not selected_categories:
        return "all service categories"
    if exclude_selected:
        return "all except " + ", ".join(selected_categories)
    return ", ".join(selected_categories)


def remoteness_context_label(remoteness: list[str], remoteness_order: list[str]) -> str:
    if not remoteness:
        return "no remoteness categories selected"
    if set(remoteness) == set(remoteness_order) or len(remoteness) >= 5:
        return "all remoteness categories"
    return ", ".join(remoteness)


def gm_chart(chart: alt.Chart | alt.LayerChart) -> alt.Chart | alt.LayerChart:
    return (
        chart
        .configure_axis(
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
            gridColor="#E8EDF2",
            domainColor="#B8C2CC",
            tickColor="#B8C2CC",
            labelFontSize=11,
            titleFontSize=12,
        )
        .configure_title(
            color=GM_NAVY,
            fontSize=15,
            fontWeight="bold",
            anchor="start",
            offset=12,
        )
        .configure_legend(
            labelColor=GM_NAVY,
            titleColor=GM_NAVY,
            orient="top",
            direction="horizontal",
        )
        .configure_view(strokeWidth=0)
    )
