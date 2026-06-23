
from __future__ import annotations

from pathlib import Path
from typing import Any
import math
import re
from urllib.parse import unquote_plus

import altair as alt
import pandas as pd
import streamlit as st


PLAN_COL = "gm_plans_per_1000"
UTIL_COL = "gm_mean_utilisation"
PLAN_GAP_COL = "gm_plan_coverage_gap_from_national"
UTIL_GAP_COL = "gm_utilisation_gap_from_national"
PLAN_CHANGE_COL = "gm_plan_coverage_change_from_baseline"
UTIL_CHANGE_COL = "gm_utilisation_change_from_baseline"

REMOTENESS_ORDER = [
    "Major Cities of Australia",
    "Inner Regional Australia",
    "Outer Regional Australia",
    "Remote Australia",
    "Very Remote Australia",
    "Unknown",
]

METRIC_OPTIONS = {
    "Plan coverage gap from national benchmark": PLAN_GAP_COL,
    "Utilisation gap from national benchmark": UTIL_GAP_COL,
    "Change in plan coverage since baseline": PLAN_CHANGE_COL,
    "Change in utilisation since baseline": UTIL_CHANGE_COL,
}

METRIC_LABELS = {
    PLAN_GAP_COL: "Plan coverage gap from national benchmark",
    UTIL_GAP_COL: "Utilisation gap from national benchmark",
    PLAN_CHANGE_COL: "Change in plan coverage since baseline",
    UTIL_CHANGE_COL: "Change in utilisation since baseline",
}

METRIC_EXPLAINERS = {
    PLAN_GAP_COL: "Positive values mean the service area is below the national plan coverage benchmark. Negative values mean it is above the benchmark.",
    UTIL_GAP_COL: "Positive values mean the service area is below the national utilisation benchmark. Negative values mean it is above the benchmark.",
    PLAN_CHANGE_COL: "Positive values mean plan coverage has increased since the selected baseline quarter.",
    UTIL_CHANGE_COL: "Positive values mean utilisation has increased since the selected baseline quarter.",
}


def _normalise_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _column_map(data: pd.DataFrame) -> dict[str, str]:
    return {_normalise_name(c): c for c in data.columns}


def _find_col(data: pd.DataFrame, candidates: list[str], contains_all: list[str] | None = None) -> str | None:
    cmap = _column_map(data)

    for candidate in candidates:
        key = _normalise_name(candidate)
        if key in cmap:
            return cmap[key]

    if contains_all:
        terms = [_normalise_name(t) for t in contains_all]
        for key, original in cmap.items():
            if all(term in key for term in terms):
                return original

    return None


def _find_area_col(data: pd.DataFrame) -> str | None:
    col = _find_col(
        data,
        [
            "ndis_service_area",
            "service_area",
            "service_area_name",
            "ndis_service_district",
            "ndis_service_district_name",
            "service_district",
            "area_name",
        ],
    )
    if col:
        return col

    object_cols = list(data.select_dtypes(include=["object", "string"]).columns)
    sample_terms = ["Sydney", "Southern NSW", "Central Australia", "Kimberley", "Brisbane", "Western Sydney", "ACT"]

    best_col = None
    best_score = 0

    for candidate in object_cols:
        try:
            values = data[candidate].dropna().astype(str).head(3000)
        except Exception:
            continue

        score = 0
        for term in sample_terms:
            score += int(values.str.contains(term, case=False, regex=False).any())

        if score > best_score:
            best_score = score
            best_col = candidate

    return best_col if best_score > 0 else None


def _safe_number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    except Exception:
        return None


def _fmt(value: Any, digits: int = 2) -> str:
    number = _safe_number(value)
    if number is None:
        return "No data"
    return f"{number:,.{digits}f}"


def _fmt_int(value: Any) -> str:
    number = _safe_number(value)
    if number is None:
        return "No data"
    return f"{number:,.0f}"


def _fmt_pct(value: Any, digits: int = 1) -> str:
    number = _safe_number(value)
    if number is None:
        return "No data"
    return f"{number:.{digits}f}%"


def _area_key(value: Any) -> str:
    text = unquote_plus(str(value or ""))
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace("&", " and ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _match_area(raw_area: str | None, area_list: list[str]) -> str | None:
    if not raw_area:
        return None

    raw_key = _area_key(raw_area)
    if not raw_key:
        return None

    area_by_key = {_area_key(area): area for area in area_list}

    if raw_key in area_by_key:
        return area_by_key[raw_key]

    for key, area in area_by_key.items():
        if raw_key == key:
            return area

    for key, area in area_by_key.items():
        if raw_key in key or key in raw_key:
            return area

    raw_tokens = set(raw_key.split())
    best_area = None
    best_score = 0

    for key, area in area_by_key.items():
        key_tokens = set(key.split())
        score = len(raw_tokens & key_tokens)
        if score > best_score:
            best_score = score
            best_area = area

    return best_area if best_score > 0 else None


def _query_value(*names: str) -> str | None:
    try:
        params = st.query_params
    except Exception:
        return None

    for name in names:
        try:
            value = params.get(name, None)
        except Exception:
            value = None

        if isinstance(value, list):
            value = value[0] if value else None

        if value not in [None, ""]:
            return str(value)

    return None


def _detect_page_context(area_list: list[str]) -> tuple[str, str | None, str | None]:
    page = _query_value("page", "view", "route", "dashboard")
    raw_area = _query_value("area", "service_area", "ndis_service_area", "selected_area", "region", "map_key")

    matched_area = _match_area(raw_area, area_list)

    page_key = _area_key(page)
    is_service_page = "service" in page_key or "area" in page_key or matched_area is not None

    if is_service_page and matched_area:
        return "service_area", matched_area, raw_area

    return "national", None, raw_area


def _position_from_gap(value: Any, tolerance: float = 0.25) -> str:
    number = _safe_number(value)
    if number is None:
        return "No data"
    if number > tolerance:
        return "Below national benchmark"
    if number < -tolerance:
        return "Above national benchmark"
    return "Near national benchmark"


def _change_label(value: Any, tolerance: float = 0.25) -> str:
    number = _safe_number(value)
    if number is None:
        return "No data"
    if number > tolerance:
        return "Increasing"
    if number < -tolerance:
        return "Decreasing"
    return "Stable"


def _read_base_csv(project_root: Path) -> pd.DataFrame:
    path = project_root / "data" / "published" / "master_ndis_service_area_quarter_all_available.csv"
    if not path.exists():
        raise FileNotFoundError(f"Base data not found: {path}")

    raw = pd.read_csv(path, low_memory=False)
    if raw.empty:
        raise ValueError(f"Base data file is empty: {path}")

    quarter_col = _find_col(raw, ["quarter", "reporting_quarter", "year_quarter"], contains_all=["quarter"])
    area_col = _find_area_col(raw)
    remote_col = _find_col(raw, ["remoteness_category", "remoteness", "remoteness_name"], contains_all=["remoteness"])
    population_col = _find_col(
        raw,
        ["population_2025_erp", "erp_2025_population", "population", "estimated_resident_population"],
        contains_all=["population"],
    )
    plans_count_col = _find_col(
        raw,
        [
            "funded_plans_count",
            "service_area_funded_plans_count",
            "funded_plan_count",
            "funded_plans",
            "participant_count",
            "participants",
        ],
    )
    plans_per_1000_col = _find_col(
        raw,
        [
            "service_area_funded_plans_per_1000_population_2025_erp",
            "funded_plans_per_1000_population_2025_erp",
            "funded_plans_per_1000",
            "plans_per_1000",
        ],
        contains_all=["per_1000"],
    )
    util_col = _find_col(
        raw,
        [
            "service_area_mean_plan_utilisation",
            "mean_plan_utilisation",
            "service_area_mean_plan_utilization",
            "mean_plan_utilization",
            "plan_utilisation",
            "plan_utilization",
        ],
        contains_all=["util"],
    )

    missing = []
    for label, col in {
        "quarter": quarter_col,
        "service area": area_col,
        "plans per 1,000": plans_per_1000_col,
        "mean utilisation": util_col,
    }.items():
        if col is None:
            missing.append(label)

    if missing:
        available = ", ".join(map(str, raw.columns.tolist()[:80]))
        raise ValueError(
            "Could not identify required column(s): "
            + ", ".join(missing)
            + ". Available columns include: "
            + available
        )

    out = pd.DataFrame()
    out["quarter"] = raw[quarter_col].astype(str)
    out["ndis_service_area"] = raw[area_col].astype(str)
    out["remoteness_category"] = raw[remote_col].astype(str) if remote_col else "Unknown"
    out["population_2025_erp"] = pd.to_numeric(raw[population_col], errors="coerce") if population_col else pd.NA
    out["funded_plans_count"] = pd.to_numeric(raw[plans_count_col], errors="coerce") if plans_count_col else pd.NA
    out[PLAN_COL] = pd.to_numeric(raw[plans_per_1000_col], errors="coerce")
    out[UTIL_COL] = pd.to_numeric(raw[util_col], errors="coerce")

    out = out.loc[
        out["quarter"].notna()
        & out["ndis_service_area"].notna()
        & ~out["ndis_service_area"].isin(["ALL", "Other", "nan", "None"])
    ].copy()

    out = out.drop_duplicates(["quarter", "ndis_service_area"]).copy()

    if out.empty:
        raise ValueError("Base data loaded but no usable service-area rows remained after cleaning.")

    return out


def _add_benchmarks(data: pd.DataFrame) -> pd.DataFrame:
    data = data.copy()

    if data["population_2025_erp"].notna().any() and data["funded_plans_count"].notna().any():
        national_plan = (
            data.groupby("quarter", dropna=False)
            .apply(
                lambda g: (
                    g["funded_plans_count"].sum() / g["population_2025_erp"].sum() * 1000
                    if g["population_2025_erp"].sum() > 0
                    else pd.NA
                )
            )
            .rename("gm_national_plans_per_1000")
            .reset_index()
        )
    else:
        national_plan = (
            data.groupby("quarter", dropna=False)[PLAN_COL]
            .median()
            .rename("gm_national_plans_per_1000")
            .reset_index()
        )

    def weighted_utilisation(g: pd.DataFrame):
        values = pd.to_numeric(g[UTIL_COL], errors="coerce")
        weights = pd.to_numeric(g["funded_plans_count"], errors="coerce")
        mask = values.notna() & weights.notna() & (weights > 0)
        if mask.sum() > 0:
            return (values[mask] * weights[mask]).sum() / weights[mask].sum()
        return values.median()

    national_util = (
        data.groupby("quarter", dropna=False)
        .apply(weighted_utilisation)
        .rename("gm_national_mean_utilisation")
        .reset_index()
    )

    data = data.merge(national_plan, on="quarter", how="left")
    data = data.merge(national_util, on="quarter", how="left")

    data[PLAN_GAP_COL] = data["gm_national_plans_per_1000"] - data[PLAN_COL]
    data[UTIL_GAP_COL] = data["gm_national_mean_utilisation"] - data[UTIL_COL]

    return data


def _add_change(data: pd.DataFrame, baseline_quarter: str) -> pd.DataFrame:
    baseline = data.loc[data["quarter"] == baseline_quarter, ["ndis_service_area", PLAN_COL, UTIL_COL]].copy()

    if baseline.empty:
        data[PLAN_CHANGE_COL] = pd.NA
        data[UTIL_CHANGE_COL] = pd.NA
        return data

    baseline = baseline.rename(
        columns={
            PLAN_COL: "gm_baseline_plans_per_1000",
            UTIL_COL: "gm_baseline_utilisation",
        }
    )

    data = data.merge(baseline, on="ndis_service_area", how="left")
    data[PLAN_CHANGE_COL] = data[PLAN_COL] - data["gm_baseline_plans_per_1000"]
    data[UTIL_CHANGE_COL] = data[UTIL_COL] - data["gm_baseline_utilisation"]

    return data


def _add_percentiles(current: pd.DataFrame) -> pd.DataFrame:
    current = current.copy()
    current["plan_coverage_percentile_national"] = current[PLAN_COL].rank(pct=True) * 100
    current["utilisation_percentile_national"] = current[UTIL_COL].rank(pct=True) * 100
    current["plan_coverage_percentile_remoteness"] = current.groupby("remoteness_category")[PLAN_COL].rank(pct=True) * 100
    current["utilisation_percentile_remoteness"] = current.groupby("remoteness_category")[UTIL_COL].rank(pct=True) * 100
    return current


def _load_service_type_data(project_root: Path) -> pd.DataFrame | None:
    path = project_root / "data" / "published" / "master_ndis_service_area_quarter_custom_service_type.csv"
    if not path.exists():
        return None

    raw = pd.read_csv(path, low_memory=False)
    if raw.empty:
        return None

    quarter_col = _find_col(raw, ["quarter", "reporting_quarter"], contains_all=["quarter"])
    area_col = _find_area_col(raw)
    service_col = _find_col(raw, ["service_type", "support_category", "support_type"], contains_all=["service"])
    share_col = _find_col(
        raw,
        [
            "service_type_payment_share_of_area_total",
            "payment_share_of_area_total",
            "service_type_share",
            "payment_share",
        ],
        contains_all=["share"],
    )
    amount_col = _find_col(
        raw,
        ["service_type_payment_amount", "payment_amount", "service_payment_amount", "amount"],
        contains_all=["amount"],
    )

    if not all([quarter_col, area_col, service_col, share_col]):
        return None

    out = pd.DataFrame()
    out["quarter"] = raw[quarter_col].astype(str)
    out["ndis_service_area"] = raw[area_col].astype(str)
    out["service_type"] = raw[service_col].astype(str)
    out["service_type_payment_share_of_area_total"] = pd.to_numeric(raw[share_col], errors="coerce")
    out["service_type_payment_amount"] = pd.to_numeric(raw[amount_col], errors="coerce") if amount_col else pd.NA
    out = out.loc[~out["ndis_service_area"].isin(["ALL", "Other", "nan", "None"])].copy()

    return out


def _pattern_label(plan_gap: Any, util_gap: Any) -> tuple[str, str]:
    plan_pos = _position_from_gap(plan_gap)
    util_pos = _position_from_gap(util_gap)

    if plan_pos == "Below national benchmark" and util_pos == "Below national benchmark":
        return (
            "Access and utilisation question",
            "Plan coverage and utilisation are both below the national benchmark. Further interpretation should examine access pathways, local service availability, workforce constraints, plan implementation and community context.",
        )

    if plan_pos == "Below national benchmark" and util_pos != "Below national benchmark":
        return (
            "Coverage/access question",
            "Plan coverage is below the national benchmark while utilisation is near or above benchmark. Further interpretation should focus on access, eligibility patterns, local referral pathways and whether people are entering the Scheme at comparable rates.",
        )

    if plan_pos == "Above national benchmark" and util_pos == "Below national benchmark":
        return (
            "Utilisation question",
            "Plan coverage is above the national benchmark while utilisation is below benchmark. Further interpretation should focus on plan implementation, support coordination, provider availability, workforce constraints and service fit.",
        )

    if plan_pos == "Above national benchmark" and util_pos == "Above national benchmark":
        return (
            "High scheme engagement",
            "Plan coverage and utilisation are both above the national benchmark. This area shows high observed Scheme engagement relative to national patterns.",
        )

    return (
        "Mixed or near-benchmark pattern",
        "The area sits close to benchmark on one or both measures. Further interpretation should consider trend, remoteness, service mix and local context before drawing conclusions.",
    )


def _configure_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_view(strokeOpacity=0)
        .configure_axis(
            labelFontSize=11,
            titleFontSize=12,
            gridOpacity=0.18,
            domainOpacity=0.25,
        )
        .configure_title(
            fontSize=18,
            anchor="start",
            fontWeight=700,
            color="#071B33",
        )
        .configure_legend(
            titleFontSize=12,
            labelFontSize=11,
            orient="bottom",
            columns=3,
        )
    )


def _render_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --gm-navy: #071B33;
            --gm-blue: #1C5D99;
            --gm-amber: #F5A400;
            --gm-cream: #FFF7E8;
            --gm-ink: #1C2E3F;
            --gm-muted: #5F6B76;
            --gm-border: rgba(7, 27, 51, 0.14);
        }

        .gm-workspace {
            border: 1px solid var(--gm-border);
            border-radius: 22px;
            padding: 1.15rem 1.25rem;
            background: linear-gradient(135deg, #ffffff 0%, #fffaf0 100%);
            margin: 1.1rem 0 1rem 0;
            box-shadow: 0 8px 24px rgba(7, 27, 51, 0.06);
        }

        .gm-kicker {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #7A5A00;
            font-size: 0.75rem;
            font-weight: 800;
            margin-bottom: 0.25rem;
        }

        .gm-title {
            color: var(--gm-navy);
            font-size: 1.75rem;
            line-height: 1.18;
            font-weight: 850;
            margin-bottom: 0.35rem;
        }

        .gm-body {
            color: var(--gm-ink);
            max-width: 980px;
            font-size: 0.98rem;
            line-height: 1.52;
        }

        .gm-context-pill {
            display: inline-block;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            background: #E8F1FA;
            color: #174A78;
            font-size: 0.8rem;
            font-weight: 800;
            margin-top: 0.6rem;
        }

        .gm-note {
            border-left: 4px solid var(--gm-amber);
            padding: 0.75rem 0.9rem;
            background: rgba(245, 164, 0, 0.08);
            margin: 0.8rem 0;
            color: var(--gm-ink);
            line-height: 1.45;
        }

        .gm-evidence-card {
            border: 1px solid var(--gm-border);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            background: #ffffff;
            margin: 1rem 0;
            box-shadow: 0 4px 16px rgba(7, 27, 51, 0.045);
        }

        .gm-evidence-title {
            color: var(--gm-navy);
            font-size: 1.25rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .gm-evidence-body {
            color: var(--gm-ink);
            font-size: 0.97rem;
            line-height: 1.55;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.35rem;
            border-bottom: 1px solid rgba(7, 27, 51, 0.16);
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 999px 999px 0 0;
            padding: 0.55rem 0.9rem;
            font-weight: 800;
            color: #20384F;
        }

        .stTabs [aria-selected="true"] {
            background: #071B33;
            color: #ffffff;
        }

        div[data-testid="stMetric"] {
            background: #FFF7E8;
            border-left: 4px solid #F5A400;
            border-radius: 14px;
            padding: 0.8rem 0.85rem;
            box-shadow: 0 3px 12px rgba(7, 27, 51, 0.045);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_warning() -> None:
    st.markdown(
        """
        <div class="gm-note">
        <strong>Interpretation note.</strong> Service-type views use payment-share weighting. These are proxy estimates, not direct service-type participant counts. Public NDIS data should be read alongside service user voice, workforce insight, local service knowledge and catchment context.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_workspace_header(scope: str, selected_area: str | None, raw_area: str | None) -> None:
    if scope == "service_area" and selected_area:
        title = f"{selected_area}: evidence workspace"
        body = "This service-area view brings the benchmark position, interpretation, diagnostic matrix, ranking context, remoteness distribution and service mix into one tabbed workspace."
        pill = "Service-area profile"
    else:
        title = "National evidence workspace"
        body = "This national view summarises benchmark direction, service-area variation, remoteness patterns, service-type mix and downloadable evidence tables."
        pill = "National overview"

    st.markdown(
        f"""
        <div class="gm-workspace">
            <div class="gm-kicker">Good Measure analytical layer</div>
            <div class="gm-title">{title}</div>
            <div class="gm-body">{body}</div>
            <div class="gm-context-pill">{pill}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if raw_area and scope != "service_area":
        st.caption(f"URL area parameter was detected as `{raw_area}`, but it did not match a service area in the published data. Showing the national overview.")


def _render_direction_cards(current: pd.DataFrame, metric: str) -> None:
    values = pd.to_numeric(current[metric], errors="coerce")
    below = int((values > 0).sum())
    above = int((values < 0).sum())
    near = int((values.abs() <= 0.25).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Areas below benchmark", f"{below:,}")
    c2.metric("Areas above benchmark", f"{above:,}")
    c3.metric("Areas near benchmark", f"{near:,}")
    c4.metric("Median selected gap", _fmt(values.median()))

    st.caption(METRIC_EXPLAINERS.get(metric, ""))


def _render_national_reading(current: pd.DataFrame, metric: str, quarter: str, baseline: str) -> None:
    st.markdown("### National evidence reading")
    _render_direction_cards(current, metric)

    values = pd.to_numeric(current[metric], errors="coerce")
    below = int((values > 0).sum())
    above = int((values < 0).sum())
    total = int(values.notna().sum())

    st.markdown(
        f"""
        <div class="gm-evidence-card">
            <div class="gm-evidence-title">National benchmark spread</div>
            <div class="gm-evidence-body">
            In {quarter}, {below:,} of {total:,} service areas sit below the selected benchmark and {above:,} sit above it.
            This view is a market-sensing and equity-screening layer. It identifies where deeper local interpretation is warranted, not where a single cause has been established.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(f"Baseline for change measures: {baseline}.")


def _render_area_interpretation(current: pd.DataFrame, selected_area: str, quarter: str, baseline: str) -> None:
    rows = current.loc[current["ndis_service_area"] == selected_area]
    if rows.empty:
        st.info("Select a service area to show the evidence reading.")
        return

    row = rows.iloc[0]
    pattern, interpretation = _pattern_label(row.get(PLAN_GAP_COL), row.get(UTIL_GAP_COL))

    st.markdown(f"### {selected_area}: evidence reading")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plan coverage position", _position_from_gap(row.get(PLAN_GAP_COL)), _fmt(row.get(PLAN_GAP_COL)))
    c2.metric("Utilisation position", _position_from_gap(row.get(UTIL_GAP_COL)), _fmt(row.get(UTIL_GAP_COL)))
    c3.metric("Plan coverage trend", _change_label(row.get(PLAN_CHANGE_COL)), _fmt(row.get(PLAN_CHANGE_COL)))
    c4.metric("Utilisation trend", _change_label(row.get(UTIL_CHANGE_COL)), _fmt(row.get(UTIL_CHANGE_COL)))

    st.markdown(
        f"""
        <div class="gm-evidence-card">
            <div class="gm-evidence-title">{pattern}</div>
            <div class="gm-evidence-body">{interpretation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Plan coverage percentile nationally", _fmt_pct(row.get("plan_coverage_percentile_national")))
    p2.metric("Plan coverage percentile by remoteness", _fmt_pct(row.get("plan_coverage_percentile_remoteness")))
    p3.metric("Utilisation percentile nationally", _fmt_pct(row.get("utilisation_percentile_national")))
    p4.metric("Utilisation percentile by remoteness", _fmt_pct(row.get("utilisation_percentile_remoteness")))

    st.caption(f"Quarter: {quarter}. Baseline for change measures: {baseline}.")


def _render_diagnostic_matrix(current: pd.DataFrame, selected_area: str | None) -> None:
    plot = current.dropna(subset=[PLAN_COL, UTIL_COL, PLAN_GAP_COL, UTIL_GAP_COL]).copy()
    if plot.empty:
        st.info("No data available for the diagnostic matrix.")
        return

    plot["selected_area"] = plot["ndis_service_area"].eq(selected_area) if selected_area else False
    national_x = (plot[PLAN_COL] + plot[PLAN_GAP_COL]).median()
    national_y = (plot[UTIL_COL] + plot[UTIL_GAP_COL]).median()

    x_min = float(plot[PLAN_COL].min())
    x_max = float(plot[PLAN_COL].max())
    y_min = float(plot[UTIL_COL].min())
    y_max = float(plot[UTIL_COL].max())

    base = alt.Chart(plot).encode(
        x=alt.X(f"{PLAN_COL}:Q", title="Funded plans per 1,000 population"),
        y=alt.Y(f"{UTIL_COL}:Q", title="Mean plan utilisation"),
        tooltip=[
            alt.Tooltip("ndis_service_area:N", title="Service area"),
            alt.Tooltip("remoteness_category:N", title="Remoteness"),
            alt.Tooltip(f"{PLAN_COL}:Q", title="Plans per 1,000", format=",.2f"),
            alt.Tooltip(f"{UTIL_COL}:Q", title="Mean utilisation", format=",.2f"),
            alt.Tooltip(f"{PLAN_GAP_COL}:Q", title="Plan coverage gap", format=",.2f"),
            alt.Tooltip(f"{UTIL_GAP_COL}:Q", title="Utilisation gap", format=",.2f"),
        ],
    )

    points = base.mark_circle(opacity=0.68).encode(
        color=alt.condition(
            "datum.selected_area",
            alt.value("#F5A400"),
            alt.Color("remoteness_category:N", title="Remoteness"),
        ),
        size=alt.condition("datum.selected_area", alt.value(230), alt.value(70)),
    )

    vline = alt.Chart(pd.DataFrame({"x": [national_x]})).mark_rule(strokeDash=[5, 5], color="#071B33").encode(x="x:Q")
    hline = alt.Chart(pd.DataFrame({"y": [national_y]})).mark_rule(strokeDash=[5, 5], color="#071B33").encode(y="y:Q")

    labels = pd.DataFrame(
        [
            {"x": x_min, "y": y_min, "label": "Access and utilisation question"},
            {"x": x_min, "y": y_max, "label": "Coverage/access question"},
            {"x": x_max, "y": y_min, "label": "Utilisation question"},
            {"x": x_max, "y": y_max, "label": "High scheme engagement"},
        ]
    )

    text = alt.Chart(labels).mark_text(align="left", baseline="middle", dx=6, fontSize=11, color="#071B33").encode(
        x="x:Q",
        y="y:Q",
        text="label:N",
    )

    chart = (points + vline + hline + text).properties(
        height=500,
        title="Plan coverage and utilisation position",
    ).interactive()

    st.altair_chart(_configure_chart(chart), use_container_width=True)
    st.caption("Dashed lines show national benchmarks. Quadrants are interpretive prompts, not causal findings.")


def _render_ranked_bars(current: pd.DataFrame, metric: str, top_n: int) -> None:
    plot = current[["ndis_service_area", "remoteness_category", metric]].dropna(subset=[metric]).copy()
    if plot.empty:
        st.info("No ranked benchmark data available.")
        return

    plot[metric] = pd.to_numeric(plot[metric], errors="coerce")
    below = plot.loc[plot[metric] > 0].nlargest(top_n, metric)
    above = plot.loc[plot[metric] < 0].nsmallest(top_n, metric)

    left, right = st.columns(2)

    with left:
        st.markdown("#### Furthest below benchmark")
        if below.empty:
            st.caption("No areas below benchmark for this metric.")
        else:
            chart = alt.Chart(below).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("ndis_service_area:N", sort="-x", title=None),
                x=alt.X(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
                color=alt.value("#F5A400"),
                tooltip=[
                    alt.Tooltip("ndis_service_area:N", title="Service area"),
                    alt.Tooltip("remoteness_category:N", title="Remoteness"),
                    alt.Tooltip(f"{metric}:Q", title="Gap", format=",.2f"),
                ],
            ).properties(height=max(330, 24 * len(below)))
            st.altair_chart(_configure_chart(chart), use_container_width=True)

    with right:
        st.markdown("#### Furthest above benchmark")
        if above.empty:
            st.caption("No areas above benchmark for this metric.")
        else:
            chart = alt.Chart(above).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("ndis_service_area:N", sort="x", title=None),
                x=alt.X(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
                color=alt.value("#1C5D99"),
                tooltip=[
                    alt.Tooltip("ndis_service_area:N", title="Service area"),
                    alt.Tooltip("remoteness_category:N", title="Remoteness"),
                    alt.Tooltip(f"{metric}:Q", title="Gap", format=",.2f"),
                ],
            ).properties(height=max(330, 24 * len(above)))
            st.altair_chart(_configure_chart(chart), use_container_width=True)


def _render_remoteness_view(current: pd.DataFrame, metric: str) -> None:
    plot = current.dropna(subset=[metric, "remoteness_category"]).copy()
    if plot.empty:
        st.info("No remoteness data available.")
        return

    plot["remoteness_category"] = pd.Categorical(
        plot["remoteness_category"],
        categories=REMOTENESS_ORDER,
        ordered=True,
    )

    strip = alt.Chart(plot).mark_circle(size=85, opacity=0.68).encode(
        x=alt.X("remoteness_category:N", sort=REMOTENESS_ORDER, title="Remoteness"),
        y=alt.Y(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
        color=alt.Color("remoteness_category:N", title="Remoteness"),
        tooltip=[
            alt.Tooltip("ndis_service_area:N", title="Service area"),
            alt.Tooltip("remoteness_category:N", title="Remoteness"),
            alt.Tooltip(f"{metric}:Q", title="Value", format=",.2f"),
        ],
    ).properties(height=380, title="Service-area spread by remoteness")

    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[5, 5], color="#071B33").encode(y="y:Q")

    means = (
        plot.groupby("remoteness_category", dropna=False)[metric]
        .mean()
        .reset_index()
        .dropna(subset=[metric])
    )

    bar = alt.Chart(means).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("remoteness_category:N", sort=REMOTENESS_ORDER, title=None),
        x=alt.X(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
        color=alt.value("#F5A400"),
        tooltip=[
            alt.Tooltip("remoteness_category:N", title="Remoteness"),
            alt.Tooltip(f"{metric}:Q", title="Mean", format=",.2f"),
        ],
    ).properties(height=300, title="Mean benchmark position by remoteness")

    st.altair_chart(_configure_chart(strip + zero), use_container_width=True)
    st.altair_chart(_configure_chart(bar), use_container_width=True)


def _render_service_mix(service_data: pd.DataFrame | None, current: pd.DataFrame, quarter: str, selected_area: str | None) -> None:
    if service_data is None:
        st.info("Service-type payment mix data was not detected.")
        return

    mix = service_data.loc[service_data["quarter"] == quarter].copy()
    if mix.empty:
        st.info("No service-type payment mix data available for the selected quarter.")
        return

    pop = current[["ndis_service_area", "population_2025_erp"]].drop_duplicates()
    mix = mix.merge(pop, on="ndis_service_area", how="left")
    mix["payment_amount_per_1000_population"] = mix["service_type_payment_amount"] / mix["population_2025_erp"] * 1000

    if mix["payment_amount_per_1000_population"].notna().any():
        totals = mix.groupby("ndis_service_area")["payment_amount_per_1000_population"].sum().nlargest(15).reset_index()
        top_areas = set(totals["ndis_service_area"])
        plot_amount = mix.loc[mix["ndis_service_area"].isin(top_areas)].copy()

        st.markdown("#### Payment amount per 1,000 population")
        chart = alt.Chart(plot_amount).mark_bar().encode(
            y=alt.Y("ndis_service_area:N", sort="-x", title=None),
            x=alt.X("payment_amount_per_1000_population:Q", title="Payment amount per 1,000 population"),
            color=alt.Color("service_type:N", title="Service type"),
            tooltip=[
                alt.Tooltip("ndis_service_area:N", title="Service area"),
                alt.Tooltip("service_type:N", title="Service type"),
                alt.Tooltip("payment_amount_per_1000_population:Q", title="Amount per 1,000", format="$,.0f"),
                alt.Tooltip("service_type_payment_share_of_area_total:Q", title="Share", format=".1%"),
            ],
        ).properties(height=540, title="Largest service-type payment intensity")
        st.altair_chart(_configure_chart(chart), use_container_width=True)

    if selected_area:
        area_mix = mix.loc[mix["ndis_service_area"] == selected_area].copy()
        if not area_mix.empty:
            st.markdown(f"#### Service-type share for {selected_area}")
            chart = alt.Chart(area_mix).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("service_type:N", sort="-x", title=None),
                x=alt.X("service_type_payment_share_of_area_total:Q", title="Share of area payments", axis=alt.Axis(format="%")),
                color=alt.value("#1C5D99"),
                tooltip=[
                    alt.Tooltip("service_type:N", title="Service type"),
                    alt.Tooltip("service_type_payment_share_of_area_total:Q", title="Share", format=".1%"),
                    alt.Tooltip("service_type_payment_amount:Q", title="Payment amount", format="$,.0f"),
                ],
            ).properties(height=400, title=f"Service mix for {selected_area}")
            st.altair_chart(_configure_chart(chart), use_container_width=True)

    concentration = (
        mix.sort_values(["ndis_service_area", "service_type_payment_share_of_area_total"], ascending=[True, False])
        .groupby("ndis_service_area", dropna=False)
        .agg(
            top_service_type=("service_type", "first"),
            top_service_share=("service_type_payment_share_of_area_total", "max"),
            top_three_service_share=("service_type_payment_share_of_area_total", lambda s: s.nlargest(3).sum()),
        )
        .reset_index()
        .sort_values("top_three_service_share", ascending=False)
        .head(20)
    )

    st.markdown("#### Service-type concentration")
    st.dataframe(
        concentration,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ndis_service_area": "Service area",
            "top_service_type": "Top service type",
            "top_service_share": st.column_config.NumberColumn("Top service share", format="%.1f%%"),
            "top_three_service_share": st.column_config.NumberColumn("Top three service share", format="%.1f%%"),
        },
    )


def _render_data_method(current: pd.DataFrame, metric: str, quarter: str, baseline: str) -> None:
    export = current.copy()
    export["selected_metric"] = metric
    export["selected_metric_label"] = METRIC_LABELS.get(metric, metric)
    export["baseline_quarter"] = baseline
    export["selected_metric_value"] = export[metric]

    st.download_button(
        "Download evidence interpretation table",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=f"good_measure_ndis_evidence_interpretation_{quarter}_{metric}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("#### Method note")
    st.markdown(
        """
        NDIS service-area boundaries and service-type views should be treated as public-data approximations.
        Benchmark gaps are calculated against inferred national benchmark values in the published service-area extract.
        Positive benchmark-gap values mean the service area is below the benchmark.

        Service-type views use payment-share weighting. These are proxy estimates, not direct service-type participant counts.
        Results should be read with service user voice, workforce insight, local service knowledge, demographics and commissioning context.
        """
    )

    st.markdown("#### Evidence table")
    columns = [
        "ndis_service_area",
        "remoteness_category",
        PLAN_COL,
        UTIL_COL,
        PLAN_GAP_COL,
        UTIL_GAP_COL,
        PLAN_CHANGE_COL,
        UTIL_CHANGE_COL,
        "plan_coverage_percentile_national",
        "utilisation_percentile_national",
    ]
    columns = [c for c in columns if c in export.columns]
    st.dataframe(export[columns], use_container_width=True, hide_index=True)


def render_good_measure_evidence_workspace(project_root: str | Path) -> None:
    project_root = Path(project_root)
    _render_css()

    try:
        base = _read_base_csv(project_root)
        base = _add_benchmarks(base)
    except Exception as exc:
        st.error(f"Good Measure evidence workspace could not load base data: {exc}")
        return

    service_data = _load_service_type_data(project_root)

    quarters = sorted(base["quarter"].dropna().astype(str).unique())
    if not quarters:
        st.warning("No quarters found in the published data.")
        return

    latest = quarters[-1]
    default_baseline = "2024Q2" if "2024Q2" in quarters else quarters[0]

    area_list = sorted(base["ndis_service_area"].dropna().astype(str).unique())
    scope, page_area, raw_area = _detect_page_context(area_list)

    _render_workspace_header(scope, page_area, raw_area)

    with st.expander("Evidence settings", expanded=False):
        c1, c2, c3, c4 = st.columns([1, 1, 1.4, 1])

        quarter = c1.selectbox(
            "Evidence quarter",
            quarters,
            index=quarters.index(latest),
            key="gm_workspace_quarter",
        )

        baseline = c2.selectbox(
            "Baseline quarter",
            quarters,
            index=quarters.index(default_baseline),
            key="gm_workspace_baseline",
        )

        metric_label = c3.selectbox(
            "Metric for benchmark ranking",
            list(METRIC_OPTIONS.keys()),
            key="gm_workspace_metric",
        )
        metric = METRIC_OPTIONS[metric_label]

        top_n = c4.slider(
            "Ranked chart length",
            8,
            30,
            15,
            key="gm_workspace_top_n",
        )

        area_select_options = ["National overview"] + area_list

        if page_area:
            default_area_label = page_area
        else:
            default_area_label = "National overview"

        default_index = area_select_options.index(default_area_label) if default_area_label in area_select_options else 0

        selected_label = st.selectbox(
            "Profile focus",
            area_select_options,
            index=default_index,
            key=f"gm_workspace_profile_focus_{_area_key(page_area or 'national')}",
        )

    selected_area = None if selected_label == "National overview" else selected_label

    data = _add_change(base.copy(), baseline)
    current = data.loc[data["quarter"] == quarter].copy()
    current = _add_percentiles(current)

    if current.empty:
        st.warning("No data available for the selected quarter.")
        return

    _render_warning()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Evidence reading",
            "Diagnostic matrix",
            "Benchmark ranks",
            "Remoteness",
            "Service mix",
            "Data and method",
        ]
    )

    with tab1:
        if selected_area:
            _render_area_interpretation(current, selected_area, quarter, baseline)
        else:
            _render_national_reading(current, metric, quarter, baseline)

    with tab2:
        _render_diagnostic_matrix(current, selected_area)

    with tab3:
        _render_ranked_bars(current, metric, top_n)

    with tab4:
        _render_remoteness_view(current, metric)

    with tab5:
        _render_service_mix(service_data, current, quarter, selected_area)

    with tab6:
        _render_data_method(current, metric, quarter, baseline)


# === GOOD MEASURE NAVIGATION SHELL V5 START ===

def _gm_v5_render_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --gm-navy: #071B33;
            --gm-blue: #1C5D99;
            --gm-amber: #F5A400;
            --gm-cream: #FFF7E8;
            --gm-ink: #1C2E3F;
            --gm-muted: #5F6B76;
            --gm-border: rgba(7, 27, 51, 0.14);
            --gm-soft-blue: #E8F1FA;
            --gm-panel: #FFFFFF;
        }

        .block-container {
            padding-top: 1.5rem;
            max-width: 1500px;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #071B33 0%, #102F4C 100%);
        }

        section[data-testid="stSidebar"] * {
            color: #F8FAFC;
        }

        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
            color: #F8FAFC;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] span {
            color: #071B33;
        }

        section[data-testid="stSidebar"] input {
            color: #071B33;
        }

        .gm-sidebar-brand {
            border: 1px solid rgba(255,255,255,0.16);
            border-radius: 18px;
            padding: 0.95rem 1rem;
            margin: 0.5rem 0 1rem 0;
            background: rgba(255,255,255,0.08);
        }

        .gm-sidebar-brand-title {
            font-weight: 850;
            font-size: 1.05rem;
            color: #FFFFFF;
            margin-bottom: 0.25rem;
        }

        .gm-sidebar-brand-line {
            font-size: 0.82rem;
            line-height: 1.35;
            color: #DCEAF6;
        }

        .gm-shell-hero {
            border: 1px solid var(--gm-border);
            border-radius: 24px;
            padding: 1.2rem 1.35rem;
            margin: 0.5rem 0 1.1rem 0;
            background: linear-gradient(135deg, #ffffff 0%, #fff7e8 100%);
            box-shadow: 0 8px 28px rgba(7, 27, 51, 0.07);
        }

        .gm-shell-kicker {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #7A5A00;
            font-size: 0.76rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .gm-shell-title {
            color: var(--gm-navy);
            font-size: 2rem;
            line-height: 1.12;
            font-weight: 900;
            margin-bottom: 0.35rem;
        }

        .gm-shell-body {
            color: var(--gm-ink);
            max-width: 1050px;
            font-size: 1rem;
            line-height: 1.52;
        }

        .gm-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.75rem;
        }

        .gm-pill {
            display: inline-block;
            padding: 0.28rem 0.6rem;
            border-radius: 999px;
            background: #E8F1FA;
            color: #174A78;
            font-size: 0.78rem;
            font-weight: 850;
        }

        .gm-section-title {
            color: var(--gm-navy);
            font-size: 1.35rem;
            font-weight: 850;
            margin-top: 0.8rem;
            margin-bottom: 0.15rem;
        }

        .gm-section-caption {
            color: var(--gm-muted);
            font-size: 0.93rem;
            line-height: 1.45;
            margin-bottom: 0.8rem;
        }

        .gm-note {
            border-left: 4px solid var(--gm-amber);
            padding: 0.75rem 0.9rem;
            background: rgba(245, 164, 0, 0.08);
            margin: 0.8rem 0;
            color: var(--gm-ink);
            line-height: 1.45;
            border-radius: 0 12px 12px 0;
        }

        .gm-evidence-card {
            border: 1px solid var(--gm-border);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            background: #ffffff;
            margin: 1rem 0;
            box-shadow: 0 4px 16px rgba(7, 27, 51, 0.045);
        }

        .gm-evidence-title {
            color: var(--gm-navy);
            font-size: 1.25rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .gm-evidence-body {
            color: var(--gm-ink);
            font-size: 0.97rem;
            line-height: 1.55;
        }

        div[data-testid="stMetric"] {
            background: #FFF7E8;
            border-left: 4px solid #F5A400;
            border-radius: 14px;
            padding: 0.8rem 0.85rem;
            box-shadow: 0 3px 12px rgba(7, 27, 51, 0.045);
        }

        div[data-testid="stMetric"] label {
            color: #4A5663;
            font-weight: 750;
        }

        div[data-testid="stMetricValue"] {
            color: #071B33;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(7, 27, 51, 0.12);
        }

        hr {
            border: none;
            border-top: 1px solid rgba(7, 27, 51, 0.12);
            margin: 1rem 0;
        }

        .gm-nav-hint {
            font-size: 0.84rem;
            color: #DCEAF6;
            line-height: 1.4;
            margin-top: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _gm_v5_render_sidebar(
    quarters: list[str],
    default_quarter: str,
    default_baseline: str,
    area_list: list[str],
    page_area: str | None,
) -> dict[str, Any]:
    st.sidebar.markdown(
        """
        <div class="gm-sidebar-brand">
            <div class="gm-sidebar-brand-title">Good Measure</div>
            <div class="gm-sidebar-brand-line">For community. Data beyond compliance. Evidence with purpose.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    page_options = [
        "National overview",
        "Service-area profile",
        "Diagnostic matrix",
        "Benchmark ranks",
        "Remoteness and equity",
        "Service mix",
        "Data and method",
    ]

    default_page = "Service-area profile" if page_area else "National overview"
    default_page_index = page_options.index(default_page)

    page = st.sidebar.radio(
        "Navigation",
        page_options,
        index=default_page_index,
        key="gm_v5_navigation",
    )

    st.sidebar.markdown('<div class="gm-nav-hint">Use this pane to move through the evidence product. Filters apply across all sections.</div>', unsafe_allow_html=True)
    st.sidebar.divider()

    quarter = st.sidebar.selectbox(
        "Evidence quarter",
        quarters,
        index=quarters.index(default_quarter),
        key="gm_v5_quarter",
    )

    baseline = st.sidebar.selectbox(
        "Baseline quarter",
        quarters,
        index=quarters.index(default_baseline),
        key="gm_v5_baseline",
    )

    metric_label = st.sidebar.selectbox(
        "Benchmark metric",
        list(METRIC_OPTIONS.keys()),
        index=0,
        key="gm_v5_metric_label",
    )

    top_n = st.sidebar.slider(
        "Ranked list length",
        8,
        30,
        15,
        key="gm_v5_top_n",
    )

    st.sidebar.divider()

    area_options = ["National overview"] + area_list

    if page_area and page_area in area_options:
        default_area = page_area
    else:
        default_area = "National overview"

    default_area_index = area_options.index(default_area)

    focus = st.sidebar.selectbox(
        "Profile focus",
        area_options,
        index=default_area_index,
        key=f"gm_v5_focus_{_area_key(page_area or 'national')}",
    )

    selected_area = None if focus == "National overview" else focus

    st.sidebar.divider()

    st.sidebar.caption(
        "Public-data market sensing. Interpret with service user voice, workforce insight and local context."
    )

    return {
        "page": page,
        "quarter": quarter,
        "baseline": baseline,
        "metric": METRIC_OPTIONS[metric_label],
        "metric_label": metric_label,
        "top_n": top_n,
        "selected_area": selected_area,
    }


def _gm_v5_header(page: str, selected_area: str | None, quarter: str, metric_label: str) -> None:
    if selected_area:
        title = f"{selected_area}: evidence workspace"
        body = (
            "A service-area profile for reading plan coverage, utilisation, benchmark position, "
            "service mix and local market signals in one evidence workspace."
        )
        scope_label = "Service-area profile"
    else:
        title = "National evidence workspace"
        body = (
            "A national view of NDIS service-area variation, benchmark gaps, remoteness patterns, "
            "service-type mix and downloadable evidence tables."
        )
        scope_label = "National overview"

    st.markdown(
        f"""
        <div class="gm-shell-hero">
            <div class="gm-shell-kicker">Good Measure analytical layer</div>
            <div class="gm-shell-title">{title}</div>
            <div class="gm-shell-body">{body}</div>
            <div class="gm-pill-row">
                <span class="gm-pill">{scope_label}</span>
                <span class="gm-pill">{page}</span>
                <span class="gm-pill">{quarter}</span>
                <span class="gm-pill">{metric_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _gm_v5_section(title: str, caption: str) -> None:
    st.markdown(f'<div class="gm-section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="gm-section-caption">{caption}</div>', unsafe_allow_html=True)


def _gm_v5_chart(chart: alt.Chart) -> None:
    try:
        st.altair_chart(_configure_chart(chart), width="stretch")
    except TypeError:
        st.altair_chart(_configure_chart(chart), use_container_width=True)


def _gm_v5_download_button(**kwargs) -> None:
    try:
        st.download_button(**kwargs, width="stretch")
    except TypeError:
        st.download_button(**kwargs, use_container_width=True)


def _gm_v5_dataframe(data: pd.DataFrame, **kwargs) -> None:
    try:
        st.dataframe(data, width="stretch", **kwargs)
    except TypeError:
        st.dataframe(data, use_container_width=True, **kwargs)


def _gm_v5_current_context_summary(current: pd.DataFrame, selected_area: str | None, metric: str) -> None:
    if selected_area:
        rows = current.loc[current["ndis_service_area"] == selected_area]
        if rows.empty:
            st.warning("The selected service area is not available in the current quarter.")
            return

        row = rows.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plans per 1,000", _fmt(row.get(PLAN_COL)))
        c2.metric("Mean utilisation", _fmt(row.get(UTIL_COL)))
        c3.metric("Plan coverage position", _position_from_gap(row.get(PLAN_GAP_COL)))
        c4.metric("Utilisation position", _position_from_gap(row.get(UTIL_GAP_COL)))
        return

    values = pd.to_numeric(current[metric], errors="coerce")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Service areas", f"{int(values.notna().sum()):,}")
    c2.metric("Below benchmark", f"{int((values > 0).sum()):,}")
    c3.metric("Above benchmark", f"{int((values < 0).sum()):,}")
    c4.metric("Median gap", _fmt(values.median()))


def _gm_v5_priority_table(current: pd.DataFrame, metric: str, selected_area: str | None = None) -> None:
    if metric not in current.columns:
        return

    data = current.copy()
    data["selected_metric_value"] = pd.to_numeric(data[metric], errors="coerce")
    data["priority_score"] = data["selected_metric_value"].abs()

    def classify(row: pd.Series) -> str:
        plan_pos = _position_from_gap(row.get(PLAN_GAP_COL))
        util_pos = _position_from_gap(row.get(UTIL_GAP_COL))

        if plan_pos == "Below national benchmark" and util_pos == "Below national benchmark":
            return "Access and utilisation question"
        if plan_pos == "Below national benchmark":
            return "Coverage/access question"
        if util_pos == "Below national benchmark":
            return "Utilisation question"
        if plan_pos == "Above national benchmark" and util_pos == "Above national benchmark":
            return "High scheme engagement"
        return "Mixed or near-benchmark pattern"

    data["evidence_reading"] = data.apply(classify, axis=1)

    if selected_area:
        data["focus_area"] = data["ndis_service_area"].eq(selected_area)
        data = data.sort_values(["focus_area", "priority_score"], ascending=[False, False])
    else:
        data = data.sort_values("priority_score", ascending=False)

    columns = [
        "ndis_service_area",
        "remoteness_category",
        "selected_metric_value",
        "evidence_reading",
        "plan_coverage_percentile_national",
        "utilisation_percentile_national",
    ]
    columns = [c for c in columns if c in data.columns]

    st.markdown("#### Priority evidence table")
    _gm_v5_dataframe(
        data[columns].head(25),
        hide_index=True,
        column_config={
            "ndis_service_area": "Service area",
            "remoteness_category": "Remoteness",
            "selected_metric_value": st.column_config.NumberColumn("Selected metric", format="%.2f"),
            "evidence_reading": "Evidence reading",
            "plan_coverage_percentile_national": st.column_config.NumberColumn("Plan coverage percentile", format="%.1f%%"),
            "utilisation_percentile_national": st.column_config.NumberColumn("Utilisation percentile", format="%.1f%%"),
        },
    )


def _gm_v5_render_area_trends(data: pd.DataFrame, selected_area: str | None) -> None:
    if not selected_area:
        st.info("Choose a service area in the sidebar to show trend lines.")
        return

    area = data.loc[data["ndis_service_area"] == selected_area].copy()
    if area.empty:
        st.info("No trend data available for the selected service area.")
        return

    trend = area[["quarter", PLAN_COL, UTIL_COL, "gm_national_plans_per_1000", "gm_national_mean_utilisation"]].copy()

    plan_long = trend.melt(
        id_vars=["quarter"],
        value_vars=[PLAN_COL, "gm_national_plans_per_1000"],
        var_name="series",
        value_name="value",
    )
    plan_long["series"] = plan_long["series"].replace(
        {
            PLAN_COL: selected_area,
            "gm_national_plans_per_1000": "National benchmark",
        }
    )

    util_long = trend.melt(
        id_vars=["quarter"],
        value_vars=[UTIL_COL, "gm_national_mean_utilisation"],
        var_name="series",
        value_name="value",
    )
    util_long["series"] = util_long["series"].replace(
        {
            UTIL_COL: selected_area,
            "gm_national_mean_utilisation": "National benchmark",
        }
    )

    left, right = st.columns(2)

    with left:
        chart = (
            alt.Chart(plan_long.dropna(subset=["value"]))
            .mark_line(point=True)
            .encode(
                x=alt.X("quarter:N", title="Quarter", sort=list(trend["quarter"])),
                y=alt.Y("value:Q", title="Funded plans per 1,000"),
                color=alt.Color("series:N", title=None),
                tooltip=[
                    alt.Tooltip("quarter:N", title="Quarter"),
                    alt.Tooltip("series:N", title="Series"),
                    alt.Tooltip("value:Q", title="Plans per 1,000", format=",.2f"),
                ],
            )
            .properties(height=330, title="Plan coverage trend")
        )
        _gm_v5_chart(chart)

    with right:
        chart = (
            alt.Chart(util_long.dropna(subset=["value"]))
            .mark_line(point=True)
            .encode(
                x=alt.X("quarter:N", title="Quarter", sort=list(trend["quarter"])),
                y=alt.Y("value:Q", title="Mean plan utilisation"),
                color=alt.Color("series:N", title=None),
                tooltip=[
                    alt.Tooltip("quarter:N", title="Quarter"),
                    alt.Tooltip("series:N", title="Series"),
                    alt.Tooltip("value:Q", title="Mean utilisation", format=",.2f"),
                ],
            )
            .properties(height=330, title="Utilisation trend")
        )
        _gm_v5_chart(chart)


def _gm_v5_render_service_mix(service_data: pd.DataFrame | None, current: pd.DataFrame, quarter: str, selected_area: str | None) -> None:
    if service_data is None:
        st.info("Service-type payment mix data was not detected.")
        return

    mix = service_data.loc[service_data["quarter"] == quarter].copy()
    if mix.empty:
        st.info("No service-type payment mix data is available for the selected quarter.")
        return

    pop = current[["ndis_service_area", "population_2025_erp"]].drop_duplicates()
    mix = mix.merge(pop, on="ndis_service_area", how="left")
    mix["payment_amount_per_1000_population"] = mix["service_type_payment_amount"] / mix["population_2025_erp"] * 1000

    share_max = pd.to_numeric(mix["service_type_payment_share_of_area_total"], errors="coerce").max()
    if pd.notna(share_max) and share_max > 1.5:
        mix["payment_share_fraction"] = mix["service_type_payment_share_of_area_total"] / 100
    else:
        mix["payment_share_fraction"] = mix["service_type_payment_share_of_area_total"]

    left, right = st.columns([1.1, 0.9])

    with left:
        if mix["payment_amount_per_1000_population"].notna().any():
            totals = (
                mix.groupby("ndis_service_area")["payment_amount_per_1000_population"]
                .sum()
                .nlargest(15)
                .reset_index()
            )
            top_areas = set(totals["ndis_service_area"])
            plot_amount = mix.loc[mix["ndis_service_area"].isin(top_areas)].copy()

            chart = (
                alt.Chart(plot_amount)
                .mark_bar()
                .encode(
                    y=alt.Y("ndis_service_area:N", sort="-x", title=None),
                    x=alt.X("payment_amount_per_1000_population:Q", title="Payment amount per 1,000 population"),
                    color=alt.Color("service_type:N", title="Service type"),
                    tooltip=[
                        alt.Tooltip("ndis_service_area:N", title="Service area"),
                        alt.Tooltip("service_type:N", title="Service type"),
                        alt.Tooltip("payment_amount_per_1000_population:Q", title="Amount per 1,000", format="$,.0f"),
                        alt.Tooltip("payment_share_fraction:Q", title="Share", format=".1%"),
                    ],
                )
                .properties(height=520, title="Largest service-type payment intensity")
            )
            _gm_v5_chart(chart)

    with right:
        if selected_area:
            area_mix = mix.loc[mix["ndis_service_area"] == selected_area].copy()
        else:
            largest_area = (
                mix.groupby("ndis_service_area")["payment_amount_per_1000_population"]
                .sum()
                .sort_values(ascending=False)
                .index[0]
            )
            area_mix = mix.loc[mix["ndis_service_area"] == largest_area].copy()
            selected_area = largest_area

        if not area_mix.empty:
            chart = (
                alt.Chart(area_mix)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    y=alt.Y("service_type:N", sort="-x", title=None),
                    x=alt.X("payment_share_fraction:Q", title="Share of area payments", axis=alt.Axis(format="%")),
                    color=alt.value("#1C5D99"),
                    tooltip=[
                        alt.Tooltip("service_type:N", title="Service type"),
                        alt.Tooltip("payment_share_fraction:Q", title="Share", format=".1%"),
                        alt.Tooltip("service_type_payment_amount:Q", title="Payment amount", format="$,.0f"),
                    ],
                )
                .properties(height=520, title=f"Service mix for {selected_area}")
            )
            _gm_v5_chart(chart)

    concentration = (
        mix.sort_values(["ndis_service_area", "payment_share_fraction"], ascending=[True, False])
        .groupby("ndis_service_area", dropna=False)
        .agg(
            top_service_type=("service_type", "first"),
            top_service_share=("payment_share_fraction", "max"),
            top_three_service_share=("payment_share_fraction", lambda s: s.nlargest(3).sum()),
        )
        .reset_index()
        .sort_values("top_three_service_share", ascending=False)
        .head(20)
    )

    st.markdown("#### Service-type concentration")
    _gm_v5_dataframe(
        concentration,
        hide_index=True,
        column_config={
            "ndis_service_area": "Service area",
            "top_service_type": "Top service type",
            "top_service_share": st.column_config.NumberColumn("Top service share", format="%.1f%%"),
            "top_three_service_share": st.column_config.NumberColumn("Top three service share", format="%.1f%%"),
        },
    )


def _gm_v5_render_data_method(current: pd.DataFrame, metric: str, quarter: str, baseline: str) -> None:
    export = current.copy()
    export["selected_metric"] = metric
    export["selected_metric_label"] = METRIC_LABELS.get(metric, metric)
    export["baseline_quarter"] = baseline
    export["selected_metric_value"] = export[metric]

    _gm_v5_download_button(
        label="Download evidence interpretation table",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=f"good_measure_ndis_evidence_interpretation_{quarter}_{metric}.csv",
        mime="text/csv",
    )

    st.markdown("#### Method note")
    st.markdown(
        """
        NDIS service-area boundaries and service-type views should be treated as public-data approximations.

        Benchmark gaps are calculated against inferred national benchmark values in the published service-area extract. Positive benchmark-gap values mean the service area is below the benchmark.

        Service-type views use payment-share weighting. These are proxy estimates, not direct service-type participant counts. Results should be read with service user voice, workforce insight, local service knowledge, demographics and commissioning context.
        """
    )

    st.markdown("#### Evidence table")
    columns = [
        "ndis_service_area",
        "remoteness_category",
        PLAN_COL,
        UTIL_COL,
        PLAN_GAP_COL,
        UTIL_GAP_COL,
        PLAN_CHANGE_COL,
        UTIL_CHANGE_COL,
        "plan_coverage_percentile_national",
        "utilisation_percentile_national",
    ]
    columns = [c for c in columns if c in export.columns]

    _gm_v5_dataframe(export[columns], hide_index=True)


def render_good_measure_evidence_workspace(project_root: str | Path) -> None:
    project_root = Path(project_root)
    _gm_v5_render_css()

    try:
        base = _read_base_csv(project_root)
        base = _add_benchmarks(base)
    except Exception as exc:
        st.error(f"Good Measure evidence workspace could not load base data: {exc}")
        return

    service_data = _load_service_type_data(project_root)

    quarters = sorted(base["quarter"].dropna().astype(str).unique())
    if not quarters:
        st.warning("No quarters found in the published data.")
        return

    latest = quarters[-1]
    default_baseline = "2024Q2" if "2024Q2" in quarters else quarters[0]

    area_list = sorted(base["ndis_service_area"].dropna().astype(str).unique())

    try:
        scope, page_area, raw_area = _detect_page_context(area_list)
    except Exception:
        scope, page_area, raw_area = ("national", None, None)

    controls = _gm_v5_render_sidebar(
        quarters=quarters,
        default_quarter=latest,
        default_baseline=default_baseline,
        area_list=area_list,
        page_area=page_area,
    )

    page = controls["page"]
    quarter = controls["quarter"]
    baseline = controls["baseline"]
    metric = controls["metric"]
    metric_label = controls["metric_label"]
    top_n = controls["top_n"]
    selected_area = controls["selected_area"]

    data = _add_change(base.copy(), baseline)
    current = data.loc[data["quarter"] == quarter].copy()
    current = _add_percentiles(current)

    if current.empty:
        st.warning("No data available for the selected quarter.")
        return

    _gm_v5_header(page, selected_area, quarter, metric_label)

    _render_warning()

    _gm_v5_current_context_summary(current, selected_area, metric)

    st.markdown("<hr>", unsafe_allow_html=True)

    if page == "National overview":
        _gm_v5_section(
            "National overview",
            "National benchmark position, service-area spread and priority evidence table.",
        )
        _render_national_reading(current, metric, quarter, baseline)
        _gm_v5_priority_table(current, metric, selected_area=None)

    elif page == "Service-area profile":
        _gm_v5_section(
            "Service-area profile",
            "Benchmark position, interpretation, percentiles and trend lines for the selected service area.",
        )

        if selected_area is None:
            st.info("Select a service area in the sidebar under Profile focus.")
        else:
            _render_area_interpretation(current, selected_area, quarter, baseline)
            _gm_v5_render_area_trends(data, selected_area)
            _gm_v5_priority_table(current, metric, selected_area=selected_area)

    elif page == "Diagnostic matrix":
        _gm_v5_section(
            "Diagnostic matrix",
            "Plan coverage and utilisation plotted together so that access, utilisation and high-engagement patterns are easier to read.",
        )
        _render_diagnostic_matrix(current, selected_area)

    elif page == "Benchmark ranks":
        _gm_v5_section(
            "Benchmark ranks",
            "Top areas below and above the selected benchmark, using clear direction labels.",
        )
        _render_ranked_bars(current, metric, top_n)
        _gm_v5_priority_table(current, metric, selected_area=selected_area)

    elif page == "Remoteness and equity":
        _gm_v5_section(
            "Remoteness and equity",
            "Service-area variation by remoteness category, with a zero benchmark line for directional reading.",
        )
        _render_remoteness_view(current, metric)

    elif page == "Service mix":
        _gm_v5_section(
            "Service mix",
            "Service-type payment intensity, selected-area service mix and concentration patterns.",
        )
        _gm_v5_render_service_mix(service_data, current, quarter, selected_area)

    elif page == "Data and method":
        _gm_v5_section(
            "Data and method",
            "Downloadable evidence table and interpretation limits.",
        )
        _gm_v5_render_data_method(current, metric, quarter, baseline)

# === GOOD MEASURE NAVIGATION SHELL V5 END ===


# === GOOD MEASURE DASHBOARD TAB WORKSPACE V6 START ===

def _gm_v6_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --gm-navy: #071B33;
            --gm-blue: #1C5D99;
            --gm-amber: #F5A400;
            --gm-cream: #FFF7E8;
            --gm-ink: #1C2E3F;
            --gm-muted: #5F6B76;
            --gm-border: rgba(7, 27, 51, 0.14);
            --gm-soft-blue: #E8F1FA;
        }

        .block-container {
            padding-top: 1.1rem;
            max-width: 1500px;
        }

        .gm-top-panel {
            border: 1px solid var(--gm-border);
            border-radius: 22px;
            padding: 1rem 1.15rem;
            margin: 0.25rem 0 0.85rem 0;
            background: linear-gradient(135deg, #ffffff 0%, #fff7e8 100%);
            box-shadow: 0 8px 26px rgba(7, 27, 51, 0.06);
        }

        .gm-kicker {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #7A5A00;
            font-size: 0.74rem;
            font-weight: 850;
            margin-bottom: 0.2rem;
        }

        .gm-title {
            color: var(--gm-navy);
            font-size: 1.7rem;
            line-height: 1.12;
            font-weight: 900;
            margin-bottom: 0.25rem;
        }

        .gm-body {
            color: var(--gm-ink);
            max-width: 1080px;
            font-size: 0.96rem;
            line-height: 1.45;
        }

        .gm-pill-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.38rem;
            margin-top: 0.65rem;
        }

        .gm-pill {
            display: inline-block;
            padding: 0.26rem 0.58rem;
            border-radius: 999px;
            background: #E8F1FA;
            color: #174A78;
            font-size: 0.76rem;
            font-weight: 850;
        }

        .gm-note {
            border-left: 4px solid var(--gm-amber);
            padding: 0.7rem 0.85rem;
            background: rgba(245, 164, 0, 0.08);
            margin: 0.65rem 0 0.8rem 0;
            color: var(--gm-ink);
            line-height: 1.4;
            border-radius: 0 12px 12px 0;
        }

        .gm-card {
            border: 1px solid var(--gm-border);
            border-radius: 18px;
            padding: 0.95rem 1.05rem;
            background: #ffffff;
            margin: 0.85rem 0;
            box-shadow: 0 4px 16px rgba(7, 27, 51, 0.045);
        }

        .gm-card-title {
            color: var(--gm-navy);
            font-size: 1.18rem;
            font-weight: 850;
            margin-bottom: 0.25rem;
        }

        .gm-card-body {
            color: var(--gm-ink);
            font-size: 0.95rem;
            line-height: 1.5;
        }

        .gm-section-title {
            color: var(--gm-navy);
            font-size: 1.25rem;
            font-weight: 850;
            margin-top: 0.35rem;
            margin-bottom: 0.1rem;
        }

        .gm-section-caption {
            color: var(--gm-muted);
            font-size: 0.9rem;
            line-height: 1.4;
            margin-bottom: 0.65rem;
        }

        div[data-testid="stMetric"] {
            background: #FFF7E8;
            border-left: 4px solid #F5A400;
            border-radius: 14px;
            padding: 0.7rem 0.8rem;
            box-shadow: 0 3px 12px rgba(7, 27, 51, 0.045);
        }

        div[data-testid="stMetric"] label {
            color: #4A5663;
            font-weight: 750;
        }

        div[data-testid="stMetricValue"] {
            color: #071B33;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid rgba(7, 27, 51, 0.12);
        }

        .stTabs [data-baseweb="tab-list"] {
            position: sticky;
            top: 0;
            z-index: 999;
            background: #ffffff;
            border-bottom: 1px solid rgba(7, 27, 51, 0.16);
            gap: 0.25rem;
            padding-top: 0.35rem;
            padding-bottom: 0.25rem;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 999px 999px 0 0;
            padding: 0.52rem 0.82rem;
            font-weight: 850;
            color: #20384F;
        }

        .stTabs [aria-selected="true"] {
            background: #071B33;
            color: #ffffff;
        }

        hr {
            border: none;
            border-top: 1px solid rgba(7, 27, 51, 0.12);
            margin: 0.9rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _gm_v6_configure_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_view(strokeOpacity=0)
        .configure_axis(
            labelFontSize=11,
            titleFontSize=12,
            gridOpacity=0.18,
            domainOpacity=0.22,
            tickOpacity=0.35,
        )
        .configure_title(
            fontSize=17,
            anchor="start",
            fontWeight=700,
            color="#071B33",
        )
        .configure_legend(
            titleFontSize=12,
            labelFontSize=11,
            orient="bottom",
            columns=3,
        )
    )


def _configure_chart(chart: alt.Chart) -> alt.Chart:
    return _gm_v6_configure_chart(chart)


def _gm_v6_chart(chart: alt.Chart) -> None:
    try:
        st.altair_chart(_gm_v6_configure_chart(chart), width="stretch")
    except TypeError:
        st.altair_chart(_gm_v6_configure_chart(chart), use_container_width=True)


def _gm_v6_dataframe(data: pd.DataFrame, **kwargs) -> None:
    try:
        st.dataframe(data, width="stretch", **kwargs)
    except TypeError:
        st.dataframe(data, use_container_width=True, **kwargs)


def _gm_v6_download_button(**kwargs) -> None:
    try:
        st.download_button(**kwargs, width="stretch")
    except TypeError:
        st.download_button(**kwargs, use_container_width=True)


def _gm_v6_section(title: str, caption: str) -> None:
    st.markdown(f'<div class="gm-section-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="gm-section-caption">{caption}</div>', unsafe_allow_html=True)


def _gm_v6_header(selected_area: str | None, quarter: str, metric_label: str) -> None:
    if selected_area:
        title = f"{selected_area}: evidence dashboard"
        body = (
            "A service-area evidence view for plan coverage, utilisation, benchmark position, trends, "
            "remoteness context, service mix and downloadable data."
        )
        scope = "Service-area profile"
    else:
        title = "National evidence dashboard"
        body = (
            "A national view of NDIS service-area variation, benchmark gaps, remoteness patterns, "
            "service-type mix and priority evidence tables."
        )
        scope = "National overview"

    st.markdown(
        f"""
        <div class="gm-top-panel">
            <div class="gm-kicker">Good Measure analytical layer</div>
            <div class="gm-title">{title}</div>
            <div class="gm-body">{body}</div>
            <div class="gm-pill-row">
                <span class="gm-pill">{scope}</span>
                <span class="gm-pill">{quarter}</span>
                <span class="gm-pill">{metric_label}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _gm_v6_warning() -> None:
    st.markdown(
        """
        <div class="gm-note">
        <strong>Interpretation note.</strong> Service-type views use payment-share weighting. These are proxy estimates, not direct service-type participant counts. Public NDIS data should be read alongside service user voice, workforce insight, local service knowledge and catchment context.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _gm_v6_controls(
    quarters: list[str],
    latest: str,
    default_baseline: str,
    area_list: list[str],
    page_area: str | None,
) -> dict:
    c1, c2, c3, c4, c5 = st.columns([1, 1, 1.55, 1.7, 0.85])

    quarter = c1.selectbox(
        "Quarter",
        quarters,
        index=quarters.index(latest),
        key="gm_v6_quarter",
    )

    baseline = c2.selectbox(
        "Baseline",
        quarters,
        index=quarters.index(default_baseline),
        key="gm_v6_baseline",
    )

    metric_label = c3.selectbox(
        "Benchmark metric",
        list(METRIC_OPTIONS.keys()),
        index=0,
        key="gm_v6_metric",
    )

    area_options = ["National overview"] + area_list
    default_area = page_area if page_area in area_options else "National overview"
    default_area_index = area_options.index(default_area)

    focus = c4.selectbox(
        "Profile focus",
        area_options,
        index=default_area_index,
        key=f"gm_v6_focus_{_area_key(page_area or 'national')}",
    )

    top_n = c5.slider(
        "Rank",
        8,
        30,
        15,
        key="gm_v6_top_n",
    )

    return {
        "quarter": quarter,
        "baseline": baseline,
        "metric": METRIC_OPTIONS[metric_label],
        "metric_label": metric_label,
        "selected_area": None if focus == "National overview" else focus,
        "top_n": top_n,
    }


def _gm_v6_summary_metrics(current: pd.DataFrame, selected_area: str | None, metric: str) -> None:
    if selected_area:
        rows = current.loc[current["ndis_service_area"] == selected_area]
        if rows.empty:
            st.warning("The selected service area is not available in the current quarter.")
            return

        row = rows.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plans per 1,000", _fmt(row.get(PLAN_COL)))
        c2.metric("Mean utilisation", _fmt(row.get(UTIL_COL)))
        c3.metric("Plan coverage", _position_from_gap(row.get(PLAN_GAP_COL)), _fmt(row.get(PLAN_GAP_COL)))
        c4.metric("Utilisation", _position_from_gap(row.get(UTIL_GAP_COL)), _fmt(row.get(UTIL_GAP_COL)))
        return

    values = pd.to_numeric(current[metric], errors="coerce")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Service areas", f"{int(values.notna().sum()):,}")
    c2.metric("Below benchmark", f"{int((values > 0).sum()):,}")
    c3.metric("Above benchmark", f"{int((values < 0).sum()):,}")
    c4.metric("Median gap", _fmt(values.median()))


def _gm_v6_national_reading(current: pd.DataFrame, metric: str, quarter: str, baseline: str) -> None:
    values = pd.to_numeric(current[metric], errors="coerce")
    below = int((values > 0).sum())
    above = int((values < 0).sum())
    total = int(values.notna().sum())

    st.markdown(
        f"""
        <div class="gm-card">
            <div class="gm-card-title">National benchmark spread</div>
            <div class="gm-card-body">
            In {quarter}, {below:,} of {total:,} service areas sit below the selected benchmark and {above:,} sit above it.
            This is a market-sensing and equity-screening layer. It identifies where deeper local interpretation is warranted.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(f"Baseline for change measures: {baseline}.")


def _gm_v6_area_reading(current: pd.DataFrame, selected_area: str, quarter: str, baseline: str) -> None:
    rows = current.loc[current["ndis_service_area"] == selected_area]
    if rows.empty:
        st.info("Select a service area to show the evidence reading.")
        return

    row = rows.iloc[0]
    pattern, interpretation = _pattern_label(row.get(PLAN_GAP_COL), row.get(UTIL_GAP_COL))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plan coverage position", _position_from_gap(row.get(PLAN_GAP_COL)), _fmt(row.get(PLAN_GAP_COL)))
    c2.metric("Utilisation position", _position_from_gap(row.get(UTIL_GAP_COL)), _fmt(row.get(UTIL_GAP_COL)))
    c3.metric("Plan coverage trend", _change_label(row.get(PLAN_CHANGE_COL)), _fmt(row.get(PLAN_CHANGE_COL)))
    c4.metric("Utilisation trend", _change_label(row.get(UTIL_CHANGE_COL)), _fmt(row.get(UTIL_CHANGE_COL)))

    st.markdown(
        f"""
        <div class="gm-card">
            <div class="gm-card-title">{pattern}</div>
            <div class="gm-card-body">{interpretation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Plan coverage percentile nationally", _fmt_pct(row.get("plan_coverage_percentile_national")))
    p2.metric("Plan coverage percentile by remoteness", _fmt_pct(row.get("plan_coverage_percentile_remoteness")))
    p3.metric("Utilisation percentile nationally", _fmt_pct(row.get("utilisation_percentile_national")))
    p4.metric("Utilisation percentile by remoteness", _fmt_pct(row.get("utilisation_percentile_remoteness")))

    st.caption(f"Quarter: {quarter}. Baseline for change measures: {baseline}.")


def _gm_v6_priority_table(current: pd.DataFrame, metric: str, selected_area: str | None = None) -> None:
    if metric not in current.columns:
        return

    data = current.copy()
    data["selected_metric_value"] = pd.to_numeric(data[metric], errors="coerce")
    data["priority_score"] = data["selected_metric_value"].abs()

    def classify(row: pd.Series) -> str:
        plan_pos = _position_from_gap(row.get(PLAN_GAP_COL))
        util_pos = _position_from_gap(row.get(UTIL_GAP_COL))

        if plan_pos == "Below national benchmark" and util_pos == "Below national benchmark":
            return "Access and utilisation question"
        if plan_pos == "Below national benchmark":
            return "Coverage/access question"
        if util_pos == "Below national benchmark":
            return "Utilisation question"
        if plan_pos == "Above national benchmark" and util_pos == "Above national benchmark":
            return "High scheme engagement"
        return "Mixed or near-benchmark pattern"

    data["evidence_reading"] = data.apply(classify, axis=1)

    if selected_area:
        data["focus_area"] = data["ndis_service_area"].eq(selected_area)
        data = data.sort_values(["focus_area", "priority_score"], ascending=[False, False])
    else:
        data = data.sort_values("priority_score", ascending=False)

    columns = [
        "ndis_service_area",
        "remoteness_category",
        "selected_metric_value",
        "evidence_reading",
        "plan_coverage_percentile_national",
        "utilisation_percentile_national",
    ]
    columns = [c for c in columns if c in data.columns]

    _gm_v6_dataframe(
        data[columns].head(25),
        hide_index=True,
        column_config={
            "ndis_service_area": "Service area",
            "remoteness_category": "Remoteness",
            "selected_metric_value": st.column_config.NumberColumn("Selected metric", format="%.2f"),
            "evidence_reading": "Evidence reading",
            "plan_coverage_percentile_national": st.column_config.NumberColumn("Plan coverage percentile", format="%.1f%%"),
            "utilisation_percentile_national": st.column_config.NumberColumn("Utilisation percentile", format="%.1f%%"),
        },
    )


def _gm_v6_diagnostic_matrix(current: pd.DataFrame, selected_area: str | None) -> None:
    plot = current.dropna(subset=[PLAN_COL, UTIL_COL, PLAN_GAP_COL, UTIL_GAP_COL]).copy()
    if plot.empty:
        st.info("No data available for the diagnostic matrix.")
        return

    plot["selected_area"] = plot["ndis_service_area"].eq(selected_area) if selected_area else False
    national_x = (plot[PLAN_COL] + plot[PLAN_GAP_COL]).median()
    national_y = (plot[UTIL_COL] + plot[UTIL_GAP_COL]).median()

    x_min = float(plot[PLAN_COL].min())
    x_max = float(plot[PLAN_COL].max())
    y_min = float(plot[UTIL_COL].min())
    y_max = float(plot[UTIL_COL].max())

    base = alt.Chart(plot).encode(
        x=alt.X(f"{PLAN_COL}:Q", title="Funded plans per 1,000 population"),
        y=alt.Y(f"{UTIL_COL}:Q", title="Mean plan utilisation"),
        tooltip=[
            alt.Tooltip("ndis_service_area:N", title="Service area"),
            alt.Tooltip("remoteness_category:N", title="Remoteness"),
            alt.Tooltip(f"{PLAN_COL}:Q", title="Plans per 1,000", format=",.2f"),
            alt.Tooltip(f"{UTIL_COL}:Q", title="Mean utilisation", format=",.2f"),
            alt.Tooltip(f"{PLAN_GAP_COL}:Q", title="Plan coverage gap", format=",.2f"),
            alt.Tooltip(f"{UTIL_GAP_COL}:Q", title="Utilisation gap", format=",.2f"),
        ],
    )

    points = base.mark_circle(opacity=0.7).encode(
        color=alt.condition(
            "datum.selected_area",
            alt.value("#F5A400"),
            alt.Color("remoteness_category:N", title="Remoteness"),
        ),
        size=alt.condition("datum.selected_area", alt.value(235), alt.value(68)),
    )

    vline = alt.Chart(pd.DataFrame({"x": [national_x]})).mark_rule(strokeDash=[5, 5], color="#071B33").encode(x="x:Q")
    hline = alt.Chart(pd.DataFrame({"y": [national_y]})).mark_rule(strokeDash=[5, 5], color="#071B33").encode(y="y:Q")

    labels = pd.DataFrame(
        [
            {"x": x_min, "y": y_min, "label": "Access and utilisation question"},
            {"x": x_min, "y": y_max, "label": "Coverage/access question"},
            {"x": x_max, "y": y_min, "label": "Utilisation question"},
            {"x": x_max, "y": y_max, "label": "High scheme engagement"},
        ]
    )

    text = alt.Chart(labels).mark_text(
        align="left",
        baseline="middle",
        dx=6,
        fontSize=11,
        color="#071B33",
    ).encode(
        x="x:Q",
        y="y:Q",
        text="label:N",
    )

    chart = (points + vline + hline + text).properties(
        height=520,
        title="Plan coverage and utilisation position",
    ).interactive()

    _gm_v6_chart(chart)
    st.caption("Dashed lines show national benchmarks. Quadrants are interpretive prompts, not causal findings.")


def _gm_v6_ranks(current: pd.DataFrame, metric: str, top_n: int) -> None:
    plot = current[["ndis_service_area", "remoteness_category", metric]].dropna(subset=[metric]).copy()
    if plot.empty:
        st.info("No ranked benchmark data available.")
        return

    plot[metric] = pd.to_numeric(plot[metric], errors="coerce")
    below = plot.loc[plot[metric] > 0].nlargest(top_n, metric)
    above = plot.loc[plot[metric] < 0].nsmallest(top_n, metric)

    left, right = st.columns(2)

    with left:
        st.markdown("#### Furthest below benchmark")
        if below.empty:
            st.caption("No areas below benchmark for this metric.")
        else:
            chart = alt.Chart(below).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("ndis_service_area:N", sort="-x", title=None),
                x=alt.X(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
                color=alt.value("#F5A400"),
                tooltip=[
                    alt.Tooltip("ndis_service_area:N", title="Service area"),
                    alt.Tooltip("remoteness_category:N", title="Remoteness"),
                    alt.Tooltip(f"{metric}:Q", title="Gap", format=",.2f"),
                ],
            ).properties(height=max(330, 24 * len(below)))
            _gm_v6_chart(chart)

    with right:
        st.markdown("#### Furthest above benchmark")
        if above.empty:
            st.caption("No areas above benchmark for this metric.")
        else:
            chart = alt.Chart(above).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("ndis_service_area:N", sort="x", title=None),
                x=alt.X(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
                color=alt.value("#1C5D99"),
                tooltip=[
                    alt.Tooltip("ndis_service_area:N", title="Service area"),
                    alt.Tooltip("remoteness_category:N", title="Remoteness"),
                    alt.Tooltip(f"{metric}:Q", title="Gap", format=",.2f"),
                ],
            ).properties(height=max(330, 24 * len(above)))
            _gm_v6_chart(chart)


def _gm_v6_area_trends(data: pd.DataFrame, selected_area: str | None) -> None:
    if not selected_area:
        st.info("Choose a service area in Profile focus to show area trend lines.")
        return

    area = data.loc[data["ndis_service_area"] == selected_area].copy()
    if area.empty:
        st.info("No trend data available for the selected service area.")
        return

    trend = area[["quarter", PLAN_COL, UTIL_COL, "gm_national_plans_per_1000", "gm_national_mean_utilisation"]].copy()

    plan_long = trend.melt(
        id_vars=["quarter"],
        value_vars=[PLAN_COL, "gm_national_plans_per_1000"],
        var_name="series",
        value_name="value",
    )
    plan_long["series"] = plan_long["series"].replace(
        {
            PLAN_COL: selected_area,
            "gm_national_plans_per_1000": "National benchmark",
        }
    )

    util_long = trend.melt(
        id_vars=["quarter"],
        value_vars=[UTIL_COL, "gm_national_mean_utilisation"],
        var_name="series",
        value_name="value",
    )
    util_long["series"] = util_long["series"].replace(
        {
            UTIL_COL: selected_area,
            "gm_national_mean_utilisation": "National benchmark",
        }
    )

    left, right = st.columns(2)

    with left:
        chart = alt.Chart(plan_long.dropna(subset=["value"])).mark_line(point=True).encode(
            x=alt.X("quarter:N", title="Quarter", sort=list(trend["quarter"])),
            y=alt.Y("value:Q", title="Funded plans per 1,000"),
            color=alt.Color("series:N", title=None),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("value:Q", title="Plans per 1,000", format=",.2f"),
            ],
        ).properties(height=350, title="Plan coverage trend")
        _gm_v6_chart(chart)

    with right:
        chart = alt.Chart(util_long.dropna(subset=["value"])).mark_line(point=True).encode(
            x=alt.X("quarter:N", title="Quarter", sort=list(trend["quarter"])),
            y=alt.Y("value:Q", title="Mean plan utilisation"),
            color=alt.Color("series:N", title=None),
            tooltip=[
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("value:Q", title="Mean utilisation", format=",.2f"),
            ],
        ).properties(height=350, title="Utilisation trend")
        _gm_v6_chart(chart)


def _gm_v6_remoteness(current: pd.DataFrame, metric: str) -> None:
    plot = current.dropna(subset=[metric, "remoteness_category"]).copy()
    if plot.empty:
        st.info("No remoteness data available.")
        return

    plot["remoteness_category"] = pd.Categorical(
        plot["remoteness_category"],
        categories=REMOTENESS_ORDER,
        ordered=True,
    )

    strip = alt.Chart(plot).mark_circle(size=82, opacity=0.68).encode(
        x=alt.X("remoteness_category:N", sort=REMOTENESS_ORDER, title="Remoteness"),
        y=alt.Y(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
        color=alt.Color("remoteness_category:N", title="Remoteness"),
        tooltip=[
            alt.Tooltip("ndis_service_area:N", title="Service area"),
            alt.Tooltip("remoteness_category:N", title="Remoteness"),
            alt.Tooltip(f"{metric}:Q", title="Value", format=",.2f"),
        ],
    ).properties(height=390, title="Service-area spread by remoteness")

    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(strokeDash=[5, 5], color="#071B33").encode(y="y:Q")

    means = (
        plot.groupby("remoteness_category", dropna=False)[metric]
        .mean()
        .reset_index()
        .dropna(subset=[metric])
    )

    bar = alt.Chart(means).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("remoteness_category:N", sort=REMOTENESS_ORDER, title=None),
        x=alt.X(f"{metric}:Q", title=METRIC_LABELS.get(metric, metric)),
        color=alt.value("#F5A400"),
        tooltip=[
            alt.Tooltip("remoteness_category:N", title="Remoteness"),
            alt.Tooltip(f"{metric}:Q", title="Mean", format=",.2f"),
        ],
    ).properties(height=310, title="Mean benchmark position by remoteness")

    left, right = st.columns([1.15, 0.85])
    with left:
        _gm_v6_chart(strip + zero)
    with right:
        _gm_v6_chart(bar)


def _gm_v6_service_mix(service_data: pd.DataFrame | None, current: pd.DataFrame, quarter: str, selected_area: str | None) -> None:
    if service_data is None:
        st.info("Service-type payment mix data was not detected.")
        return

    mix = service_data.loc[service_data["quarter"] == quarter].copy()
    if mix.empty:
        st.info("No service-type payment mix data is available for the selected quarter.")
        return

    pop = current[["ndis_service_area", "population_2025_erp"]].drop_duplicates()
    mix = mix.merge(pop, on="ndis_service_area", how="left")
    mix["payment_amount_per_1000_population"] = mix["service_type_payment_amount"] / mix["population_2025_erp"] * 1000

    share_max = pd.to_numeric(mix["service_type_payment_share_of_area_total"], errors="coerce").max()
    if pd.notna(share_max) and share_max > 1.5:
        mix["payment_share_fraction"] = mix["service_type_payment_share_of_area_total"] / 100
    else:
        mix["payment_share_fraction"] = mix["service_type_payment_share_of_area_total"]

    left, right = st.columns([1.12, 0.88])

    with left:
        if mix["payment_amount_per_1000_population"].notna().any():
            totals = (
                mix.groupby("ndis_service_area")["payment_amount_per_1000_population"]
                .sum()
                .nlargest(15)
                .reset_index()
            )
            top_areas = set(totals["ndis_service_area"])
            plot_amount = mix.loc[mix["ndis_service_area"].isin(top_areas)].copy()

            chart = alt.Chart(plot_amount).mark_bar().encode(
                y=alt.Y("ndis_service_area:N", sort="-x", title=None),
                x=alt.X("payment_amount_per_1000_population:Q", title="Payment amount per 1,000 population"),
                color=alt.Color("service_type:N", title="Service type"),
                tooltip=[
                    alt.Tooltip("ndis_service_area:N", title="Service area"),
                    alt.Tooltip("service_type:N", title="Service type"),
                    alt.Tooltip("payment_amount_per_1000_population:Q", title="Amount per 1,000", format="$,.0f"),
                    alt.Tooltip("payment_share_fraction:Q", title="Share", format=".1%"),
                ],
            ).properties(height=520, title="Largest service-type payment intensity")
            _gm_v6_chart(chart)

    with right:
        if selected_area:
            area_mix = mix.loc[mix["ndis_service_area"] == selected_area].copy()
            area_title = selected_area
        else:
            area_title = (
                mix.groupby("ndis_service_area")["payment_amount_per_1000_population"]
                .sum()
                .sort_values(ascending=False)
                .index[0]
            )
            area_mix = mix.loc[mix["ndis_service_area"] == area_title].copy()

        if not area_mix.empty:
            chart = alt.Chart(area_mix).mark_bar(cornerRadiusEnd=4).encode(
                y=alt.Y("service_type:N", sort="-x", title=None),
                x=alt.X("payment_share_fraction:Q", title="Share of area payments", axis=alt.Axis(format="%")),
                color=alt.value("#1C5D99"),
                tooltip=[
                    alt.Tooltip("service_type:N", title="Service type"),
                    alt.Tooltip("payment_share_fraction:Q", title="Share", format=".1%"),
                    alt.Tooltip("service_type_payment_amount:Q", title="Payment amount", format="$,.0f"),
                ],
            ).properties(height=520, title=f"Service mix for {area_title}")
            _gm_v6_chart(chart)

    concentration = (
        mix.sort_values(["ndis_service_area", "payment_share_fraction"], ascending=[True, False])
        .groupby("ndis_service_area", dropna=False)
        .agg(
            top_service_type=("service_type", "first"),
            top_service_share=("payment_share_fraction", "max"),
            top_three_service_share=("payment_share_fraction", lambda s: s.nlargest(3).sum()),
        )
        .reset_index()
        .sort_values("top_three_service_share", ascending=False)
        .head(20)
    )

    st.markdown("#### Service-type concentration")
    _gm_v6_dataframe(
        concentration,
        hide_index=True,
        column_config={
            "ndis_service_area": "Service area",
            "top_service_type": "Top service type",
            "top_service_share": st.column_config.NumberColumn("Top service share", format="%.1f%%"),
            "top_three_service_share": st.column_config.NumberColumn("Top three service share", format="%.1f%%"),
        },
    )


def _gm_v6_data_method(current: pd.DataFrame, metric: str, quarter: str, baseline: str) -> None:
    export = current.copy()
    export["selected_metric"] = metric
    export["selected_metric_label"] = METRIC_LABELS.get(metric, metric)
    export["baseline_quarter"] = baseline
    export["selected_metric_value"] = export[metric]

    _gm_v6_download_button(
        label="Download evidence interpretation table",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name=f"good_measure_ndis_evidence_interpretation_{quarter}_{metric}.csv",
        mime="text/csv",
    )

    st.markdown("#### Method note")
    st.markdown(
        """
        NDIS service-area boundaries and service-type views should be treated as public-data approximations.

        Benchmark gaps are calculated against inferred national benchmark values in the published service-area extract. Positive benchmark-gap values mean the service area is below the benchmark.

        Service-type views use payment-share weighting. These are proxy estimates, not direct service-type participant counts. Results should be read with service user voice, workforce insight, local service knowledge, demographics and commissioning context.
        """
    )

    st.markdown("#### Evidence table")

    columns = [
        "ndis_service_area",
        "remoteness_category",
        PLAN_COL,
        UTIL_COL,
        PLAN_GAP_COL,
        UTIL_GAP_COL,
        PLAN_CHANGE_COL,
        UTIL_CHANGE_COL,
        "plan_coverage_percentile_national",
        "utilisation_percentile_national",
    ]
    columns = [c for c in columns if c in export.columns]

    _gm_v6_dataframe(export[columns], hide_index=True)


def render_good_measure_evidence_workspace(project_root: str | Path) -> None:
    project_root = Path(project_root)
    _gm_v6_css()

    try:
        base = _read_base_csv(project_root)
        base = _add_benchmarks(base)
    except Exception as exc:
        st.error(f"Good Measure evidence dashboard could not load base data: {exc}")
        return

    service_data = _load_service_type_data(project_root)

    quarters = sorted(base["quarter"].dropna().astype(str).unique())
    if not quarters:
        st.warning("No quarters found in the published data.")
        return

    latest = quarters[-1]
    default_baseline = "2024Q2" if "2024Q2" in quarters else quarters[0]

    area_list = sorted(base["ndis_service_area"].dropna().astype(str).unique())

    try:
        scope, page_area, raw_area = _detect_page_context(area_list)
    except Exception:
        scope, page_area, raw_area = ("national", None, None)

    controls = _gm_v6_controls(
        quarters=quarters,
        latest=latest,
        default_baseline=default_baseline,
        area_list=area_list,
        page_area=page_area,
    )

    quarter = controls["quarter"]
    baseline = controls["baseline"]
    metric = controls["metric"]
    metric_label = controls["metric_label"]
    selected_area = controls["selected_area"]
    top_n = controls["top_n"]

    data = _add_change(base.copy(), baseline)
    current = data.loc[data["quarter"] == quarter].copy()
    current = _add_percentiles(current)

    if current.empty:
        st.warning("No data available for the selected quarter.")
        return

    _gm_v6_header(selected_area, quarter, metric_label)
    _gm_v6_warning()
    _gm_v6_summary_metrics(current, selected_area, metric)

    evidence_tab, trends_tab, diagnostic_tab, ranks_tab, remoteness_tab, mix_tab, data_tab = st.tabs(
        [
            "Evidence reading",
            "Trends",
            "Diagnostic matrix",
            "Benchmark ranks",
            "Remoteness",
            "Service mix",
            "Data and method",
        ]
    )

    with evidence_tab:
        _gm_v6_section(
            "Evidence reading",
            "Benchmark position, interpretation and priority evidence table.",
        )

        if selected_area:
            _gm_v6_area_reading(current, selected_area, quarter, baseline)
            _gm_v6_priority_table(current, metric, selected_area=selected_area)
        else:
            _gm_v6_national_reading(current, metric, quarter, baseline)
            _gm_v6_priority_table(current, metric, selected_area=None)

    with trends_tab:
        _gm_v6_section(
            "Trends",
            "Quarterly movement for the selected service area against the national benchmark.",
        )
        _gm_v6_area_trends(data, selected_area)

    with diagnostic_tab:
        _gm_v6_section(
            "Diagnostic matrix",
            "Plan coverage and utilisation plotted together to separate access, utilisation and high-engagement patterns.",
        )
        _gm_v6_diagnostic_matrix(current, selected_area)

    with ranks_tab:
        _gm_v6_section(
            "Benchmark ranks",
            "Top areas below and above the selected benchmark, using clear direction labels.",
        )
        _gm_v6_ranks(current, metric, top_n)

    with remoteness_tab:
        _gm_v6_section(
            "Remoteness",
            "Service-area variation by remoteness category, with a zero benchmark line for directional reading.",
        )
        _gm_v6_remoteness(current, metric)

    with mix_tab:
        _gm_v6_section(
            "Service mix",
            "Service-type payment intensity, selected-area service mix and concentration patterns.",
        )
        _gm_v6_service_mix(service_data, current, quarter, selected_area)

    with data_tab:
        _gm_v6_section(
            "Data and method",
            "Downloadable evidence table and interpretation limits.",
        )
        _gm_v6_data_method(current, metric, quarter, baseline)

# === GOOD MEASURE DASHBOARD TAB WORKSPACE V6 END ===

